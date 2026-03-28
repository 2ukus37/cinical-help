"""
CDSS FastAPI Backend – Production Entry Point
"""
import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.schemas.patient import (
    PatientInput, PredictionResponse, MetricsResponse, ModelInfoResponse, DiseaseTarget
)
from backend.services.prediction_service import predict, get_model_metrics, get_model_info
from backend.services.monitoring_service import get_prediction_distribution
from backend.services.document_service import process_upload
from backend.utils.database import init_db, log_invalid_input, get_prediction_count
from backend.utils.logger import audit_logger

# ── App setup ──────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    audit_logger.info("CDSS backend started")
    yield

app = FastAPI(
    title="Clinical Decision Support System",
    description=(
        "⚠️ DISCLAIMER: This system is NOT a medical diagnosis tool. "
        "It is for clinical decision support only. "
        "All predictions must be reviewed by a qualified clinician."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DISCLAIMER = (
    "⚠️ This system is NOT a medical diagnosis tool. "
    "It is for clinical decision support only. "
    "All predictions must be reviewed by a qualified clinician."
)


# ── Exception handlers ─────────────────────────────────────────────────────────

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    log_invalid_input(body, str(exc))
    audit_logger.warning(f"INVALID_INPUT | path={request.url.path} errors={exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "Clinical input validation failed"},
    )


@app.exception_handler(FileNotFoundError)
async def model_not_found_handler(request: Request, exc: FileNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc), "message": "Model not trained yet"},
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "disclaimer": DISCLAIMER,
    }


# ── Prediction ─────────────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictionResponse, tags=["Inference"])
def predict_endpoint(patient: PatientInput):
    """
    Run disease risk prediction for a patient.

    Returns:
    - prediction: Positive / Negative
    - probability: calibrated probability [0, 1]
    - risk_level: Low / Moderate / High Risk
    - confidence_flag: CONFIDENT / LOW CONFIDENCE / UNCERTAIN
    - explanation: SHAP top contributing factors
    """
    try:
        result = predict(patient)
        result["disclaimer"] = DISCLAIMER
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        audit_logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# ── Metrics ────────────────────────────────────────────────────────────────────

@app.get("/metrics", response_model=MetricsResponse, tags=["Model"])
def metrics_endpoint(disease: DiseaseTarget = DiseaseTarget.heart_disease):
    """Return clinical performance metrics for the active model."""
    try:
        m = get_model_metrics(disease.value)
        return {
            "model_version": m.get("model_version", "unknown"),
            "disease_target": disease.value,
            "sensitivity": m.get("sensitivity", 0.0),
            "specificity": m.get("specificity", 0.0),
            "roc_auc": m.get("roc_auc", 0.0),
            "pr_auc": m.get("pr_auc", 0.0),
            "brier_score": m.get("brier_score", 0.0),
            "training_date": m.get("training_date", "unknown"),
            "dataset": m.get("dataset", "unknown"),
            "total_predictions": get_prediction_count(disease.value),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Model Info ─────────────────────────────────────────────────────────────────

@app.get("/model_info", response_model=ModelInfoResponse, tags=["Model"])
def model_info_endpoint(disease: DiseaseTarget = DiseaseTarget.heart_disease):
    """Return model versioning and architecture details."""
    try:
        return get_model_info(disease.value)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Monitoring ─────────────────────────────────────────────────────────────────

@app.get("/monitoring", tags=["Monitoring"])
def monitoring_endpoint(disease: DiseaseTarget = DiseaseTarget.heart_disease):
    """Return prediction distribution and drift indicators."""
    return get_prediction_distribution(disease.value)


# ── Document Upload ────────────────────────────────────────────────────────────

@app.post("/upload-document", tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a medical document (CT scan, lab report, ECG, PDF).
    Returns extracted clinical values ready to pre-fill the prediction form.
    Supported: PDF, JPG, PNG, WEBP (max 10MB)
    """
    try:
        file_bytes = await file.read()
        content_type = file.content_type or "application/octet-stream"
        result = process_upload(file_bytes, file.filename or "upload", content_type)
        if "error" in result and len(result) <= 2:
            raise HTTPException(status_code=422, detail=result["error"])
        return {
            "status": "parsed",
            "filename": file.filename,
            "extracted_fields": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        audit_logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


# ── Audit Log ──────────────────────────────────────────────────────────────────

@app.get("/audit", tags=["Governance"])
def audit_endpoint(disease: DiseaseTarget = DiseaseTarget.heart_disease, limit: int = 50):
    """Return recent audit log entries from the database."""
    from backend.utils.database import get_conn
    import json
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE disease=? ORDER BY id DESC LIMIT ?",
            (disease.value, limit),
        ).fetchall()
    return [dict(r) for r in rows]
