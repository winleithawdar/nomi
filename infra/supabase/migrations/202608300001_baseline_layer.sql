create extension if not exists pgcrypto;

create table if not exists public.senior_interactions (
    id uuid primary key default gen_random_uuid(),
    senior_id uuid not null,
    checkin_id uuid null,
    occurred_at timestamptz not null,
    interaction_type text not null,
    checkin_sent_at timestamptz null,
    response_received_at timestamptz null,
    response_latency_minutes double precision null,
    missed_checkin boolean not null default false,
    wellbeing_score double precision null,
    source text not null default 'nomi',
    created_at timestamptz not null default now(),
    constraint senior_interactions_source_check check (source = 'nomi')
);

create index if not exists senior_interactions_senior_time_idx
    on public.senior_interactions (senior_id, occurred_at desc);

create index if not exists senior_interactions_checkin_idx
    on public.senior_interactions (checkin_id)
    where checkin_id is not null;

create table if not exists public.senior_baseline_snapshots (
    id uuid primary key default gen_random_uuid(),
    senior_id uuid not null,
    calculated_at timestamptz not null default now(),
    latest_interaction_at timestamptz not null,
    status text not null,
    min_observations_for_stable integer not null,
    total_interactions integer not null,
    numeric_window_size integer not null,
    binary_window_size integer not null,
    frequency_window_days integer not null,
    baseline_payload jsonb not null
);

create index if not exists senior_baseline_snapshots_senior_calc_idx
    on public.senior_baseline_snapshots (senior_id, calculated_at desc);
