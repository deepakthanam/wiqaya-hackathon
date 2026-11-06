"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import FamilyGraph from "@/components/FamilyGraph";
import Phone from "@/components/Phone";
import { Band, Disclaimer, ErrorBox, Loading, Status } from "@/components/ui";
import { api, fmt } from "@/lib/api";

type Person = any;

const LANGS = ["en", "ar", "ur", "hi", "ml", "tl"];
const CHANNELS = ["whatsapp", "sms", "call_script", "chw_script"];

function GapCard({ g }: { g: any }) {
  const ev = Object.entries(g.evidence as Record<string, unknown>).filter(([k]) => !["index_person_ids", "index_reasons"].includes(k));
  return (
    <article className={`card ${g.requires_clinician ? "border-coral" : ""}`} data-testid="gap-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{g.title}</h3>
          <code className="text-xs text-muted">{g.rule_ref}</code>
        </div>
        <div className="text-right text-sm">
          <Status status={g.status} />
          <div className="text-xs text-muted">due {g.due_date}{g.days_overdue > 0 ? ` · ${g.days_overdue} days overdue` : ""}</div>
        </div>
      </div>
      <p className="mt-2 text-xs">
        Source:{" "}
        <a href={g.source.url} target="_blank" rel="noreferrer" className="text-teal underline">
          {g.source.name} ({g.source.year})
        </a>{" "}
        · retrieved {g.source.retrieved_on} · {g.source.verified ? "verified" : <span className="text-coral">unverified source</span>}
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        {ev.map(([k, v]) => (
          <div key={k}>
            <dt className="text-muted">{k.replaceAll("_", " ")}</dt>
            <dd className="font-medium">{Array.isArray(v) ? (v.length ? v.join(", ") : "none") : typeof v === "object" && v ? JSON.stringify(v) : fmt(v, 2)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-muted">Fields read: {g.fields_read.join(", ")} · {g.rule_status.replaceAll("_", " ")}</p>
      {g.requires_clinician && (
        <p className="mt-2 rounded bg-coral-light p-2 text-xs text-coral">
          Clinician task. Never auto-contacts. Outreach only after clinician approval and the index person&apos;s consent to share.
        </p>
      )}
    </article>
  );
}

function PriorityBars({ flag }: { flag: any }) {
  const comps: [string, string][] = [["risk", "Clinical risk"], ["time_sensitivity", "Time sensitivity"], ["no_show", "No-show risk"], ["household_bundle", "Household bundle"]];
  return (
    <div className="space-y-2">
      {comps.map(([k, label]) => {
        const v = flag.components[k] ?? 0, w = flag.weights[k] ?? 0;
        return (
          <div key={k}>
            <div className="flex justify-between text-xs"><span>{label} <span className="text-muted">× weight {w}</span></span><span className="tabular-nums">{fmt(v, 2)}</span></div>
            <div className="h-2 rounded bg-paper"><div className="h-2 rounded bg-teal" style={{ width: `${Math.round(v * 100)}%` }} /></div>
          </div>
        );
      })}
      <p className="text-xs text-muted">Risk component: {flag.risk_note}{flag.risk_calibrated != null ? ` (calibrated probability ${fmt(flag.risk_calibrated, 3)})` : ""}.</p>
    </div>
  );
}

export default function PersonPage({ params }: { params: { id: string } }) {
  const [p, setP] = useState<Person | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<any>(null);
  const [channel, setChannel] = useState<string>("");
  const [lang, setLang] = useState<string>("");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [hh, setHh] = useState<any>(null);

  const load = useCallback(() => {
    api(`/people/${params.id}`).then((r) => setP(r.data)).catch((e) => setError(e.message));
  }, [params.id]);
  useEffect(load, [load]);
  useEffect(() => {
    if (p?.household_id) api(`/households/${p.household_id}`).then((r) => setHh(r.data)).catch(() => setHh(null));
  }, [p?.household_id]);
  useEffect(() => {
    if (!p?.flag) return;
    api("/outreach/preview", { method: "POST", body: JSON.stringify({ flag_id: p.flag.flag_id, channel: channel || null, language: lang || null }) })
      .then((r) => setMsg(r.data))
      .catch((e) => setMsg({ error: e.message }));
  }, [p, channel, lang, saved]);

  async function decide(decision: string) {
    setSaved(null);
    try {
      await api(`/flags/${p.flag.flag_id}/decision`, { method: "POST", body: JSON.stringify({ decision, note }) });
      setSaved(`Saved: ${decision}`);
      load();
    } catch (e) {
      setSaved(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!p) return <Loading what="Loading record" />;
  const f = p.flag;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/coordinator" className="text-sm text-teal hover:underline">← Worklist</Link>
          <h1 className="text-2xl font-bold">{p.name}</h1>
          <p className="text-sm text-muted">
            {p.age} y · {p.sex} · {p.nationality_group.replace("_", " ")} · prefers <strong>{p.preferred_language}</strong> · {p.phone_type} phone ·{" "}
            <Link href={`/households/${p.household_id}`} className="underline">{p.household_id}</Link> ({p.housing_type.replace("_", " ")}) · {p.assigned_clinic}
          </p>
        </div>
        {f && (
          <div className="text-right">
            <div className="label">Priority rank</div>
            <div className="text-3xl font-bold text-teal">#{f.rank}</div>
            <Band band={f.band} />
          </div>
        )}
      </div>
      <Disclaimer />
      {p.fhir_banner ? (
        <p className="rounded-md border border-line bg-white px-3 py-2 text-xs text-muted" data-testid="fhir-banner">ⓘ {p.fhir_banner} ({p.data_source})</p>
      ) : (
        <p className="text-xs text-muted">Record read from the FHIR store: {p.fhir?.resource} (version {p.fhir?.versionId})</p>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2" aria-label="Care gaps">
          <h2 className="text-lg font-semibold">Care gaps ({p.gaps.length})</h2>
          {p.gaps.length === 0 && <p className="card text-sm text-muted">No open gaps for this person.</p>}
          {p.gaps.map((g: any) => <GapCard key={g.gap_id} g={g} />)}
          {p.cascade_index && (
            <div className="card border-coral" data-testid="cascade-index">
              <h3 className="font-semibold">Index case for family cascade</h3>
              <p className="text-sm">This record created <strong>{p.cascade_index.tasks_created}</strong> cascade clinician task(s) for consented first-degree relatives:{" "}
                {p.cascade_index.relatives.map((r: string) => <Link key={r} href={`/people/${r}`} className="mr-2 text-teal underline">{r}</Link>)}
              </p>
              <p className="mt-1 text-xs text-muted">Relatives are never told this person&apos;s diagnosis.</p>
            </div>
          )}
          {Array.isArray(p.genomic) ? (
            <div className="card" data-testid="genomic">
              <h3 className="font-semibold">Genome programme findings <span className="chip ml-1 bg-coral-light text-coral">clinician/admin only</span></h3>
              {p.genomic.length === 0 ? <p className="text-sm text-muted">None.</p> : p.genomic.map((x: any, i: number) => (
                <p key={i} className="mt-1 text-sm"><strong>{x.gene}</strong> · {x.classification.replace("_", " ")} · {x.variant} · consent {x.consent}<br /><span className="text-xs text-muted">{x.note}</span></p>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted">Genomic information: {p.genomic}</p>
          )}
          <div className="card">
            <h3 className="mb-2 font-semibold">Family graph (consent-filtered)</h3>
            <FamilyGraph personId={p.person_id} />
          </div>
        </section>

        <aside className="space-y-4" aria-label="Priority and outreach">
          {f ? (
            <>
              <div className="card">
                <h2 className="font-semibold">Why this rank</h2>
                <p className="mt-1 text-xs text-muted">1. Rule citation (see the gap cards). 2. Model drivers:</p>
                <ul className="mt-2 space-y-1 text-sm" data-testid="shap-phrases">
                  {f.shap_top3.length ? f.shap_top3.map((s: any) => <li key={s.feature}>• {s.phrase}</li>) : <li className="text-muted">No model score (child or no adult features): ranked by rule time sensitivity.</li>}
                </ul>
                <div className="mt-3"><PriorityBars flag={f} /></div>
                {f.fairness_adjusted && <p className="mt-2 text-xs text-coral">Position adjusted by the fairness floor (logged).</p>}
              </div>
              <div className="card">
                <h2 className="font-semibold">Slot</h2>
                <p className="text-sm">{f.slot.date ? <>{f.slot.date} at {f.slot.time}<br /><span className="text-muted">{f.slot.site}</span></> : "Waitlist (no slot within capacity yet)"}</p>
                <p className="mt-1 text-xs text-muted">Contact: {f.contact.reason} · channels {f.contact.channels.join(" → ") || "none consented"} · {f.contact.language}</p>
              </div>
              <div className="card">
                <h2 className="font-semibold">Human review</h2>
                <p className="text-xs text-muted">Current: <strong className="capitalize">{f.decision.decision}</strong>{f.decision.by ? ` by ${f.decision.by}` : ""}</p>
                <textarea aria-label="Reason or note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason (required to change or reject)" className="mt-2 w-full rounded-md border border-line p-2 text-sm" rows={2} />
                <div className="mt-2 flex flex-wrap gap-2">
                  <button data-testid="accept" className="btn-primary" onClick={() => decide("accepted")}>{f.requires_clinician ? "Clinician sign-off" : "Accept"}</button>
                  <button className="btn-ghost" onClick={() => decide("changed")}>Change</button>
                  <button className="btn-coral" onClick={() => decide("rejected")}>Reject</button>
                </div>
                {saved && <p className="mt-2 text-sm" role="status" data-testid="decision-status">{saved}</p>}
              </div>
              <div className="card">
                <h2 className="font-semibold">Message preview</h2>
                <div className="my-2 flex gap-2 text-sm">
                  <select aria-label="Channel" value={channel} onChange={(e) => setChannel(e.target.value)} className="rounded-md border border-line px-2 py-1">
                    <option value="">Planned channel</option>
                    {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} className="rounded-md border border-line px-2 py-1">
                    <option value="">Preferred language</option>
                    {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                </div>
                {!msg ? <Loading what="Rendering" /> : msg.error ? <p className="text-sm text-coral">{msg.error}</p> : (
                  <>
                    <p className={`mb-2 rounded px-2 py-1 text-xs ${msg.status.startsWith("blocked") ? "bg-coral-light text-coral" : "bg-teal-light text-teal"}`} data-testid="preview-status">
                      {msg.status.replaceAll("_", " ")}
                    </p>
                    <Phone m={msg} />
                    <p className="mt-2 text-xs text-muted">Template {msg.template_id} · {msg.pathway} · {msg.audience}{msg.household_bundled ? ` · bundled: ${msg.bundled_members.join(", ")}` : ""}</p>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="card text-sm text-muted">No flag: this person has no open gaps.</div>
          )}
          {hh && (
            <div className="card">
              <h2 className="font-semibold">Household</h2>
              {hh.bundle && <p className="mt-1 rounded bg-teal-light p-2 text-xs text-teal" data-testid="bundle">{hh.bundle.suggestion}</p>}
              <ul className="mt-2 space-y-1 text-sm">
                {hh.members.map((m: any) => (
                  <li key={m.person_id}>
                    <Link href={`/people/${m.person_id}`} className={m.person_id === p.person_id ? "font-semibold" : "text-teal underline"}>{m.name}</Link>
                    <span className="text-xs text-muted"> · {m.age} y · {m.gaps.length ? m.gaps.map((g: any) => g.title).join("; ") : "no gaps"}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
