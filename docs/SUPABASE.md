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
- **1 credit = 1 minute** of source video (rounded up)
- Free plan: 30 credits/mo on signup
- Starter $19 · 200 cr · Pro $49 · 600 cr · Business $99 · 1,500 cr

Paid checkout (Stripe) is the next integration step; plan rows live in `public.plans`.
