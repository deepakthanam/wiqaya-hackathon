# Demo script (3 minutes)

Uses the pinned demo personas (seed 42). Every screen carries the **Simulated cohort** badge. The roles share one guest
session, so a decision made as clinician shows up in the family view.

| Persona | Who | What to show |
|---|---|---|
| `demo-001` | Khalid Al-Hammadi, 41, Khalifa City: **FH index case** (LDLR finding, FH confirmed 3 weeks before T0) | Rule-generated cascade tasks, family graph, clinician-only genomic detail |
| `demo-002` | Mariam Al-Hammadi, 36: cervical screen **426 days (~14 months) overdue** | Arabic WhatsApp bundle message |
| `demo-003`, `demo-004` | Saeed (9) and Shamma (4): **CASCADE_FH** tasks; Shamma's **4-year WCV** is overdue | Clinician sign-off |
| `demo-005` | Hamad, 45, father's brother, Al Shamkha (other household): CASCADE_FH task | Cascade across households |
| `demo-010` | Biju, 38, Indian, Malayalam, basic phone, Musaffah labour accommodation: **prediabetes follow-up and T2D screen overdue** | Malayalam SMS, mobile-van slot |
| `demo-020` | Noura, 38, father's sister: **family_links consent denied** | Excluded from graph, no cascade task |

## Steps

1. **Guest login as Coordinator** (≈10 s)
   - Open the app and click **Continue as Guest**, then **Care coordinator**.
   - Point out the disabled login fields ("Prototype: use guest access") and the coral **Simulated cohort** badge.

2. **The worklist shows the Al-Hammadi household ranked high** (≈20 s)
   - Filter by clinic **Primary Care Centre – Khalifa City 1**. The Al-Hammadi children (**#207, #208** of 14,835) appear near the top in the **high** band, marked *clinician sign-off*. Their mother is in the same household bundle.
   - Read the banner: *Population prioritisation, not a clinical decision.*

3. **Open the father** (`/people/demo-001`; ≈30 s)
   - He has no open gaps. His record is the **index case** that created **3 cascade clinician tasks** (demo-003, demo-004, demo-005).
   - The family graph shows consented links only. Noura (`demo-020`) is missing because she denied family_links.
   - Switch the role selector to **clinician**: the LDLR genome-programme finding appears, labelled *illustrative ClinVar reference*. Coordinators see "restricted".
   - Open a child or the mother to show gap cards with `rule_id@version`, the source link (e.g. USPSTF 2018, NICE CG71), evidence values and fields read. Then show **Why this rank**: SHAP phrases and the four weighted priority components.

4. **The cascade tasks need clinician sign-off. Accept** (≈25 s)
   - On Shamma (`demo-004`) as **coordinator**, click **Clinician sign-off**. It is refused: *Cascade tasks require clinician sign-off*.
   - The message preview shows *blocked until clinician approval and index consent*.
   - Switch to **clinician** and click **Clinician sign-off** again. Status becomes **accepted**, and the preview changes to *approved: ready to send*.

5. **Family view: the mother's WhatsApp in Arabic offers one combined visit day** (≈25 s)
   - Switch to **family**. Mariam's WhatsApp is in Modern Standard Arabic (right-to-left). It offers **one visit day for 3 family members (Saeed, Shamma, Mariam) on 05/11** at Khalifa City 1, with the English gloss and the *machine-drafted translation* flag.
   - Because Shamma was signed off in step 4, the generic family heart-health message appears too. It never names the father or a condition.
   - Show the preference centre: channel order, opt-out per pathway, remind later, decline with reason. Save to see the confirmation message.

6. **The worker's SMS in Malayalam and the van slot** (≈20 s)
   - Switch to **coordinator** and open `/people/demo-010`.
   - Two overdue gaps: FOLLOWUP_PREDIABETES (HbA1c 6.1% eighteen months ago) and ADULT_T2D_SCREEN (interval shortened to 12 months by the prediabetes result).
   - Contact plan: **SMS, then a CHW visit after 2 non-responses**.
   - The preview is a short Malayalam SMS (two 70-character segments at most) inviting him to the **free health van at the Musaffah labour-accommodation area on 14/12 at 17:40**.

7. **Planner console** (≈30 s)
   - Switch to **planner**. KPI cards: completed screenings per 100 contacts, **Wiqaya 44.6 vs baseline 19.8**. Also gaps closed (21.7% vs 8.0%), missed latent cases, and reach (the honest trade-off).
   - On the map, choose **Children under 6** or **Labour accommodation**: small districts are hatched and *suppressed (n<11)*. Use **Show grid** for the SVG fallback.
   - In the equity table, choose **District × nationality**: hatched suppressed cells.
   - Show the calibration plot (AUROC 0.78, slope 0.89) and the sensitivity panel (the advantage holds in all three scenarios).
   - *Optional, needs `ANTHROPIC_API_KEY`:* in **Ask the AI analyst**, click the first suggested question. The steps appear as the agent reads district need and runs a van-day what-if. It answers with evidence and caveats, every figure is checked against the data it looked up, and it drafts a proposal that you **Approve** or **Dismiss**. The decision shows in the admin audit log. The analyst sees only suppressed aggregates. (≈40 s, so skip it if time is short.)

8. **Admin: rule library with sources, and the provenance register** (≈20 s)
   - Switch to **admin**. The rule library lists 15 rules with version, cited source, verification state (HTTP status, retrieved 2026-11-07), status *demo encoding requires clinical validation*, and the assumptions per rule.
   - **Translations** tab: 390 machine-drafted templates flagged for native review.
   - **Provenance** tab: *No real personal data, no organiser data, no employer or client data*.
   - **Audit log**: every person-level read you just made, with fields read.

## If something goes wrong
- **"No session":** click *Continue as Guest* again. Sessions last 2 hours.
- **Map tiles blocked:** the planner switches to the SVG district grid automatically.
- **HAPI not running:** person pages show *FHIR server unavailable – showing the DuckDB read model*. Everything else works.
