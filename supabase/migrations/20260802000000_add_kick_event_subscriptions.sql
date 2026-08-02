create table if not exists public.kick_event_subscriptions (
    subscription_id text primary key,
    user_id text not null,
    bot boolean not null default false,
    event_name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.kick_event_subscriptions enable row level security;

revoke all on table public.kick_event_subscriptions from anon, authenticated;

grant all on table public.kick_event_subscriptions to service_role;
