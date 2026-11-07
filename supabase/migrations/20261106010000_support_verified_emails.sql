-- Allow a purchase made with any verified account email to be claimed
-- during the checkout window started by the account.
create or replace function public.support_status(
  p_user_id text,
  p_email_hashes text[] default '{}',
  p_receipt_id text default null
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare active boolean; intent public.support_checkout_intents; state text; granted timestamptz;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user_id, 0));
  select * into intent from public.support_checkout_intents where user_id = p_user_id;
  update public.support_payments p set claimed_by = p_user_id, claimed_at = now()
  where p.claimed_by is null and p.state = 'confirmed' and p.email_hash = any(p_email_hashes)
    and ((p_receipt_id is not null and p.transaction_id = p_receipt_id)
      or (p_receipt_id is null and intent.user_id is not null
        and p.paid_at >= intent.created_at - interval '5 seconds' and p.paid_at <= intent.expires_at));
  select exists(select 1 from public.support_payments where claimed_by = p_user_id and support_payments.state = 'confirmed') into active;
  select min(claimed_at) into granted from public.support_payments where claimed_by = p_user_id and support_payments.state = 'confirmed';
  state := case when active then 'active'
    when exists(select 1 from public.support_payments p where p.claimed_by = p_user_id and p.state in ('refunded','disputed')) then 'revoked'
    when intent.user_id is null then 'free'
    when exists(select 1 from public.support_payments p where p.email_hash = intent.email_hash and p.state = 'review' and p.claimed_by is null) then 'review'
    when intent.expires_at >= now() or exists(select 1 from public.support_payments p where p.email_hash = any(p_email_hashes) and p.state = 'confirmed' and p.claimed_by is null
      and p.paid_at >= intent.created_at - interval '5 seconds' and p.paid_at <= intent.expires_at) then 'pending'
    else 'expired' end;
  return jsonb_build_object('watermark_free', active, 'state', state, 'granted_at', granted);
end $$;

revoke all on function public.support_status(text,text[],text) from public, anon, authenticated;
grant execute on function public.support_status(text,text[],text) to service_role;
