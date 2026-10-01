/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly V_SUPABASE_URL?: string;
  readonly V_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}