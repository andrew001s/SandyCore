-- Migration: Crear tabla de recompensas personalizadas
create table if not exists public.custom_rewards (
    user_id text not null,
    platform text not null, -- 'twitch' o 'kick'
    reward_id text not null, -- UUID de Twitch o ID de Kick
    title text not null,
    enabled boolean not null default false,
    prompt text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, platform, reward_id)
);

alter table public.custom_rewards enable row level security;
revoke all on table public.custom_rewards from anon, authenticated;
grant all on table public.custom_rewards to service_role;
