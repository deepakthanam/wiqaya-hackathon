# Assumptions and limitations

> **Wiqaya is a prototype running on a simulated cohort.** It ranks outreach; it does not diagnose and does not change any
> clinical pathway. Nothing here is real-world evidence of benefit.

## 1. Non-diagnostic positioning
- Flags are **population prioritisation, not clinical decisions**. Every guideline-due gap stays on the worklist; the
  score changes only the order and intensity of outreach.
- Cascade (family) tasks are clinician tasks. They never auto-contact anyone, and they need clinician sign-off plus the
  index person's consent to share before any message is sent. Messages to relatives never name the relative or a condition.

## 2. Synthetic data and placeholder parameters
- **Every person-level record is synthetic.** No organiser, employer, client or real personal data is used.
- **Every numeric value in `config/population.yaml` is a placeholder assumption.** That covers:
  - nationality mix, household composition, district weights, deprivation proxy;
  - language, literacy, phone type and insurance shares;
  - condition model coefficients, FH founder prevalence, consanguinity share, HBB and BRCA rates;
  - genome-programme participation, consent rates, attendance behaviour, test sensitivity and specificity.

  Each should be replaced with a published SCAD or DOH figure before any calibration claim.
- **Consanguinity raising recessive-carrier co-occurrence** is a modelling assumption only.
- **Response-model parameters** (`config/simulation.yaml: response_model`) are assumptions: channel propensity,
  language match, distance, bundling, van, literacy, repeat touches.
- **Capacity** is set to about 15% of open gaps over 12 weeks (`config/capacity.yaml`), deliberately below need.
  Clinic slot splits and the van rota are assumptions.

## 3. Simulator circularity and the sensitivity analysis
- The simulator's response model was written by the same team as Wiqaya. Language match, bundling and the van help in
  the simulator *because we assumed they help*. The main result (completed visits per 100 contacts) therefore partly
  reflects our own assumptions.
- Safeguards:
  - Wiqaya's models never read the response parameters or the latent truth.
  - Both policies share capacity, invitation budget and random draws (common random numbers).
  - `make sensitivity` re-runs both policies with a weaker language effect, weaker bundling and van effects, and a stronger distance penalty.
- Results are reported in `docs/EVALUATION.md`. The advantage persists in every scenario, but its **size** depends on
  effects that have not been measured in Abu Dhabi. Only a randomised pilot can establish it.
- **Reach trade-off.** Wiqaya contacts fewer distinct people than the baseline (repeat touches, CHW visits and bundles
  for prioritised people instead of one SMS to everyone) and completes more visits. A pilot should set this balance
  explicitly (`invites_per_slot`, `max_touches`).

## 4. Rules and guidelines
- **All 15 rules are demo encodings** (`status: demo_encoding_requires_clinical_validation`). Each cites a guideline,
  year and URL that was fetched on 2026-11-07, but none has been reviewed by a clinician.
- Local assumptions inside rules are listed in each rule's `assumptions`:
  - T2D early eligibility from age 25 with family history;
  - 60-month lipid interval;
  - 130/80 trigger and 3-month recheck for elevated BP;
  - first-degree-only cascade (NICE also covers second- and third-degree relatives);
  - FIT-only colorectal strategy;
  - hysterectomy and adequate prior screening not modelled.
- **The immunisation schedule is a placeholder** modelled on the CDC schedule. The Abu Dhabi schedule (DOH/ADPHC
  Circular 2026/77) has been located but is not yet encoded.
- **The WCV schedule** follows the AAP/Bright Futures periodicity schedule and should be replaced with the DOH schedule.
- US and UK guidelines are used as stand-ins where the equivalent UAE guidance was not encoded. Thresholds and intervals
  may differ locally.

## 5. Codes
- Standard codes are used only where verified on tx.fhir.org (see `docs/CODES.md`). The following use local codes:
  - BI-RADS, autism (M-CHAT) and generic developmental screening results;
  - CIN2+;
  - advanced colorectal neoplasia;
  - combination vaccines.
- Variant references are real ClinVar records attached to **synthetic** findings. They are illustrative only.

## 6. Translations and language
- **English templates are human-written. Arabic, Urdu, Hindi, Malayalam and Tagalog are machine drafts** that need
  native-speaker review. The Admin console flags this, and every preview carries an English gloss.
  `docs/TRANSLATION_REVIEW_NOTES.md` lists what to check first.
- **Bengali speakers receive English messages.** There are no Bengali templates yet. This shows up as a language
  mismatch in the equity console.
- Clinic names inside non-English messages stay in English.

## 7. Models
- **Model R** is trained and validated on simulated history only.
  - Held-out AUROC about 0.78, calibration slope about 0.89 after isotonic calibration.
  - The label (a condition detected after a screening visit) exists only for people who were screened, so the model inherits that selection.
  - Several segments have fewer than 100 held-out people and show "Model not validated for this segment".
- **Model N** (no-show) is weak: held-out AUROC about 0.64. It is used only to plan outreach effort and estimate attendance per site.
- **Children** have no Model R score. Their risk component is neutral (0.5), and their order comes from rule time sensitivity.
- **No external validation** is possible without real data.
- **Uplift model:** not built (first item in the brief's cut order). The history includes randomised-channel invitations so it can be added.

## 8. Capacity optimisation
- The CP-SAT site assignment runs per group of connected sites with a deterministic time budget, so it is reproducible.
  Most groups end FEASIBLE rather than proven OPTIMAL. Weeks are then filled deterministically by rank.
- About 3,800 of 4,735 slots are used: some buckets (slot type × site × week) have no eligible candidate within the travel limits.

## 9. FHIR and infrastructure
- By default only a sample of about 2,000 people plus the personas is loaded into HAPI (`FHIR_LOAD=sample`), so the full
  load fits on a laptop. Person pages for people outside the sample come from DuckDB with a banner.
- Care gaps are written as `DetectedIssue` and simulated detections as provisional `Condition` NDJSON in the run folder.
  Simulated detections are not loaded into HAPI by default.
- Guest sessions keep decisions and preferences in memory for 2 hours. Nothing a guest does changes the base data, and
  the overlays are lost when the API restarts.

## 10. What a pilot would need
- Clinical validation of every rule.
- Replacement of placeholder parameters with SCAD/DOH aggregates.
- The Abu Dhabi immunisation and WCV schedules.
- Native-speaker review of the translations, and Bengali templates.
- A Malaffi read interface.
- A DOH data-protection impact assessment.
- A randomised outreach pilot to measure the real effects of language match, bundling and channel choice.
