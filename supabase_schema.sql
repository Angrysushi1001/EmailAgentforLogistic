-- Run this once in Supabase SQL Editor to create required tables.

create table if not exists pending_quotes (
    id               uuid primary key default gen_random_uuid(),
    message_id       text not null unique,
    sender           text,
    subject          text,
    received_at      timestamptz,
    email_body       text,
    raw_extraction   jsonb,
    confidence_score float,
    status           text not null default 'pending',  -- pending | approved | rejected
    created_at       timestamptz not null default now()
);

create table if not exists fee_dictionary (
    id          uuid primary key default gen_random_uuid(),
    raw_name    text not null unique,
    master_name text not null,
    created_at  timestamptz not null default now()
);
