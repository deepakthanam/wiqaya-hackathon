"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Band, Disclaimer, ErrorBox, Loading, Status } from "@/components/ui";
import { api, PATHWAY_LABEL } from "@/lib/api";

type Row = {
  rank: number;
  flag_id: string;
  person_id: string;
  person: string;
  age: number;
  sex: string;
  household_id: string;
  pathway: string;
  gap_status: string;
  days_overdue: number;
  n_gaps: number;
  priority_band: string;
  top_reason: string;
  requires_clinician: boolean;
  slot: { site: string; date: string; time: string } | null;
  slot_status: string;
  decision: string;
  fairness_adjusted: boolean;
};

export default function Worklist() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; clinics: { id: string; name: string }[]; pathways: string[] } | null>(null);
  const [clinic, setClinic] = useState("");
  const [pathway, setPathway] = useState("");
  const [band, setBand] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams({ page: String(page), page_size: "50" });
    if (clinic) q.set("clinic_id", clinic);
    if (pathway) q.set("pathway", pathway);
    if (band) q.set("band", band);
    setRows(null);
    api(`/worklist?${q}`)
      .then((r) => {
        setRows(r.data);
        setMeta({ total: r.total, clinics: r.clinics, pathways: r.pathways });
      })
      .catch((e) => setError(e.message));
  }, [clinic, pathway, band, page]);

  if (error) return <ErrorBox error={error} />;
  const pages = meta ? Math.ceil(meta.total / 50) : 1;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Coordinator worklist</h1>
          <p className="text-sm text-muted">
            {meta ? `${meta.total.toLocaleString()} people with open gaps` : "…"} · ranked by priority (risk, time
            sensitivity, no-show risk, household bundle) after the fairness floor
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <select aria-label="Clinic" value={clinic} onChange={(e) => { setPage(1); setClinic(e.target.value); }} className="rounded-md border border-line bg-white px-2 py-1.5">
            <option value="">All clinics</option>
            {meta?.clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select aria-label="Pathway" value={pathway} onChange={(e) => { setPage(1); setPathway(e.target.value); }} className="rounded-md border border-line bg-white px-2 py-1.5">
            <option value="">All pathways</option>
            {meta?.pathways.map((p) => <option key={p} value={p}>{PATHWAY_LABEL[p] ?? p}</option>)}
          </select>
          <select aria-label="Priority band" value={band} onChange={(e) => { setPage(1); setBand(e.target.value); }} className="rounded-md border border-line bg-white px-2 py-1.5">
            <option value="">All bands</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>
      <Disclaimer />
      {!rows ? (
        <Loading what="Loading worklist" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white">
          <table className="table-base" data-testid="worklist">
            <caption className="sr-only">Ranked outreach worklist</caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Person</th>
                <th scope="col">Pathway</th>
                <th scope="col">Gap status</th>
                <th scope="col" className="text-right">Days overdue</th>
                <th scope="col">Priority</th>
                <th scope="col">Top reason (rule)</th>
                <th scope="col">Slot</th>
                <th scope="col">Review</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.flag_id} className="hover:bg-paper" data-person={r.person_id}>
                  <td className="font-semibold">{r.rank}</td>
                  <td>
                    <Link href={`/people/${r.person_id}`} className="font-medium text-teal underline-offset-2 hover:underline">
                      {r.person}
                    </Link>
                    <div className="text-xs text-muted">
                      {r.age} y · {r.sex === "female" ? "F" : "M"} · <Link className="hover:underline" href={`/households/${r.household_id}`}>{r.household_id}</Link>
                    </div>
                  </td>
                  <td>
                    {PATHWAY_LABEL[r.pathway] ?? r.pathway}
                    {r.n_gaps > 1 && <span className="ml-1 text-xs text-muted">+{r.n_gaps - 1}</span>}
                    {r.requires_clinician && <div className="chip mt-1 bg-coral-light text-coral">clinician sign-off</div>}
                  </td>
                  <td><Status status={r.gap_status} /></td>
                  <td className="text-right tabular-nums" title={`${r.days_overdue} days`}>{r.days_overdue > 730 ? "> 2 years" : r.days_overdue > 0 ? r.days_overdue : "–"}</td>
                  <td>
                    <Band band={r.priority_band} />
                    {r.fairness_adjusted && <div className="mt-1 text-xs text-muted" title="Moved by the fairness floor">fairness floor</div>}
                  </td>
                  <td className="max-w-xs text-xs">{r.top_reason}</td>
                  <td className="text-xs">
                    {r.slot ? (
                      <>
                        <div>{r.slot.date} {r.slot.time}</div>
                        <div className="text-muted">{r.slot.site}</div>
                      </>
                    ) : (
                      <span className="text-muted">waitlist</span>
                    )}
                  </td>
                  <td className="text-xs capitalize">{r.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex items-center justify-end gap-2 text-sm">
        <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {pages.toLocaleString()}</span>
        <button className="btn-ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
