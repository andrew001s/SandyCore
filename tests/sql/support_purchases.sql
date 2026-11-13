-- Run after both support-purchases migrations against a disposable PostgreSQL database.
-- All fixtures are rolled back; requires an administrative test role.
begin;
do $$
declare first_created timestamptz; result jsonb; key jsonb; rotated jsonb; old jsonb;
begin
  perform public.support_start_checkout('test-account-a','test-hash-a');
  select created_at into first_created from public.support_checkout_intents where user_id='test-account-a';
  perform public.support_start_checkout('test-account-a','test-hash-a');
  if first_created <> (select created_at from public.support_checkout_intents where user_id='test-account-a') then raise exception 'Repeated checkout lost its payment window'; end if;
  result := public.support_overlay_key('test-account-a');
  if (public.support_overlay_status((result->>'viewer_id')::uuid,1)->>'watermark_free')::boolean then raise exception 'Free account received OBS entitlement'; end if;
  old := jsonb_build_object('transaction_id','test-payment-001','message_id','test-message-001','email_hash','test-hash-a','amount_cents',300,'currency','USD','product_code','test-product','state','confirmed','paid_at',now()-interval '1 day');
  perform public.support_record_payment(old);
  result := public.support_status('test-account-a',array['test-hash-a']);
  if (result->>'watermark_free')::boolean then raise exception 'Historical purchase claimed automatically'; end if;
  result := public.support_status('test-account-b',array['test-hash-b'],'test-payment-001');
  if (result->>'watermark_free')::boolean then raise exception 'Receipt alone claimed another email payment'; end if;
  result := public.support_status('test-account-a',array['test-hash-a'],'test-payment-001');
  if not (result->>'watermark_free')::boolean then raise exception 'Verified receipt recovery failed'; end if;
  result := public.support_status('test-account-b',array['test-hash-a'],'test-payment-001');
  if (result->>'watermark_free')::boolean then raise exception 'Payment ownership was reassigned'; end if;
  key := public.support_overlay_key('test-account-a');
  if not (public.support_overlay_status((key->>'viewer_id')::uuid,(key->>'revision')::integer)->>'watermark_free')::boolean then raise exception 'Paid OBS key rejected'; end if;
  rotated := public.support_overlay_key('test-account-a',true);
  if (public.support_overlay_status((key->>'viewer_id')::uuid,(key->>'revision')::integer)->>'watermark_free')::boolean then raise exception 'Old OBS key remained valid'; end if;
  perform public.support_revoke_payment('test-payment-001','refunded','test-operator','Provider refund verified');
  result := public.support_record_payment(old);
  if (result->>'recorded')::boolean then raise exception 'Webhook replay replaced a revoked receipt'; end if;
  if (public.support_status('test-account-a')->>'watermark_free')::boolean then raise exception 'Refund did not revoke account'; end if;
  if (public.support_overlay_status((rotated->>'viewer_id')::uuid,(rotated->>'revision')::integer)->>'watermark_free')::boolean then raise exception 'Refund did not revoke OBS'; end if;
  if (select count(*) from public.support_payment_audit where transaction_id='test-payment-001') <> 1 then raise exception 'Refund audit missing'; end if;
  perform public.support_start_checkout('test-account-c','test-hash-c');
  perform public.support_record_payment(jsonb_build_object('transaction_id','test-payment-002','message_id','test-message-002','email_hash','test-hash-c','amount_cents',300,'currency','USD','product_code','test-product','state','confirmed','paid_at',now()));
  if not (public.support_status('test-account-c',array['test-hash-c'])->>'watermark_free')::boolean then raise exception 'Automatic account association failed'; end if;
  perform public.support_start_checkout('test-account-d','test-hash-d');
  perform public.support_record_payment(jsonb_build_object('transaction_id','test-payment-003','message_id','test-message-003','email_hash','test-alt-hash-d','amount_cents',300,'currency','USD','product_code','test-product','state','confirmed','paid_at',now()));
  if not (public.support_status('test-account-d',array['test-hash-d','test-alt-hash-d'])->>'watermark_free')::boolean then raise exception 'Verified alternate email association failed'; end if;
end $$;
set local role authenticated;
do $$
begin
  begin
    perform public.support_status('forged-account');
    raise exception 'Authenticated client could execute privileged payment RPC';
  exception when insufficient_privilege then null;
  end;
  begin
    perform 1 from public.support_payments;
    raise exception 'Authenticated client could read payments';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;
rollback;
