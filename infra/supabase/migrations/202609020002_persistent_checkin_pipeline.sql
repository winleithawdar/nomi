-- P6: make the P3 WhatsApp/check-in pipeline restart-safe and auditable.

alter table public.whatsapp_events
    add column if not exists verification_request_id text null,
    add column if not exists event_type text not null default 'checkin_response';

create index if not exists nomi_checkins_senior_sent_idx
    on public.nomi_checkins (senior_id, sent_at desc);

create unique index if not exists nomi_checkins_one_open_per_senior_idx
    on public.nomi_checkins (senior_id)
    where status = 'sent';

create unique index if not exists senior_interactions_unique_checkin_idx
    on public.senior_interactions (checkin_id)
    where checkin_id is not null;

create index if not exists whatsapp_events_verification_idx
    on public.whatsapp_events (verification_request_id)
    where verification_request_id is not null;

-- Safe mock contacts for local/API testing. Replace wa_id values with the Meta test
-- phone IDs before testing the live WhatsApp Cloud API.
insert into public.senior_contacts (senior_id, wa_id, phone_e164, role)
values
    ('senior-1', '6590000001', '+6590000001', 'senior'),
    ('senior-1', '6590000002', '+6590000002', 'caregiver')
on conflict (senior_id, role) do nothing;
