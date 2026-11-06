"use client";
import { useCallback, useEffect, useState } from "react";
import Phone from "@/components/Phone";
import { ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";

const LABELS: Record<string, string> = {
  wcv: "Child check-ups", developmental: "Play and growth checks", immunisation: "Vaccines", child_growth_followup: "Growth follow-up",
  adult_t2d: "Blood sugar checks", adult_bp: "Blood pressure checks", adult_lipid: "Heart-health blood tests", cervical: "Cervical screening",
  colorectal: "Bowel screening", breast: "Breast screening", followup_retest: "Repeat checks", household_bundle: "Family check-up days",
  mobile_van: "Health van", cascade_family: "Family heart-health check",
};

export default function Family() {
  const [session, setSession] = useState<any>(null);
  const [msgs, setMsgs] = useState<any>(null);
  const [prefs, setPrefs] = useState<any>(null);
  const [who, setWho] = useState<string>("");
  const [order, setOrder] = useState<string[]>(["whatsapp", "sms", "call_script"]);
  const [optOut, setOptOut] = useState<string[]>([]);
  const [later, setLater] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((hid: string) => {
    api(`/family/${hid}/messages`).then((r) => {
      setMsgs(r);
      setWho((w) => w || r.data[0]?.recipient_id || r.members[0]?.person_id);
    }).catch((e) => setError(e.message));
    api(`/family/${hid}/preferences`).then((r) => setPrefs(r)).catch(() => null);
  }, []);
  useEffect(() => {
    api("/session").then((s) => { setSession(s); load(s.household_id); }).catch((e) => setError(e.message));
  }, [load]);

  async function save() {
    try {
      const r = await api(`/family/${who}/preferences`, {
        method: "POST",
        body: JSON.stringify({ channel_order: order, opt_out_pathways: optOut, remind_later_until: later || null, decline_reason: reason || null }),
      });
      setConfirm(r.confirmation);
      load(session.household_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!msgs) return <Loading what="Loading your messages" />;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Messages to household {msgs.household_id}</h1>
        <p className="text-sm text-muted">What the family receives, exactly as sent. Cascade messages appear only after a clinician signs off, and never name a relative or a condition. Simulated cohort.</p>
      </div>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {msgs.data.length === 0 && <p className="card text-sm text-muted">No messages for this household right now.</p>}
        {msgs.data.map((m: any, i: number) => (
          <div key={i}>
            <p className="mb-1 text-sm"><strong>{m.to}</strong> · {LABELS[m.pathway] ?? m.pathway}{m.household_bundled ? " · one visit day for the family" : ""}</p>
            <Phone m={m} />
          </div>
        ))}
      </div>

      <section className="card max-w-2xl" aria-label="Preference centre">
        <h2 className="text-lg font-semibold">Preference centre</h2>
        <label className="mt-2 block text-sm">
          Preferences for
          <select value={who} onChange={(e) => setWho(e.target.value)} className="ml-2 rounded-md border border-line px-2 py-1">
            {msgs.members.map((m: any) => <option key={m.person_id} value={m.person_id}>{m.given}</option>)}
          </select>
        </label>
        <fieldset className="mt-3">
          <legend className="label">Contact me by (in this order)</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {order.map((c, i) => (
              <span key={c} className="chip border border-line bg-paper">
                {i + 1}. {c.replace("_script", "")}
                {i > 0 && <button aria-label={`Move ${c} up`} className="ml-1 text-teal" onClick={() => { const o = [...order]; [o[i - 1], o[i]] = [o[i], o[i - 1]]; setOrder(o); }}>↑</button>}
              </span>
            ))}
          </div>
        </fieldset>
        <fieldset className="mt-3">
          <legend className="label">Stop reminders about</legend>
          <div className="mt-1 grid grid-cols-2 gap-1 text-sm">
            {(prefs?.pathways ?? []).map((p: string) => (
              <label key={p} className="flex items-center gap-2">
                <input type="checkbox" checked={optOut.includes(p)} onChange={(e) => setOptOut(e.target.checked ? [...optOut, p] : optOut.filter((x) => x !== p))} />
                {LABELS[p] ?? p}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Remind me later, after
            <input type="date" value={later} onChange={(e) => setLater(e.target.value)} className="mt-1 block w-full rounded-md border border-line px-2 py-1" />
          </label>
          <label className="text-sm">Reason for declining (optional)
            <input value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 block w-full rounded-md border border-line px-2 py-1" placeholder="e.g. already done elsewhere" />
          </label>
        </div>
        <button className="btn-primary mt-4" onClick={save}>Save preferences</button>
        {confirm && (
          <div className="mt-4">
            <p className="label mb-1">Confirmation sent</p>
            <Phone m={confirm} />
          </div>
        )}
        <p className="mt-3 text-xs text-muted">Saved to this guest session only and reset after 2 hours. Declining a pathway stops outreach for that pathway and does not change your care.</p>
      </section>
    </div>
  );
}
