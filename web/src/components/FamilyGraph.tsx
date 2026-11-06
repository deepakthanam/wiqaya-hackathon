"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Node = { id: string; label: string; age: number; sex: string; same_household: boolean; has_open_gaps: boolean; cascade_task: boolean; is_index?: boolean };
type Edge = { source: string; target: string; type: string };

// Simple radial SVG layout: centre person, first ring = direct links, second ring = the rest.
export default function FamilyGraph({ personId }: { personId: string }) {
  const [g, setG] = useState<{ nodes: Node[]; edges: Edge[]; in_graph: boolean; excluded_links: { relationship: string }[]; consent_note: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api(`/family-graph/${personId}?depth=2`).then((r) => setG(r.data)).catch((e) => setError(e.message));
  }, [personId]);
  if (error) return <p className="text-sm text-coral">{error}</p>;
  if (!g) return <p className="text-sm text-muted">Loading family graph…</p>;

  const SHOWN = new Set(["mother", "father", "child", "sibling", "spouse"]);
  const edges = g.edges.filter((e) => SHOWN.has(e.type));
  const W = 520, H = 340, cx = W / 2, cy = H / 2;
  const direct = new Set(edges.filter((e) => e.source === personId || e.target === personId).flatMap((e) => [e.source, e.target]));
  direct.delete(personId);
  const ring1 = g.nodes.filter((n) => direct.has(n.id));
  const ring2 = g.nodes.filter((n) => n.id !== personId && !direct.has(n.id));
  const pos: Record<string, [number, number]> = { [personId]: [cx, cy] };
  ring1.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(ring1.length, 1) - Math.PI / 2;
    pos[n.id] = [cx + 115 * Math.cos(a), cy + 105 * Math.sin(a)];
  });
  ring2.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(ring2.length, 1) - Math.PI / 2 + 0.3;
    pos[n.id] = [cx + 225 * Math.cos(a), cy + 150 * Math.sin(a)];
  });

  return (
    <div>
      {!g.in_graph ? (
        <p className="rounded-md border border-coral/40 bg-coral-light p-3 text-sm" data-testid="graph-excluded">
          This person is not in the family graph: <strong>family_links consent was not granted</strong>. No cascade task can be
          created through them. {g.excluded_links.length} relationship(s) hidden.
        </p>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Consent-filtered family graph">
          {edges.map((e, i) => {
            const a = pos[e.source], b = pos[e.target];
            if (!a || !b) return null;
            return (
              <g key={i}>
                <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#C9BEB1" strokeWidth={1.5} />
                <text x={(a[0] + b[0]) / 2} y={(a[1] + b[1]) / 2 - 3} fontSize="9" fill="#6B6259" textAnchor="middle">{e.type}</text>
              </g>
            );
          })}
          {g.nodes.map((n) => {
            const p = pos[n.id];
            if (!p) return null;
            const centre = n.id === personId;
            const fill = n.is_index ? "#B5543F" : n.cascade_task ? "#F6E6E1" : n.has_open_gaps ? "#E3EFEE" : "#FFFFFF";
            return (
              <Link key={n.id} href={`/people/${n.id}`}>
                <g className="cursor-pointer">
                  <circle cx={p[0]} cy={p[1]} r={centre ? 24 : 19} fill={fill} stroke={centre ? "#0E6B68" : n.cascade_task ? "#B5543F" : "#C9BEB1"} strokeWidth={centre ? 3 : n.cascade_task ? 2 : 1.5} strokeDasharray={n.same_household ? undefined : "3 2"} />
                  <text x={p[0]} y={p[1] + 3} fontSize="9" textAnchor="middle" fill={n.is_index ? "#fff" : "#2E2A26"} fontWeight={600}>{n.age}{n.sex === "female" ? "F" : "M"}</text>
                  <text x={p[0]} y={p[1] + (centre ? 38 : 32)} fontSize="9.5" textAnchor="middle" fill="#2E2A26">{n.label}</text>
                </g>
              </Link>
            );
          })}
        </svg>
      )}
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
        <span><span className="mr-1 inline-block h-3 w-3 rounded-full border border-coral bg-coral-light align-middle" />cascade task</span>
        <span><span className="mr-1 inline-block h-3 w-3 rounded-full border border-line bg-teal-light align-middle" />open gaps</span>
        <span><span className="mr-1 inline-block h-3 w-3 rounded-full bg-coral align-middle" />index case (clinician/admin only)</span>
        <span>dashed = other household · parent, child, sibling and spouse links drawn</span>
      </div>
      <p className="mt-1 text-xs text-muted">{g.consent_note}</p>
    </div>
  );
}
