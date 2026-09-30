-- Cleepye Supabase schema
-- Run in Supabase SQL Editor (or via CLI migration)

-- Profiles (1:1 with auth.users)
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  plan_id text not null default 'starter',
  credits_balance integer not null default 5 check (credits_balance >= 0),
  credits_monthly_allowance integer not null default 0,
  subscription_status text not null default 'active', -- active | cancelled | past_due
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Credit ledger (audit trail)
create table if not exists public.credit_ledger (
  id bigserial primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  delta integer not null, -- positive = grant, negative = spend
  reason text not null,   -- signup_bonus | subscription_grant | mine_job | admin_adjust | pack_purchase
  job_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists credit_ledger_user_id_idx on public.credit_ledger (user_id, created_at desc);

-- Plans catalog (reference; enforced in app too)
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

insert into public.plans (id, name, price_monthly_cents, credits_per_month, max_clips_per_job, max_source_minutes, features, sort_order)
values
  ('starter', 'Starter', 1000000, 8, 8, 45, '["8 credits/mo","8 clips/mine","45 min sources","Custom fonts","9:16 reframe"]', 0),
  ('creator', 'Creator', 2000000, 20, 12, 90, '["20 credits/mo","12 clips/mine","90 min sources"]', 1),
  ('pro', 'Pro', 3500000, 40, 0, 180, '["40 credits/mo","Unlimited clips/mine","3h sources"]', 2)
on conflict (id) do update set
  name = excluded.name,
  price_monthly_cents = excluded.price_monthly_cents,
  credits_per_month = excluded.credits_per_month,
  max_clips_per_job = excluded.max_clips_per_job,
  max_source_minutes = excluded.max_source_minutes,
  features = excluded.features,
  sort_order = excluded.sort_order;

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name, avatar_url, plan_id, credits_balance, credits_monthly_allowance)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url',
    'starter',
    5,
    0
  );
  insert into public.credit_ledger (user_id, delta, reason, metadata)
  values (new.id, 5, 'signup_bonus', jsonb_build_object('credits', 5));
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- updated_at helper
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

-- RLS
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
