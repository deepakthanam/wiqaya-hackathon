"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ROLE_HOME, startGuest, type Role } from "@/lib/api";

const NAV: Record<Role, { href: string; label: string }[]> = {
  coordinator: [
    { href: "/coordinator", label: "Worklist" },
    { href: "/admin", label: "Rules" },
  ],
  clinician: [
    { href: "/coordinator", label: "Worklist" },
    { href: "/admin", label: "Rules & model" },
  ],
  planner: [
    { href: "/planner", label: "Planner console" },
    { href: "/admin?tab=provenance", label: "Provenance" },
  ],
  family: [{ href: "/family", label: "My household" }],
  admin: [
    { href: "/admin", label: "Admin" },
    { href: "/planner", label: "Planner" },
    { href: "/coordinator", label: "Worklist" },
  ],
};
const ROLES: Role[] = ["coordinator", "clinician", "planner", "family", "admin"];

export function SimulatedBadge() {
  return (
    <span
      data-testid="simulated-badge"
      className="chip bg-coral text-white"
      title="Every record and every metric in this app is synthetic"
    >
      Simulated cohort
    </span>
  );
}

export default function Header() {
  const [role, setRole] = useState<Role | null>(null);
  const path = usePathname();
  const router = useRouter();
  useEffect(() => {
    api("/session")
      .then((s) => setRole(s.role))
      .catch(() => setRole(null));
  }, [path]);

  async function switchRole(r: Role) {
    await startGuest(r);
    setRole(r);
    router.push(ROLE_HOME[r]);
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-[1000] border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
        <Link href="/" className="flex items-baseline gap-2" aria-label="Wiqaya home">
          <span className="text-xl font-bold tracking-tight text-teal">Wiqaya</span>
          <span className="text-lg text-teal" lang="ar" dir="rtl">
            وقاية
          </span>
        </Link>
        <SimulatedBadge />
        <nav className="ml-2 flex gap-1" aria-label="Main">
          {role &&
            NAV[role].map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`rounded-md px-3 py-1.5 text-sm ${
                  path.startsWith(n.href.split("?")[0]) ? "bg-teal-light font-semibold text-teal" : "hover:bg-white"
                }`}
              >
                {n.label}
              </Link>
            ))}
          <Link href="/about" className="rounded-md px-3 py-1.5 text-sm hover:bg-white">
            About
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {role ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">Guest as</span>
              <select
                data-testid="role-switch"
                value={role}
                onChange={(e) => switchRole(e.target.value as Role)}
                className="rounded-md border border-line bg-white px-2 py-1 text-sm"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <Link href="/" className="btn-primary">
              Continue as Guest
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
