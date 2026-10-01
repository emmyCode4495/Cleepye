import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.V_SUPABASE_URL as string | undefined;
const anon = import.meta.env.V_SUPABASE_ANON_KEY as string | undefined;

export const supabaseConfigured = Boolean(url && anon);

export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url!, anon!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
