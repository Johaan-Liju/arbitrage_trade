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

Health check path: `/api/health`. Use a Python version compatible with the lock; this repository was tested with Python 3.11.9. The app needs no feed credentials to serve its synthetic fixture data.

Wait for the backend to become healthy, then open its actual URL with `/api/health` appended. It should report `status: ok` and the synthetic dataset ready. If that endpoint fails, inspect the backend logs before connecting the frontend. Copy the base URL, with no `/api` suffix.

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
- Frontend `/api/contracts?dataset=synthetic`: HTTP 200 and explicit synthetic labeling.
- Real datasets remain unavailable; connecting a backend does not verify real MCX inputs or enable a real feed. There is no synthetic fallback for real requests.

This remains a synthetic demo. SQLite is stored on the backend filesystem; non-persistent hosting does not retain imported observations or simulation ledgers across replacement instances. Fixtures regenerate. There is no authentication or multi-user production hardening.

Official references: [Render FastAPI setup](https://render.com/docs/deploy-fastapi), [port binding](https://render.com/docs/web-services#port-binding), [environment variables and rebuild options](https://render.com/docs/configure-environment-variables).
