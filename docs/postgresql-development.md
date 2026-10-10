# PostgreSQL Development Setup

The application database is PostgreSQL. FastAPI owns database access; the browser and Next.js client code must never connect to PostgreSQL directly. Configure `DATABASE_URL` in the ignored root `.env.local` for local development and in the server environment for deployment. Do not commit credentials.

## Local development

Each developer runs a separate PostgreSQL instance or local PostgreSQL service and creates their own application role and database. Do not connect daily development to another developer's workstation and do not share local database passwords. A typical local setup uses database `shanhe`, a dedicated `shanhe_app` role, and `127.0.0.1:5432`, but credentials remain local and may differ between machines.

Alembic migrations are the only shared schema source. After pulling schema changes, each developer applies `python -m alembic upgrade head` to their own database. The ignored root `.env.local` contains that machine's `DATABASE_URL`; `.env.example` contains placeholders only.

## Same-server deployment

For the first cloud deployment, run PostgreSQL on the Alibaba Cloud Linux server and bind its listener to `127.0.0.1`. Keep the cloud firewall closed on port 5432. The application connects over loopback. Back up the database separately from the application files.

## Future cloud access

Being on the same office Wi-Fi does not put a teammate on a cloud server's private network. Do not open PostgreSQL to `0.0.0.0/0`. For cloud access, give each developer an individually managed SSH account/key, then establish a local tunnel:

```bash
ssh -N -L 127.0.0.1:15432:127.0.0.1:5432 <developer>@<server-public-ip>
```

Set that developer's local `DATABASE_URL` to `postgresql+psycopg://<db-user>:<password>@127.0.0.1:15432/<database>`. Use a separate least-privilege PostgreSQL account for each developer and never share production credentials. A VPN/private network can replace SSH tunnels later.

## Schema migrations

Install `backend/requirements.txt`, configure `DATABASE_URL`, then apply migrations:

```bash
python -m alembic upgrade head
```

Do not use `Base.metadata.create_all()` as a substitute for reviewed migrations. To inspect SQL without applying it, run `python -m alembic upgrade head --sql` with a configured PostgreSQL URL.

The schema and APIs must evolve together through reviewed migrations. Never use `Base.metadata.create_all()` to repair schema drift or bypass a missing migration.
