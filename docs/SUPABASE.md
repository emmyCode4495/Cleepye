# Supabase setup (Auth + Credits)

## 1. Create a Supabase project
https://supabase.com → New project

## 2. Run the schema
SQL Editor → paste and run `supabase/schema.sql`

## 3. Enable Google auth
Authentication → Providers → Google  
Add Client ID / Secret from Google Cloud Console  
Redirect URL: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`

Also enable **Email** provider for password sign-up.

## 4. Backend `.env`
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
AUTH_REQUIRED=true
```

## 5. Frontend `frontend/.env`
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

## Credit model
Source of truth is `backend/services/pricing.py`.
- **Mining credit** = 1 mining job (one source video). **Clarity credits** are a separate meter for enhance/upscale/HDR.
- New users start on the `free` plan with **1 mining credit and 0 Clarity credits**.
- Paid plans (Starter / Creator / Pro) are priced in NGN; checkout is covered in `PAYMENTS_NG.md`.

## Troubleshooting
**"Database error saving new user" on sign-up** — Supabase Auth runs the `on_auth_user_created`
trigger (`public.handle_new_user`) inside the sign-up transaction, so any error in it blocks the
account. Re-run `supabase/schema.sql` (it is idempotent) to add missing columns and install the
defensive version of the trigger. If you still see it, open **Logs → Postgres Logs** in the
Supabase dashboard and look for the error right after the sign-up attempt, or a
`handle_new_user failed for user …` warning, which names the real cause.
