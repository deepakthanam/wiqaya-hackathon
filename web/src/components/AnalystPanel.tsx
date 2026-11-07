"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Step = { tool: string; label: string; input: Record<string, unknown>; error: string | null };
type Proposal = {
  id: string; title: string; action_type: string; district_id: string; rationale: string; expected_effect: string;
  status: "pending_approval" | "approved" | "dismissed"; decided_by: string | null;
};
type Job = {
  id: string; question: string; status: "running" | "done" | "error"; steps: Step[]; answer: string;
  proposals: Proposal[]; number_check: { checked: number; verified: number; unverified: string[] } | null;
  error: string | null; seconds: number | null; usage: Record<string, number>; model: string;
};

const SUGGESTIONS = [
  "Which districts have the most unmet need for their capacity, and where would one extra van day help most?",
  "Is any nationality or language group doing worse under Wiqaya than under the baseline?",
  "How much does the Wiqaya result depend on the simulation's assumptions?",
];

function Answer({ text }: { text: string }) {
  const lines = text.replace(/\*\*/g, "").split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1 text-sm leading-relaxed">
      {lines.map((l, i) => {
        const t = l.trim();
        if (/^(Evidence|Caveats):?$/i.test(t)) return <p key={i} className="label pt-2">{t.replace(/:$/, "")}</p>;
        if (/^[-•*]\s/.test(t)) return <p key={i} className="pl-4 -indent-3">• {t.replace(/^[-•*]\s+/, "")}</p>;
        return <p key={i}>{t.replace(/^\d+\.\s+/, "")}</p>;
      })}
    </div>
  );
}

function ProposalCard({ p, onDecide }: { p: Proposal; onDecide: (id: string, d: "approve" | "dismiss") => void }) {
  return (
    <div className="rounded-md border border-line bg-white p-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-semibold">{p.title}</p>
        <span className={`chip ${p.status === "approved" ? "bg-teal text-white" : p.status === "dismissed" ? "bg-paper text-muted border border-line" : "bg-coral-light text-ink border border-coral/40"}`}>
          {p.status === "pending_approval" ? "Needs your decision" : p.status === "approved" ? `Approved by ${p.decided_by}` : "Dismissed"}
        </span>
      </div>
      <p className="mt-1 text-muted">{p.action_type.replace(/_/g, " ")} · {p.district_id.replace(/_/g, " ")}</p>
      <p className="mt-2"><span className="font-medium">Why:</span> {p.rationale}</p>
      <p className="mt-1"><span className="font-medium">Expected effect:</span> {p.expected_effect}</p>
      {p.status === "pending_approval" && (
        <div className="mt-3 flex gap-2">
          <button className="btn-primary" onClick={() => onDecide(p.id, "approve")}>Approve</button>
          <button className="btn-ghost" onClick={() => onDecide(p.id, "dismiss")}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

export default function AnalystPanel() {
  const [status, setStatus] = useState<{ enabled: boolean; reason: string | null; model: string } | null>(null);
  const [q, setQ] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const running = jobs.some((j) => j.status === "running");

  useEffect(() => {
    api("/planner/analyst/status").then((r) => setStatus(r.data)).catch((e) => setError(e.message));
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, []);

  function poll(id: string) {
    api(`/planner/analyst/jobs/${id}`).then((r) => {
      setJobs((js) => js.map((j) => (j.id === id ? r.data : j)));
      if (r.data.status === "running") timer.current = setTimeout(() => poll(id), 1200);
    }).catch((e) => setError(e.message));
  }

  async function ask(question: string) {
    if (!question.trim() || running) return;
    setError(null);
    try {
      const r = await api("/planner/analyst/ask", { method: "POST", body: JSON.stringify({ question }) });
      setJobs((js) => [...js, r.data]);
      setQ("");
      timer.current = setTimeout(() => poll(r.data.id), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not ask the analyst");
    }
  }

  async function decide(id: string, decision: "approve" | "dismiss") {
    try {
      const r = await api(`/planner/analyst/proposals/${id}/decision`, { method: "POST", body: JSON.stringify({ decision }) });
      setJobs((js) => js.map((j) => ({ ...j, proposals: j.proposals.map((p) => (p.id === id ? r.data : p)) })));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the decision");
    }
  }

  async function reset() {
    await api("/planner/analyst/reset", { method: "POST" }).catch(() => null);
    setJobs([]);
  }

  return (
    <section className="card" aria-label="AI analyst">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Ask the AI analyst</h2>
          <p className="text-sm text-muted">
            An AI agent{status?.model ? ` (${status.model})` : ""} that looks up the planner data, runs what-if estimates
            and drafts proposals. It sees only aggregate, suppressed figures. Nothing changes until you approve. Simulated cohort.
          </p>
        </div>
        {jobs.length > 0 && !running && <button className="btn-ghost" onClick={reset}>New conversation</button>}
      </div>

      {status && !status.enabled && (
        <p className="mt-3 rounded-md border border-line bg-paper p-3 text-sm">
          The AI analyst is off. {status.reason} The rest of the console works without it.
        </p>
      )}

      {status?.enabled && (
        <>
          <div className="mt-4 space-y-5">
            {jobs.map((j) => (
              <div key={j.id} className="space-y-3">
                <p className="rounded-md bg-teal-light px-3 py-2 text-sm"><span className="font-semibold">You:</span> {j.question}</p>
                {j.steps.length > 0 && (
                  <ol className="space-y-0.5 text-xs text-muted" aria-label="Agent steps">
                    {j.steps.map((s, i) => (
                      <li key={i}>
                        {s.error ? "⚠" : "✓"} {s.label}
                        {Object.keys(s.input).length > 0 && s.tool !== "propose_action" && (
                          <span> · {Object.values(s.input).map(String).join(", ").replace(/_/g, " ")}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
                {j.status === "running" && <p className="text-sm text-muted" aria-live="polite">Analysing…</p>}
                {j.status === "error" && <p role="alert" className="text-sm text-coral">{j.error}</p>}
                {j.status === "done" && (
                  <div className="rounded-md border border-line bg-white p-4">
                    <Answer text={j.answer} />
                    {j.number_check && j.number_check.checked > 0 && (
                      <p className={`mt-3 text-xs ${j.number_check.unverified.length ? "text-coral" : "text-teal"}`}>
                        {j.number_check.unverified.length === 0
                          ? `All ${j.number_check.checked} figures match the data the agent looked up.`
                          : `${j.number_check.verified} of ${j.number_check.checked} figures match the data looked up. Not found (may be calculated by the AI, check before use): ${j.number_check.unverified.join(", ")}.`}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-muted">
                      {j.model} · {j.seconds}s · {j.steps.length} steps · Simulated cohort
                    </p>
                  </div>
                )}
                {j.proposals.length > 0 && (
                  <div className="space-y-2">
                    <p className="label">Proposals for your decision</p>
                    {j.proposals.map((p) => <ProposalCard key={p.id} p={p} onDecide={decide} />)}
                  </div>
                )}
              </div>
            ))}
          </div>

          {jobs.length === 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip border border-line bg-paper text-left hover:bg-teal-light" onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
          )}

          <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
            <label htmlFor="analyst-q" className="sr-only">Question for the AI analyst</label>
            <input
              id="analyst-q"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              maxLength={600}
              placeholder={jobs.length ? "Ask a follow-up…" : "Ask about need, capacity, equity or the results…"}
              className="flex-1 rounded-md border border-line px-3 py-2 text-sm"
              disabled={running}
            />
            <button className="btn-primary" disabled={running || q.trim().length < 3}>{running ? "Working…" : "Ask"}</button>
          </form>
        </>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-coral">{error}</p>}
    </section>
  );
}
