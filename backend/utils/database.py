"""
SQLite audit database for prediction logging and model versioning.
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

DB_PATH = Path("logs/cdss_audit.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS predictions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id  TEXT NOT NULL,
                disease     TEXT NOT NULL,
                input_data  TEXT NOT NULL,
                prediction  TEXT NOT NULL,
                probability REAL NOT NULL,
                risk_level  TEXT NOT NULL,
                confidence  TEXT NOT NULL,
                model_ver   TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_registry (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                version          TEXT UNIQUE NOT NULL,
                disease          TEXT NOT NULL,
                training_date    TEXT NOT NULL,
                dataset          TEXT NOT NULL,
                calibration      TEXT NOT NULL,
                sensitivity      REAL,
                specificity      REAL,
                roc_auc          REAL,
                pr_auc           REAL,
                brier_score      REAL,
                is_active        INTEGER DEFAULT 0,
                artifact_path    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invalid_inputs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                input_data  TEXT NOT NULL,
                error_msg   TEXT NOT NULL
            );
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_prediction(
    patient_id: str,
    disease: str,
    input_data: dict,
    prediction: str,
    probability: float,
    risk_level: str,
    confidence: str,
    model_ver: str,
):
    ts = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO predictions
               (patient_id, disease, input_data, prediction, probability,
                risk_level, confidence, model_ver, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                patient_id,
                disease,
                json.dumps(input_data),
                prediction,
                probability,
                risk_level,
                confidence,
                model_ver,
                ts,
            ),
        )


def log_invalid_input(input_data: dict, error_msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO invalid_inputs (timestamp, input_data, error_msg) VALUES (?,?,?)",
            (ts, json.dumps(input_data), error_msg),
        )


def register_model(
    version: str,
    disease: str,
    training_date: str,
    dataset: str,
    calibration: str,
    metrics: dict,
    artifact_path: str,
    set_active: bool = True,
):
    with get_conn() as conn:
        if set_active:
            conn.execute(
                "UPDATE model_registry SET is_active=0 WHERE disease=?", (disease,)
            )
        conn.execute(
            """INSERT OR REPLACE INTO model_registry
               (version, disease, training_date, dataset, calibration,
                sensitivity, specificity, roc_auc, pr_auc, brier_score,
                is_active, artifact_path)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                version,
                disease,
                training_date,
                dataset,
                calibration,
                metrics.get("sensitivity"),
                metrics.get("specificity"),
                metrics.get("roc_auc"),
                metrics.get("pr_auc"),
                metrics.get("brier_score"),
                1 if set_active else 0,
                artifact_path,
            ),
        )


def get_active_model(disease: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_registry WHERE disease=? AND is_active=1",
            (disease,),
        ).fetchone()
    return row


def get_prediction_count(disease: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM predictions WHERE disease=?", (disease,)
        ).fetchone()
    return row["cnt"] if row else 0
