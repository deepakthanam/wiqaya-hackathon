"use client";
import { isSuppressed } from "@/lib/api";
import { colourFor, range } from "./colour";

// SVG fallback when map tiles are blocked: one tile per district, grouped by region, hatched when suppressed.
export default function DistrictGrid({ rows }: { rows: any[] }) {
  const [min, max] = range(rows);
  const regions = ["al_dhafra", "abu_dhabi", "al_ain"];
  const W = 132, H = 74;
  return (
    <svg viewBox={`0 0 ${W * 7 + 20} ${H * 3 + 60}`} className="w-full" role="img" aria-label="District grid of unmet need per 1,000">
      <defs>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="#F7F4F0" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="#C9BEB1" strokeWidth="2" />
        </pattern>
      </defs>
      {regions.map((reg, ri) => (
        <g key={reg} transform={`translate(10, ${ri * (H + 20) + 20})`}>
          <text x={0} y={-6} fontSize="11" fill="#6B6259" fontWeight={600}>{reg.replace("_", " ").toUpperCase()}</text>
          {rows.filter((r) => r.region === reg).map((r, i) => {
            const sup = isSuppressed(r.unmet_need_per_1000);
            return (
              <g key={r.district_id} transform={`translate(${i * W}, 0)`} data-testid={sup ? "suppressed-cell" : undefined}>
                <rect width={W - 6} height={H - 6} rx={6} fill={sup ? "url(#hatch)" : colourFor(r.unmet_need_per_1000, max, min)} stroke="#2E2A26" strokeWidth={0.5} />
                <text x={8} y={18} fontSize="11" fill={sup ? "#2E2A26" : "#fff"} fontWeight={600}>{r.name}</text>
                <text x={8} y={40} fontSize="16" fill={sup ? "#6B6259" : "#fff"} fontWeight={700}>{sup ? "suppressed" : r.unmet_need_per_1000}</text>
                <text x={8} y={58} fontSize="10" fill={sup ? "#6B6259" : "#fff"}>{sup ? "n < 11" : `per 1,000 · n ${r.n}`}</text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}
