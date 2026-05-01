-- Run this in the Supabase SQL editor for the first hosted setup.
-- After your owner signs up once, update their profile role to admin:
-- update public.profiles set role = 'admin' where email = 'you@example.com';

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  role text not null default 'user' check (role in ('admin', 'user')),
  created_at timestamptz not null default now()
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.app_settings (
  id integer primary key default 1 check (id = 1),
  provider text not null,
  model_name text not null,
  system_prompt text not null,
  enabled_tools jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'tool')),
  content text not null,
  attachments jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.files (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  content_type text not null,
  storage_path text not null,
  summary text not null,
  extracted_text text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.tool_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  tool_name text not null,
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  ok boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_projects_user_updated on public.projects(user_id, updated_at desc);
create index if not exists idx_conversations_user_updated on public.conversations(user_id, updated_at desc);
create index if not exists idx_messages_conversation_created on public.messages(conversation_id, created_at);
create index if not exists idx_files_user_created on public.files(user_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.app_settings enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.files enable row level security;
alter table public.tool_runs enable row level security;

create policy "Users can read own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can insert own profile"
  on public.profiles for insert
  with check (auth.uid() = id);

create policy "Users can update own profile email only"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id and role = 'user');

create policy "Users can manage own projects"
  on public.projects for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can manage own conversations"
  on public.conversations for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can manage own messages"
  on public.messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can manage own file metadata"
  on public.files for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can read own tool runs"
  on public.tool_runs for select
  using (auth.uid() = user_id);

create policy "Admins can read settings"
  on public.app_settings for select
  using (exists (select 1 from public.profiles where id = auth.uid() and role = 'admin'));

create policy "Admins can update settings"
  on public.app_settings for update
  using (exists (select 1 from public.profiles where id = auth.uid() and role = 'admin'))
  with check (exists (select 1 from public.profiles where id = auth.uid() and role = 'admin'));

insert into public.app_settings (id, provider, model_name, system_prompt, enabled_tools)
values (
  1,
  'openrouter',
  'qwen/qwen3-32b',
  'You are a helpful, careful AI assistant. Be concise, honest, and practical.',
  '["datetime", "calculator", "summarize_file"]'::jsonb
)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('assistant-files', 'assistant-files', false)
on conflict (id) do nothing;

create policy "Users can upload own assistant files"
  on storage.objects for insert
  with check (
    bucket_id = 'assistant-files'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Users can read own assistant files"
  on storage.objects for select
  using (
    bucket_id = 'assistant-files'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Users can update own assistant files"
  on storage.objects for update
  using (
    bucket_id = 'assistant-files'
    and auth.uid()::text = (storage.foldername(name))[1]
  )
  with check (
    bucket_id = 'assistant-files'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Users can delete own assistant files"
  on storage.objects for delete
  using (
    bucket_id = 'assistant-files'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

