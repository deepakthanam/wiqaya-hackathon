"""SHAP top-3 drivers rendered as plain phrases. The rule citation is always shown first (in the UI)."""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
import shap

from wiqaya.models.train import CalibratedModel

warnings.filterwarnings("ignore", message="LightGBM binary classifier")


def _fmt(v: float, nd: int = 1) -> str:
    return f"{v:.{nd}f}"


PHRASES: dict[str, Any] = {
    "age": lambda v: f"Age {int(v)}",
    "sex_female": lambda v: "Female" if v else "Male",
    "bmi_last": lambda v: f"Last BMI {_fmt(v)}",
    "bmi_trend": lambda v: "BMI rising over time" if v > 0 else "BMI falling over time",
    "hba1c_last": lambda v: f"Last HbA1c {_fmt(v)}%",
    "hba1c_trend": lambda v: "HbA1c rising across tests" if v > 0 else "HbA1c stable or falling",
    "sbp_last": lambda v: f"Last systolic BP {int(v)} mmHg",
    "dbp_last": lambda v: f"Last diastolic BP {int(v)} mmHg",
    "ldl_last": lambda v: f"Last LDL {int(v)} mg/dL",
    "n_conditions": lambda v: f"{int(v)} recorded long-term condition(s)" if v else "No long-term condition recorded yet",
    "fhx_t2d": lambda v: "Family history of type 2 diabetes" if v else "No family history of type 2 diabetes",
    "fhx_cvd": lambda v: "Family history of early heart disease" if v else "No family history of early heart disease",
    "fhx_crc": lambda v: "Family history of bowel disease" if v else "No family history of bowel disease",
    "fhx_breast": lambda v: "Family history of breast disease" if v else "No family history of breast disease",
    "genomic_flag": lambda v: "Genome programme result on file (consented)" if v else "No genome programme result",
    "missed_visits": lambda v: f"{int(v)} missed appointment(s)",
    "deprivation": lambda v: "Lives in a higher-need district" if v >= 0.5 else "Lives in a lower-need district",
    "months_since_screen": lambda v: "No screening visit on record" if v >= 119 else f"{int(v)} months since last screening visit",
    "encounters_24m": lambda v: f"{int(v)} clinic visit(s) in the last 2 years",
}  # fmt: skip


NAN_PHRASES = {
    "bmi_last": "No BMI on record", "bmi_trend": "Not enough BMI readings to see a trend",
    "hba1c_last": "No HbA1c result on record", "hba1c_trend": "Not enough HbA1c results to see a trend",
    "sbp_last": "No blood pressure reading on record", "dbp_last": "No blood pressure reading on record",
    "ldl_last": "No LDL result on record",
}  # fmt: skip


def top3(model: CalibratedModel, X: pd.DataFrame) -> list[list[dict[str, Any]]]:
    """Top-3 features pushing each person's risk UP, as plain phrases."""
    explainer = shap.TreeExplainer(model.booster)
    vals = explainer.shap_values(X[model.features])
    if isinstance(vals, list):  # older shap: [neg, pos]
        vals = vals[1]
    vals = np.asarray(vals)
    if vals.ndim == 3:
        vals = vals[:, :, 1]
    out: list[list[dict[str, Any]]] = []
    feats = model.features
    Xv = X[feats].to_numpy()
    for i in range(len(X)):
        order = np.argsort(-vals[i])
        items = []
        for j in order[:3]:
            if vals[i, j] <= 0:
                break
            v = Xv[i, j]
            if isinstance(v, float) and math.isnan(v):
                phrase = NAN_PHRASES.get(feats[j], "No result on record")
            else:
                phrase = PHRASES[feats[j]](float(v))
            items.append({"feature": feats[j], "phrase": phrase, "shap": round(float(vals[i, j]), 4)})
        out.append(items)
    return out
