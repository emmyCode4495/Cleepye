-- Cleepye Supabase schema
-- Safe to run (and re-run) in the Supabase SQL Editor, on a fresh project OR an
-- existing one. It creates what's missing, adds columns that older versions of
-- this file didn't have, and replaces the signup trigger.
--
-- Keep the numbers below in sync with backend/services/pricing.py:
--   new user  -> plan 'free', 1 mining credit, 0 Clarity credits

-- ───────────────────────── Profiles (1:1 with auth.users) ─────────────────────────
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  plan_id text not null default 'free',
  credits_balance integer not null default 1 check (credits_balance >= 0),
  credits_monthly_allowance integer not null default 0,
  clarity_credits_balance integer not null default 0 check (clarity_credits_balance >= 0),
  clarity_monthly_allowance integer not null default 0,
  subscription_status text not null default 'active', -- active | cancelled | past_due
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- If `profiles` already existed from an older schema, "create table if not exists"
-- above did nothing, so make sure every column the trigger/backend uses is there.
alter table public.profiles add column if not exists email text;
alter table public.profiles add column if not exists display_name text;
alter table public.profiles add column if not exists avatar_url text;
alter table public.profiles add column if not exists plan_id text not null default 'free';
alter table public.profiles add column if not exists credits_balance integer not null default 1;
alter table public.profiles add column if not exists credits_monthly_allowance integer not null default 0;
alter table public.profiles add column if not exists clarity_credits_balance integer not null default 0;
alter table public.profiles add column if not exists clarity_monthly_allowance integer not null default 0;
alter table public.profiles add column if not exists subscription_status text not null default 'active';
alter table public.profiles add column if not exists current_period_end timestamptz;
alter table public.profiles add column if not exists created_at timestamptz not null default now();
alter table public.profiles add column if not exists updated_at timestamptz not null default now();

-- New-user defaults follow the current free plan (existing users are not touched).
alter table public.profiles alter column plan_id set default 'free';
alter table public.profiles alter column credits_balance set default 1;

-- ───────────────────────── Credit ledger (audit trail) ─────────────────────────
create table if not exists public.credit_ledger (
  id bigserial primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  delta integer not null, -- positive = grant, negative = spend
  reason text not null,   -- signup_bonus | subscription_grant | mine_job | clarity_job | clarity_subscription_grant | admin_adjust | pack_purchase
  job_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists credit_ledger_user_id_idx on public.credit_ledger (user_id, created_at desc);

-- ───────────────────────── Plans catalog (reference; enforced in app too) ─────────────────────────
-- Prices are in kobo (NGN x 100), matching pricing.py.
create table if not exists public.plans (
  id text primary key,
  name text not null,
  price_monthly_cents integer not null default 0,
  credits_per_month integer not null,
  max_clips_per_job integer not null default 8,
  max_source_minutes integer not null default 60,
  features jsonb not null default '[]'::jsonb,
  sort_order integer not null default 0,
  active boolean not null default true
);

alter table public.plans add column if not exists clarity_credits_per_month integer not null default 0;

insert into public.plans
  (id, name, price_monthly_cents, credits_per_month, clarity_credits_per_month, max_clips_per_job, max_source_minutes, features, sort_order, active)
values
  ('free',    'Free',    0,       1,  0,   1, 15,  '["1 free mining credit","1 clip per mine","15 min sources"]', -1, false),
  ('starter', 'Starter', 1000000, 8,  40,  8, 45,  '["8 credits/mo","40 Clarity credits/mo","8 clips/mine","45 min sources"]', 0, true),
  ('creator', 'Creator', 2000000, 20, 120, 12, 90, '["20 credits/mo","120 Clarity credits/mo","12 clips/mine","90 min sources"]', 1, true),
  ('pro',     'Pro',     3500000, 40, 300, 0, 180, '["40 credits/mo","300 Clarity credits/mo","Unlimited clips/mine","3h sources"]', 2, true)
on conflict (id) do update set
  name = excluded.name,
  price_monthly_cents = excluded.price_monthly_cents,
  credits_per_month = excluded.credits_per_month,
  clarity_credits_per_month = excluded.clarity_credits_per_month,
  max_clips_per_job = excluded.max_clips_per_job,
  max_source_minutes = excluded.max_source_minutes,
  features = excluded.features,
  sort_order = excluded.sort_order,
  active = excluded.active;

-- ───────────────────────── Auto-create profile on signup ─────────────────────────
-- Runs inside the sign-up transaction. If this function raises, Supabase Auth
-- answers "Database error saving new user" and the account is NOT created.
-- So it is deliberately defensive:
--   * ON CONFLICT DO NOTHING   -> never fails on a duplicate profile
--   * EXCEPTION handler        -> a profile problem can't block sign-up; the real
--                                 cause is written to the Postgres logs as a WARNING
--                                 (the backend's /api/me creates a missing profile on first login)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  v_name text;
begin
  v_name := coalesce(
    nullif(new.raw_user_meta_data->>'full_name', ''),
    nullif(new.raw_user_meta_data->>'name', ''),
    nullif(split_part(coalesce(new.email, ''), '@', 1), '')
  );

  insert into public.profiles (
    id, email, display_name, avatar_url,
    plan_id, credits_balance, credits_monthly_allowance,
    clarity_credits_balance, clarity_monthly_allowance
  )
  values (
    new.id, new.email, v_name, new.raw_user_meta_data->>'avatar_url',
    'free', 1, 0,
    0, 0
  )
  on conflict (id) do nothing;

  if found then
    insert into public.credit_ledger (user_id, delta, reason, metadata)
    values (new.id, 1, 'signup_bonus', jsonb_build_object('credits', 1));
  end if;

  return new;
exception when others then
  raise warning 'handle_new_user failed for user %: % (SQLSTATE %)', new.id, sqlerrm, sqlstate;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ───────────────────────── updated_at helper ─────────────────────────
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ───────────────────────── RLS ─────────────────────────
alter table public.profiles enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.plans enable row level security;

drop policy if exists "Users read own profile" on public.profiles;
create policy "Users read own profile" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "Users update own profile (safe fields)" on public.profiles;
create policy "Users update own profile (safe fields)" on public.profiles
  for update using (auth.uid() = id)
  with check (auth.uid() = id);

drop policy if exists "Users read own ledger" on public.credit_ledger;
create policy "Users read own ledger" on public.credit_ledger
  for select using (auth.uid() = user_id);

drop policy if exists "Anyone can read active plans" on public.plans;
create policy "Anyone can read active plans" on public.plans
  for select using (active = true);

-- Service role bypasses RLS for credit mutations from the Python engine
