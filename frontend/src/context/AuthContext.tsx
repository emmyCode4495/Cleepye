import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase, supabaseConfigured } from "../lib/supabase";
import {  apiUrl, setAccessTokenProvider } from "../lib/api";

export type Profile = {
  id: string;
  email?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
  plan_id: string;
  credits_balance: number;
  clarity_credits_balance?: number;
  clarity_monthly_allowance?: number;
  credits_monthly_allowance: number;
  subscription_status: string;
};

export type PlanLimits = {
  plan_id: string;
  name: string;
  max_clips_per_job: number;
  max_clips_ui: number;
  max_source_minutes: number;
  credits_per_month: number | null;
};

type AuthState = {
  configured: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  planLimits: PlanLimits | null;
  accessToken: string | null;
  refreshProfile: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUpWithPassword: (email: string, password: string, name?: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthCtx = createContext<AuthState | null>(null);

async function fetchMe(token: string): Promise<{ profile: Profile | null; planLimits: PlanLimits | null }> {
  try {
    const res = await fetch(apiUrl("/api/me"), {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) return { profile: null, planLimits: null };
    const data = await res.json();
    return {
      profile: (data.profile as Profile | null) ?? null,
      planLimits: (data.plan_limits as PlanLimits | null) ?? null,
    };
  } catch {
    return { profile: null, planLimits: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(supabaseConfigured);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [planLimits, setPlanLimits] = useState<PlanLimits | null>(null);

  const refreshProfile = useCallback(async () => {
    const token = session?.access_token;
    if (!token) {
      setProfile(null);
      setPlanLimits(null);
      return;
    }
    const { profile: p, planLimits: lim } = await fetchMe(token);
    setProfile(p);
    setPlanLimits(lim);
  }, [session?.access_token]);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    setAccessTokenProvider(() => session?.access_token ?? null);
    return () => setAccessTokenProvider(null);
  }, [session?.access_token]);

  useEffect(() => {
    if (!session?.access_token) {
      setProfile(null);
      setPlanLimits(null);
      return;
    }
    fetchMe(session.access_token).then(({ profile: p, planLimits: lim }) => {
      setProfile(p);
      setPlanLimits(lim);
    });
  }, [session?.access_token]);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error("Auth is not configured");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }, []);

  const signUpWithPassword = useCallback(async (email: string, password: string, name?: string) => {
    if (!supabase) throw new Error("Auth is not configured");
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: name || undefined } },
    });
    if (error) throw error;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) throw new Error("Auth is not configured");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (error) throw error;
  }, []);

  const signOut = useCallback(async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    setProfile(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      configured: supabaseConfigured,
      loading,
      session,
      user: session?.user ?? null,
      profile,
      planLimits,
      accessToken: session?.access_token ?? null,
      refreshProfile,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      signOut,
    }),
    [
      loading,
      session,
      profile,
      planLimits,
      refreshProfile,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      signOut,
    ]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
