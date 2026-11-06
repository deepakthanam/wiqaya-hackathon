"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Disclaimer, ErrorBox, Loading, Status } from "@/components/ui";
import { api } from "@/lib/api";

export default function HouseholdPage({ params }: { params: { id: string } }) {
  const [h, setH] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api(`/households/${params.id}`).then((r) => setH(r.data)).catch((e) => setError(e.message));
  }, [params.id]);
  if (error) return <ErrorBox error={error} />;
  if (!h) return <Loading />;
  return (
    <div className="space-y-4">
      <Link href="/coordinator" className="text-sm text-teal hover:underline">← Worklist</Link>
      <h1 className="text-2xl font-bold">Household {h.household_id}</h1>
      <p className="text-sm text-muted">{h.district_id.replaceAll("_", " ")} · {h.housing_type.replace("_", " ")} · household language {h.primary_language}</p>
      <Disclaimer />
      {h.bundle && <p className="card border-teal text-sm" data-testid="bundle">{h.bundle.suggestion}</p>}
      <table className="table-base rounded-lg border border-line bg-white">
        <thead><tr><th scope="col">Member</th><th scope="col">Age</th><th scope="col">Open gaps</th><th scope="col">Rank</th><th scope="col">Slot</th></tr></thead>
        <tbody>
          {h.members.map((m: any) => (
            <tr key={m.person_id}>
              <td><Link className="text-teal underline" href={`/people/${m.person_id}`}>{m.name}</Link><div className="text-xs text-muted">{m.role}</div></td>
              <td>{m.age}</td>
              <td className="text-xs">{m.gaps.length ? m.gaps.map((g: any) => <div key={g.rule_ref}>{g.title} · <Status status={g.status} /></div>) : <span className="text-muted">none</span>}</td>
              <td>{m.rank ?? "–"}</td>
              <td className="text-xs">{m.slot?.date ? `${m.slot.date} ${m.slot.time} · ${m.slot.site}` : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
