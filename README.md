# AI Assistant Foundation

This repository contains a Claude-like assistant foundation with a Next.js frontend in `web/` and a FastAPI backend in `api/`.

## What Is Included

- Local email/password auth with JWT sessions, or Supabase Auth.
- Admin/user roles with backend admin enforcement.
- SQLite persistence for quick testing, or Supabase Postgres/Storage for hosted use.
- Environment-selected model providers: `mock`, `openai`, `anthropic`, `claude`, `openrouter`, `groq`, `ollama`, or any OpenAI-compatible endpoint.
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
AUTH_PROVIDER=local
DATA_BACKEND=sqlite
MODEL_PROVIDER=mock
MODEL_NAME=mock-local
```

Use `MODEL_PROVIDER=openai` with `OPENAI_API_KEY`, or `MODEL_PROVIDER=anthropic` / `MODEL_PROVIDER=claude` with `ANTHROPIC_API_KEY`, when you are ready to call a real model.

For Qwen/Gemma hosted through OpenRouter:

```env
MODEL_PROVIDER=openrouter
MODEL_NAME=qwen/qwen3-32b
OPENROUTER_API_KEY=your-openrouter-key
```

For local/self-hosted OpenAI-compatible servers such as Ollama or vLLM:

```env
MODEL_PROVIDER=ollama
MODEL_NAME=qwen3:32b
OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1
```

Codespaces does not run an offline 32B model by itself. Use Codespaces for the web app/API, and use a hosted model endpoint for Qwen/Gemma unless you have a GPU machine.

## Supabase Mode

1. Create a Supabase project.
2. Open the Supabase SQL editor and run `supabase/migrations/0001_assistant_foundation.sql`.
3. Set these env vars:

```env
AUTH_PROVIDER=supabase
DATA_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

Put the `NEXT_PUBLIC_*` values in `web/.env.local` as well, or copy `web/.env.local.example` and fill them in.

4. Start the app, create your owner account from the login screen, then run this once in Supabase SQL editor:

```sql
update public.profiles set role = 'admin' where email = 'you@example.com';
```

Never put `SUPABASE_SERVICE_ROLE_KEY` in any `NEXT_PUBLIC_` variable.

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
npm run dev -- -H 0.0.0.0 -p 3000
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
