import { existsSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:net";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(import.meta.url);
const root = resolve(dirname(script), "..");
const workers = new Set();

function killTree(pid) {
  if (process.platform === "win32") {
    const result = spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "pipe", windowsHide: true });
    if (result.error || result.status !== 0) throw new Error(`无法停止本次启动的进程树 PID ${pid}。`);
  } else {
    try { process.kill(-pid, "SIGKILL"); } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
  }
}

// The worker remains alive when a service exits, so Windows taskkill still
// has an owned root PID for cleanup of any remaining reload/server children.
function serviceWorker() {
  process.once("message", ({ command, args }) => {
    const child = spawn(command, args, { cwd: root, env: process.env, stdio: "inherit", windowsHide: true });
    child.once("error", (error) => process.send?.({ error: error.message }));
    child.once("exit", (code, signal) => process.send?.({ code, signal }));
  });
  process.on("disconnect", () => killTree(process.pid));
}

function selectPython() {
  if (process.env.SHANHE_PYTHON?.trim()) return process.env.SHANHE_PYTHON.trim();
  const local = join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  if (existsSync(local)) return local;
  if (process.platform === "win32" && process.env.USERPROFILE) {
    const bundled = join(process.env.USERPROFILE, ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe");
    if (existsSync(bundled)) return bundled;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function checkPort(port, host) {
  return new Promise((resolveCheck, rejectCheck) => {
    const server = createServer();
    server.once("error", (error) => rejectCheck(new Error(error.code === "EADDRINUSE"
      ? `端口 ${port} 已被占用，请先停止原来的服务；本命令不会替你终止它。`
      : `无法检查 ${host}:${port}：${error.message}`)));
    server.listen(port, host, () => server.close((error) => error ? rejectCheck(error) : resolveCheck()));
  });
}

async function preflight() {
  if (!existsSync(join(root, ".env.local"))) throw new Error("缺少项目根目录的 .env.local，请按 .env.example 配置真实数据库和服务凭据。");
  const nextBin = join(root, "node_modules/next/dist/bin/next");
  if (!existsSync(nextBin)) throw new Error("缺少前端依赖，请先在项目根目录执行 npm ci。");
  createRequire(import.meta.url)("@next/env").loadEnvConfig(root, true);
  for (const name of ["DATABASE_URL", "FASTAPI_BASE_URL"]) {
    if (!process.env[name]?.trim()) throw new Error(`缺少必需配置 ${name}。`);
  }
  let apiUrl;
  try { apiUrl = new URL(process.env.FASTAPI_BASE_URL); } catch {
    throw new Error("FASTAPI_BASE_URL 必须是有效的本地后端 URL。");
  }
  if (apiUrl.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(apiUrl.hostname)
      || apiUrl.port !== "8000" || apiUrl.pathname !== "/"
      || apiUrl.username || apiUrl.password || apiUrl.search || apiUrl.hash) {
    throw new Error("FASTAPI_BASE_URL 必须指向 http://127.0.0.1:8000（也可用 localhost）。");
  }
  const python = selectPython();
  const checkCode = [
    "import importlib, sys",
    "for name in ['fastapi', 'uvicorn', 'sqlalchemy', 'alembic', 'psycopg', 'httpx', 'dotenv']:",
    "    try: importlib.import_module(name)",
    "    except ImportError: sys.exit('Missing Python dependency: ' + name)",
    "import backend.main",
  ].join("\n");
  const result = spawnSync(python, ["-B", "-c", checkCode], {
    cwd: root, env: process.env, stdio: "pipe", encoding: "utf8", windowsHide: true,
  });
  if (result.error) throw new Error(`无法运行选定的 Python：${python}。请设置 SHANHE_PYTHON 为已安装的 Python 可执行文件路径。`);
  if (result.status !== 0) throw new Error(`Python 预检失败：${result.stderr.trim()}\n请用选定的 Python 安装 backend/requirements.txt 的依赖；本命令不会自动更换 Python。`);
  const checks = await Promise.allSettled([checkPort(3001, "0.0.0.0"), checkPort(8000, "127.0.0.1")]);
  const failures = checks.filter((item) => item.status === "rejected");
  if (failures.length) throw new Error(failures.map((item) => item.reason.message).join("\n"));
  console.log(`[dev:all] 预检通过，Python：${python}`);
  return { python, nextBin };
}

function startCommand(name, command, args) {
  const worker = spawn(process.execPath, [script, "--service-worker"], {
    cwd: root, env: process.env, stdio: ["ignore", "inherit", "inherit", "ipc"], detached: true, windowsHide: true,
  });
  workers.add(worker);
  const completion = new Promise((resolveCommand, rejectCommand) => {
    worker.once("error", (error) => {
      workers.delete(worker);
      rejectCommand(new Error(`${name} 监督进程启动失败：${error.message}`));
    });
    worker.once("message", (result) => {
      if (result.error) rejectCommand(new Error(`${name} 启动失败：${result.error}`));
      else resolveCommand(result);
    });
    worker.once("exit", (code, signal) => {
      workers.delete(worker);
      rejectCommand(new Error(`${name} 监督进程退出（code=${code}, signal=${signal}）。`));
    });
  });
  worker.once("spawn", () => worker.send({ command, args }));
  return { worker, completion };
}

function stopWorker(worker) {
  if (worker.pid && workers.has(worker)) {
    killTree(worker.pid);
    workers.delete(worker);
  }
}

function shutdown(code) {
  for (const worker of workers) {
    try { stopWorker(worker); } catch (error) {
      console.error(`[dev:all] ${error.message}`);
      code = 1;
    }
  }
  process.exit(code);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.some((arg) => !["--help", "--check"].includes(arg))) throw new Error("仅支持 --check 或 --help 参数。");
  if (args.includes("--help")) {
    console.log("用法：npm run dev:all [-- --check]\n--check 只做预检，不迁移数据库或启动服务。\nCtrl+C 停止本次启动的前后端。");
    return;
  }
  const { python, nextBin } = await preflight();
  if (args.includes("--check")) return;
  process.on("SIGINT", () => shutdown(0));
  process.on("SIGTERM", () => shutdown(0));
  console.log("[dev:all] 正在迁移数据库……");
  const migration = startCommand("数据库迁移", python, ["-m", "alembic", "upgrade", "head"]);
  const result = await migration.completion;
  stopWorker(migration.worker);
  if (result.code !== 0) throw new Error(`数据库迁移失败（code=${result.code}, signal=${result.signal}），尚未启动服务。`);

  const backend = startCommand("FastAPI", python, ["-m", "uvicorn", "backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]);
  const frontend = startCommand("Next.js", process.execPath, [nextBin, "dev", "--hostname", "0.0.0.0", "--port", "3001"]);
  console.log("[dev:all] 前端：http://127.0.0.1:3001/event-agent\n[dev:all] 后端：http://127.0.0.1:8000\n[dev:all] 按 Ctrl+C 停止两个服务。");
  const stopped = await Promise.race([
    backend.completion.then((result) => ({ name: "FastAPI", ...result })),
    frontend.completion.then((result) => ({ name: "Next.js", ...result })),
  ]);
  throw new Error(`${stopped.name} 意外退出（code=${stopped.code}, signal=${stopped.signal}），正在停止本次启动的全部服务。`);
}

if (process.argv[2] === "--service-worker") serviceWorker();
else main().catch((error) => {
  console.error(`[dev:all] ${error.message}`);
  shutdown(1);
});
