"""
Core prediction service: loads model, runs inference, applies risk stratification,
computes SHAP explanations, and enforces confidence thresholds.
"""
import pickle
import uuid
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from backend.schemas.patient import PatientInput, DiseaseTarget
from backend.utils.database import log_prediction, get_active_model
from backend.utils.logger import audit_logger, model_logger
from backend.services.llm_service import generate_clinical_narrative
from ml.evaluation import compute_shap_local

ARTIFACT_DIR = Path("backend/models")

# ── Risk stratification thresholds ────────────────────────────────────────────
RISK_THRESHOLDS = {
    "low":      (0.0,  0.30),
    "moderate": (0.30, 0.60),
    "high":     (0.60, 1.01),
}

CONFIDENCE_THRESHOLD = 0.65  # Below this → flag for clinical review

_model_cache: dict = {}


def _load_model(disease: str) -> dict:
    """Load model artifact from disk with in-memory caching."""
    if disease in _model_cache:
        return _model_cache[disease]

    artifact_path = ARTIFACT_DIR / f"{disease}_pipeline.pkl"
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"No trained model found for '{disease}'. "
            f"Run: python ml/training.py --disease {disease}"
        )

    with open(artifact_path, "rb") as f:
        artifact = pickle.load(f)

    _model_cache[disease] = artifact
    model_logger.info(f"Loaded model: {artifact['version']}")
    return artifact


def invalidate_cache(disease: Optional[str] = None):
    """Force reload of model from disk (after retraining)."""
    if disease:
        _model_cache.pop(disease, None)
    else:
        _model_cache.clear()


def _stratify_risk(probability: float) -> str:
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= probability < high:
            return level.capitalize() + " Risk"
    return "High Risk"


def _build_feature_df(patient: PatientInput, features: list) -> pd.DataFrame:
    """Convert PatientInput to a DataFrame row matching model feature order."""
    data = patient.model_dump(exclude={"disease_target"})
    row = {feat: data.get(feat, np.nan) for feat in features}
    return pd.DataFrame([row])


def predict(patient: PatientInput) -> dict:
    disease = patient.disease_target.value
    patient_id = str(uuid.uuid4())[:8].upper()

    # Load model
    artifact = _load_model(disease)
    model = artifact["model"]
    features = artifact["features"]
    version = artifact["version"]

    # Build feature matrix
    X = _build_feature_df(patient, features)

    # Inference
    probability = float(model.predict_proba(X)[0, 1])
    prediction = "Positive" if probability >= 0.5 else "Negative"
    risk_level = _stratify_risk(probability)

    # Confidence flag
    distance_from_boundary = abs(probability - 0.5)
    if probability < CONFIDENCE_THRESHOLD and probability > (1 - CONFIDENCE_THRESHOLD):
        confidence_flag = "UNCERTAIN – Requires Clinical Review"
    elif distance_from_boundary < 0.15:
        confidence_flag = "LOW CONFIDENCE – Borderline prediction"
    else:
        confidence_flag = "CONFIDENT"

    # SHAP local explanation
    explanation = compute_shap_local(model, X.values, features)

    # LLM clinical narrative
    narrative = generate_clinical_narrative(
        disease=disease,
        prediction=prediction,
        probability=probability,
        risk_level=risk_level,
        confidence_flag=confidence_flag,
        explanation=explanation,
    )

    # Audit log
    input_dict = patient.model_dump()
    log_prediction(
        patient_id=patient_id,
        disease=disease,
        input_data=input_dict,
        prediction=prediction,
        probability=round(probability, 4),
        risk_level=risk_level,
        confidence=confidence_flag,
        model_ver=version,
    )

    audit_logger.info(
        f"PREDICTION | patient={patient_id} disease={disease} "
        f"result={prediction} prob={probability:.4f} risk={risk_level} "
        f"confidence={confidence_flag} model={version}"
    )

    return {
        "patient_id": patient_id,
        "disease_target": disease,
        "prediction": prediction,
        "probability": round(probability, 4),
        "risk_level": risk_level,
        "confidence_flag": confidence_flag,
        "explanation": explanation,
        "clinical_narrative": narrative,
        "model_version": version,
    }


def get_model_metrics(disease: str) -> dict:
    artifact = _load_model(disease)
    return {
        "model_version": artifact["version"],
        "disease_target": disease,
        "training_date": artifact["training_date"],
        "dataset": artifact["dataset"],
        **artifact.get("metrics", {}),
    }


def get_model_info(disease: str) -> dict:
    artifact = _load_model(disease)
    return {
        "model_version": artifact["version"],
        "disease_target": disease,
        "training_date": artifact["training_date"],
        "dataset": artifact["dataset"],
        "calibration_method": "isotonic",
        "models_ensemble": ["LogisticRegression", "RandomForest", "XGBoost"],
        "feature_count": len(artifact["features"]),
        "features": artifact["features"],
    }
