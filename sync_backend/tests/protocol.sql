-- Run against the installed schema. All probe writes are rolled back.
begin;
set local role service_role;
do $$
declare
  result jsonb;
  group_a text := repeat('1',64);
  group_b text := repeat('2',64);
  ip_key text := repeat('3',64);
  device text := lpad('1',32,'0');
begin
  result := public.gametime_sync_exchange(group_a,ip_key,device,'9007199254740993',repeat('A',44),'{}');
  if result ->> 'need_upload' <> 'false' then raise exception 'First upload failed'; end if;
  result := public.gametime_sync_exchange(group_b,ip_key,device,'1',null,'{}');
  if result ->> 'need_upload' <> 'true' then raise exception 'Groups are not isolated'; end if;
  result := public.gametime_sync_exchange(group_a,ip_key,device,'9007199254740992',repeat('B',44),'{}');
  if (select revision from public.gametime_sync_devices where group_hash=group_a and device_id=device) <> 9007199254740993 then
    raise exception 'Stale snapshot overwrote newer data';
  end if;
  result := public.gametime_sync_exchange(group_a,ip_key,lpad('2',32,'0'),'1',repeat('A',44),
    jsonb_build_object(device,'9007199254740993'));
  if jsonb_array_length(result -> 'snapshots') <> 0 then raise exception 'Known snapshot was downloaded again'; end if;
  result := public.gametime_sync_exchange(group_a,ip_key,lpad('2',32,'0'),'1',null,'{}');
  if result #>> '{snapshots,0,revision}' <> '9007199254740993' then raise exception 'Revision precision lost'; end if;
  for i in 3..20 loop
    result := public.gametime_sync_exchange(group_a,ip_key,lpad(to_hex(i),32,'0'),'1',repeat('A',44),'{}');
    if result ? 'error' then raise exception 'Unexpected early device cap'; end if;
  end loop;
  result := public.gametime_sync_exchange(group_a,ip_key,lpad('21',32,'0'),'1',repeat('A',44),'{}');
  if result ->> 'error' <> 'quota' then raise exception 'Device cap missing'; end if;
  update public.gametime_sync_budget set used_bytes=209715200 where singleton;
  result := public.gametime_sync_exchange(group_b,ip_key,device,'1',repeat('A',44),'{}');
  if result ->> 'error' <> 'quota' then raise exception 'Storage cap missing'; end if;
  for i in 1..121 loop
    result := public.gametime_sync_exchange(group_a,ip_key,device,'9007199254740993',null,'{}');
  end loop;
  if result ->> 'error' <> 'rate' then raise exception 'Rate cap missing'; end if;
end;
$$;
select 'isolation, revisions, known cache, device/storage/rate quotas passed' as checks;
rollback;
