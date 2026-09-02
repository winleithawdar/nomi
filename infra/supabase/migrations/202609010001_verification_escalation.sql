create extension if not exists pgcrypto;

create table if not exists public.verification_requests (
    id uuid primary key default gen_random_uuid(),
    senior_id text not null,
    detection_payload jsonb not null,
    status text not null,
    outcome text null,
    escalation_decision text not null default 'none',
    check_in_message text not null,
    message_sent_at timestamptz null,
    response_received_at timestamptz null,
    response_text text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz null,
    constraint verification_requests_status_check check (
        status in (
            'awaiting_response',
            'resolved_reassuring',
            'resolved_no_escalation',
            'escalated'
        )
    ),
    constraint verification_requests_outcome_check check (
        outcome is null or outcome in (
            'reassuring',
            'help_needed',
            'no_response',
            'repeated_change'
        )
    ),
    constraint verification_requests_escalation_decision_check check (
        escalation_decision in ('none', 'caregiver_alert')
    )
);

create index if not exists verification_requests_senior_created_idx
    on public.verification_requests (senior_id, created_at desc);

create index if not exists verification_requests_senior_status_idx
    on public.verification_requests (senior_id, status)
    where status = 'awaiting_response';

create table if not exists public.caregiver_alerts (
    id uuid primary key default gen_random_uuid(),
    senior_id text not null,
    verification_request_id uuid not null references public.verification_requests (id),
    what_changed text not null,
    context text not null,
    verification_outcome text not null,
    suggested_action text not null,
    detection_summary text not null default '',
    detection_payload jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default now(),
    delivered_at timestamptz null,
    constraint caregiver_alerts_status_check check (
        status in ('pending', 'delivered')
    )
);

create index if not exists caregiver_alerts_senior_created_idx
    on public.caregiver_alerts (senior_id, created_at desc);

create index if not exists caregiver_alerts_status_idx
    on public.caregiver_alerts (status, created_at desc)
    where status = 'pending';
