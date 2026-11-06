# Code systems and codes

Generated from `content/reference/codes.yaml` by `wiqaya docs-codes`. Do not edit by hand.

Rule: a standard code (LOINC, SNOMED CT, CVX, HL7 v3) is used only where it was verified on
tx.fhir.org or the publisher's site on 2026-11-07 (evidence: `content/reference/codes_verification.yaml`).
Everything else uses the local code system `http://wiqaya.health/CodeSystem/local`.

## Code systems

| Name | URI |
|---|---|
| loinc | http://loinc.org |
| snomed | http://snomed.info/sct |
| cvx | http://hl7.org/fhir/sid/cvx |
| rolecode | http://terminology.hl7.org/CodeSystem/v3-RoleCode |
| local | http://wiqaya.health/CodeSystem/local |

## Observations

| Key | System | Code | Display |
|---|---|---|---|
| `hba1c` | http://loinc.org | `4548-4` | Hemoglobin A1c/Hemoglobin.total in Blood |
| `bmi` | http://loinc.org | `39156-5` | Body mass index (BMI) [Ratio] |
| `sbp` | http://loinc.org | `8480-6` | Systolic blood pressure |
| `dbp` | http://loinc.org | `8462-4` | Diastolic blood pressure |
| `ldl` | http://loinc.org | `13457-7` | Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation |
| `total_chol` | http://loinc.org | `2093-3` | Cholesterol [Mass/volume] in Serum or Plasma |
| `bmi_pct` | http://loinc.org | `59576-9` | Body mass index (BMI) [Percentile] Per age and sex |
| `dev_screen` | http://wiqaya.health/CodeSystem/local | `obs-developmental-screen` | Developmental screening result (1=refer, 0=pass) |
| `autism_screen` | http://wiqaya.health/CodeSystem/local | `obs-autism-screen` | Autism screening result (1=refer, 0=pass) |
| `cytology` | http://wiqaya.health/CodeSystem/local | `obs-cervical-cytology` | Cervical cytology result (1=abnormal, 0=normal) |
| `cytology` | http://loinc.org | `19762-4` | General categories [Interpretation] of Cervical or vaginal smear or scraping by Cyto stain |
| `hpv` | http://wiqaya.health/CodeSystem/local | `obs-hpv-test` | High-risk HPV test (1=detected, 0=not detected) |
| `hpv` | http://loinc.org | `59420-0` | Human papilloma virus 16+18+31+33+35+39+45+51+52+56+58+59+66+68 DNA [Presence] in Cervix by Probe with signal amplification |
| `fit` | http://wiqaya.health/CodeSystem/local | `obs-fit` | Faecal immunochemical test (1=positive, 0=negative) |
| `fit` | http://loinc.org | `29771-3` | Hemoglobin [Presence] in Stool from gastrointestinal lower by Immunoassay |
| `mammogram` | http://wiqaya.health/CodeSystem/local | `obs-mammogram-birads` | Mammogram BI-RADS assessment category |
| `mammogram` | http://loinc.org | `24606-6` | MG Breast Screening |

## Conditions

| Key | System | Code | Display |
|---|---|---|---|
| `t2d` | http://wiqaya.health/CodeSystem/local | `cond-t2d` | Type 2 diabetes mellitus |
| `t2d` | http://snomed.info/sct | `44054006` | Type 2 diabetes mellitus |
| `t1d` | http://wiqaya.health/CodeSystem/local | `cond-t1d` | Type 1 diabetes mellitus |
| `prediabetes` | http://wiqaya.health/CodeSystem/local | `cond-prediabetes` | Prediabetes |
| `prediabetes` | http://snomed.info/sct | `714628002` | Prediabetes |
| `hypertension` | http://wiqaya.health/CodeSystem/local | `cond-hypertension` | Hypertension |
| `hypertension` | http://snomed.info/sct | `38341003` | Hypertensive disorder |
| `dyslipidaemia` | http://wiqaya.health/CodeSystem/local | `cond-dyslipidaemia` | Dyslipidaemia |
| `dyslipidaemia` | http://snomed.info/sct | `55822004` | Hyperlipidemia |
| `fh` | http://wiqaya.health/CodeSystem/local | `cond-fh` | Familial hypercholesterolaemia |
| `fh` | http://snomed.info/sct | `398036000` | Familial hypercholesterolemia |
| `developmental_delay` | http://wiqaya.health/CodeSystem/local | `cond-developmental-delay` | Developmental delay (suspected, referred) |
| `developmental_delay` | http://snomed.info/sct | `248290002` | Developmental delay |
| `cin2plus` | http://wiqaya.health/CodeSystem/local | `cond-cin2plus` | Cervical intraepithelial neoplasia grade 2 or worse |
| `colorectal_neoplasia` | http://wiqaya.health/CodeSystem/local | `cond-colorectal-adv-neoplasia` | Advanced colorectal neoplasia |
| `child_obesity` | http://wiqaya.health/CodeSystem/local | `cond-child-high-bmi` | BMI-for-age at or above 95th percentile |

## Family history

| Key | System | Code | Display |
|---|---|---|---|
| `t2d` | http://wiqaya.health/CodeSystem/local | `fhx-t2d` | Family history: type 2 diabetes |
| `premature_cvd` | http://wiqaya.health/CodeSystem/local | `fhx-premature-cvd` | Family history: premature cardiovascular disease |
| `colorectal` | http://wiqaya.health/CodeSystem/local | `fhx-colorectal` | Family history: colorectal neoplasia |
| `breast` | http://wiqaya.health/CodeSystem/local | `fhx-breast` | Family history: breast/ovarian neoplasia |

## Vaccines

| Key | System | Code | Display |
|---|---|---|---|
| `hepb` | http://wiqaya.health/CodeSystem/local | `vax-hepb` | Hepatitis B |
| `hepb` | http://hl7.org/fhir/sid/cvx | `08` | Hep B, adolescent or pediatric |
| `dtap_ipv_hib` | http://wiqaya.health/CodeSystem/local | `vax-dtap-ipv-hib` | DTaP-IPV-Hib (combination) |
| `dtap_ipv` | http://wiqaya.health/CodeSystem/local | `vax-dtap-ipv` | DTaP-IPV booster |
| `pcv` | http://wiqaya.health/CodeSystem/local | `vax-pcv` | Pneumococcal conjugate |
| `pcv` | http://hl7.org/fhir/sid/cvx | `152` | Pneumococcal Conjugate, unspecified formulation |
| `rotavirus` | http://wiqaya.health/CodeSystem/local | `vax-rotavirus` | Rotavirus |
| `rotavirus` | http://hl7.org/fhir/sid/cvx | `122` | rotavirus, unspecified formulation |
| `mmr` | http://wiqaya.health/CodeSystem/local | `vax-mmr` | Measles, mumps, rubella |
| `mmr` | http://hl7.org/fhir/sid/cvx | `03` | MMR |
| `varicella` | http://wiqaya.health/CodeSystem/local | `vax-varicella` | Varicella |
| `varicella` | http://hl7.org/fhir/sid/cvx | `21` | varicella |
| `hepa` | http://wiqaya.health/CodeSystem/local | `vax-hepa` | Hepatitis A |
| `hepa` | http://hl7.org/fhir/sid/cvx | `85` | Hep A, unspecified formulation |
| `tdap` | http://wiqaya.health/CodeSystem/local | `vax-tdap` | Tdap |
| `tdap` | http://hl7.org/fhir/sid/cvx | `115` | Tdap |
| `hpv` | http://wiqaya.health/CodeSystem/local | `vax-hpv` | HPV |
| `hpv` | http://hl7.org/fhir/sid/cvx | `165` | HPV9 |

## Genomic findings (Observation)

Modelled loosely on the HL7 FHIR Genomics Reporting IG: one `Observation` per finding with
LOINC `69548-6` *Genetic variant assessment* and a component for the gene studied (`48018-6`).
Variant references come from ClinVar and are **illustrative only**.

| Part | System | Code | Display |
|---|---|---|---|
| `panel` | http://loinc.org | `69548-6` | Genetic variant assessment |
| `gene` | http://loinc.org | `48018-6` | Gene studied [ID] |
| `variant` | http://wiqaya.health/CodeSystem/local | `obs-variant-ref` | Variant reference (ClinVar variation id; illustrative) |
| `significance` | http://wiqaya.health/CodeSystem/local | `obs-variant-significance` | Variant clinical significance |

## Encounter types (local)

| Key | Code |
|---|---|
| `wcv` | `enc-wcv` |
| `adult_screen` | `enc-adult-screen` |
| `acute` | `enc-acute` |
| `chronic_review` | `enc-chronic-review` |
| `mobile_van` | `enc-mobile-van` |

## Family relationships (HL7 v3-RoleCode)

| Internal type | Code |
|---|---|
| `mother` | `MTH` |
| `father` | `FTH` |
| `child` | `CHILD` |
| `sibling` | `SIB` |
| `spouse` | `SPS` |
| `grandparent` | `GRPRN` |
| `aunt_uncle` | `FAMMEMB` |
| `cousin` | `COUSN` |

## Care gaps (`DetectedIssue.code`, local)

| Rule | Code |
|---|---|
| ADULT_BP_SCREEN@1.0.0 | `gap-bp-screen` |
| ADULT_LIPID_CVD@1.0.0 | `gap-lipid` |
| ADULT_T2D_SCREEN@1.0.0 | `gap-t2d-screen` |
| AUTISM_SCREEN@1.0.0 | `gap-autism-screen` |
| BREAST_SCREEN@1.0.0 | `gap-breast` |
| CASCADE_BRCA@1.0.0 | `gap-cascade-brca` |
| CASCADE_FH@1.0.0 | `gap-cascade-fh` |
| CERVICAL_SCREEN@1.0.0 | `gap-cervical` |
| CHILD_BMI_FOLLOWUP@1.0.0 | `gap-child-bmi-followup` |
| COLORECTAL_SCREEN@1.0.0 | `gap-colorectal` |
| DEV_SCREEN@1.0.0 | `gap-dev-screen` |
| FOLLOWUP_BP_ELEVATED@1.0.0 | `gap-followup-bp` |
| FOLLOWUP_PREDIABETES@1.0.0 | `gap-followup-prediabetes` |
| IMMUNISATION_CATCHUP@1.0.0 | `gap-immunisation` |
| WCV_SCHEDULE@1.0.0 | `gap-wcv` |

## Other local codes

| Code | Use |
|---|---|
| `synthetic` | `meta.tag` on every resource: *Simulated cohort* |
| `consent-<category>` | `Consent.category` per consent category (clinical_data, family_links, genomic, contact_sms, contact_whatsapp, contact_call, chw_visit) |
| extension URLs under `http://wiqaya.health/StructureDefinition/` | person attributes (nationality group, literacy proxy, phone type, insurance tier, household, housing type), rule version, priority |

## Not verified (local codes used instead)

- Autism screening instrument result (M-CHAT LOINC not found)
- Mammogram BI-RADS assessment category (LOINC not found)
- Generic developmental screening result (only proprietary ASQ-specific LOINC codes exist)
- CIN 2+ grouping (SNOMED has CIN 2 `285838002`; no single CIN 2+ concept; kept local)
- Colorectal advanced neoplasia (SNOMED adenomatous polyp of colon `428054006` is narrower; kept local)
