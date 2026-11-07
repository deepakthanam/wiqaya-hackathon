# Demo recording script: Wiqaya (وقاية)

A shot-by-shot script for recording the demo video. It covers the introduction, the problem, a walk-through of every
console, the technical design, where AI is used and how it is controlled, the benefits, and the close.

- **Main cut:** about 8 minutes, 14 scenes. A **3-minute cut** for strict time limits is in Appendix A.
- **Every scene lists:** what to click (**Do**), what to say (**Say**), an optional caption (**Show**) and the point the scene proves (**Proves**).
- **Every number in the narration was checked against the running app** (seed 42, run `sim-seed1234`, T0 = 2026-11-01). If you regenerate the data with a different seed, re-check the numbers marked ★.

---

## Part 0: before you record

### Set up the app (about 15 minutes before)
1. Start the services from the repository root, in two terminals:
   ```bash
   make api        # API on http://localhost:8000 (reads .env, including ANTHROPIC_API_KEY for the AI analyst)
   make web        # web on http://localhost:3000
   ```
   - HAPI FHIR (`make up`) is optional. With it running, person pages say *Record read from the FHIR store*, which is a nice detail.
   - For the smoothest playback, use a production build instead of `make web`: `cd web && corepack pnpm build && corepack pnpm start`. The dev server compiles each page on its first visit, which can take several seconds on camera.
2. **Warm up every page once** so nothing compiles while you record: open `/`, `/coordinator`, `/people/demo-001`, `/people/demo-004`, `/people/demo-010`, `/family`, `/planner` and `/admin`.
3. **Start a fresh guest session just before recording.** Open a new incognito window and go to `http://localhost:3000`.
   - Decisions such as the clinician sign-off are kept per session. A new session puts Shamma back to *Pending*, so the sign-off scene works again.
   - To retake a scene, close the incognito window and open a new one.
4. **AI analyst:** check that the planner page shows the *Ask the AI analyst* box with suggested questions.
   - If it says *The AI analyst is off*, the API did not load `ANTHROPIC_API_KEY`. Restart it with `make api`.
   - A live answer takes 20 to 30 seconds. Record it in real time, then speed it up or trim it when editing.

### Set up the recording
| Setting | Recommendation |
|---|---|
| Resolution | 1920 × 1080; browser window maximised |
| Browser zoom | 110–125%, so table text is readable in the video |
| Browser | Incognito window, bookmarks bar hidden, no other tabs, notifications off |
| Recorder | OBS Studio, Loom or the Windows Snipping Tool screen recorder; record the browser window only |
| Cursor | Turn on cursor highlight (OBS or Loom) so viewers can follow the clicks |
| Audio | Record the narration separately or on a headset mic. Read the **Say** lines slowly, at about 140 words per minute |
| Editing | Add the **Show** captions as lower-thirds. Speed up waits (the AI analyst, page loads) to 2–4× |

### Personas used (all synthetic)
| ID | Who | Role in the story |
|---|---|---|
| `demo-001` | Khalid Al-Hammadi, 41, Khalifa City | **Index case**: familial hypercholesterolaemia (FH) with an LDLR genome-programme finding |
| `demo-002` | Mariam Al-Hammadi, 36 (his wife) | Cervical screen overdue; receives the family's WhatsApp |
| `demo-003` / `demo-004` | Saeed (9) and Shamma (4), their children | FH cascade tasks ★ ranked **#207** and **#208**; Shamma's 4-year Well-Child Visit is overdue |
| `demo-005` | Hamad, 45, Khalid's brother, another household | Cascade across households (★ rank #213) |
| `demo-010` | Biju Nair, 38, Indian, speaks Malayalam, basic phone, Musaffah labour accommodation | Prediabetes follow-up; Malayalam SMS; mobile screening van |
| `demo-020` | Noura, Khalid's sister | **Denied family-links consent**, so she is left out of the family graph |

---

## Part 1: the script

### Scene 1. Title and hook (0:00–0:25)
**Show:** Title card: *Wiqaya وقاية: precision prevention and screening · Future Health Digital Innovation Challenge · Population Health 04*. Then the landing page.

**Say:**
> "Every year, thousands of people in Abu Dhabi miss a screening, a vaccine or a follow-up test they are due for. Often nobody has worked out who to call first, or how to reach them. Wiqaya, Arabic for *prevention*, is a population-health layer that finds who is due, finds hidden risk, decides who to contact first and reaches them the right way. Then it measures whether that worked, and whether it worked fairly."

**Proves:** the problem and the one-line promise.

### Scene 2. The problem and our approach (0:25–0:55)
**Do:** Stay on the landing page. Move the cursor over the four facts (15 rules, 6 languages, 20,000 people, n < 11) and the coral banner.

**Say:**
> "Today, outreach is mostly one generic SMS to everyone on a list. People who don't read English, who only have a basic phone, or who live in labour accommodation are the least likely to respond. Family risk, such as an inherited cholesterol disorder, is rarely followed up across relatives. Wiqaya runs beside the clinical record. It reads FHIR data, checks 15 cited, versioned rules, and plans outreach in six languages across four channels. To be clear about scope: it never diagnoses and never changes a clinical pathway. It only changes **who is contacted first, and how**. Everything you will see runs on a simulated cohort of 20,000 synthetic people. There is no real patient data."

**Show:** *Population prioritisation, not a clinical decision · Simulated cohort.*

**Proves:** non-diagnostic positioning; synthetic data only.

### Scene 3. Guest access and the coordinator's worklist (0:55–1:35)
**Do:**
1. Click **Continue as Guest**, then **Care coordinator**. Point at the greyed-out email and password fields, then the coral **Simulated cohort** badge.
2. On the worklist, point at the header line: ★ *14,835 people with open gaps · ranked by priority …*
3. Open the **Clinic** filter and choose **Primary Care Centre – Khalifa City 1**. Point at the high-band rows for Saeed and Shamma and the *clinician sign-off* marker.
4. Optionally, open the **Pathway** filter and show the options: Adult screening, Cascade (clinician), Immunisation, and so on.

**Say:**
> "Judges and visitors get in with one click. There are no accounts, and each role sees only what it should. This is the care coordinator's worklist: about fifteen thousand people with an open care gap, ranked. The ranking combines four things: clinical risk from a calibrated model, how time-sensitive the gap is, the chance the person won't turn up, and whether we can bundle a household into one visit. Then the plan is fitted to real clinic capacity. Filtering to Khalifa City 1, two young children of the Al-Hammadi family are near the top of the high band. Let's see why."

**Show:** *Ranked by risk × time sensitivity × no-show × household bundle, then fitted to clinic capacity.*

**Proves:** criterion 3 (decide who to contact first); capacity-aware ranking.

### Scene 4. The index case and the family cascade (1:35–2:20)
**Do:**
1. Open the father: go to `/people/demo-001`, or click through from the household.
2. Point at **Care gaps (0)**, then the **Index case for family cascade** card: *3 cascade clinician tasks … demo-003, demo-004, demo-005*. Then the line *Relatives are never told this person's diagnosis.*
3. Point at the **family graph** and the dashed edge to another household (Hamad). Read the note *Only links where both people granted family_links consent are shown*.
4. Point at *Genomic information: restricted (clinician/admin only)*.
5. Switch the role selector (top right) to **clinician** and reopen `/people/demo-001`. The **LDLR · pathogenic** finding appears, labelled *Illustrative ClinVar reference on a synthetic finding*.

**Say:**
> "This is the children's father, Khalid. He has no open gaps of his own. Three weeks ago he was confirmed with familial hypercholesterolaemia, an inherited cholesterol disorder. Under NICE guidance, first-degree relatives should be tested. Wiqaya's rule engine picked that up and created three clinician tasks: his two children, and his brother Hamad, who lives in a different household. The family graph shows only links where both people consented. His sister Noura refused family-link consent, so she doesn't appear at all, and no task can go through her. As a coordinator I can't see genetic detail. When I switch to the clinician role, the genome-programme finding appears. Genomic data is shown only to clinicians, and the model uses it only with genomic consent."

**Show:** *Hidden risk: family links, genomics, past results. Consent is checked per category.*

**Proves:** criterion 2 (hidden risk); consent per category; role-based access to genomic data.

### Scene 5. Explainability: why Shamma is ranked #208 (2:20–3:00)
**Do:**
1. Switch back to **coordinator** and open Shamma: `/people/demo-004`. Point at **PRIORITY RANK #208 · high**.
2. On the first gap card, **Well-Child Visit schedule**, point at `WCV_SCHEDULE@1.0.0`, *119 days overdue*, the source line, *verified*, the evidence values and *Fields read*.
3. On the second card, **CASCADE_FH@1.0.0**, point at the source: *NICE CG71*.
4. Scroll to **Why this rank**. Point at the four weighted components (0.40 / 0.35 / 0.15 / 0.10) and the line *guideline prior: first-degree relative of an index case*.
5. Point at the **Slot** box: *2026-11-05 at 08:50, Primary Care Centre – Khalifa City 1*.

**Say:**
> "Every flag explains itself, with the rule first and the model second. Each gap card shows the exact rule and version, the guideline it comes from with a verified link, the values it used, and even which fields it read. Shamma's four-year check-up is 119 days overdue, and she has a family-cascade task. Under 'Why this rank' you can see the four weighted components. For adults, this panel also shows the model's top three reasons in plain language. Because she's a child, she has no model score: the cascade guideline sets her risk component. The capacity planner has already reserved her a slot on the fifth of November."

**Show:** *Every flag: rule@version → cited source → evidence → fields read → weighted score.*

**Proves:** auditable, versioned rules; explainable ranking.

### Scene 6. Human in the loop: clinician sign-off (3:00–3:35)
**Do:**
1. Still on Shamma as **coordinator**, scroll to **Human review** and click **Clinician sign-off**. It is refused: *Cascade tasks require clinician sign-off. Switch to the Clinician role to approve.* The **Message preview** status says *blocked until clinician approval and index consent*.
2. Switch the role to **clinician**, reopen `/people/demo-004` and click **Clinician sign-off**. It shows *Saved: accepted*, and the preview changes to *approved: ready to send*.
3. Optionally, point at **Change** and **Reject**: a coordinator can override the order, giving a reason.

**Say:**
> "Nothing reaches a family without a person deciding. A coordinator can accept, change or reject any flag, with a reason. A family-cascade message is sensitive, so even the coordinator can't release it: the system refuses and the message stays blocked. Once a clinician signs off, the message is approved and ready to send. Every one of these decisions goes into the audit log."

**Show:** *Human review gate: coordinator decisions; clinician sign-off for cascade.*

**Proves:** human oversight; the AI never acts alone.

### Scene 7. The family's view: one visit, in Arabic (3:35–4:20)
**Do:**
1. Switch the role to **family**. The page shows *Messages to household hh-demo-001*.
2. Point at the first WhatsApp to Mariam, in Arabic and right to left, offering **one visit day for 3 family members (Saeed, Shamma and Mariam)** on 05/11. Point at the **English gloss** and the *Machine-drafted translation: needs native-speaker review* flag.
3. Point at the second message, **Family heart-health check**, which appeared because of the sign-off. It says *"Your doctor recommends a heart-health check for your family"* and names neither the father nor the condition.
4. Scroll to the **Preference centre**: channel order (WhatsApp → SMS → call), *Stop reminders about …* per pathway, then save.

**Say:**
> "This is exactly what the family receives. Instead of three separate appointments, Mariam gets one WhatsApp in Arabic offering a single visit day for herself and both children. That's household bundling. Because the clinician signed off a moment ago, the heart-health invitation now appears. Notice what it doesn't say: it never names the father or his diagnosis. Families stay in control. In the preference centre they choose the channel order and can stop reminders for any single pathway."

**Show:** *Right language · right channel · right time · one visit for the household.*

**Proves:** criterion 4 (reach people the right way); privacy-preserving cascade messaging; preference centre.

### Scene 8. Reaching a worker: Malayalam SMS and the mobile van (4:20–5:00)
**Do:**
1. Switch the role to **coordinator** and open Biju: `/people/demo-010`. The header shows *38 y · indian · prefers ml · basic phone · labour accommodation*.
2. Point at the two gap cards:
   - **ADULT_T2D_SCREEN**: the screening interval is shortened to 12 months because his last HbA1c was 6.1%;
   - **FOLLOWUP_PREDIABETES**: 184 days overdue.
3. In **Why this rank**, read the three plain-language model drivers: *No long-term condition recorded yet · 18 months since last screening visit · Last HbA1c 6.1%*.
4. Point at the **Slot**: *2026-12-14 at 17:40 · Mobile Screening Van – Musaffah labour-accommodation area*. Then the contact plan: *sms → chw_script · ml*.
5. Point at the **Message preview**: a short Malayalam SMS with its English gloss: *"Biju, free health van: Musaffah labour-accommodation area, 14/12. 1=reserve 2=other day 3=STOP"*.
6. Open the **Household** (`/households/hh-demo-010`) and point at *Bundle into one day: 2 members at Mobile Screening Van … on 2026-12-14*.

**Say:**
> "Now a very different person. Biju is a 38-year-old worker in Musaffah. He speaks Malayalam, has a basic phone, and his last blood-sugar test was in the prediabetes range eighteen months ago. Nobody followed it up. The model explains his priority in plain words. Instead of a daytime clinic appointment across the city, Wiqaya books the mobile screening van at his accommodation at 5:40 in the evening, and texts him in Malayalam, in a message short enough for a basic phone. If he doesn't reply twice, a community health worker visits in person. Vineeth, who lives with him, is booked into the same van visit."

**Show:** *Equity by design: language, phone type, shift times, mobile van, CHW fallback.*

**Proves:** criterion 4 for underserved groups; follow-up of abnormal results; timing rules.

### Scene 9. The planner: does it work? (5:00–5:50)
**Do:**
1. Switch the role to **planner**. Point at the 4 KPI cards, each with a **Simulated cohort** badge:
   - ★ **44.6 vs 19.8** completed screenings per 100 contacts;
   - **21.7% vs 8.0%** of gaps closed in 12 weeks;
   - missed latent cases **69.5% vs 89.2%**;
   - people reached **19.3% vs 41.5%**.
2. On the map (**Unmet need per 1,000 by district**), choose **Residents of labour accommodation**. Point at the hatched (suppressed) districts. Optionally, click **Show grid**.
3. In **Equity: baseline vs Wiqaya by segment**, choose **District × nationality (fine-grained)** and point at the hatched cells *(n < 11)*.
4. Point at **Calibration: Model R**: *AUROC 0.779 · slope 0.89*.
5. Point at **Sensitivity analysis**: Wiqaya stays ahead in all four rows; the smallest gap is **+19.9** under *weak language*.

**Say:**
> "The planner sees only aggregates, never individuals. In a 12-week simulation with the same clinic capacity and the same random draws, Wiqaya gets 44.6 completed screenings per 100 contacts, against 19.8 for today's approach. It closes nearly three times as many gaps and misses far fewer hidden conditions. The trade-off is reach: Wiqaya contacts fewer people, but it gives them repeat contacts in their own language and a community health worker visit, instead of one SMS to everyone. Any group smaller than eleven people is hidden, as you can see in the hatched cells. The risk model is calibrated, and the sensitivity analysis asks whether our simulator flatters us: under weaker assumptions the advantage shrinks, but it never reverses. Only a randomised pilot can confirm the real size of the effect."

**Show:** *Criterion 5: measures itself, with equity, calibration, suppression and an honest sensitivity analysis.*

**Proves:** criterion 5 (measure itself); honest reporting.

### Scene 10. The AI analyst: an agent with guardrails (5:50–6:40)
**Do:**
1. Still as **planner**, scroll to **Ask the AI analyst**. Point at the description: *sees only aggregate, suppressed figures. Nothing changes until you approve.*
2. Click the first suggested question: *"Which districts have the most unmet need for their capacity, and where would one extra van day help most?"*
3. While it works, point at the live **steps** list (*district need → capacity estimate → …*). Speed this up in the edit.
4. When the answer appears, point at:
   - the **Evidence** and **Caveats** sections;
   - the number-check line (e.g. *9 of 12 figures match the data looked up …*);
   - the model name and timing line.
5. Under **Proposals for your decision**, click **Approve** on one proposal. It shows *Approved by planner*.
6. Optionally, switch to **admin → Audit log** and show the `analyst_question`, `analyst_answer_done` and `analyst_proposal_approved` entries.

**Say:**
> "Planners can also ask questions in plain English. This is an AI agent built on Claude. It doesn't make things up from memory. It calls the same suppressed aggregate tools the planner console uses, so it can never see an individual. Watch the steps: it looks up unmet need by district, then runs a what-if for one extra van day. Every number in its answer is checked against the data it actually retrieved, and anything it calculated itself is flagged for the planner to check. Most importantly, it can't change anything. It drafts a proposal, and a person approves or dismisses it. The question, the answer and the decision all go into the audit log."

**Show:** *Agentic AI, fenced: aggregate-only tools · every number checked · human approval · audited · rate-limited.*

**Note:** the answer's wording and figures change from run to run. Read what appears; don't read out the example numbers from this script.

**Proves:** responsible agentic AI; human accountability.

### Scene 11. Governance: rules, translations, provenance, audit (6:40–7:15)
**Do:**
1. Switch the role to **admin**.
2. **Rule library:** 15 rules, each with its source, *verified · retrieved 2026-11-07 · HTTP 200*, the status *demo encoding requires clinical validation*, and the open-gap count.
3. **Translations:** 78 templates in each of 6 languages; the non-English ones are marked *needs review*.
4. **Provenance:** *No real personal data, no organiser data, and no employer or client data are used anywhere in this prototype.*
5. **Model card:** held-out performance for both models.
6. **Audit log:** the reads you just made, with role, session, entity and **fields read**.

**Say:**
> "Everything is governed and inspectable. Administrators can see every rule with its cited source and the date it was verified, which machine-drafted translations still need a native speaker, where every piece of data comes from, the model card, and an audit log of every record read, down to the fields."

**Show:** *Governance band: consent · field guards · role-based access + audit · n<11 · genomic stripping · human review · simulated labels.*

**Proves:** Responsible AI, safety and governance.

### Scene 12. How it's built (7:15–7:45)
**Show:** an architecture slide built from the *Six layers* diagram in `docs/ARCHITECTURE.md`, or screen-record that diagram on GitHub. A stack list as a lower-third.

**Say:**
> "Under the hood there are six layers. Data comes in as FHIR R4. A HAPI FHIR server is the system of record, with a DuckDB read model for analytics. Care gaps come from 15 YAML rules in a pure, traced evaluator. Risk and no-show come from calibrated LightGBM models explained with SHAP. A fairness floor protects under-served groups. Google OR-Tools fits the plan to real clinic and van capacity. Messages come from a library of 468 templates in six languages. A FastAPI backend serves Next.js consoles. For production, the pilot path is Azure in the UAE North region, reading from Malaffi, Abu Dhabi's health information exchange, with Entra ID sign-in and data kept in the UAE."

**Show (stack):** *FHIR R4 · HAPI FHIR · DuckDB · LightGBM + isotonic · SHAP · OR-Tools CP-SAT · FastAPI · Next.js 14 · Claude Haiku 5.5 (optional) · Docker · Vercel.*

### Scene 13. Benefits (7:45–8:10)
**Show:** a benefits slide (Part 3 below).

**Say:**
> "So what does this mean? For families: one visit in their own language, and control over their reminders. For coordinators: a worklist that explains itself and fits real capacity. For clinicians: inherited risk surfaced across households, with consent. For the Department of Health: more completed screenings from the same capacity, with equity monitored in the open. And because it plugs into existing FHIR feeds, it can be added without replacing any system."

### Scene 14. Close (8:10–8:25)
**Show:** title card: *Wiqaya وقاية · The right person, the right pathway, on time.* Add the repository URL and *Simulated cohort, prototype*.

**Say:**
> "Wiqaya: the right person, the right pathway, on time. It's a working prototype on synthetic data, ready for a supervised pilot. Thank you."

---

## Part 2: AI interventions (reference for Scene 10 and for Q&A)

| # | Where | What the AI does | Technique | How it is controlled |
|---|---|---|---|---|
| 1 | Worklist ranking | Estimates each adult's chance that a screen finds a condition (**Model R**) | LightGBM + isotonic calibration; AUROC 0.779, slope 0.89 | Nationality, language, district and insurance are **excluded** as predictors; it only reorders, and every due gap stays listed |
| 2 | Contact effort | Predicts no-shows (**Model N**) so people likely to miss get **more** help, not less | LightGBM + isotonic; AUROC 0.639 | Used to add effort (CHW, repeat touches), never to drop anyone |
| 3 | Explanations | Turns the top 3 risk drivers into plain phrases | SHAP TreeExplainer | Shown after the rule citation; rule first, model second |
| 4 | Fairness | Promotes flags for groups below their share of slots | Fairness floor: share ≥ 0.8 × share of need | Every swap is logged (17 in this run) and visible to admins |
| 5 | Scheduling | Fits outreach to real clinic and van slots and bundles households | OR-Tools CP-SAT, two stages | Hard capacity limits per site and day; outreach timing separately follows quiet-hour, Friday, Eid and Ramadan rules |
| 6 | Messaging | Chooses channel, language and timing per person | Deterministic contact-planning rules over a template library | No free-text generation; translations are flagged for native review |
| 7 | Planner analyst | Answers questions, runs what-ifs, drafts proposals | Claude Haiku 5.5 agent with tool use | Aggregate-only tools; n<11 suppression; every number checked; human approval; audit log; 8-step and 15-questions-per-hour limits |
| 8 | Measurement | Tests whether the system helps, and for whom | 12-week simulator with common random numbers; sensitivity analysis | Reported honestly, including the reach trade-off and the weak-assumption scenarios |

**One-line framing:** *"Rules decide who is due. Models decide who goes first. People decide what is sent."*

## Part 3: benefits (for Scene 13 and slides)

| Stakeholder | Benefit | Evidence in the demo |
|---|---|---|
| Families | One bundled visit; their own language and channel; control over reminders; relatives' diagnoses stay private | Scene 7 |
| Under-served residents | Evening van slots, SMS for basic phones, CHW follow-up, fairness floor | Scene 8 and the equity table |
| Care coordinators | A ranked, explained worklist that fits capacity; accept, change or reject with a reason | Scenes 3, 5 and 6 |
| Clinicians | Inherited (FH) risk surfaced across households; sign-off control; genomic detail only for them | Scenes 4 and 6 |
| DOH planners | ★ 44.6 vs 19.8 completions per 100 contacts; 2.7× more gaps closed; equity and calibration in the open; an AI analyst with guardrails | Scenes 9 and 10 |
| Health system | Plugs into existing FHIR (Malaffi); no rip-and-replace; configurable rules; licence-clean stack; UAE data residency on the pilot path | Scene 12 |

## Part 4: key numbers cheat sheet (simulated cohort)

| Metric | Baseline | Wiqaya |
|---|---|---|
| Completed screenings per 100 contacts ★ | 19.8 | **44.6** |
| Gaps closed in 12 weeks | 8.0% | **21.7%** |
| Missed latent cases (FN rate) | 89.2% | **69.5%** |
| Follow-up completion of abnormal results | 0% | **21.4%** |
| People reached (the trade-off) | 41.5% | 19.3% |
| Smallest advantage in the sensitivity analysis | | +19.9 per 100 (weak language) |

Other numbers: 20,000 synthetic people · 14,835 with open gaps · 15 rules · 468 templates (78 × 6 languages) · 4 channels · n < 11 suppression · Model R AUROC 0.779 · Model N AUROC 0.639.

---

## Appendix A: 3-minute cut
| Time | Scene | Keep |
|---|---|---|
| 0:00–0:20 | 1 + 2 | Hook plus the line *"it never diagnoses; it only changes who is contacted first and how"* |
| 0:20–0:45 | 3 | Guest login; worklist; filter Khalifa City 1 |
| 0:45–1:15 | 4 | Father: 3 cascade tasks; consent-filtered graph; clinician-only genomics |
| 1:15–1:40 | 5 + 6 | Shamma's gap card and *Why this rank*; sign-off refused, then accepted |
| 1:40–2:00 | 7 | The Arabic WhatsApp bundle for 3 family members |
| 2:00–2:15 | 8 | Biju's Malayalam SMS and the evening van slot |
| 2:15–2:40 | 9 | KPI cards (44.6 vs 19.8); hatched suppressed cells |
| 2:40–2:55 | 10 | The AI analyst answer and the Approve button (sped up) |
| 2:55–3:00 | 14 | Close |

## Appendix B: if something goes wrong while recording
| Symptom | Fix |
|---|---|
| *Your guest session has ended* or *No session* | Click **Continue as Guest** again. Sessions last 2 hours, and a restarted API clears them |
| Shamma already shows *accepted* | You are in an old session. Open a new incognito window |
| A page spins for several seconds | The dev server is compiling it. Warm up the pages first, or use the production build |
| *The AI analyst is off* | The API did not load `.env`. Restart it with `make api` |
| The AI analyst shows an error or the hourly limit | Click **New conversation**, or skip Scene 10. The rest of the console works without it |
| The map is grey or blocked | Click **Show grid** to show the SVG district grid |
| *FHIR server unavailable* on person pages | HAPI is not running. Everything still works from the DuckDB read model; run `make up` if you want the FHIR line |

## Appendix C: likely judge questions and short answers
- **"Is this real data?"** No. Every person-level record is synthetic and labelled *Simulated cohort*. Provenance is listed in Admin → Provenance and `docs/DATA_PROVENANCE.md`.
- **"Could the model discriminate?"** Nationality, language, district and insurance are excluded as predictors. They are used only to monitor outcomes. A fairness floor and the equity tables check the results, and no gap is ever dropped.
- **"How do you know it works?"** On simulated data, compared against today's approach with the same capacity and the same random draws. The sensitivity analysis shows the direction holds. Only a randomised pilot can confirm the size.
- **"What stops the AI agent from leaking data or acting on its own?"** Its tools return only suppressed aggregates. Numbers are verified. It can only draft proposals, which a person must approve. Everything is audited and rate-limited.
- **"How would you deploy it in Abu Dhabi?"** Azure UAE North, reading Malaffi FHIR, with Entra ID roles and Key Vault, after a DOH data-protection impact assessment and clinical validation of the rules (`docs/DEPLOYMENT.md`).
