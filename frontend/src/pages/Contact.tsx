import { useState } from "react";
import { Mail, MessageSquare, Send } from "lucide-react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useNotice } from "../context/NoticeContext";

export default function Contact() {
  useDocumentTitle("Contact");
  const notice = useNotice();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Frontend-only for now — wire to Formspree / Supabase / API later
    const subject = encodeURIComponent(`Cleepye contact from ${name || email}`);
    const body = encodeURIComponent(`${message}\n\n— ${name}\n${email}`);
    window.location.href = `mailto:support@cleepye.com?subject=${subject}&body=${body}`;
    notice.success("Opening your email app", "Send the message from your mail client. We typically reply within 1–2 business days.");
  }

  return (
    <div className="mx-auto max-w-2xl">
      <p className="eyebrow text-lime">Contact</p>
      <h1 className="mt-2 font-display text-4xl font-bold tracking-tight">We’re here to help</h1>
      <p className="mt-3 text-muted">
        Questions about plans, credits, or the desktop app? Send a note — or email us directly.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <a href="mailto:support@cleepye.com" className="surface flex items-start gap-3 p-5 transition hover:border-white/20">
          <Mail className="mt-0.5 h-5 w-5 text-lime" />
          <div>
            <p className="font-medium">Email</p>
            <p className="mt-1 text-sm text-muted">support@cleepye.com</p>
          </div>
        </a>
        <div className="surface flex items-start gap-3 p-5">
          <MessageSquare className="mt-0.5 h-5 w-5 text-lime" />
          <div>
            <p className="font-medium">Response time</p>
            <p className="mt-1 text-sm text-muted">Usually within 1–2 business days</p>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="surface mt-8 space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-sm text-muted">Name</label>
          <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
        </div>
        <div>
          <label className="mb-1.5 block text-sm text-muted">Email</label>
          <input
            className="field"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm text-muted">Message</label>
          <textarea
            className="field min-h-[140px] resize-y py-3"
            required
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="How can we help?"
          />
        </div>
        <button type="submit" className="btn-primary inline-flex items-center gap-2 px-5 py-2.5">
          <Send className="h-4 w-4" /> Send message
        </button>
      </form>
    </div>
  );
}
