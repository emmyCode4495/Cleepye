import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, Loader2, Sparkles } from "lucide-react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useAuth } from "../context/AuthContext";
import { useNotice } from "../context/NoticeContext";
import { cn } from "../lib/cn";

type Plan = {
  id: string;
  name: string;
  currency: string;
  price_monthly: number;
  price_label: string;
  credits_per_month: number;
  max_clips_per_job: number;
  max_source_minutes: number;
  description: string;
  features: string[];
  popular?: boolean;
};

function formatNgn(n: number) {
  return `₦${n.toLocaleString("en-NG")}`;
}

export default function Pricing() {
  useDocumentTitle("Pricing");
  const auth = useAuth();
  const notice = useNotice();
  const navigate = useNavigate();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [rule, setRule] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/plans")
      .then((r) => r.json())
      .then((d) => {
        setPlans(d.plans || []);
        setRule(d.credit_rule || "");
      })
      .finally(() => setLoading(false));
  }, []);

  async function choosePlan(planId: string) {
    if (!auth.configured) {
      notice.info("Auth not configured", "Add Supabase keys to enable checkout.");
      return;
    }
    if (!auth.user || !auth.accessToken) {
      navigate("/auth");
      return;
    }
    setBusyPlan(planId);
    try {
      const res = await fetch("/api/billing/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${auth.accessToken}`,
        },
        body: JSON.stringify({
          plan_id: planId,
          redirect_url: `${window.location.origin}/pricing?paid=1`,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === "string" ? detail : data.message || "Checkout failed";
        throw new Error(msg);
      }
      if (data.payment_url) {
        window.location.href = data.payment_url;
        return;
      }
      throw new Error("No payment URL returned");
    } catch (e: any) {
      notice.error("Payment unavailable", e?.message || "Try again in a moment.");
    } finally {
      setBusyPlan(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-10 text-center">
        <p className="eyebrow text-lime">Pricing</p>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight">Credits that match your volume</h1>
        <p className="mx-auto mt-3 max-w-xl text-muted">
          {rule || "1 credit = 1 mining job. Prices in Naira (₦)."}
        </p>
        {auth.profile && (
          <p className="mt-4 text-sm text-bone">
            You’re on <span className="capitalize text-lime">{auth.profile.plan_id}</span> ·{" "}
            <span className="font-mono text-lime">{auth.profile.credits_balance}</span> credits left
          </p>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-20 text-dim">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {plans.map((p) => (
            <div
              key={p.id}
              className={cn(
                "surface relative flex flex-col p-5",
                p.popular && "border-lime/40 shadow-[0_0_40px_-16px_rgba(163,230,53,0.35)]"
              )}
            >
              {p.popular && (
                <span className="absolute -top-2.5 left-4 inline-flex items-center gap-1 rounded-full bg-lime px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-black">
                  <Sparkles className="h-3 w-3" /> Popular
                </span>
              )}
              <h2 className="font-display text-xl font-semibold">{p.name}</h2>
              <p className="mt-2 font-display text-3xl font-bold tracking-tight">
                {formatNgn(p.price_monthly)}
                <span className="text-base font-normal text-dim">/mo</span>
              </p>
              <p className="mt-1 font-mono text-xs text-dim">{p.credits_per_month} credits / month</p>
              {p.description && <p className="mt-3 text-sm text-muted">{p.description}</p>}
              <ul className="mt-5 flex-1 space-y-2">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-muted">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-lime" />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                disabled={busyPlan === p.id}
                onClick={() => choosePlan(p.id)}
                className={cn(
                  "mt-6 block w-full text-center",
                  p.popular ? "btn-primary py-2.5" : "btn-ghost border border-white/10 py-2.5"
                )}
              >
                {busyPlan === p.id ? (
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                ) : auth.profile?.plan_id === p.id ? (
                  "Current plan"
                ) : (
                  `Choose ${p.name}`
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="mt-10 text-center text-xs text-dim">
        {!auth.user && (
          <>
            <Link to="/auth" className="text-lime hover:underline">
              Sign in
            </Link>{" "}
            to subscribe.
          </>
        )}
      </p>
    </div>
  );
}
