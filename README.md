# AI Assistant Foundation

This repository contains a Claude-like assistant foundation with a Next.js frontend in `web/` and a FastAPI backend in `api/`.

## What Is Included

- Local email/password auth with JWT sessions.
- Admin/user roles with backend admin enforcement.
- SQLite persistence for users, settings, conversations, messages, uploaded files, and tool runs.
- Environment-selected model providers: `mock`, `openai`, `anthropic`, or `claude`.
- Upload processing for text, PDF, and image files.
- Chat UI with file attachments, loading and error states, and conversation history.
- Admin panel for model name, system prompt, and enabled tools.
- Tool dispatcher with `datetime`, `calculator`, and `summarize_file`.
- Codespaces/devcontainer setup.

## Setup

Copy the environment template and edit the owner credentials first:

```powershell
Copy-Item .env.example .env
```

Set at least:

```env
JWT_SECRET=replace-with-a-long-random-secret
OWNER_EMAIL=you@example.com
OWNER_PASSWORD=replace-with-a-strong-password
MODEL_PROVIDER=mock
MODEL_NAME=mock-local
```

Use `MODEL_PROVIDER=openai` with `OPENAI_API_KEY`, or `MODEL_PROVIDER=anthropic` / `MODEL_PROVIDER=claude` with `ANTHROPIC_API_KEY`, when you are ready to call a real model.

## Run The Backend

```powershell
cd api
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

## Run The Frontend

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. Sign in with `OWNER_EMAIL` and `OWNER_PASSWORD`.

## Tests And Checks

From the repository root:

```powershell
python -m pytest
```

For the frontend:

```powershell
cd web
npm run typecheck
npm run build
```

## Admin Model Settings

The active provider comes from `MODEL_PROVIDER` in the environment. The admin panel persists:

- model name
- system prompt
- enabled tools

This keeps deployment-level provider selection separate from runtime assistant behavior.

## File Processing

Supported uploads:

- text-like files: `.txt`, `.md`, `.csv`, `.json`, `.log`
- PDFs through `pypdf`
- images through `Pillow`

Text and PDF files are extracted into prompt context. Images store metadata and, when they are under `MAX_INLINE_IMAGE_BYTES`, are sent to OpenAI/Claude as vision inputs during the chat turn where they are attached.

## Production Gaps

- Replace local password auth with your production identity provider or add email verification and password reset.
- Move SQLite to Postgres for multi-instance deployments.
- Store uploads in object storage, scan files, and add per-user limits.
- Add streaming model responses.
- Add connector-specific OAuth flows for Google Drive, GitHub, Notion, and web search.
- Add rate limiting, audit logs, and a secrets manager.
- Expand tests to include browser-level flows and provider contract tests.
