"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ErrorBox, Loading } from "@/components/ui";
import { api, fmt } from "@/lib/api";

const TABS = [
  ["rules", "Rule library"],
  ["translations", "Translations"],
  ["provenance", "Provenance"],
  ["model", "Model card"],
  ["audit", "Audit log"],
  ["config", "Config (read-only)"],
] as const;

export default function Admin() {
  const [tab, setTab] = useState<string>("rules");
  const [data, setData] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab");
    if (q) setTab(q);
  }, []);
  useEffect(() => {
    const path: Record<string, string> = { rules: "/admin/rules", translations: "/admin/rules", provenance: "/admin/provenance", model: "/admin/model-card", audit: "/admin/audit?limit=200", config: "/admin/config" };
    setError(null);
    api(path[tab]).then((r) => setData((d) => ({ ...d, [tab]: r }))).catch((e) => setError(e.message));
  }, [tab]);

  const r = data[tab];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Administration</h1>
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`-mb-px rounded-t-md px-3 py-2 text-sm ${tab === k ? "border border-b-white border-line bg-white font-semibold text-teal" : "text-muted hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </div>
      {error ? <ErrorBox error={error} /> : !r ? <Loading /> : (
        <>
          {tab === "rules" && (
            <div className="overflow-x-auto rounded-lg border border-line bg-white">
              <table className="table-base" data-testid="rules-table">
                <thead><tr><th scope="col">Rule</th><th scope="col">Pathway</th><th scope="col">Source</th><th scope="col">Verification</th><th scope="col">Status</th><th scope="col">Open gaps</th></tr></thead>
                <tbody>{r.data.map((x: any) => (
                  <tr key={x.id}>
                    <td><div className="font-medium">{x.title}</div><code className="text-xs text-muted">{x.ref}</code>{x.requires_clinician && <div className="chip mt-1 bg-coral-light text-coral">clinician task</div>}</td>
                    <td className="text-xs">{x.pathway} · {x.kind}</td>
                    <td className="max-w-sm text-xs"><a className="text-teal underline" href={x.source.url} target="_blank" rel="noreferrer">{x.source.name}</a> ({x.source.year})<div className="text-muted">{x.source.licence}</div>{x.source.verification_url && <a className="text-muted underline" href={x.source.verification_url} target="_blank" rel="noreferrer">verification copy</a>}</td>
                    <td className="text-xs"><span className={`chip ${x.verification_state === "verified" ? "bg-teal-light text-teal" : "bg-coral text-white"}`}>{x.verification_state}</span><div className="text-muted">retrieved {x.source.retrieved_on} · HTTP {x.source.http_status}</div></td>
                    <td className="text-xs">{x.status.replaceAll("_", " ")}{x.assumptions.length > 0 && <details><summary className="cursor-pointer text-coral">{x.assumptions.length} assumption(s)</summary>{x.assumptions.map((a: string) => <p key={a}>• {a}</p>)}</details>}</td>
                    <td className="text-right">{fmt(x.open_gaps)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {tab === "translations" && (
            <div className="card">
              <p className="text-sm">{r.translation_note}</p>
              <table className="table-base mt-3 max-w-lg">
                <thead><tr><th scope="col">Language</th><th scope="col">Source</th><th scope="col">Machine draft</th><th scope="col">Native reviewed</th></tr></thead>
                <tbody>{Object.entries(r.translations as Record<string, any>).map(([lang, c]) => (
                  <tr key={lang}><td>{lang}</td><td>{c.source ?? 0}</td><td className={c.machine_draft ? "font-semibold text-coral" : ""}>{c.machine_draft ?? 0}{c.machine_draft ? " · needs review" : ""}</td><td>{c.native_reviewed ?? 0}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {tab === "provenance" && (
            <div>
              <p className="card mb-3 border-teal text-sm font-semibold" data-testid="provenance-statement">{r.statement}</p>
              <div className="overflow-x-auto rounded-lg border border-line bg-white">
                <table className="table-base">
                  <thead><tr><th scope="col">Source</th><th scope="col">Type</th><th scope="col">Owner</th><th scope="col">Licence</th><th scope="col">Personal data</th><th scope="col">Use</th><th scope="col">Retrieved</th></tr></thead>
                  <tbody>{r.data.map((x: any) => (
                    <tr key={x.source}><td className="font-medium">{x.source}</td><td className="text-xs">{x.type}</td><td className="text-xs">{x.owner}</td><td className="text-xs">{x.licence}</td><td>{x.personal_data}</td><td className="text-xs">{x.use}</td><td className="text-xs">{x.retrieved_on}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
          {tab === "model" && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="card">
                <h2 className="font-semibold">Held-out performance (Simulated cohort)</h2>
                {(["model_r", "model_n"] as const).map((k) => (
                  <div key={k} className="mt-2 text-sm">
                    <strong>{k === "model_r" ? "Model R – risk elevation" : "Model N – no-show"}</strong>: AUROC {fmt(r.data[k].test_calibrated?.auroc, 3)} · Brier {fmt(r.data[k].test_calibrated?.brier, 3)} · calibration slope {fmt(r.data[k].test_calibrated?.calibration_slope, 2)} · test n {r.data[k].n_test}
                    <div className="text-xs text-muted">Label: {r.data[k].label}</div>
                  </div>
                ))}
                <p className="mt-3 text-sm"><strong>Features (Model R):</strong> {r.data.features_r?.join(", ")}</p>
                <p className="mt-1 text-sm"><strong>Excluded:</strong> {r.data.excluded_from_model_r?.join(", ")} (monitoring segments only)</p>
                <p className="mt-1 text-sm"><strong>Capacity fit:</strong> {r.data.fit?.method} · {r.data.fit?.status}</p>
                <p className="mt-1 text-sm"><strong>Fairness floor adjustments:</strong> {r.data.fairness?.adjustments}</p>
              </div>
              <div className="card prose prose-sm max-w-none text-sm">
                {r.data.markdown ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.data.markdown}</ReactMarkdown> : <p>MODEL_CARD.md not found.</p>}
              </div>
            </div>
          )}
          {tab === "audit" && (
            <div className="overflow-x-auto rounded-lg border border-line bg-white">
              <table className="table-base" data-testid="audit-table">
                <thead><tr><th scope="col">Time (UTC)</th><th scope="col">Role</th><th scope="col">Session</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Fields read</th></tr></thead>
                <tbody>{r.data.map((x: any, i: number) => (
                  <tr key={i}><td className="text-xs">{x.ts}</td><td>{x.actor_role}</td><td className="text-xs">{x.session}</td><td>{x.action}</td><td className="text-xs">{x.entity}/{x.entity_id}</td><td className="text-xs">{x.fields_read.join(", ")}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {tab === "config" && (
            <pre className="card overflow-x-auto text-xs">{JSON.stringify(r.data, null, 2)}</pre>
          )}
        </>
      )}
    </div>
  );
}
