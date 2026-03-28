"""
Clinical evaluation metrics for CDSS models.
Sensitivity is prioritized because in healthcare, missing a true positive
(false negative) is far more dangerous than a false alarm (false positive).
A missed heart disease or diabetes diagnosis can be life-threatening.
"""
import numpy as np
import json
from pathlib import Path
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
    brier_score_loss,
)
import shap

REPORT_DIR = Path("logs/evaluation")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_model(model, X_test, y_test, features: list, disease: str) -> dict:
    """
    Compute full clinical evaluation suite.

    Why sensitivity matters in healthcare:
    - A false negative (missed disease) can lead to untreated conditions,
      disease progression, and preventable death.
    - A false positive triggers further testing, not immediate harm.
    - Therefore, we optimize for high sensitivity (recall ≥ 0.85) even at
      the cost of some specificity.
    """
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    roc_auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    metrics = {
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }

    # Clinical sensitivity warning
    if sensitivity < 0.80:
        print(f"⚠️  WARNING: Sensitivity {sensitivity:.3f} < 0.80 – model may miss too many positive cases")

    # Save report
    report = classification_report(y_test, y_pred, output_dict=True)
    report_path = REPORT_DIR / f"{disease}_eval.json"
    with open(report_path, "w") as f:
        json.dump({"metrics": metrics, "classification_report": report}, f, indent=2)

    print(f"\n📊 Clinical Evaluation – {disease}")
    print(f"   Sensitivity (Recall+): {sensitivity:.4f}")
    print(f"   Specificity          : {specificity:.4f}")
    print(f"   ROC-AUC              : {roc_auc:.4f}")
    print(f"   PR-AUC               : {pr_auc:.4f}")
    print(f"   Brier Score          : {brier:.4f}")
    print(f"   Confusion Matrix     : TP={tp} TN={tn} FP={fp} FN={fn}")

    return metrics


def compute_shap_global(model, X_train, features: list, disease: str) -> dict:
    """Compute global SHAP feature importance using TreeExplainer or KernelExplainer."""
    try:
        # Try to get the underlying XGB estimator for TreeExplainer
        xgb_pipe = None
        if hasattr(model, "estimators_"):
            for name, est in model.estimators_:
                if "xgb" in name:
                    xgb_pipe = est
                    break

        if xgb_pipe is not None:
            # Use the scaler-transformed data
            X_transformed = xgb_pipe.named_steps["imputer"].transform(X_train)
            X_transformed = xgb_pipe.named_steps["scaler"].transform(X_transformed)
            explainer = shap.TreeExplainer(xgb_pipe.named_steps["model"])
            shap_values = explainer.shap_values(X_transformed)
        else:
            # Fallback: KernelExplainer on a sample
            sample = X_train.sample(min(100, len(X_train)), random_state=42)
            explainer = shap.KernelExplainer(
                lambda x: model.predict_proba(x)[:, 1], sample
            )
            shap_values = explainer.shap_values(sample)

        mean_abs = np.abs(shap_values).mean(axis=0)
        importance = dict(zip(features, mean_abs.tolist()))
        sorted_imp = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        # Save
        shap_path = REPORT_DIR / f"{disease}_shap_global.json"
        with open(shap_path, "w") as f:
            json.dump(sorted_imp, f, indent=2)

        return sorted_imp
    except Exception as e:
        print(f"⚠️  SHAP global computation failed: {e}")
        return {}


def compute_shap_local(model, X_instance: np.ndarray, features: list) -> dict:
    """
    Compute local SHAP explanation for a single patient prediction.
    Extracts the XGBoost sub-pipeline from the VotingClassifier for reliable
    TreeExplainer-based attribution. Falls back to feature importance if SHAP fails.
    Returns top contributing factors with direction (positive = increases risk).
    """
    try:
        # Unwrap: CalibratedClassifierCV → _CalibratedClassifier → VotingClassifier
        base = model
        if hasattr(base, "calibrated_classifiers_"):
            base = base.calibrated_classifiers_[0].estimator

        # VotingClassifier: named_estimators_ maps name → Pipeline
        xgb_pipe = None
        if hasattr(base, "named_estimators_"):
            xgb_pipe = base.named_estimators_.get("xgb")

        if xgb_pipe is None:
            raise ValueError("XGB pipeline not found in ensemble")

        # Transform through imputer + scaler
        X_t = xgb_pipe.named_steps["imputer"].transform(X_instance)
        X_t = xgb_pipe.named_steps["scaler"].transform(X_t)
        xgb_model = xgb_pipe.named_steps["model"]

        explainer = shap.TreeExplainer(xgb_model)
        shap_vals = explainer.shap_values(X_t)

        # For binary XGBoost, shap_values returns shape (n_samples, n_features)
        shap_row = shap_vals[0] if shap_vals.ndim == 2 else shap_vals

        contributions = {
            feat: round(float(val), 4)
            for feat, val in zip(features, shap_row)
        }
        top_factors = dict(
            sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        )
        return {
            "top_factors": top_factors,
            "interpretation": {
                k: ("increases risk" if v > 0 else "decreases risk")
                for k, v in top_factors.items()
            },
        }
    except Exception as e:
        # Fallback: use XGB feature importances as directional proxy
        try:
            base = model
            if hasattr(base, "calibrated_classifiers_"):
                base = base.calibrated_classifiers_[0].estimator
            xgb_pipe = base.named_estimators_.get("xgb")
            if xgb_pipe:
                xgb_model = xgb_pipe.named_steps["model"]
                imp = xgb_model.feature_importances_
                row_vals = X_instance[0] if X_instance.ndim == 2 else X_instance
                # Use median of training data as direction baseline (0 after scaling)
                signed = {
                    feat: round(float(imp[i]) * (1.0 if row_vals[i] >= 0 else -1.0), 4)
                    for i, feat in enumerate(features)
                }
                top = dict(sorted(signed.items(), key=lambda x: abs(x[1]), reverse=True)[:5])
                return {
                    "top_factors": top,
                    "interpretation": {
                        k: ("increases risk" if v > 0 else "decreases risk")
                        for k, v in top.items()
                    },
                    "method": "feature_importance_fallback",
                }
        except Exception:
            pass
        return {"error": str(e), "top_factors": {}, "interpretation": {}}
