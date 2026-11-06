"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, ResponsiveContainer, Scatter, ComposedChart, Tooltip, XAxis, YAxis } from "recharts";
import DistrictGrid from "@/components/DistrictGrid";
import { Cell, ErrorBox, KPI, Loading } from "@/components/ui";
import { api, fmt } from "@/lib/api";

const DistrictMap = dynamic(() => import("@/components/DistrictMap"), { ssr: false, loading: () => <Loading what="Loading map" /> });

const SEGMENT_LABEL: Record<string, string> = {
  nationality_group: "Nationality group", language: "Language", age_band: "Age band", sex: "Sex", district: "District",
  housing_type: "Housing type", insurance_tier: "Insurance tier", district_x_nationality: "District × nationality (fine-grained)",
};

export default function Planner() {
  const [cmp, setCmp] = useState<any>(null);
  const [districts, setDistricts] = useState<any>(null);
  const [population, setPopulation] = useState("all");
  const [segment, setSegment] = useState("nationality_group");
  const [equity, setEquity] = useState<any>(null);
  const [cal, setCal] = useState<any>(null);
  const [view, setView] = useState<"map" | "grid">("map");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api("/planner/compare").then((r) => setCmp(r)).catch((e) => setError(e.message));
    api("/planner/calibration").then((r) => setCal(r.data)).catch(() => null);
  }, []);
  useEffect(() => {
    api(`/planner/districts?population=${population}`).then((r) => setDistricts(r)).catch((e) => setError(e.message));
  }, [population]);
  useEffect(() => {
    api(`/planner/equity?segment=${segment}&policy=both`).then((r) => setEquity(r)).catch((e) => setError(e.message));
  }, [segment]);

  if (error) return <ErrorBox error={error} />;
  if (!cmp) return <Loading what="Loading planner console" />;
  const d = cmp.data;
  const b = d.policies.baseline, w = d.policies.wiqaya;
  const rel = cal?.model_r?.reliability ?? [];
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Planner console</h1>
        <p className="text-sm text-muted">
          Run <code>{cmp.run_id}</code> · T0 {cmp.as_of} · {d.weeks} simulated weeks · {d.capacity_slots.toLocaleString()} slots, same for both policies ·
          aggregates only, cells with n &lt; 11 suppressed
        </p>
      </div>

      <section className="grid gap-3 md:grid-cols-4" aria-label="Primary endpoint">
        <KPI accent label="Completed per 100 contacts" value={`${fmt(w.completed_per_100_contacts)} vs ${fmt(b.completed_per_100_contacts)}`} sub={`Wiqaya vs baseline (primary endpoint, ${d.primary_endpoint.difference > 0 ? "+" : ""}${d.primary_endpoint.difference})`} />
        <KPI label="Gaps closed in 12 weeks" value={`${fmt(w.gaps_closed_pct)}% vs ${fmt(b.gaps_closed_pct)}%`} sub="Wiqaya vs baseline" />
        <KPI label="Missed latent cases (FN)" value={`${fmt(w.false_negative_rate_pct)}% vs ${fmt(b.false_negative_rate_pct)}%`} sub="latent condition, not reached" />
        <KPI label="People reached" value={`${fmt(w.reach_pct)}% vs ${fmt(b.reach_pct)}%`} sub="fewer people, more touches each: see trade-off" />
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Unmet need per 1,000 by district</h2>
          <div className="flex gap-2 text-sm">
            <select aria-label="Population" value={population} onChange={(e) => setPopulation(e.target.value)} className="rounded-md border border-line px-2 py-1">
              {districts && Object.entries(districts.populations as Record<string, string>).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <button className="btn-ghost" onClick={() => setView(view === "map" ? "grid" : "map")}>{view === "map" ? "Show grid" : "Show map"}</button>
          </div>
        </div>
        <p className="mb-2 text-xs text-muted">Unmet need = people with open gaps who did not get a slot in the 12-week plan. Hatched or dashed = suppressed (fewer than 11 people). Simulated cohort.</p>
        {!districts ? <Loading /> : view === "map" ? (
          <DistrictMap rows={districts.data} onTileError={() => setView("grid")} />
        ) : (
          <DistrictGrid rows={districts.data} />
        )}
        {districts && (
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-semibold">District table</summary>
            <table className="table-base mt-2">
              <thead><tr><th scope="col">District</th><th scope="col">n</th><th scope="col">Open gaps</th><th scope="col">Gaps / 1,000</th><th scope="col">Unmet / 1,000</th><th scope="col">Slots (12 w)</th><th scope="col">Need : capacity</th></tr></thead>
              <tbody>{districts.data.map((r: any) => (
                <tr key={r.district_id}><td>{r.name}</td><td><Cell v={r.n} /></td><td><Cell v={r.open_gaps} /></td><td><Cell v={r.gaps_per_1000} /></td><td><Cell v={r.unmet_need_per_1000} /></td><td><Cell v={r.slots_12w} /></td><td><Cell v={r.need_vs_capacity} /></td></tr>
              ))}</tbody>
            </table>
          </details>
        )}
      </section>

      <section className="card" aria-label="Equity">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Equity: baseline vs Wiqaya by segment</h2>
          <select aria-label="Segment" data-testid="segment-select" value={segment} onChange={(e) => setSegment(e.target.value)} className="rounded-md border border-line px-2 py-1 text-sm">
            {(equity?.segments ?? Object.keys(SEGMENT_LABEL)).map((s: string) => <option key={s} value={s}>{SEGMENT_LABEL[s] ?? s}</option>)}
          </select>
        </div>
        <p className="mb-2 text-xs text-muted">Segments are for monitoring only: nationality, language, district and insurance are never risk-model inputs. Simulated cohort.</p>
        {!equity ? <Loading /> : (
          <div className="max-h-[480px] overflow-auto">
            <table className="table-base" data-testid="equity-table">
              <thead>
                <tr>
                  <th scope="col">Segment</th><th scope="col">n</th>
                  <th scope="col">Reach % B</th><th scope="col">Reach % W</th>
                  <th scope="col">Per 100 contacts B</th><th scope="col">Per 100 contacts W</th>
                  <th scope="col">Gaps closed % B</th><th scope="col">Gaps closed % W</th>
                </tr>
              </thead>
              <tbody>
                {equity.data.map((r: any) => (
                  <tr key={r.segment}>
                    <td className="font-medium">{r.segment}</td><td><Cell v={r.n} /></td>
                    <td><Cell v={r.baseline_reach_pct} /></td><td><Cell v={r.wiqaya_reach_pct} /></td>
                    <td><Cell v={r.baseline_completed_per_100} /></td><td><Cell v={r.wiqaya_completed_per_100} /></td>
                    <td><Cell v={r.baseline_gaps_closed_pct} /></td><td><Cell v={r.wiqaya_gaps_closed_pct} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card" aria-label="Calibration">
          <h2 className="text-lg font-semibold">Calibration: Model R (held-out people)</h2>
          {cal && (
            <p className="text-xs text-muted">AUROC {fmt(cal.model_r.test.auroc, 3)} · Brier {fmt(cal.model_r.test.brier, 3)} · slope {fmt(cal.model_r.test.calibration_slope, 2)} · intercept {fmt(cal.model_r.test.calibration_intercept, 2)} · n {cal.model_r.test.n} · Simulated cohort</p>
          )}
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                <CartesianGrid stroke="#eee" />
                <XAxis type="number" dataKey="mean_predicted" domain={[0, 1]} name="Predicted" label={{ value: "Mean predicted risk", position: "bottom", fontSize: 11 }} tick={{ fontSize: 11 }} />
                <YAxis type="number" dataKey="observed_rate" domain={[0, 1]} name="Observed" tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => v.toFixed(3)} />
                <Legend verticalAlign="top" height={24} />
                <Line data={[{ mean_predicted: 0, observed_rate: 0 }, { mean_predicted: 1, observed_rate: 1 }]} dataKey="observed_rate" stroke="#C9BEB1" dot={false} name="Perfect calibration" strokeDasharray="4 4" />
                <Scatter data={rel} dataKey="observed_rate" fill="#0E6B68" name="Deciles (isotonic)" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {cal && (
            <details className="text-sm">
              <summary className="cursor-pointer font-semibold">Per-segment validation</summary>
              <table className="table-base mt-2">
                <thead><tr><th scope="col">Segment</th><th scope="col">Value</th><th scope="col">n</th><th scope="col">AUROC</th><th scope="col">Status</th></tr></thead>
                <tbody>
                  {Object.entries(cal.model_r.segments as Record<string, any[]>).flatMap(([seg, rows]) => rows.map((r) => (
                    <tr key={seg + r.segment}><td>{seg}</td><td>{r.segment}</td><td><Cell v={r.n} /></td><td><Cell v={r.auroc} /></td><td className="text-xs">{r.status}</td></tr>
                  )))}
                </tbody>
              </table>
            </details>
          )}
        </section>

        <section className="card" aria-label="Sensitivity analysis">
          <h2 className="text-lg font-semibold">Sensitivity analysis</h2>
          <p className="text-xs text-muted">Does the simulator flatter Wiqaya? Both policies were re-run with weaker or stronger response effects. Simulated cohort.</p>
          <table className="table-base mt-2" data-testid="sensitivity">
            <thead><tr><th scope="col">Scenario</th><th scope="col">Baseline /100</th><th scope="col">Wiqaya /100</th><th scope="col">Difference</th></tr></thead>
            <tbody>
              <tr><td>Main</td><td>{fmt(d.primary_endpoint.baseline)}</td><td>{fmt(d.primary_endpoint.wiqaya)}</td><td className="font-semibold">{fmt(d.primary_endpoint.difference)}</td></tr>
              {Object.entries((d.sensitivity ?? {}) as Record<string, any>).map(([k, v]) => (
                <tr key={k}><td>{k.replace("_", " ")}</td><td>{fmt(v.baseline_per_100)}</td><td>{fmt(v.wiqaya_per_100)}</td><td className="font-semibold">{fmt(v.difference)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted">
            The direction of the result holds in every scenario. The size depends on effect sizes that have not been measured in Abu Dhabi.
            Only a randomised pilot can establish them.
          </p>
        </section>
      </div>
    </div>
  );
}
