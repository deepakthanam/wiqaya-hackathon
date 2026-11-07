# Demo recording script: Wiqaya (وقاية), 2 minutes 30 seconds

This walk-through plays **after the 30-second intro video**, which covers the problem. It starts straight in the product.
The total video runs 3:00.

The story follows one family and one worker through the app, then shows that it works and that it's safe. There are
seven scenes and about 280 words of narration, so you can speak calmly with pauses.

| Time | Scene | Screen | The one point to land |
|---|---|---|---|
| 0:00–0:15 | 1. Who to contact first | Coordinator worklist | Everyone due, ranked |
| 0:15–0:50 | 2. Shamma | Shamma's page | Hidden family risk, explained, with a clinician in control |
| 0:50–1:08 | 3. The family's message | Family view | One visit, in Arabic, privacy kept |
| 1:08–1:28 | 4. Biju | Biju's page | Reaching people the usual approach misses |
| 1:28–1:52 | 5. Does it work? | Planner KPIs | In simulation, 21.7% vs 8% of care gaps closed; a pilot would confirm |
| 1:52–2:15 | 6. AI analyst | Planner, AI analyst | AI that helps but can't act alone |
| 2:15–2:30 | 7. Close | Admin audit log | Rules, models, people |

All numbers below were checked against the running app (seed 42). Every person is synthetic.

---

## Before you record

1. **Start the app** in two terminals from the repository root: `make api` and `make web`. Both must stay running.
2. **Warm up the pages** so nothing loads slowly on camera. Open these once: `/coordinator`, `/people/demo-004`,
   `/people/demo-010`, `/family`, `/planner` and `/admin`.
3. **Open a fresh incognito window** at `http://localhost:3000`. A new session puts Shamma's sign-off back to *Pending*.
   For a retake, close the window and open a new one.
4. **Set up the first shot (not recorded):** click **Continue as Guest**, then **Care coordinator**. Leave the filters
   on *All*, so the header reads *14,835 people with open gaps*. Now start recording.
5. **Recording settings:** 1920 × 1080, browser maximised, zoom 110–125%, cursor highlight on, no other tabs.
6. **You switch roles** with the *Guest as* drop-down at the top right (coordinator, clinician, planner, family, admin). Each switch opens that role's home page. Cut the switches short in the edit.

---

## The script

### Scene 1. Who to contact first (0:00–0:15)
**Do:** Show the worklist. Point at the header line *14,835 people with open gaps · ranked by priority*, then move the cursor slowly down the top rows.

**Say:**
> "This is Wiqaya at work. A care coordinator sees everyone with an open screening or vaccine gap, about fifteen
> thousand people, ranked by who to contact first."

**Caption:** *Everyone due · ranked · fitted to clinic capacity*

### Scene 2. Shamma: hidden family risk (0:15–0:50)
**Do:**
1. Open Shamma's page: type `localhost:3000/people/demo-004` in the address bar. Point at **PRIORITY RANK #208 · high**.
2. Point at the first gap card: the rule name, the cited source and *verified*.
3. Scroll to **Why this rank** for two seconds.
4. Scroll to **Human review** and click **Clinician sign-off**. It is refused: *Cascade tasks require clinician sign-off*.
5. Switch the role to **clinician**, reopen `/people/demo-004` and click **Clinician sign-off**. It shows *accepted*.

**Say:**
> "Four-year-old Shamma ranks 208th out of nearly fifteen thousand. Her father was just diagnosed with an inherited cholesterol disorder, so the
> rules flag his children for testing. Every flag shows its rule, its cited guideline, and why it ranks here.
> Family messages are sensitive, so a coordinator can't release this one. A clinician has to sign off. Now it's
> approved."

**Caption:** *Rule → cited guideline → reason for rank · clinician sign-off*

### Scene 3. The family's message (0:50–1:08)
**Do:** Switch the role to **family**. Point at the first WhatsApp, in Arabic, then its English gloss underneath.

**Say:**
> "Instead of three appointments, the mother gets one WhatsApp, in Arabic, offering a single visit for herself and
> both children. It never mentions the father's diagnosis."

**Caption:** *Right language · right channel · one visit for the household*

### Scene 4. Biju: reaching people who get missed (1:08–1:28)
**Do:**
1. Switch the role to **coordinator** and open `/people/demo-010`.
2. Point at the header line: *prefers ml · basic phone · labour accommodation*.
3. Point at the **Slot**: *Mobile Screening Van – Musaffah, 2026-12-14 at 17:40*.
4. Point at the **Message preview**: the Malayalam SMS and its English gloss.

**Say:**
> "Biju works in Musaffah, speaks Malayalam and has a basic phone. His prediabetes result was never followed up.
> Wiqaya books the mobile van at his accommodation in the evening, texts him in Malayalam, and sends a community
> health worker if he doesn't reply."

**Caption:** *Evening van slot · Malayalam SMS · health-worker follow-up*

### Scene 5. Does it work? (1:28–1:52)
**Do:**
1. Switch the role to **planner**. Point at the **Gaps closed in 12 weeks** card: **21.7% vs 8.0%**, then at its
   **Simulated cohort** badge.
2. Scroll to the map or the equity table and point at a hatched cell (*n < 11*).

**Say:**
> "Does it work? In a simulation on synthetic data, with the same clinic capacity, Wiqaya closed 21.7% of care gaps
> in twelve weeks, against 8% for a generic SMS approach. That's a modelled estimate; a pilot would measure the real
> effect. Planners see only totals, and any group under eleven people is hidden."

**Caption:** *Simulated estimate on synthetic data · same capacity · small groups suppressed*

**Why this wording:** the comparison is a *modelled* generic-SMS approach, not Abu Dhabi's measured current rate, and
the simulator carries our own assumptions. *Gaps closed* counts everyone who is due, so unlike the per-contact rate it
doesn't benefit from Wiqaya contacting fewer people. Avoid saying "today" or quoting 44.6 vs 19.8 as the headline.

### Scene 6. The AI analyst (1:52–2:15)
**Do:**
1. Scroll to **Ask the AI analyst** and click the first suggested question.
2. Let the steps appear. The answer takes 20–30 seconds, so **cut or speed up the wait** in the edit.
3. When the answer appears, point at the number-check line, then click **Approve** on a proposal.

**Say:**
> "Planners can also ask an AI analyst, built on Claude. It works only from those protected totals, checks every
> number it quotes against the data, and can't change anything on its own. It drafts a proposal, and a person
> approves it."

**Caption:** *AI with guardrails: totals only · numbers checked · human approval*

**Note:** the answer's wording changes each run. The narration above doesn't quote its numbers, so it always fits.

### Scene 7. Close (2:15–2:30)
**Do:** Switch the role to **admin** and open the **Audit log** tab. Hold for two seconds, then cut to the end card:
*Wiqaya وقاية · The right person, the right pathway, on time.*

**Say:**
> "Every decision is logged. Rules decide who is due, models decide who goes first, and people decide what is sent.
> Wiqaya: the right person, the right pathway, on time."

---

## If something goes wrong while recording
| Problem | Fix |
|---|---|
| Shamma already shows *accepted* | You're in an old session. Open a new incognito window |
| *Your guest session has ended* | Click **Continue as Guest** again |
| A page spins for a few seconds | Warm up the pages first; cut the wait in the edit |
| *The AI analyst is off* | The API didn't load `.env`. Restart it with `make api` |
| The AI analyst shows an error | Click **New conversation** and ask again, or record Scene 6 separately |
| The AI analyst never answers, or no **Proposals for your decision** appear | Check the API is running: `http://localhost:8000/api/v1/healthz` should show `"status":"ok"`. If not, restart both servers (`make api`, `make web`). Then open a new incognito window and click the **first** suggested question; the other two are analysis questions and don't draft proposals |
| The suggested questions are missing | They only show before the first question. Click **New conversation** |
| The map is grey | Click **Show grid** |

## Reference for questions afterwards

**Key numbers (simulated cohort):**
- 20,000 synthetic people, 14,835 with open gaps.
- 15 cited rules, 6 languages, 4 channels.
- Gaps closed in 12 weeks, across everyone due: **21.7% vs 8.0%** (the headline).
- Completed screenings per 100 contacts: 44.6 vs 19.8. Quote this only with the reach figure, because a per-contact
  rate rises when fewer people are contacted.
- People reached: 19.3% vs 41.5%. This is the trade-off: fewer people, contacted better.
- Under weaker simulator assumptions Wiqaya still leads (smallest gap: +19.9 completions per 100 contacts).
- The baseline is a modelled generic-SMS approach, not a measured real-world rate.
- Risk model AUROC 0.779.

**Where AI is used:**

| Where | What it does | How it's controlled |
|---|---|---|
| Ranking | A calibrated risk model (LightGBM) orders the worklist | Nationality, language, district and insurance are not used as inputs; nobody due is dropped |
| Explanations | SHAP turns the top risk drivers into plain words | Shown after the rule citation: rule first, model second |
| Fairness | A floor promotes under-served groups | Every swap is logged |
| Scheduling | OR-Tools fits outreach to real clinic and van slots | Hard capacity limits |
| AI analyst | Claude answers planner questions and drafts proposals | Totals only, every number checked, human approval, audit log |

**Likely judge questions:**
- **Is this real data?** No. Every record is synthetic and labelled *Simulated cohort*.
- **Could the model discriminate?** Protected attributes are not inputs. They are used only to monitor fairness.
- **How do you know it works?** We don't yet, in the real world. A simulation on synthetic data compares Wiqaya with a
  modelled generic-SMS approach, using the same capacity and the same random draws. A sensitivity analysis shows the
  advantage holds under weaker assumptions. Only a supervised pilot, ideally randomised, can measure the real effect.
- **Isn't 44.6 vs 19.8 inflated because you contact fewer people?** Partly, yes. That's why we lead with gaps closed
  across everyone due (21.7% vs 8.0%) and show reach (19.3% vs 41.5%) openly.
- **How would it be deployed?** Azure UAE North, reading Malaffi FHIR, with DOH sign-in roles (see `DEPLOYMENT.md`).

The earlier 8-minute version of this script is in git history (commit e00716f).
