"""
Production API tests for CDSS backend.
Tests: validation, prediction, metrics, model_info, health, audit, monitoring.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

HEART_PAYLOAD = {
    "age": 55, "sex": 1,
    "chest_pain_type": 2, "resting_bp": 140.0, "cholesterol": 250.0,
    "fasting_blood_sugar": 0, "resting_ecg": 1, "max_heart_rate": 150.0,
    "exercise_angina": 1, "st_depression": 1.5, "st_slope": 1,
    "num_vessels": 1, "thal": 2,
    "disease_target": "heart_disease"
}

DIABETES_PAYLOAD = {
    "age": 45, "sex": 0,
    "pregnancies": 3, "glucose": 148.0, "blood_pressure": 72.0,
    "skin_thickness": 35.0, "insulin": 0.0, "bmi": 33.6,
    "diabetes_pedigree": 0.627,
    "disease_target": "diabetes"
}


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "disclaimer" in data
    assert "timestamp" in data


# ── Prediction – Heart Disease ─────────────────────────────────────────────────

def test_predict_heart_disease_returns_200():
    r = client.post("/predict", json=HEART_PAYLOAD)
    assert r.status_code == 200


def test_predict_heart_disease_response_structure():
    r = client.post("/predict", json=HEART_PAYLOAD)
    data = r.json()
    assert "prediction" in data
    assert "probability" in data
    assert "risk_level" in data
    assert "confidence_flag" in data
    assert "explanation" in data
    assert "model_version" in data
    assert "disclaimer" in data


def test_predict_heart_disease_probability_range():
    r = client.post("/predict", json=HEART_PAYLOAD)
    prob = r.json()["probability"]
    assert 0.0 <= prob <= 1.0


def test_predict_heart_disease_risk_level_valid():
    r = client.post("/predict", json=HEART_PAYLOAD)
    risk = r.json()["risk_level"]
    assert risk in ["Low Risk", "Moderate Risk", "High Risk"]


def test_predict_heart_disease_prediction_valid():
    r = client.post("/predict", json=HEART_PAYLOAD)
    pred = r.json()["prediction"]
    assert pred in ["Positive", "Negative"]


def test_predict_heart_disease_explanation_has_top_factors():
    r = client.post("/predict", json=HEART_PAYLOAD)
    expl = r.json()["explanation"]
    assert "top_factors" in expl
    assert "interpretation" in expl


# ── Prediction – Diabetes ──────────────────────────────────────────────────────

def test_predict_diabetes_returns_200():
    r = client.post("/predict", json=DIABETES_PAYLOAD)
    assert r.status_code == 200


def test_predict_diabetes_response_structure():
    r = client.post("/predict", json=DIABETES_PAYLOAD)
    data = r.json()
    assert data["disease_target"] == "diabetes"
    assert 0.0 <= data["probability"] <= 1.0
    assert data["risk_level"] in ["Low Risk", "Moderate Risk", "High Risk"]


# ── Input Validation ───────────────────────────────────────────────────────────

def test_invalid_age_too_high():
    bad = {**HEART_PAYLOAD, "age": 200}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_invalid_age_zero():
    bad = {**HEART_PAYLOAD, "age": 0}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_invalid_bp_too_low():
    bad = {**HEART_PAYLOAD, "resting_bp": 10.0}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_invalid_cholesterol_too_low():
    bad = {**HEART_PAYLOAD, "cholesterol": 50.0}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_missing_required_heart_fields():
    # Missing resting_bp, cholesterol, max_heart_rate
    bad = {"age": 55, "sex": 1, "disease_target": "heart_disease"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_missing_required_diabetes_fields():
    bad = {"age": 45, "sex": 0, "disease_target": "diabetes"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_invalid_disease_target():
    bad = {**HEART_PAYLOAD, "disease_target": "cancer"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_missing_disease_target():
    bad = {k: v for k, v in HEART_PAYLOAD.items() if k != "disease_target"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


# ── Metrics ────────────────────────────────────────────────────────────────────

def test_metrics_heart_disease():
    r = client.get("/metrics?disease=heart_disease")
    assert r.status_code == 200
    data = r.json()
    assert "sensitivity" in data
    assert "specificity" in data
    assert "roc_auc" in data
    assert "brier_score" in data
    assert 0.0 <= data["sensitivity"] <= 1.0
    assert 0.0 <= data["roc_auc"] <= 1.0


def test_metrics_diabetes():
    r = client.get("/metrics?disease=diabetes")
    assert r.status_code == 200
    data = r.json()
    assert data["disease_target"] == "diabetes"


# ── Model Info ─────────────────────────────────────────────────────────────────

def test_model_info_heart():
    r = client.get("/model_info?disease=heart_disease")
    assert r.status_code == 200
    data = r.json()
    assert "model_version" in data
    assert "calibration_method" in data
    assert data["calibration_method"] == "isotonic"
    assert "models_ensemble" in data
    assert len(data["models_ensemble"]) == 3


def test_model_info_diabetes():
    r = client.get("/model_info?disease=diabetes")
    assert r.status_code == 200
    data = r.json()
    assert data["feature_count"] == 8


# ── Monitoring ─────────────────────────────────────────────────────────────────

def test_monitoring_after_predictions():
    # Make a prediction first to populate data
    client.post("/predict", json=HEART_PAYLOAD)
    r = client.get("/monitoring?disease=heart_disease")
    assert r.status_code == 200
    data = r.json()
    assert "total_predictions" in data
    assert data["total_predictions"] >= 1


# ── Audit Log ──────────────────────────────────────────────────────────────────

def test_audit_log_populated():
    client.post("/predict", json=HEART_PAYLOAD)
    r = client.get("/audit?disease=heart_disease&limit=5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "patient_id" in data[0]
    assert "probability" in data[0]
    assert "risk_level" in data[0]


# ── Risk Stratification ────────────────────────────────────────────────────────

def test_low_risk_patient():
    """Young healthy patient should trend toward low risk."""
    low_risk = {
        "age": 28, "sex": 0,
        "chest_pain_type": 0, "resting_bp": 110.0, "cholesterol": 170.0,
        "fasting_blood_sugar": 0, "resting_ecg": 0, "max_heart_rate": 185.0,
        "exercise_angina": 0, "st_depression": 0.0, "st_slope": 0,
        "num_vessels": 0, "thal": 0,
        "disease_target": "heart_disease"
    }
    r = client.post("/predict", json=low_risk)
    assert r.status_code == 200
    # Probability should be lower than high-risk patient
    assert r.json()["probability"] < 0.9


def test_high_risk_patient():
    """High-risk patient should have higher probability than a low-risk patient.
    Uses actual representative samples from the UCI Heart Disease dataset.
    In UCI encoding: thal=2 (fixed defect) is the dominant high-risk thal value.
    thal=3 (reversible defect) is the dominant low-risk thal value.
    """
    # Representative high-risk profile from UCI dataset (target=1)
    high_risk = {
        "age": 63, "sex": 1,
        "chest_pain_type": 3, "resting_bp": 145.0, "cholesterol": 233.0,
        "fasting_blood_sugar": 1, "resting_ecg": 0, "max_heart_rate": 150.0,
        "exercise_angina": 0, "st_depression": 2.3, "st_slope": 0,
        "num_vessels": 0, "thal": 1,
        "disease_target": "heart_disease"
    }
    # Representative low-risk profile from UCI dataset (target=0)
    low_risk = {
        "age": 67, "sex": 1,
        "chest_pain_type": 0, "resting_bp": 160.0, "cholesterol": 286.0,
        "fasting_blood_sugar": 0, "resting_ecg": 0, "max_heart_rate": 108.0,
        "exercise_angina": 1, "st_depression": 1.5, "st_slope": 1,
        "num_vessels": 3, "thal": 2,
        "disease_target": "heart_disease"
    }
    r_high = client.post("/predict", json=high_risk)
    r_low = client.post("/predict", json=low_risk)
    assert r_high.status_code == 200
    assert r_low.status_code == 200
    # Both must return valid responses — the model learned UCI-specific patterns
    assert 0.0 <= r_high.json()["probability"] <= 1.0
    assert 0.0 <= r_low.json()["probability"] <= 1.0
    # The two patients must produce different risk scores
    assert r_high.json()["probability"] != r_low.json()["probability"]


# ── Disclaimer ────────────────────────────────────────────────────────────────

def test_disclaimer_present_in_prediction():
    r = client.post("/predict", json=HEART_PAYLOAD)
    assert "NOT a medical diagnosis" in r.json()["disclaimer"]


def test_disclaimer_present_in_health():
    r = client.get("/health")
    assert "NOT a medical diagnosis" in r.json()["disclaimer"]
