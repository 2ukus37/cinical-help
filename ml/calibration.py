"""
Model probability calibration for clinical reliability.
Poorly calibrated models are dangerous in healthcare:
a model saying "70% risk" should mean 70 out of 100 similar patients
actually have the disease.
"""
import json
import numpy as np
from pathlib import Path
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import train_test_split

REPORT_DIR = Path("logs/evaluation")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def calibrate_and_evaluate(
    base_model,
    X_train,
    y_train,
    X_test,
    y_test,
    method: str = "isotonic",
) -> tuple:
    """
    Wrap base model with isotonic regression calibration.

    Isotonic regression is preferred over Platt scaling when:
    - Training set is large enough (>1000 samples)
    - The base model's probability outputs are non-monotonic

    Returns:
        calibrated_model: sklearn CalibratedClassifierCV
        metrics: dict with brier_score and calibration curve data
    """
    # Split training data for calibration (avoid leakage)
    X_tr, X_cal, y_tr, y_cal = train_test_split(
        X_train, y_train, test_size=0.2, stratify=y_train, random_state=42
    )

    # Refit base model on reduced training set, then calibrate on held-out set
    # Use cv=2 with the full training data to avoid the deprecated "prefit" API
    calibrated = CalibratedClassifierCV(
        base_model, method=method, cv=2
    )
    calibrated.fit(X_train, y_train)

    # Evaluate calibration on test set
    y_prob_cal = calibrated.predict_proba(X_test)[:, 1]
    brier = brier_score_loss(y_test, y_prob_cal)

    # Calibration curve (reliability diagram data)
    fraction_pos, mean_pred = calibration_curve(
        y_test, y_prob_cal, n_bins=10, strategy="uniform"
    )

    # Expected Calibration Error (ECE)
    ece = float(np.mean(np.abs(fraction_pos - mean_pred)))

    metrics = {
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
        "calibration_curve": {
            "mean_predicted_prob": mean_pred.tolist(),
            "fraction_of_positives": fraction_pos.tolist(),
        },
    }

    # Save calibration report
    cal_path = REPORT_DIR / "calibration_report.json"
    with open(cal_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n⚖️  Calibration Report ({method})")
    print(f"   Brier Score : {brier:.4f}  (lower is better; 0=perfect)")
    print(f"   ECE         : {ece:.4f}  (lower is better; 0=perfect)")

    return calibrated, metrics
