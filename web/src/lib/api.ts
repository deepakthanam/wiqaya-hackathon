// Thin API client. Paths are typed by the generated OpenAPI schema (src/lib/api-types.ts, `pnpm gen:api`).
import createClient from "openapi-fetch";
import type { paths } from "./api-types";

export const client = createClient<paths>({ baseUrl: "", credentials: "include" });

export type Role = "coordinator" | "clinician" | "planner" | "family" | "admin";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Responses are wrapped in an envelope: { label: "Simulated cohort", run_id, as_of, data, ... }.
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export async function startGuest(role: Role, householdId = "hh-demo-001") {
  return api("/session/guest", { method: "POST", body: JSON.stringify({ role, household_id: householdId }) });
}

export const ROLE_HOME: Record<Role, string> = {
  coordinator: "/coordinator",
  clinician: "/coordinator",
  planner: "/planner",
  family: "/family",
  admin: "/admin",
};

export const fmt = (v: unknown, digits = 1): string => {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(digits);
  return String(v);
};

export const isSuppressed = (v: unknown) => typeof v === "string" && v.startsWith("suppressed");

export const PATHWAY_LABEL: Record<string, string> = {
  wcv: "Well-Child Visit",
  immunisation: "Immunisation",
  developmental: "Developmental",
  adult_screening: "Adult screening",
  followup: "Follow-up",
  cascade: "Cascade (clinician)",
};
