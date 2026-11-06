"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ROLE_HOME, startGuest, type Role } from "@/lib/api";

const ROLES: { role: Role; title: string; text: string }[] = [
  { role: "coordinator", title: "Care coordinator", text: "Ranked worklist, person and household detail, review decisions, message previews." },
  { role: "clinician", title: "Clinician", text: "Everything a coordinator sees, plus genomic detail and sign-off of family cascade tasks." },
  { role: "planner", title: "Health-authority planner", text: "Aggregate, small-cell-suppressed population metrics, equity and calibration." },
  { role: "family", title: "Family member", text: "The messages the Al-Hammadi household receives, and the preference centre." },
  { role: "admin", title: "Administrator", text: "Rule library with sources, provenance register, model card, audit log." },
];

export default function Landing() {
  const router = useRouter();
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function go(role: Role) {
    setBusy(role);
    setError(null);
    try {
      await startGuest(role);
      router.push(ROLE_HOME[role]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start a guest session.");
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-10 py-6 md:grid-cols-2">
      <section>
        <p className="label">Future Health Challenge · Population Health 04</p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight text-ink">
          Find who is due. <span className="text-teal">Reach them the right way.</span>
        </h1>
        <p className="mt-4 text-lg text-muted">
          Wiqaya runs every record against versioned, cited screening and immunisation rules. It finds hidden risk
          through family links and past results, and ranks outreach to fit real clinic capacity. It explains every flag
          and measures equity.
        </p>
        <p className="mt-4 rounded-md border border-coral/40 bg-coral-light p-3 text-sm text-ink">
          <strong>Population prioritisation, not a clinical decision.</strong> Wiqaya only reorders outreach. It never
          diagnoses or changes a clinical pathway. Every person in this prototype is synthetic.
        </p>
        <ul className="mt-6 grid grid-cols-2 gap-3 text-sm">
          {[
            ["15 rules", "every one cited, versioned and verified"],
            ["6 languages", "WhatsApp, SMS, call and CHW scripts"],
            ["20,000 people", "synthetic, household-first cohort"],
            ["n < 11", "cells suppressed on every aggregate"],
          ].map(([a, b]) => (
            <li key={a} className="card">
              <div className="text-lg font-bold text-teal">{a}</div>
              <div className="text-muted">{b}</div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card self-start p-6" aria-label="Sign in">
        <h2 className="text-xl font-semibold">Sign in</h2>
        <form className="mt-4 space-y-3" onSubmit={(e) => e.preventDefault()}>
          <label className="block text-sm">
            Email
            <input disabled className="mt-1 w-full rounded-md border border-line bg-paper px-3 py-2" placeholder="name@health.example" />
          </label>
          <label className="block text-sm">
            Password
            <input disabled type="password" className="mt-1 w-full rounded-md border border-line bg-paper px-3 py-2" />
          </label>
          <p className="text-xs text-muted">Prototype: use guest access. No accounts or credentials exist.</p>
        </form>
        {!picking ? (
          <button data-testid="continue-guest" className="btn-primary mt-4 w-full justify-center py-2.5 text-base" onClick={() => setPicking(true)}>
            Continue as Guest
          </button>
        ) : (
          <div className="mt-4 space-y-2" role="group" aria-label="Choose a role">
            <p className="label">Choose a role</p>
            {ROLES.map((r) => (
              <button
                key={r.role}
                data-testid={`role-${r.role}`}
                onClick={() => go(r.role)}
                disabled={busy !== null}
                className="w-full rounded-md border border-line p-3 text-left hover:border-teal hover:bg-teal-light focus:outline-none focus-visible:ring-2 focus-visible:ring-teal"
              >
                <div className="font-semibold">{busy === r.role ? "Starting…" : r.title}</div>
                <div className="text-sm text-muted">{r.text}</div>
              </button>
            ))}
            {error && <p className="text-sm text-coral">{error}</p>}
          </div>
        )}
      </section>
    </div>
  );
}
