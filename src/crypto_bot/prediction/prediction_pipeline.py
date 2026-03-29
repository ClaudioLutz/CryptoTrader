"""Wrapper um das coin_prediction-Projekt fuer Live-Trading.

Fuehrt den vollstaendigen ML-Zyklus aus:
1. Daten herunterladen (OHLCV, Sentiment, On-Chain)
2. Features berechnen
3. Modell trainieren (LightGBM auf gesamter Historie)
4. Prediction fuer den neuesten Zeitpunkt generieren

Laeuft synchron und wird via asyncio.to_thread() aufgerufen.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PredictionResult:
    """Ergebnis einer Vorhersage fuer einen Coin."""

    coin: str
    direction: str  # "up" oder "down"
    probability: float  # Rohe Wahrscheinlichkeit fuer "Up"
    confidence: float  # |probability - 0.5| + 0.5
    features_date: str  # Datum der neuesten Feature-Zeile


class PredictionPipeline:
    """Wrapper um coin_prediction fuer Live-Inference.

    Importiert Module aus dem coin_prediction-Projekt dynamisch,
    um zirkulaere Abhaengigkeiten zu vermeiden.
    """

    def __init__(
        self,
        coin_prediction_path: str,
        coins: list[str],
        horizon_days: int = 7,
    ) -> None:
        self._path = Path(coin_prediction_path)
        self._coins = coins
        self._horizon_days = horizon_days
        self._modules_loaded = False

    def _ensure_imports(self) -> None:
        """Fuegt coin_prediction zum sys.path hinzu und importiert Module."""
        if self._modules_loaded:
            return

        path_str = str(self._path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

        # Imports aus coin_prediction
        from src.config.settings import get_settings as cp_get_settings
        from src.features.feature_selection import select_features
        from src.features.pipeline import build_all_features, build_features_for_coin
        from src.ingestion.ohlcv_fetcher import fetch_all_coins
        from src.ingestion.sentiment_fetcher import fetch_fear_greed
        from src.models.lightgbm_model import predict_with_confidence, train_lightgbm
        from src.models.targets import create_target
        from src.utils.timeframe import days_to_periods

        self._cp_get_settings = cp_get_settings
        self._fetch_all_coins = fetch_all_coins
        self._fetch_fear_greed = fetch_fear_greed
        self._build_all_features = build_all_features
        self._build_features_for_coin = build_features_for_coin
        self._select_features = select_features
        self._train_lightgbm = train_lightgbm
        self._predict_with_confidence = predict_with_confidence
        self._create_target = create_target
        self._days_to_periods = days_to_periods

        self._modules_loaded = True
        logger.info("coin_prediction_modules_loaded", path=path_str)

    async def run_full_pipeline(self) -> dict[str, PredictionResult]:
        """Fuehrt die komplette Pipeline in einem Thread aus."""
        return await asyncio.to_thread(self._run_sync)

    def _run_sync(self) -> dict[str, PredictionResult]:
        """Synchrone Pipeline-Ausfuehrung."""
        import os
        import pandas as pd

        # Working Directory auf coin_prediction setzen (fuer .env-Loading)
        original_cwd = os.getcwd()
        os.chdir(str(self._path))

        try:
            self._ensure_imports()
            settings = self._cp_get_settings()
            data_dir = settings.pipeline.data_dir
            timeframe = settings.pipeline.timeframe
            seed = settings.pipeline.random_seed

            # 1. Daten herunterladen
            logger.info("pipeline_step", step="fetch_data", coins=len(self._coins))
            self._fetch_all_coins(self._coins)
            try:
                self._fetch_fear_greed()
            except Exception:
                logger.warning("fear_greed_fetch_failed")

            # 2. Features berechnen
            logger.info("pipeline_step", step="build_features")
            self._build_all_features(self._coins)

            # 3. Fuer jeden Coin: trainieren und predicten
            results: dict[str, PredictionResult] = {}
            horizon_periods = self._days_to_periods(self._horizon_days, timeframe)

            for coin in self._coins:
                try:
                    result = self._train_and_predict_coin(
                        coin, data_dir, timeframe, horizon_periods, seed,
                    )
                    if result:
                        results[coin] = result
                except Exception:
                    logger.exception("coin_prediction_failed", coin=coin)

            logger.info(
                "pipeline_complete",
                n_predictions=len(results),
                up_count=sum(1 for r in results.values() if r.direction == "up"),
                down_count=sum(1 for r in results.values() if r.direction == "down"),
            )
            return results

        finally:
            os.chdir(original_cwd)

    def _train_and_predict_coin(
        self,
        coin: str,
        data_dir: Path,
        timeframe: str,
        horizon_periods: int,
        seed: int,
    ) -> PredictionResult | None:
        """Trainiert ein Modell und erstellt eine Prediction fuer einen Coin."""
        import numpy as np
        import pandas as pd

        # Daten laden
        feat_path = data_dir / "features" / f"{coin}_features.parquet"
        ohlcv_path = data_dir / "raw" / f"{coin}_USDT_{timeframe}.parquet"

        if not feat_path.exists() or not ohlcv_path.exists():
            logger.warning("data_missing", coin=coin)
            return None

        features = pd.read_parquet(feat_path)
        ohlcv = pd.read_parquet(ohlcv_path).set_index("timestamp").sort_index()
        close = ohlcv["close"]

        # Target erstellen
        target = self._create_target(close, horizon_periods)

        # Align
        common_idx = features.index.intersection(target.dropna().index)
        X = features.loc[common_idx].copy()
        y = target.loc[common_idx].copy()

        # NaN-Spalten entfernen
        X = X.dropna(axis=1, how="all")

        # Feature Selection (Core-Features)
        X = self._select_features(X, method="core")

        # NaN-Zeilen entfernen
        valid = X.notna().all(axis=1) & y.notna()
        X = X[valid]
        y = y[valid]

        if len(X) < 200:
            logger.warning("too_few_samples", coin=coin, n=len(X))
            return None

        # Live-Prediction: neueste Feature-Zeile (die KEIN Target hat)
        # NaN in Cross-Asset-Features per forward-fill auffuellen
        latest_features = features[X.columns].ffill().iloc[[-1]].copy()

        if latest_features.isna().any(axis=1).iloc[0]:
            # Verbleibende NaN mit Median auffuellen (sicherster Fallback)
            for col in latest_features.columns[latest_features.isna().iloc[0]]:
                latest_features[col] = X[col].median()

        # Train/Val Split fuer Early Stopping (80/20)
        split_idx = int(len(X) * 0.8)
        X_train = X.iloc[:split_idx]
        y_train = y.iloc[:split_idx]
        X_val = X.iloc[split_idx:]
        y_val = y.iloc[split_idx:]

        # Modell trainieren
        model = self._train_lightgbm(X_train, y_train, X_val, y_val, seed=seed)

        # Prediction
        preds, proba = self._predict_with_confidence(model, latest_features)
        probability = float(proba[0])
        direction = "up" if probability > 0.5 else "down"
        confidence = abs(probability - 0.5) + 0.5

        features_date = str(latest_features.index[0].date())

        logger.info(
            "coin_predicted",
            coin=coin,
            direction=direction,
            probability=round(probability, 4),
            confidence=round(confidence, 4),
            features_date=features_date,
        )

        return PredictionResult(
            coin=coin,
            direction=direction,
            probability=probability,
            confidence=confidence,
            features_date=features_date,
        )
