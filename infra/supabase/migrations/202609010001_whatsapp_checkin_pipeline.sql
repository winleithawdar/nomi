create table if not exists public.senior_contacts (
    id uuid primary key default gen_random_uuid(),
    senior_id text not null,
    wa_id text not null unique,
    phone_e164 text null,
    role text not null,
    created_at timestamptz not null default now(),
    unique (senior_id, role),
    constraint senior_contacts_role_check check (role in ('senior', 'caregiver'))
);

create table if not exists public.nomi_checkins (
    id text primary key,
    senior_id text not null,
    sent_at timestamptz not null,
    outbound_wamid text null,
    status text not null,
    response_wamid text null,
    response_received_at timestamptz null,
    wellbeing_score double precision null,
    created_at timestamptz not null default now(),
    constraint nomi_checkins_status_check check (status in ('sent', 'responded', 'missed'))
);

create table if not exists public.whatsapp_events (
    inbound_wamid text primary key,
    wa_id text not null,
    received_at timestamptz not null,
    checkin_id text null,
    ignored_reason text null
);
