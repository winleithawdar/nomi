-- P6 integration migration: align senior identifiers across all workstreams,
-- add caregiver-facing profiles, and provide deterministic MVP demo data.

alter table public.senior_interactions
    alter column senior_id type text using senior_id::text,
    alter column checkin_id type text using checkin_id::text;

alter table public.senior_baseline_snapshots
    alter column senior_id type text using senior_id::text;

create table if not exists public.senior_profiles (
    id text primary key,
    name text not null,
    relationship text not null,
    age_band text not null,
    active boolean not null default true,
    consented_at timestamptz null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.caregiver_profiles (
    id text primary key,
    name text not null,
    phone_e164 text null,
    created_at timestamptz not null default now()
);

create table if not exists public.caregiver_senior_links (
    caregiver_id text not null references public.caregiver_profiles (id),
    senior_id text not null references public.senior_profiles (id),
    relationship text not null,
    consent_status text not null default 'active',
    created_at timestamptz not null default now(),
    primary key (caregiver_id, senior_id),
    constraint caregiver_senior_links_consent_check
        check (consent_status in ('active', 'revoked'))
);

insert into public.senior_profiles (id, name, relationship, age_band, consented_at)
values
    ('senior-1', 'Mdm Tan', 'Mother', 'Late 70s', '2026-08-01T00:00:00Z'),
    ('senior-2', 'Mr Rahman', 'Father', 'Early 80s', '2026-08-01T00:00:00Z'),
    ('senior-3', 'Auntie Lee', 'Aunt', 'Mid 70s', '2026-08-01T00:00:00Z')
on conflict (id) do update set
    name = excluded.name,
    relationship = excluded.relationship,
    age_band = excluded.age_band,
    updated_at = now();

insert into public.caregiver_profiles (id, name)
values ('caregiver-demo', 'Demo Caregiver')
on conflict (id) do update set name = excluded.name;

insert into public.caregiver_senior_links (
    caregiver_id, senior_id, relationship, consent_status
)
values ('caregiver-demo', 'senior-1', 'Daughter', 'active')
on conflict (caregiver_id, senior_id) do update set
    relationship = excluded.relationship,
    consent_status = excluded.consent_status;

insert into public.senior_interactions (
    senior_id,
    occurred_at,
    interaction_type,
    checkin_sent_at,
    response_received_at,
    response_latency_minutes,
    missed_checkin,
    wellbeing_score,
    source
)
select
    'senior-1',
    '2026-08-01T09:00:00Z'::timestamptz + make_interval(days => day_number),
    'checkin_response',
    '2026-08-01T09:00:00Z'::timestamptz + make_interval(days => day_number, mins => -(24 + day_number % 5)),
    '2026-08-01T09:00:00Z'::timestamptz + make_interval(days => day_number),
    24 + day_number % 5,
    false,
    case when day_number % 6 = 0 then 3 else 4 end,
    'nomi'
from generate_series(0, 24) as day_number
where not exists (
    select 1
    from public.senior_interactions existing
    where existing.senior_id = 'senior-1'
      and existing.occurred_at =
          '2026-08-01T09:00:00Z'::timestamptz + make_interval(days => day_number)
);

insert into public.senior_interactions (
    senior_id,
    occurred_at,
    interaction_type,
    checkin_sent_at,
    response_received_at,
    response_latency_minutes,
    missed_checkin,
    wellbeing_score,
    source
)
select
    'senior-1',
    '2026-08-26T09:00:00Z',
    'checkin_response',
    '2026-08-26T06:00:00Z',
    '2026-08-26T09:00:00Z',
    180,
    false,
    1,
    'nomi'
where not exists (
    select 1 from public.senior_interactions
    where senior_id = 'senior-1' and occurred_at = '2026-08-26T09:00:00Z'
);
