import { Link } from "react-router-dom";
import {
  ArrowRight,
  Captions,
  Crop,
  Download,
  FileAudio,
  Lock,
  Play,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { LogoMark } from "../components/Logo";

const STEPS = [
  {
    icon: Download,
    title: "Drop a link or file",
    body: "Paste YouTube or upload MP4/MOV. Processing stays on your machine.",
  },
  {
    icon: FileAudio,
    title: "Transcribe locally",
    body: "Whisper builds a word-level transcript — no cloud upload required.",
  },
  {
    icon: ScanSearch,
    title: "Score viral moments",
    body: "AI ranks the strongest 25–65 second stretches worth posting.",
  },
  {
    icon: Crop,
    title: "Reframe to 9:16",
    body: "Smart crop tracks the subject so clips look native on Shorts & Reels.",
  },
  {
    icon: Captions,
    title: "Burn animated captions",
    body: "Word-level styles ready for TikTok, YouTube Shorts, and Instagram.",
  },
];

const FEATURES = [
  {
    icon: Lock,
    title: "Privacy-first",
    body: "Video and transcripts stay on your device unless you opt into a cloud AI provider.",
  },
  {
    icon: Zap,
    title: "Credit-based plans",
    body: "Simple pricing: 1 credit ≈ 1 minute of source video. Free tier to try, Pro when you scale.",
  },
  {
    icon: Sparkles,
    title: "Export-ready clips",
    body: "Vertical 9:16, captions burned in, ranked by viral potential — post in minutes.",
  },
];

export default function Home() {
  useDocumentTitle();

  return (
    <div className="mx-auto max-w-6xl">
      {/* Hero */}
      <section className="relative overflow-hidden pb-16 pt-4 md:pb-24 md:pt-8">
        <div className="pointer-events-none absolute -right-20 top-0 h-72 w-72 rounded-full bg-lime/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-16 bottom-0 h-56 w-56 rounded-full bg-lime/5 blur-3xl" />

        <div className="relative grid items-center gap-12 lg:grid-cols-2">
          <div className="animate-rise">
            <p className="eyebrow mb-5 flex items-center gap-2 text-lime">
              <ShieldCheck className="h-3.5 w-3.5" />
              AI video clipper · runs locally
            </p>
            <h1
              className="font-display text-[clamp(2.5rem,6vw,4.25rem)] font-bold leading-[0.98] tracking-[-0.03em]"
              style={{ fontVariationSettings: '"wdth" 90' }}
            >
              Turn long videos into <span className="hl">viral clips</span> in minutes.
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted">
              Cleepye finds the strongest moments, reframes them to vertical, and burns in captions —
              so you can post to TikTok, Shorts, and Reels without living in a timeline editor.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/mine" className="btn-primary inline-flex items-center gap-2 px-6 py-3 text-base">
                Start mining <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/download" className="btn-ghost inline-flex items-center gap-2 border border-white/10 px-6 py-3">
                Download app
              </Link>
            </div>
            <p className="mt-4 text-xs text-dim">New accounts get 2 free credits · No card required</p>
          </div>

          {/* Product visual / how-it-works preview */}
          <div className="animate-rise [animation-delay:100ms]">
            <div className="surface relative overflow-hidden p-2">
              <div className="relative aspect-video overflow-hidden rounded-xl bg-gradient-to-br from-ink-3 to-black">
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                  <div className="grid h-16 w-16 place-items-center rounded-full border border-lime/30 bg-lime/10 text-lime">
                    <Play className="h-7 w-7 fill-current" />
                  </div>
                  <p className="text-sm font-medium text-bone">How Cleepye works</p>
                  <p className="max-w-xs px-4 text-center text-xs text-dim">
                    Short product walkthrough — drop your demo MP4 or Loom link here later.
                  </p>
                </div>
                {/* Decorative film strip */}
                <div className="absolute bottom-0 left-0 right-0 flex gap-1 p-3 opacity-40">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="h-10 flex-1 rounded-md bg-white/10" />
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between px-3 py-3">
                <div className="flex items-center gap-2">
                  <LogoMark className="h-6 w-6" />
                  <span className="text-sm font-medium">Pipeline preview</span>
                </div>
                <span className="font-mono text-[11px] text-dim">5 stages · live progress</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t py-16 md:py-20">
        <div className="mb-10 max-w-xl">
          <p className="eyebrow text-lime">Why Cleepye</p>
          <h2 className="mt-2 font-display text-3xl font-bold tracking-tight md:text-4xl">
            Built for creators who ship daily
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="surface p-6">
              <div className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-lime/20 bg-lime/10 text-lime">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="font-display text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t py-16 md:py-20">
        <div className="mb-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-xl">
            <p className="eyebrow text-lime">How it works</p>
            <h2 className="mt-2 font-display text-3xl font-bold tracking-tight md:text-4xl">
              From long-form to post-ready in five stages
            </h2>
          </div>
          <Link to="/mine" className="btn-ghost inline-flex items-center gap-2 self-start border border-white/10">
            Try it now <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <li key={title} className="surface relative p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-lime/10 text-lime">
                  <Icon className="h-4 w-4" />
                </div>
                <span className="font-mono text-[11px] text-dim">0{i + 1}</span>
              </div>
              <p className="text-sm font-semibold">{title}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* CTA */}
      <section className="border-t py-16 md:py-20">
        <div className="surface relative overflow-hidden px-6 py-12 text-center md:px-12">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-lime/10 via-transparent to-transparent" />
          <h2 className="relative font-display text-3xl font-bold tracking-tight md:text-4xl">
            Ready to clip smarter?
          </h2>
          <p className="relative mx-auto mt-3 max-w-md text-muted">
            Open the miner, drop a video, and get ranked vertical clips with captions.
          </p>
          <div className="relative mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/mine" className="btn-primary inline-flex items-center gap-2 px-6 py-3">
              New mine <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/pricing" className="btn-ghost border border-white/10 px-6 py-3">
              View pricing
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
