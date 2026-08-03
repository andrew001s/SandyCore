create table if not exists public.youtube_tokens (
    user_id text primary key,
    access_token text not null,
    refresh_token text not null,
    expires_at bigint,
    scope text,
    token_type text,
    provider_account_id text,
    email text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.youtube_tokens enable row level security;

revoke all on table public.youtube_tokens from anon, authenticated;

grant all on table public.youtube_tokens to service_role;
