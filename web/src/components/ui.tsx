"use client";
import { isSuppressed } from "@/lib/api";

export function Disclaimer() {
  return (
    <div role="note" className="mb-4 rounded-md border border-coral/40 bg-coral-light px-4 py-2 text-sm">
      <strong>Population prioritisation, not a clinical decision.</strong> Ranking changes the order and intensity of
      outreach only. Every guideline-due gap stays on the list. <span className="font-semibold">Simulated cohort.</span>
    </div>
  );
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <p className="py-8 text-center text-muted" aria-live="polite">{what}…</p>;
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div role="alert" className="rounded-md border border-coral bg-coral-light p-4 text-sm">
      {error}{" "}
      {error.toLowerCase().includes("session") && (
        <a className="underline" href="/">
          Start a guest session
        </a>
      )}
    </div>
  );
}

const BAND: Record<string, string> = {
  high: "bg-coral text-white",
  medium: "bg-[#E9D8B7] text-ink",
  low: "bg-paper text-muted border border-line",
};

export function Band({ band }: { band: string }) {
  return <span className={`chip ${BAND[band] ?? ""}`}>{band}</span>;
}

const STATUS: Record<string, string> = {
  overdue: "text-coral",
  followup_overdue: "text-coral",
  missed: "text-coral",
  due: "text-teal",
  eligible_early: "text-teal",
};

export function Status({ status }: { status: string }) {
  return <span className={`font-medium ${STATUS[status] ?? ""}`}>{status.replace("_", " ")}</span>;
}

export function Cell({ v, suffix = "" }: { v: unknown; suffix?: string }) {
  if (isSuppressed(v)) {
    return (
      <span data-testid="suppressed-cell" className="suppressed block rounded px-1" title="Fewer than 11 people: hidden to protect privacy">
        suppressed (n&lt;11)
      </span>
    );
  }
  if (v === null || v === undefined) return <span className="text-muted">–</span>;
  return (
    <span>
      {typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(1)) : String(v)}
      {suffix}
    </span>
  );
}

export function KPI({ label, value, sub, accent = false }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className={`card ${accent ? "border-teal" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="label">{label}</div>
        <span className="chip shrink-0 whitespace-nowrap bg-coral-light text-[10px] text-coral" data-testid="kpi-simulated">
          Simulated cohort
        </span>
      </div>
      <div className={`mt-2 text-3xl font-bold ${accent ? "text-teal" : ""}`}>{value}</div>
      {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
    </div>
  );
}
