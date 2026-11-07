create table public.support_checkout_intents (
  user_id text primary key,
  email_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '1 hour'
);
create table public.support_payments (
  transaction_id text primary key,
  message_id text not null unique,
  email_hash text not null,
  amount_cents integer not null check (amount_cents >= 0),
  currency text not null,
  product_code text not null,
  state text not null check (state in ('confirmed','review','refunded','disputed')),
  review_reason text,
  paid_at timestamptz not null,
  received_at timestamptz not null default now(),
  claimed_by text,
  claimed_at timestamptz
);
create index support_payments_owner_idx on public.support_payments (claimed_by, state);
create index support_payments_unclaimed_idx on public.support_payments (email_hash) where claimed_by is null;
create table public.support_overlay_keys (
  user_id text primary key,
  viewer_id uuid not null unique default gen_random_uuid(),
  revision integer not null default 1 check (revision > 0)
);
create table public.support_payment_audit (
  id bigint generated always as identity primary key,
  transaction_id text not null references public.support_payments(transaction_id),
  previous_state text not null,
  new_state text not null,
  actor text not null,
  reason text not null,
  created_at timestamptz not null default now()
);
alter table public.support_checkout_intents enable row level security;
alter table public.support_payments enable row level security;
alter table public.support_overlay_keys enable row level security;
alter table public.support_payment_audit enable row level security;
revoke all on public.support_checkout_intents, public.support_payments, public.support_overlay_keys, public.support_payment_audit from public, anon, authenticated;
grant all on public.support_checkout_intents, public.support_payments, public.support_overlay_keys, public.support_payment_audit to service_role;
grant usage, select on sequence public.support_payment_audit_id_seq to service_role;

create function public.support_start_checkout(p_user_id text, p_email_hash text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user_id, 0));
  insert into public.support_checkout_intents as current (user_id, email_hash)
  values (p_user_id, p_email_hash)
  on conflict (user_id) do update set
    email_hash = excluded.email_hash,
    created_at = case when current.email_hash = excluded.email_hash and current.expires_at > now() then current.created_at else now() end,
    expires_at = case when current.email_hash = excluded.email_hash and current.expires_at > now() then current.expires_at else now() + interval '1 hour' end;
  return jsonb_build_object('pending', true);
end $$;

create function public.support_record_payment(p_payment jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare inserted integer;
begin
  insert into public.support_payments(transaction_id, message_id, email_hash, amount_cents, currency, product_code, state, review_reason, paid_at)
  values (p_payment->>'transaction_id', p_payment->>'message_id', p_payment->>'email_hash', (p_payment->>'amount_cents')::integer,
    p_payment->>'currency', p_payment->>'product_code', p_payment->>'state', p_payment->>'review_reason', (p_payment->>'paid_at')::timestamptz)
  on conflict do nothing;
  get diagnostics inserted = row_count;
  return jsonb_build_object('recorded', inserted = 1);
end $$;

create function public.support_status(p_user_id text, p_email_hashes text[] default '{}', p_receipt_id text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare active boolean; intent public.support_checkout_intents; state text; granted timestamptz;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user_id, 0));
  select * into intent from public.support_checkout_intents where user_id = p_user_id;
  update public.support_payments p set claimed_by = p_user_id, claimed_at = now()
  where p.claimed_by is null and p.state = 'confirmed' and p.email_hash = any(p_email_hashes)
    and ((p_receipt_id is not null and p.transaction_id = p_receipt_id)
      or (p_receipt_id is null and intent.user_id is not null and p.email_hash = intent.email_hash
        and p.paid_at >= intent.created_at - interval '5 seconds' and p.paid_at <= intent.expires_at));
  select exists(select 1 from public.support_payments where claimed_by = p_user_id and support_payments.state = 'confirmed') into active;
  select min(claimed_at) into granted from public.support_payments where claimed_by = p_user_id and support_payments.state = 'confirmed';
  state := case when active then 'active'
    when exists(select 1 from public.support_payments p where p.claimed_by = p_user_id and p.state in ('refunded','disputed')) then 'revoked'
    when intent.user_id is null then 'free'
    when exists(select 1 from public.support_payments p where p.email_hash = intent.email_hash and p.state = 'review' and p.claimed_by is null) then 'review'
    when intent.expires_at >= now() or exists(select 1 from public.support_payments p where p.email_hash = intent.email_hash and p.state = 'confirmed' and p.claimed_by is null
      and p.paid_at >= intent.created_at - interval '5 seconds' and p.paid_at <= intent.expires_at) then 'pending'
    else 'expired' end;
  return jsonb_build_object('watermark_free', active, 'state', state, 'granted_at', granted);
end $$;

create function public.support_overlay_key(p_user_id text, p_rotate boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare key public.support_overlay_keys;
begin
  insert into public.support_overlay_keys(user_id) values (p_user_id) on conflict do nothing;
  if p_rotate then update public.support_overlay_keys set revision = revision + 1 where user_id = p_user_id; end if;
  select * into key from public.support_overlay_keys where user_id = p_user_id;
  return jsonb_build_object('viewer_id', key.viewer_id, 'revision', key.revision);
end $$;

create function public.support_overlay_status(p_viewer_id uuid, p_revision integer) returns jsonb
language sql security definer set search_path = '' as $$
  select jsonb_build_object('watermark_free', exists (
    select 1 from public.support_overlay_keys k join public.support_payments p on p.claimed_by = k.user_id
    where k.viewer_id = p_viewer_id and k.revision = p_revision and p.state = 'confirmed'
  ));
$$;

create function public.support_revoke_payment(p_transaction_id text, p_state text, p_actor text, p_reason text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare previous text;
begin
  if p_state not in ('refunded','disputed') or length(trim(p_reason)) < 10 or length(trim(p_actor)) < 3 then
    raise exception 'Invalid reconciliation';
  end if;
  select state into previous from public.support_payments where transaction_id = p_transaction_id for update;
  if previous is null then raise exception 'Unknown transaction'; end if;
  if previous = p_state then return jsonb_build_object('changed', false); end if;
  update public.support_payments set state = p_state where transaction_id = p_transaction_id;
  insert into public.support_payment_audit(transaction_id, previous_state, new_state, actor, reason)
    values(p_transaction_id, previous, p_state, p_actor, p_reason);
  return jsonb_build_object('changed', true);
end $$;

revoke all on function public.support_start_checkout(text,text), public.support_record_payment(jsonb), public.support_status(text,text[],text), public.support_overlay_key(text,boolean), public.support_overlay_status(uuid,integer), public.support_revoke_payment(text,text,text,text) from public, anon, authenticated;
grant execute on function public.support_start_checkout(text,text), public.support_record_payment(jsonb), public.support_status(text,text[],text), public.support_overlay_key(text,boolean), public.support_overlay_status(uuid,integer), public.support_revoke_payment(text,text,text,text) to service_role;
