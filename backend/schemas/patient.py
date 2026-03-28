"""
Pydantic schemas for patient input validation with clinical range checks.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from enum import Enum


class DiseaseTarget(str, Enum):
    heart_disease = "heart_disease"
    diabetes = "diabetes"


class PatientInput(BaseModel):
    # Demographics
    age: int = Field(..., ge=1, le=120, description="Patient age in years")
    sex: int = Field(..., ge=0, le=1, description="Sex: 0=Female, 1=Male")

    # Heart Disease specific features
    chest_pain_type: Optional[int] = Field(None, ge=0, le=3, description="Chest pain type (0-3)")
    resting_bp: Optional[float] = Field(None, ge=50, le=250, description="Resting blood pressure (mmHg)")
    cholesterol: Optional[float] = Field(None, ge=100, le=600, description="Serum cholesterol (mg/dL)")
    fasting_blood_sugar: Optional[int] = Field(None, ge=0, le=1, description="Fasting blood sugar > 120 mg/dL")
    resting_ecg: Optional[int] = Field(None, ge=0, le=2, description="Resting ECG results (0-2)")
    max_heart_rate: Optional[float] = Field(None, ge=60, le=220, description="Maximum heart rate achieved")
    exercise_angina: Optional[int] = Field(None, ge=0, le=1, description="Exercise-induced angina")
    st_depression: Optional[float] = Field(None, ge=-5.0, le=10.0, description="ST depression induced by exercise")
    st_slope: Optional[int] = Field(None, ge=0, le=2, description="Slope of peak exercise ST segment")
    num_vessels: Optional[int] = Field(None, ge=0, le=4, description="Number of major vessels colored by fluoroscopy")
    thal: Optional[int] = Field(None, ge=0, le=3, description="Thalassemia type")

    # Diabetes specific features
    pregnancies: Optional[int] = Field(None, ge=0, le=20, description="Number of pregnancies")
    glucose: Optional[float] = Field(None, ge=0, le=500, description="Plasma glucose concentration (mg/dL)")
    blood_pressure: Optional[float] = Field(None, ge=0, le=200, description="Diastolic blood pressure (mmHg)")
    skin_thickness: Optional[float] = Field(None, ge=0, le=100, description="Triceps skin fold thickness (mm)")
    insulin: Optional[float] = Field(None, ge=0, le=1000, description="2-Hour serum insulin (mu U/ml)")
    bmi: Optional[float] = Field(None, ge=10.0, le=70.0, description="Body mass index (kg/m²)")
    diabetes_pedigree: Optional[float] = Field(None, ge=0.0, le=3.0, description="Diabetes pedigree function")

    # Target disease
    disease_target: DiseaseTarget = Field(..., description="Disease to predict")

    @field_validator("resting_bp")
    @classmethod
    def validate_bp(cls, v):
        if v is not None and v < 50:
            raise ValueError("Resting BP below 50 mmHg is physiologically implausible")
        return v

    @field_validator("cholesterol")
    @classmethod
    def validate_cholesterol(cls, v):
        if v is not None and v < 100:
            raise ValueError("Cholesterol below 100 mg/dL is clinically implausible")
        return v

    @field_validator("glucose")
    @classmethod
    def validate_glucose(cls, v):
        if v is not None and v > 500:
            raise ValueError("Glucose above 500 mg/dL requires immediate emergency care")
        return v

    @model_validator(mode="after")
    def validate_disease_features(self):
        if self.disease_target == DiseaseTarget.heart_disease:
            required = ["resting_bp", "cholesterol", "max_heart_rate"]
            missing = [f for f in required if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Heart disease prediction requires: {missing}")
        elif self.disease_target == DiseaseTarget.diabetes:
            required = ["glucose", "bmi"]
            missing = [f for f in required if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Diabetes prediction requires: {missing}")
        return self


class PredictionResponse(BaseModel):
    patient_id: str
    disease_target: str
    prediction: str
    probability: float
    risk_level: str
    confidence_flag: str
    explanation: dict
    clinical_narrative: str = ""
    model_version: str
    disclaimer: str = (
        "⚠️ This system is NOT a medical diagnosis tool. "
        "It is for clinical decision support only. "
        "All predictions must be reviewed by a qualified clinician."
    )


class MetricsResponse(BaseModel):
    model_version: str
    disease_target: str
    sensitivity: float
    specificity: float
    roc_auc: float
    pr_auc: float
    brier_score: float
    training_date: str
    dataset: str
    total_predictions: int


class ModelInfoResponse(BaseModel):
    model_version: str
    disease_target: str
    training_date: str
    dataset: str
    calibration_method: str
    models_ensemble: list
    feature_count: int
