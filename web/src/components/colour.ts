// Sequential scale for unmet need: teal (lowest) to coral (highest), normalised to the shown range.
export function colourFor(v: unknown, max: number, min = 0): string {
  if (typeof v !== "number") return "#C9BEB1";
  const t = Math.max(0, Math.min(1, (v - min) / Math.max(max - min, 1e-9)));
  const a = [14, 107, 104];
  const b = [181, 84, 63];
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * t));
  return `rgb(${c.join(",")})`;
}

export function range(rows: { unmet_need_per_1000?: unknown }[]): [number, number] {
  const v = rows.map((r) => r.unmet_need_per_1000).filter((x): x is number => typeof x === "number");
  return v.length ? [Math.min(...v), Math.max(...v)] : [0, 1];
}
