# Model card: Wiqaya prioritisation models

Snapshot from run `sim-seed1234` (model seed 7, T0 = 2026-11-01). **Simulated cohort.** Live figures are in
`docs/EVALUATION.md` (auto-generated) and on the Planner and Admin consoles.

## Intended use
- **Use:** order and size outreach for people who **already** have a guideline-due care gap. Every flag shows its rule
  citation first, then its model drivers. A human reviews each flag, and a clinician signs off family cascade tasks.
- **Users:** care coordinators and clinicians (person level); planners (aggregates only).

## Out-of-scope uses (prohibited)
- Diagnosis, triage or any change to a clinical pathway.
- Insurance pricing, underwriting, eligibility or coverage decisions.
- Denying or delaying care. The guardrail keeps every due gap on the worklist whatever its score.
- Any use on real people before clinical validation and a DOH data-protection impact assessment.

## Model R: clinical risk elevation
| Item | Value |
|---|---|
| Algorithm | LightGBM (200 trees, 15 leaves, seed 7, deterministic) + isotonic calibration on a separate split |
| Population | Adults (≥ 18) with a screening visit in the 12 months after the reference date (T0 − 12 m) |
| Label | A condition (T2D, prediabetes, hypertension, dyslipidaemia, FH, CIN2+, colorectal neoplasia) **detected** in that window. Observed outcomes only: never latent truth, never cost |
| Features (`data_required`) | Age, sex, last BMI and BMI trend, last HbA1c and trend, last SBP/DBP, last LDL, number of conditions, family history (T2D, early CVD, colorectal, breast), genome-programme flag **only if genomic consent was granted**, missed appointments, district deprivation proxy, months since last screen, visits in 24 months |
| Excluded (by design and asserted in code) | Nationality group, preferred language, district id, insurance tier. These are **monitoring segments only** |
| Split | By person: 60% train (1,919), 20% calibration (663), 20% held-out test (616) |
| Held-out performance | AUROC **0.779**, Brier **0.124**, calibration slope **0.89**, intercept **−0.09**. Uncalibrated slope was 0.65 |
| Top drivers (gain) | Age, last SBP, last BMI, last DBP, last HbA1c, BMI trend |
| Explanations | SHAP TreeExplainer top-3 drivers that push risk up, rendered as plain phrases (`models/explain.py`) |
| Use in priority | Percentile rank among scored adults (weight 0.40). Cascade relatives get a guideline prior (≥ 0.99); children get a neutral 0.5 |

## Model N: no-show propensity
| Item | Value |
|---|---|
| Algorithm | LightGBM + isotonic calibration |
| Unit / label | One past invitation (8,297 in history); label = no attended visit within 30 days |
| Features | Past attendance rate, number of past invitations, distance to clinic, phone type, channel used, language match of the message, household size, labour accommodation |
| Held-out performance | AUROC **0.639**, Brier **0.155**, calibration slope **1.10** (1,516 invitations) |
| Top drivers | Distance, household size, language match, past attendance |
| Use | Priority weight 0.15 (a **higher** no-show risk earns **more** outreach effort), plus P(attend \| site) in the capacity fit |

## Performance by segment (held-out)
- Segments with fewer than 100 held-out people show **"Model not validated for this segment"** (`config/segments.yaml: min_eval_n`).
- **Model R:**
  - Validated: Emirati (AUROC 0.75), Indian (0.82), female (0.78), male (0.78), apartment (0.81), labour accommodation (0.79), villa (0.71).
  - Not validated (n < 100): Bangladeshi, Filipino, Other, Other Arab, Pakistani, Western, and several languages and districts.
- **Model N:** most nationality groups validated (AUROC 0.53–0.67). Filipino, Western, Tagalog and several small districts are not validated.
- **Known weakness:** discrimination is lower for villa residents (Model R) and Emirati households (Model N).
- **Fairness floor:** the fairness floor and the equity console monitor outcomes, so the ranking is not left to these models alone.

## Fairness and safety mechanisms
- **Fairness floor:** after ranking, each monitoring segment's share of slots must be at least 0.8 × its share of
  high-time-sensitivity need. Segments below the floor have their next-highest flags promoted. Every swap is logged
  (17 in this run; `fairness_log` table, Admin → Model card).
- **Small-cell suppression:** n < 11 on every aggregate.
- **Genomic privacy:** genomic features are used only with genomic consent. Genomic detail is visible to clinicians and admins only.

## Known failure modes
- **Selection bias:** labels exist only for people who were screened. People who never attend are under-represented.
- **Synthetic reality:** relationships learnt from simulated data may not hold in Abu Dhabi data.
- **Missing labs:** people with no labs depend on age and visit patterns. "No HbA1c on record" can rank as a driver, which reflects missing data, not risk biology.
- **Weak no-show model:** the no-show model has little signal, so it should not be over-interpreted.
- **Distribution shift:** a new clinic network, new channels or new invitation policies all require recalibration.

## Update policy
- Retrain and recalibrate quarterly, or when a monitored segment's calibration slope leaves 0.8–1.2, or when the
  fairness-floor adjustments double.
- Each model artefact is versioned with the run id and seed (`data/models/*.pkl`, `data/runs/models.json`).
- Any change to features, label or intended use needs clinical-governance sign-off and an updated model card.
