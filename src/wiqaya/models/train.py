"""Train, calibrate and evaluate Model R (risk elevation) and Model N (no-show).

Training uses the history period only. Person-level split: train / calibration / held-out test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from wiqaya.common import config as C
from wiqaya.models.features import FEATURES_N, FEATURES_R, risk_features, risk_labels


@dataclass
class CalibratedModel:
    name: str
    features: list[str]
    booster: lgb.LGBMClassifier
    iso: IsotonicRegression
    metrics: dict[str, Any] = field(default_factory=dict)

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.booster.predict_proba(X[self.features]))[:, 1]

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.iso.predict(self.raw(X)))


def split_people(ids: pd.Series, seed: int) -> pd.Series:
    """Deterministic person-level split: 'train' | 'cal' | 'test'."""
    s = C.cfg("simulation")["models"]
    rng = np.random.default_rng(seed)
    u = pd.Series(rng.random(len(ids)), index=ids.values)
    out = pd.Series("train", index=ids.values)
    out[u < s["test_share"]] = "test"
    out[(u >= s["test_share"]) & (u < s["test_share"] + s["calibration_share"])] = "cal"
    return out


def calibration_stats(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict[str, Any]:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    out: dict[str, Any] = {"n": int(len(y)), "prevalence": float(y.mean()), "brier": float(brier_score_loss(y, p))}
    if len(set(y)) > 1:
        lr = LogisticRegression(C=1e6).fit(logit, y)
        out["calibration_slope"] = float(lr.coef_[0][0])
        out["calibration_intercept"] = float(lr.intercept_[0])
        out["auroc"] = float(roc_auc_score(y, p))
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = 0.0, 1.0
    table = []
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum():
            table.append({"bin": i + 1, "n": int(m.sum()), "mean_predicted": float(p[m].mean()),
                          "observed_rate": float(y[m].mean())})  # fmt: skip
    out["reliability"] = table
    return out


def fit(
    name: str, X: pd.DataFrame, y: np.ndarray, split: np.ndarray, features: list[str], seed: int
) -> CalibratedModel:
    params = C.cfg("simulation")["models"]["lightgbm"]
    clf = lgb.LGBMClassifier(**params, random_state=seed, n_jobs=1, verbose=-1, deterministic=True,
                             force_row_wise=True, subsample_freq=1)  # fmt: skip
    tr, ca, te = split == "train", split == "cal", split == "test"
    clf.fit(X.loc[tr, features], y[tr])
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(clf.predict_proba(X.loc[ca, features]))[:, 1], y[ca])
    model = CalibratedModel(name, features, clf, iso)
    p_test = model.predict(X.loc[te])
    raw_test = model.raw(X.loc[te])
    model.metrics = {
        "n_train": int(tr.sum()), "n_calibration": int(ca.sum()), "n_test": int(te.sum()),
        "test_calibrated": calibration_stats(y[te], p_test),
        "test_uncalibrated": {k: v for k, v in calibration_stats(y[te], raw_test).items() if k != "reliability"},
    }  # fmt: skip
    return model


def segment_metrics(df: pd.DataFrame, y_col: str, p_col: str, segments: pd.DataFrame) -> dict[str, Any]:
    """Per-segment calibration on held-out people; segments with n < min_eval_n are 'not validated'."""
    seg_cfg = C.cfg("segments")
    min_n = seg_cfg["min_eval_n"]
    merged = df.merge(segments, on="person_id", how="left")
    out: dict[str, Any] = {}
    for seg in ("nationality_group", "preferred_language", "sex", "district_id", "housing_type", "insurance_tier",
                "age_band"):  # fmt: skip
        if seg not in merged:
            continue
        res = {}
        for val, g in merged.groupby(seg):
            if len(g) < min_n:
                res[str(val)] = {"n": int(len(g)), "status": "Model not validated for this segment"}
            else:
                st = calibration_stats(g[y_col].to_numpy(), g[p_col].to_numpy(), bins=5)
                st.pop("reliability", None)
                res[str(val)] = {**st, "status": "validated"}
        out[seg] = res
    return out


def segments_frame(people: pd.DataFrame, ref: Any) -> pd.DataFrame:
    s = people[["id", "nationality_group", "preferred_language", "sex", "district_id", "housing_type",
                "insurance_tier", "birth_date"]].rename(columns={"id": "person_id"}).copy()  # fmt: skip
    cfg = C.cfg("segments")["segments"]["age_band"]
    age = s.birth_date.map(lambda b: (ref - b).days / 365.25)
    s["age_band"] = pd.cut(age, bins=cfg["bins"], labels=cfg["labels"], right=False).astype(str)
    return s.drop(columns=["birth_date"])


def train_risk(t: dict[str, pd.DataFrame], seed: int) -> tuple[CalibratedModel, pd.DataFrame]:
    t0 = C.t0()
    window = C.cfg("simulation")["history"]["risk_label_window_months"]
    ref = t0 - timedelta(days=round(window * 30.4375))
    X = risk_features(t, ref)
    labels = risk_labels(t, ref, t0)
    data = X.merge(labels, on="person_id", how="inner").sort_values("person_id").reset_index(drop=True)
    split = split_people(data.person_id, seed).to_numpy()
    model = fit("model_r", data, data.label.to_numpy(), split, FEATURES_R, seed)
    te = data[split == "test"].copy()
    te["p"] = model.predict(te)
    model.metrics["label"] = "condition detected in the 12 months after the reference date among adults screened"
    model.metrics["reference_date"] = ref.isoformat()
    model.metrics["segments"] = segment_metrics(te[["person_id", "label", "p"]], "label", "p",
                                                segments_frame(t["people"], ref))  # fmt: skip
    model.metrics["feature_importance"] = dict(sorted(
        zip(FEATURES_R, map(int, model.booster.feature_importances_), strict=True), key=lambda kv: -kv[1]))  # fmt: skip
    return model, data


def train_noshow(training: pd.DataFrame, t: dict[str, pd.DataFrame], seed: int) -> CalibratedModel:
    data = training.sort_values(["person_id"], kind="mergesort").reset_index(drop=True)
    ids = pd.Series(sorted(data.person_id.unique()))
    split_by_person = split_people(ids, seed + 1)
    split = data.person_id.map(split_by_person).to_numpy()
    model = fit("model_n", data, data.label.to_numpy(), split, FEATURES_N, seed)
    te = data[split == "test"].copy()
    te["p"] = model.predict(te)
    model.metrics["label"] = "past invitation not followed by an attended visit within 30 days"
    model.metrics["segments"] = segment_metrics(te[["person_id", "label", "p"]], "label", "p",
                                                segments_frame(t["people"], C.t0()))  # fmt: skip
    model.metrics["feature_importance"] = dict(sorted(
        zip(FEATURES_N, map(int, model.booster.feature_importances_), strict=True), key=lambda kv: -kv[1]))  # fmt: skip
    return model
