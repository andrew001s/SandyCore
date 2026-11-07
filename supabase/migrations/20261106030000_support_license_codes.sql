create table public.support_license_codes (
  transaction_id text primary key references public.support_payments(transaction_id),
  code_hash text not null unique,
  redeemed_by text,
  redeemed_at timestamptz
);

alter table public.support_license_codes enable row level security;
revoke all on public.support_license_codes from public, anon, authenticated;
grant all on public.support_license_codes to service_role;

create or replace function public.support_issue_license_code(
  p_transaction_id text,
  p_code_hash text
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare inserted integer;
begin
  insert into public.support_license_codes(transaction_id, code_hash)
  select p.transaction_id, p_code_hash
  from public.support_payments p
  where p.transaction_id = p_transaction_id and p.state = 'confirmed'
  on conflict do nothing;
  get diagnostics inserted = row_count;
  return jsonb_build_object('created', inserted = 1);
end $$;

create or replace function public.support_redeem_license_code(
  p_user_id text,
  p_code_hash text
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare redeemed integer;
begin
  update public.support_license_codes c
  set redeemed_by = p_user_id, redeemed_at = now()
  where c.code_hash = p_code_hash and c.redeemed_by is null
    and exists (
      select 1 from public.support_payments p
      where p.transaction_id = c.transaction_id and p.state = 'confirmed'
    );
  get diagnostics redeemed = row_count;
  if redeemed = 1 then
    update public.support_payments p
    set claimed_by = p_user_id, claimed_at = now()
    from public.support_license_codes c
    where c.transaction_id = p.transaction_id
      and c.code_hash = p_code_hash
      and p.claimed_by is null;
  end if;
  return jsonb_build_object('redeemed', redeemed = 1);
end $$;

revoke all on function public.support_issue_license_code(text,text),
  public.support_redeem_license_code(text,text) from public, anon, authenticated;
grant execute on function public.support_issue_license_code(text,text),
  public.support_redeem_license_code(text,text) to service_role;
