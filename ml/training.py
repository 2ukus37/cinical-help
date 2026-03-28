"""
ML Training Pipeline for CDSS.
Trains Logistic Regression, Random Forest, and XGBoost with calibration.
Supports: heart_disease, diabetes
"""
import os
import sys
import json
import pickle
import warnings
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.evaluation import evaluate_model
from ml.calibration import calibrate_and_evaluate
from backend.utils.database import register_model, init_db
from backend.utils.logger import model_logger

ARTIFACT_DIR = Path("backend/models")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# ── Feature definitions ────────────────────────────────────────────────────────

HEART_FEATURES = [
    "age", "sex", "chest_pain_type", "resting_bp", "cholesterol",
    "fasting_blood_sugar", "resting_ecg", "max_heart_rate",
    "exercise_angina", "st_depression", "st_slope", "num_vessels", "thal",
]

DIABETES_FEATURES = [
    "pregnancies", "glucose", "blood_pressure", "skin_thickness",
    "insulin", "bmi", "diabetes_pedigree", "age",
]

FEATURE_MAP = {
    "heart_disease": HEART_FEATURES,
    "diabetes": DIABETES_FEATURES,
}


# ── Data loading ───────────────────────────────────────────────────────────────

def load_heart_disease_data() -> pd.DataFrame:
    """Load UCI Heart Disease dataset via sklearn or fallback synthetic."""
    try:
        from sklearn.datasets import fetch_openml
        data = fetch_openml("heart-disease", version=1, as_frame=True, parser="auto")
        df = data.frame.copy()
        df.columns = HEART_FEATURES + ["target"]
        df["target"] = (df["target"].astype(float) > 0).astype(int)
        df[HEART_FEATURES] = df[HEART_FEATURES].apply(pd.to_numeric, errors="coerce")
        return df
    except Exception:
        model_logger.warning("OpenML unavailable – generating synthetic heart disease data")
        return _synthetic_heart()


def load_diabetes_data() -> pd.DataFrame:
    """Load Pima Indians Diabetes dataset."""
    try:
        from sklearn.datasets import load_diabetes as _ld
        # Use the well-known Pima dataset via OpenML
        from sklearn.datasets import fetch_openml
        data = fetch_openml("diabetes", version=1, as_frame=True, parser="auto")
        df = data.frame.copy()
        col_map = {
            "preg": "pregnancies", "plas": "glucose", "pres": "blood_pressure",
            "skin": "skin_thickness", "insu": "insulin", "mass": "bmi",
            "pedi": "diabetes_pedigree", "age": "age", "class": "target",
        }
        df.rename(columns=col_map, inplace=True)
        df["target"] = (df["target"].astype(str).str.lower() == "tested_positive").astype(int)
        df[DIABETES_FEATURES] = df[DIABETES_FEATURES].apply(pd.to_numeric, errors="coerce")
        return df
    except Exception:
        model_logger.warning("OpenML unavailable – generating synthetic diabetes data")
        return _synthetic_diabetes()


def _synthetic_heart(n=1000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "age": rng.integers(30, 80, n),
        "sex": rng.integers(0, 2, n),
        "chest_pain_type": rng.integers(0, 4, n),
        "resting_bp": rng.normal(130, 20, n).clip(80, 200),
        "cholesterol": rng.normal(240, 50, n).clip(150, 400),
        "fasting_blood_sugar": rng.integers(0, 2, n),
        "resting_ecg": rng.integers(0, 3, n),
        "max_heart_rate": rng.normal(150, 25, n).clip(80, 200),
        "exercise_angina": rng.integers(0, 2, n),
        "st_depression": rng.uniform(0, 5, n),
        "st_slope": rng.integers(0, 3, n),
        "num_vessels": rng.integers(0, 4, n),
        "thal": rng.integers(0, 4, n),
    })
    logit = (
        0.04 * df["age"] + 0.5 * df["chest_pain_type"]
        - 0.01 * df["max_heart_rate"] + 0.3 * df["exercise_angina"]
        + 0.2 * df["st_depression"] - 5
    )
    prob = 1 / (1 + np.exp(-logit))
    df["target"] = (rng.random(n) < prob).astype(int)
    return df


def _synthetic_diabetes(n=768) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "pregnancies": rng.integers(0, 15, n),
        "glucose": rng.normal(120, 30, n).clip(50, 300),
        "blood_pressure": rng.normal(70, 12, n).clip(40, 130),
        "skin_thickness": rng.normal(25, 10, n).clip(0, 80),
        "insulin": rng.normal(80, 60, n).clip(0, 500),
        "bmi": rng.normal(32, 7, n).clip(15, 60),
        "diabetes_pedigree": rng.uniform(0.08, 2.5, n),
        "age": rng.integers(21, 80, n),
    })
    logit = (
        0.03 * df["glucose"] + 0.05 * df["bmi"]
        + 0.02 * df["age"] + 0.1 * df["pregnancies"] - 8
    )
    prob = 1 / (1 + np.exp(-logit))
    df["target"] = (rng.random(n) < prob).astype(int)
    return df


# ── Pipeline builder ───────────────────────────────────────────────────────────

def build_base_pipeline(model) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", model),
    ])


def build_ensemble() -> VotingClassifier:
    lr = build_base_pipeline(
        LogisticRegression(max_iter=1000, C=1.0, random_state=42)
    )
    rf = build_base_pipeline(
        RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    )
    xgb = build_base_pipeline(
        XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42, verbosity=0,
        )
    )
    return VotingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("xgb", xgb)],
        voting="soft",
        n_jobs=-1,
    )


# ── Training entry point ───────────────────────────────────────────────────────

def train(disease: str):
    model_logger.info(f"Starting training for: {disease}")
    init_db()

    if disease == "heart_disease":
        df = load_heart_disease_data()
        features = HEART_FEATURES
        dataset_name = "UCI Heart Disease (OpenML)"
    else:
        df = load_diabetes_data()
        features = DIABETES_FEATURES
        dataset_name = "Pima Indians Diabetes (OpenML)"

    X = df[features]
    y = df["target"]

    model_logger.info(f"Dataset shape: {X.shape}, Positive rate: {y.mean():.3f}")

    # ── Stratified K-Fold CV ──────────────────────────────────────────────────
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    ensemble = build_ensemble()

    cv_aucs = cross_val_score(ensemble, X, y, cv=skf, scoring="roc_auc", n_jobs=-1)
    model_logger.info(f"CV ROC-AUC: {cv_aucs.mean():.4f} ± {cv_aucs.std():.4f}")

    # ── Final train/test split (stratified) ──────────────────────────────────
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # ── Fit ensemble ──────────────────────────────────────────────────────────
    ensemble.fit(X_train, y_train)

    # ── Calibrate ─────────────────────────────────────────────────────────────
    calibrated_model, cal_metrics = calibrate_and_evaluate(
        ensemble, X_train, y_train, X_test, y_test
    )

    # ── Full evaluation ───────────────────────────────────────────────────────
    eval_metrics = evaluate_model(calibrated_model, X_test, y_test, features, disease)
    eval_metrics.update(cal_metrics)

    # ── Persist artifact ──────────────────────────────────────────────────────
    version = f"{disease}_v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    artifact = {
        "model": calibrated_model,
        "features": features,
        "version": version,
        "disease": disease,
        "metrics": eval_metrics,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_name,
    }
    artifact_path = str(ARTIFACT_DIR / f"{disease}_pipeline.pkl")
    with open(artifact_path, "wb") as f:
        pickle.dump(artifact, f)

    # ── Register in DB ────────────────────────────────────────────────────────
    register_model(
        version=version,
        disease=disease,
        training_date=artifact["training_date"],
        dataset=dataset_name,
        calibration="isotonic",
        metrics=eval_metrics,
        artifact_path=artifact_path,
        set_active=True,
    )

    model_logger.info(f"Model saved: {artifact_path} | Version: {version}")
    print(f"\n✅ Training complete for {disease}")
    print(f"   Version  : {version}")
    print(f"   ROC-AUC  : {eval_metrics.get('roc_auc', 'N/A'):.4f}")
    print(f"   Sensitivity: {eval_metrics.get('sensitivity', 'N/A'):.4f}")
    print(f"   Brier Score: {eval_metrics.get('brier_score', 'N/A'):.4f}")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--disease", choices=["heart_disease", "diabetes"], default="heart_disease")
    args = parser.parse_args()
    train(args.disease)
