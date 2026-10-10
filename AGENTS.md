<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Project engineering rules

- The main agent makes decisions and reviews; sub-agents perform all code changes.
- Implement only the single confirmed contract. Do not add compatibility for legacy fields.
- Do not silently degrade, synthesize default business data, swallow exceptions with catch-all handling, or automatically switch model providers.
- Fail explicitly when configuration or schemas do not match the confirmed contract.
- Keep authentication, input validation, transactions, and optimistic locking as required correctness boundaries.
- Treat the confirmed contract as the only supported contract. Unknown fields, structures, persisted states, and configuration mismatches must fail explicitly.
- Do not add guessed compatibility aliases, broad dictionary fallbacks, range clamping, or generic error remapping that hides the actual domain error.
- Fake providers are test-only. Production paths must never return fake or demonstration business output.
- When model context becomes too large, prefer splitting work into multiple scoped model requests. Every multi-request generation must expose real per-unit status and completed/total progress, including failure, instead of only a spinner or simulated percentage.
