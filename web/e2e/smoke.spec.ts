import { expect, test, type Page } from "@playwright/test";

async function guest(page: Page, role: string) {
  await page.goto("/");
  await page.getByTestId("continue-guest").click();
  await page.getByTestId(`role-${role}`).click();
}

for (const [role, path] of [
  ["coordinator", "/coordinator"],
  ["clinician", "/coordinator"],
  ["planner", "/planner"],
  ["family", "/family"],
  ["admin", "/admin"],
] as const) {
  test(`guest login as ${role}`, async ({ page }) => {
    await guest(page, role);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByTestId("simulated-badge")).toBeVisible();
  });
}

test("coordinator: worklist, persona 1, cascade sign-off and message preview", async ({ page }) => {
  await guest(page, "coordinator");
  await expect(page.getByTestId("worklist")).toBeVisible();
  await expect(page.getByText("Population prioritisation, not a clinical decision.")).toBeVisible();

  // Demo persona 1: the father (index case) – rule-generated cascade tasks and the family graph.
  await page.goto("/people/demo-001");
  await expect(page.getByTestId("cascade-index")).toBeVisible();
  await expect(page.getByRole("img", { name: "Consent-filtered family graph" })).toBeVisible();

  // A cascade task needs clinician sign-off: the coordinator is refused.
  await page.goto("/people/demo-004");
  await expect(page.getByTestId("gap-card").first()).toBeVisible();
  await page.getByTestId("accept").click();
  await expect(page.getByTestId("decision-status")).toContainText("clinician sign-off");
  await expect(page.getByTestId("preview-status")).toContainText("blocked");

  // Switch role to clinician (same session) and accept.
  await page.getByTestId("role-switch").selectOption("clinician");
  await expect(page).toHaveURL(/\/coordinator$/);
  await page.goto("/people/demo-004");
  await page.getByTestId("accept").click();
  await expect(page.getByTestId("decision-status")).toContainText("accepted");
  await expect(page.getByTestId("preview-status")).toContainText("approved");

  // Message preview for the mother: Arabic WhatsApp, right-to-left, with an English gloss.
  await page.goto("/people/demo-002");
  const text = page.getByTestId("message-text");
  await expect(text).toBeVisible();
  await expect(text).toHaveAttribute("dir", "rtl");
  await expect(page.getByText("English gloss")).toBeVisible();
});

test("planner: equity console with suppressed-cell hatching", async ({ page }) => {
  await guest(page, "planner");
  await expect(page.getByText("Completed per 100 contacts")).toBeVisible();
  expect(await page.getByTestId("kpi-simulated").count()).toBeGreaterThanOrEqual(4);
  await page.getByTestId("segment-select").selectOption("district_x_nationality");
  await expect(page.getByTestId("equity-table")).toBeVisible();
  const hatched = page.getByTestId("equity-table").getByTestId("suppressed-cell");
  await expect(hatched.first()).toBeVisible();
  const bg = await hatched.first().evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(bg).toContain("repeating-linear-gradient");
  await expect(page.getByTestId("sensitivity")).toBeVisible();
});

test("planner: AI analyst panel is present and states its data limits", async ({ page }) => {
  await guest(page, "planner");
  const panel = page.getByRole("region", { name: "AI analyst" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/aggregate, suppressed figures/)).toBeVisible();
  // Without a key it says it is off; with a key it offers questions. Either way it never blocks the console.
  await expect(panel.getByText(/AI analyst is off|Ask about need/).or(panel.getByPlaceholder(/Ask about need/))).toBeVisible();
});

test("family: household messages and preference centre", async ({ page }) => {
  await guest(page, "family");
  await expect(page.getByTestId("phone").first()).toBeVisible();
  await expect(page.getByText("Preference centre")).toBeVisible();
});

test("admin: rule library with sources and provenance register", async ({ page }) => {
  await guest(page, "admin");
  await expect(page.getByTestId("rules-table")).toBeVisible();
  await page.getByRole("tab", { name: "Provenance" }).click();
  await expect(page.getByTestId("provenance-statement")).toContainText("No real personal data");
});
