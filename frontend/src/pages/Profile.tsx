import { Link, Navigate } from "react-router-dom";
import { CreditCard, LogOut, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function Profile() {
  useDocumentTitle("Profile");
  const auth = useAuth();

  if (auth.loading) {
    return <p className="text-sm text-dim">Loading account…</p>;
  }

  if (!auth.configured) {
    return (
      <div className="mx-auto max-w-lg">
        <h1 className="font-display text-3xl font-bold">Profile</h1>
        <p className="mt-2 text-muted">Auth isn’t configured on this deployment. Set Supabase env vars to enable accounts.</p>
      </div>
    );
  }

  if (!auth.user) {
    return <Navigate to="/auth" replace state={{ from: "/profile" }} />;
  }

  const p = auth.profile;

  return (
    <div className="mx-auto max-w-lg">
      <p className="eyebrow text-lime">Account</p>
      <h1 className="mt-2 font-display text-3xl font-bold tracking-tight">Your profile</h1>

      <div className="surface mt-8 p-6">
        <div className="flex items-center gap-4">
          {p?.avatar_url ? (
            <img src={p.avatar_url} alt="" className="h-14 w-14 rounded-full object-cover" />
          ) : (
            <div className="grid h-14 w-14 place-items-center rounded-full bg-lime/15 text-lime">
              <User className="h-6 w-6" />
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate font-medium">{p?.display_name || auth.user.email}</p>
            <p className="truncate text-sm text-dim">{auth.user.email}</p>
          </div>
        </div>

        <dl className="mt-6 grid gap-3 border-t pt-6 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Plan</dt>
            <dd className="capitalize font-medium">{p?.plan_id || "free"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Credits</dt>
            <dd className="font-mono font-medium text-lime">{p?.credits_balance ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Monthly allowance</dt>
            <dd className="font-mono">{p?.credits_monthly_allowance ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Status</dt>
            <dd className="capitalize">{p?.subscription_status || "active"}</dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap gap-2">
          <Link to="/pricing" className="btn-primary inline-flex items-center gap-2 px-4 py-2">
            <CreditCard className="h-4 w-4" /> Manage plan
          </Link>
          <button type="button" onClick={() => auth.signOut()} className="btn-ghost inline-flex items-center gap-2 border border-white/10 px-4 py-2">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
