"""Prediction Journaling — Jede Prediction mit Features loggen (F2).

Speichert in SQLite:
- Prediction (Richtung, Confidence, Feature-Vektor)
- Outcome (tatsaechliche Preisaenderung nach Ablauf)
- Model-Metadaten (Trainings-Fenster, Optuna-Params)

Ermoeglicht Post-hoc-Analyse:
- Bei welchen Features liegt das Modell systematisch falsch?
- Wie veraendern sich die Feature-Werte ueber die Zeit?
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

DB_PATH = Path("logs/prediction_journal.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    coin TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    prediction TEXT NOT NULL,
    confidence REAL NOT NULL,
    probability REAL NOT NULL,
    position_size_pct REAL,
    features_json TEXT,
    optuna_params_json TEXT,
    train_samples INTEGER,
    actual_outcome TEXT,
    actual_return_pct REAL,
    outcome_filled_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_journal_coin_ts ON prediction_journal(coin, timestamp);
CREATE INDEX IF NOT EXISTS idx_journal_outcome ON prediction_journal(actual_outcome);
"""


class PredictionJournal:
    """SQLite-basiertes Prediction Journal."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Erstellt DB und Tabelle falls nicht vorhanden."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(CREATE_TABLE_SQL)
        self._conn.commit()
        logger.info("prediction_journal_initialized", path=str(self._db_path))

    def log_prediction(
        self,
        coin: str,
        timeframe: str,
        prediction: str,
        confidence: float,
        probability: float,
        position_size_pct: float = 0.0,
        features: dict | None = None,
        optuna_params: dict | None = None,
        train_samples: int = 0,
    ) -> int:
        """Loggt eine neue Prediction.

        Returns:
            ID des Journal-Eintrags.
        """
        now = datetime.now(UTC).isoformat()
        features_json = json.dumps(features, default=str) if features else None
        params_json = json.dumps(optuna_params, default=str) if optuna_params else None

        cursor = self._conn.execute(
            """
            INSERT INTO prediction_journal
                (timestamp, coin, timeframe, prediction, confidence, probability,
                 position_size_pct, features_json, optuna_params_json, train_samples)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, coin, timeframe, prediction, confidence, probability,
             position_size_pct, features_json, params_json, train_samples),
        )
        self._conn.commit()
        entry_id = cursor.lastrowid
        logger.debug(
            "prediction_journaled",
            id=entry_id,
            coin=coin,
            prediction=prediction,
            confidence=round(confidence, 3),
        )
        return entry_id

    def fill_outcome(
        self,
        coin: str,
        timestamp: str,
        actual_outcome: str,
        actual_return_pct: float,
    ) -> None:
        """Fuellt das tatsaechliche Outcome nach (z.B. 72h spaeter).

        Args:
            coin: Coin-Symbol.
            timestamp: Original-Prediction-Timestamp.
            actual_outcome: "up" oder "down".
            actual_return_pct: Tatsaechliche Rendite in %.
        """
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE prediction_journal
            SET actual_outcome = ?, actual_return_pct = ?, outcome_filled_at = ?
            WHERE coin = ? AND timestamp = ? AND actual_outcome IS NULL
            """,
            (actual_outcome, actual_return_pct, now, coin, timestamp),
        )
        self._conn.commit()

    def get_recent_predictions(
        self, coin: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Gibt die letzten Predictions zurueck."""
        query = "SELECT * FROM prediction_journal"
        params: list = []
        if coin:
            query += " WHERE coin = ?"
            params.append(coin)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def get_accuracy_stats(self, coin: str | None = None) -> dict:
        """Berechnet Accuracy-Statistiken fuer Predictions mit Outcomes."""
        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN prediction = actual_outcome THEN 1 ELSE 0 END) as correct,
                AVG(actual_return_pct) as avg_return,
                AVG(CASE WHEN prediction = 'up' THEN actual_return_pct END) as avg_return_up,
                AVG(CASE WHEN prediction = 'down' THEN actual_return_pct END) as avg_return_down
            FROM prediction_journal
            WHERE actual_outcome IS NOT NULL
        """
        params: list = []
        if coin:
            query += " AND coin = ?"
            params.append(coin)

        cursor = self._conn.execute(query, params)
        row = cursor.fetchone()
        total = row[0] or 0
        correct = row[1] or 0

        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": correct / total if total > 0 else 0.0,
            "avg_return_pct": row[2] or 0.0,
            "avg_return_up_pct": row[3] or 0.0,
            "avg_return_down_pct": row[4] or 0.0,
        }

    def close(self) -> None:
        """Schliesst die DB-Verbindung."""
        if self._conn:
            self._conn.close()
