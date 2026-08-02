create table if not exists public.user_settings (
    user_id text primary key,
    settings_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.twitch_tokens (
    user_id text not null,
    bot boolean not null default false,
    access_token text not null,
    refresh_token text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, bot)
);

create table if not exists public.kick_tokens (
    user_id text not null,
    bot boolean not null default false,
    access_token text not null,
    refresh_token text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, bot)
);

create table if not exists public.kick_event_subscriptions (
    subscription_id text primary key,
    user_id text not null,
    bot boolean not null default false,
    event_name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.user_settings enable row level security;
alter table public.twitch_tokens enable row level security;
alter table public.kick_tokens enable row level security;
alter table public.kick_event_subscriptions enable row level security;

revoke all on table public.user_settings from anon, authenticated;
revoke all on table public.twitch_tokens from anon, authenticated;
revoke all on table public.kick_tokens from anon, authenticated;
revoke all on table public.kick_event_subscriptions from anon, authenticated;

grant all on table public.user_settings to service_role;
grant all on table public.twitch_tokens to service_role;
grant all on table public.kick_tokens to service_role;
grant all on table public.kick_event_subscriptions to service_role;
