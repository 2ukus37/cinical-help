"""
Prediction distribution monitoring and basic drift detection.
"""
import json
from collections import Counter
from pathlib import Path
from backend.utils.database import get_conn

REPORT_DIR = Path("logs/monitoring")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def get_prediction_distribution(disease: str) -> dict:
    """Aggregate prediction stats for drift monitoring."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT probability, risk_level, prediction FROM predictions WHERE disease=?",
            (disease,),
        ).fetchall()

    if not rows:
        return {"message": "No predictions recorded yet", "disease": disease}

    probs = [r["probability"] for r in rows]
    risk_counts = Counter(r["risk_level"] for r in rows)
    pred_counts = Counter(r["prediction"] for r in rows)

    # Basic drift indicator: if mean probability shifts > 0.1 from 0.5 baseline
    mean_prob = sum(probs) / len(probs)
    drift_flag = abs(mean_prob - 0.5) > 0.15

    stats = {
        "disease": disease,
        "total_predictions": len(probs),
        "mean_probability": round(mean_prob, 4),
        "std_probability": round((sum((p - mean_prob) ** 2 for p in probs) / len(probs)) ** 0.5, 4),
        "risk_distribution": dict(risk_counts),
        "prediction_distribution": dict(pred_counts),
        "positive_rate": round(pred_counts.get("Positive", 0) / len(probs), 4),
        "drift_indicator": {
            "flagged": drift_flag,
            "reason": "Mean probability deviates >15% from 0.5 baseline" if drift_flag else "Within normal range",
        },
    }

    # Persist snapshot
    snap_path = REPORT_DIR / f"{disease}_distribution.json"
    with open(snap_path, "w") as f:
        json.dump(stats, f, indent=2)

    return stats
