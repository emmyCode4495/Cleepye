import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Loader2, Mail } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useNotice } from "../context/NoticeContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { Logo } from "../components/Logo";


type Mode = "signin" | "signup";

export default function Auth() {
  useDocumentTitle("Sign in");
  const auth = useAuth();
  const notice = useNotice();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState("");

  if (!auth.configured) {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center">
        <Logo className="justify-center" />
        <p className="mt-6 text-muted">
          Auth isn’t configured. Add <code className="text-bone">VITE_SUPABASE_URL</code> and{" "}
          <code className="text-bone">VITE_SUPABASE_ANON_KEY</code> to the frontend env, and run{" "}
          <code className="text-bone">supabase/schema.sql</code> in your project.
        </p>
        <Link to="/" className="btn-primary mt-6 inline-flex">
          Back home
        </Link>
      </div>
    );
  }

  if (auth.user && !auth.loading) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setInfo("");
    setBusy(true);
    try {
      if (mode === "signin") {
        await auth.signInWithPassword(email.trim(), password);
        navigate("/");
      } else {
        await auth.signUpWithPassword(email.trim(), password, name.trim() || undefined);
        setInfo("Check your email to confirm your account (if confirmation is enabled).");
      }
    } catch (err: any) {
      notice.error("Sign-in failed", err?.message || "Authentication failed. Check your email and password.");
    } finally {
      setBusy(false);
    }
  }

  async function onGoogle() {
    setBusy(true);
    try {
      await auth.signInWithGoogle();
    } catch (err: any) {
      notice.error("Google sign-in failed", err?.message || "Could not start Google sign-in. Check Supabase Google provider settings.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12">
      <div className="mb-8 flex justify-center">
        <Logo />
      </div>
      <div className="surface p-6 sm:p-8">
        <h1 className="font-display text-2xl font-bold tracking-tight">
          {mode === "signin" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {mode === "signin" ? "Sign in to mine clips and manage credits." : "Start with 2 free credits."}
        </p>

        <button
          type="button"
          onClick={onGoogle}
          disabled={busy}
          className="btn-ghost mt-6 flex w-full items-center justify-center gap-2 border border-white/10 py-2.5"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </button>

        <div className="my-5 flex items-center gap-3 text-xs text-dim">
          <span className="h-px flex-1 bg-white/10" />
          or email
          <span className="h-px flex-1 bg-white/10" />
        </div>

        <form onSubmit={onSubmit} className="space-y-3">
          {mode === "signup" && (
            <input
              className="field"
              placeholder="Name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
            />
          )}
          <input
            className="field"
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          <input
            className="field"
            type="password"
            required
            minLength={6}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
          />
          {info && <p className="text-sm text-lime">{info}</p>}
          <button type="submit" disabled={busy} className="btn-primary flex w-full items-center justify-center gap-2 py-2.5">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
            {mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-muted">
          {mode === "signin" ? (
            <>
              No account?{" "}
              <button type="button" className="text-lime hover:underline" onClick={() => setMode("signup")}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" className="text-lime hover:underline" onClick={() => setMode("signin")}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
