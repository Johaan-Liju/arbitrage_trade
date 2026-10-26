# Render: frontend and backend

The local app has two processes. Deploying only Next.js leaves its API unavailable. `127.0.0.1:8000` on a frontend container cannot reach a separately hosted FastAPI service. HTTP 500 alone is not a complete diagnosis; check backend health and deployment logs as well.

These are manual setup instructions. No services have been created or deployed by this change. Local commands still bind only to loopback. Render start-command overrides below bind public services as required by Render.

## 1. Create the backend service

Use the same repository/revision as the frontend. Create a **Web Service**, runtime **Python 3**, with **Root Directory blank** (repository root):

Build command:

```sh
pip install -r backend/requirements.lock.txt
```

Start command:

```sh
python -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
```

Health check path: `/api/health`. Use a Python version compatible with the lock; this repository was tested with Python 3.11.9. The app starts without feed credentials; normal startup serves only real data and does not generate synthetic fixtures.

Wait for the backend to become healthy, then open its actual URL with `/api/health` appended. It should report `status: ok`; on a fresh checkout the real dataset is `empty`. If that endpoint fails, inspect the backend logs before connecting the frontend. Copy the base URL, with no `/api` suffix.

## 2. Connect and rebuild the frontend

First make the local changes to `frontend/next.config.ts` available in the revision Render builds. Merely adding an environment variable to an older revision with the hard-coded localhost rewrite will not work.

On the frontend service, add the server-side environment variable:

```text
BACKEND_URL=https://YOUR-ACTUAL-BACKEND-SERVICE.onrender.com
```

The value above is a placeholder: replace it with the backend's real base URL. Do not append `/api`; the rewrite adds that path. No `NEXT_PUBLIC_` prefix or CORS change is needed: the browser still calls `/api/*` on its frontend origin, and Next proxies the requests.

For a blank frontend Root Directory:

```sh
# Build
npm --prefix frontend ci && npm --prefix frontend run build
# Start
cd frontend && node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port "$PORT"
```

If Root Directory is `frontend`, use `npm ci && npm run build` and omit `cd frontend &&` from the start command.

Choose **Save, rebuild, and deploy** after setting/changing `BACKEND_URL`. Rewrites are generated during the build; restarting an old build is insufficient. With no variable, local development continues to use `http://127.0.0.1:8000`.

## 3. Verify the connection and data boundary

- Backend `/api/health`: HTTP 200.
- Frontend `/api/health`: HTTP 200 through the proxy, with the same dataset status.
- Frontend `/api/contracts?dataset=real`: HTTP 200; an empty contract list is expected until real records are supplied.
- Frontend `/api/contracts?dataset=synthetic`: HTTP 422; synthetic data is disabled in the normal application.
- Connecting a backend does not collect or verify MCX inputs or enable a live feed. Local source archives and databases are git-ignored and are not included in a fresh Render checkout. Unverified source quotes remain separate from approved normalized research. There is no synthetic fallback for real requests.

SQLite, source archives and paper-session history live on the backend filesystem; non-persistent hosting does not retain them across replacement instances. Supply validated real imports or collected source archives separately to populate the workspace. Source browsing alone does not enable verified signals or historical backtests. There is no authentication or multi-user production hardening.

Official references: [Render FastAPI setup](https://render.com/docs/deploy-fastapi), [port binding](https://render.com/docs/web-services#port-binding), [environment variables and rebuild options](https://render.com/docs/configure-environment-variables).
