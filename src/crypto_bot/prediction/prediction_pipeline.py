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
    atr_14d: float = 0.0  # ATR fuer SL/TP-Berechnung
    sl_pct: float = 0.10  # Stop-Loss in % (Fallback 10%)
    tp_pct: float = 0.15  # Take-Profit in % (Fallback 15%)
    # Quantil-Regression Ergebnisse
    q10: float = 0.0  # Pessimistischer Return (10. Perzentil)
    q50: float = 0.0  # Erwarteter Return (Median)
    q90: float = 0.0  # Optimistischer Return (90. Perzentil)


class PredictionPipeline:
    """Wrapper um coin_prediction fuer Live-Inference.

    Unterstuetzt 1h-Timeframe (BTC-only) und 1d-Timeframe (Multi-Coin).
    Bei 1h werden Features inline berechnet (schneller, keine Feature-Pipeline noetig).
    """

    def __init__(
        self,
        coin_prediction_path: str,
        coins: list[str],
        horizon_days: int = 7,
        timeframe: str = "1d",
        horizon_hours: int = 0,
        train_window_hours: int = 720,
        optuna_enabled: bool = False,
        optuna_n_trials: int = 30,
        optuna_timeout: int = 300,
    ) -> None:
        self._path = Path(coin_prediction_path)
        self._coins = coins
        self._horizon_days = horizon_days
        self._timeframe = timeframe
        self._horizon_hours = horizon_hours or (horizon_days * 24)
        self._train_window_hours = train_window_hours
        self._modules_loaded = False
        self._optuna_enabled = optuna_enabled
        self._optuna_n_trials = optuna_n_trials
        self._optuna_timeout = optuna_timeout
        self._best_params: dict | None = None  # Gecachte Optuna-Params

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
        from src.ingestion.derivatives_fetcher import fetch_and_save_derivatives
        from src.ingestion.funding_fetcher import fetch_all_funding_rates
        from src.ingestion.ohlcv_fetcher import fetch_all_coins
        from src.ingestion.sentiment_fetcher import fetch_fear_greed
        from src.models.lightgbm_model import predict_with_confidence, train_lightgbm
        from src.models.quantile_model import (
            create_return_target,
            predict_quantiles,
            train_quantile_models,
        )
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
        self._train_quantile_models = train_quantile_models
        self._predict_quantiles = predict_quantiles
        self._create_return_target = create_return_target
        self._fetch_all_funding_rates = fetch_all_funding_rates
        self._fetch_derivatives = fetch_and_save_derivatives

        # B8: Optuna Tuner (optional)
        if self._optuna_enabled:
            try:
                from src.models.optuna_tuner import tune_and_train
                self._tune_and_train = tune_and_train
                logger.info("optuna_tuner_loaded")
            except ImportError:
                logger.warning("optuna_not_available_falling_back_to_default")
                self._optuna_enabled = False

        # C6+C11: Macro/Cross-Market Fetcher
        try:
            from src.ingestion.macro_fetcher import build_macro_features, fetch_macro_data
            self._fetch_macro_data = fetch_macro_data
            self._build_macro_features = build_macro_features
            logger.info("macro_fetcher_loaded")
        except ImportError:
            self._fetch_macro_data = None
            self._build_macro_features = None
            logger.warning("macro_fetcher_not_available")

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
            seed = settings.pipeline.random_seed

            # 1. Daten herunterladen (OHLCV fuer konfigurierten Timeframe)
            logger.info("pipeline_step", step="fetch_data", coins=len(self._coins),
                        timeframe=self._timeframe)
            self._fetch_all_coins(self._coins)

            # Funding Rates und Derivate sammeln (unabhaengig vom Timeframe)
            try:
                self._fetch_all_funding_rates(self._coins)
            except Exception:
                logger.warning("funding_rates_fetch_failed")
            try:
                self._fetch_derivatives(self._coins)
            except Exception:
                logger.warning("derivatives_fetch_failed")

            # C6+C11: Macro/Cross-Market Daten laden
            if self._fetch_macro_data:
                try:
                    self._fetch_macro_data(data_dir, period="90d", interval="1h")
                except Exception:
                    logger.warning("macro_data_fetch_failed", exc_info=True)

            # 2. Bei 1h: Features inline berechnen (kein Umweg ueber Feature-Pipeline)
            #    Bei 1d: Features ueber coin_prediction Feature-Pipeline
            if self._timeframe == "1h":
                try:
                    self._fetch_fear_greed()
                except Exception:
                    logger.warning("fear_greed_fetch_failed")
            else:
                try:
                    self._fetch_fear_greed()
                except Exception:
                    logger.warning("fear_greed_fetch_failed")
                logger.info("pipeline_step", step="build_features")
                self._build_all_features(self._coins)

            # 3. Fuer jeden Coin: trainieren und predicten
            results: dict[str, PredictionResult] = {}

            for coin in self._coins:
                try:
                    if self._timeframe == "1h":
                        result = self._train_and_predict_1h(coin, data_dir, seed)
                    else:
                        horizon_periods = self._days_to_periods(
                            self._horizon_days, self._timeframe)
                        result = self._train_and_predict_coin(
                            coin, data_dir, self._timeframe, horizon_periods, seed)
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

        # Target: Einfaches binaeres Target (Preis in N Tagen hoeher?)
        # Diagnose zeigte: Simple Target performt gleich oder besser als Triple Barrier
        # weil TB mit asymmetrischen Barrieren (2x SL/3x TP) verzerrte Labels erzeugt
        future_return = close.shift(-horizon_periods) / close - 1
        target = (future_return > 0).astype(float)
        target[future_return.isna()] = float("nan")
        target.name = f"target_{horizon_periods}d"

        # Align
        common_idx = features.index.intersection(target.dropna().index)
        X = features.loc[common_idx].copy()
        y = target.loc[common_idx].copy()

        # NaN-Spalten entfernen
        X = X.dropna(axis=1, how="all")

        # Feature Selection: Korrelations-basiert (Top-15 pro Coin)
        # Diagnose zeigte: Top-5-15 Features schlagen alle Features
        # (SOL: +5%, DOGE: +1.4%)
        X = self._select_features(X, method="correlation", target=y, top_n=15)

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

        # Rollierendes Trainings-Fenster: 500 Tage
        max_train_days = 500
        if len(X) > max_train_days:
            X = X.iloc[-max_train_days:]
            y = y.iloc[-max_train_days:]

        # Train/Val Split fuer Early Stopping (80/20)
        split_idx = int(len(X) * 0.8)
        X_train = X.iloc[:split_idx]
        y_train = y.iloc[:split_idx]
        X_val = X.iloc[split_idx:]
        y_val = y.iloc[split_idx:]

        # Modell trainieren (mit oder ohne Optuna)
        if self._optuna_enabled:
            model, self._best_params = self._tune_and_train(
                X_train, y_train, X_val, y_val,
                seed=seed, n_trials=self._optuna_n_trials,
                timeout=self._optuna_timeout,
            )
        else:
            model = self._train_lightgbm(X_train, y_train, X_val, y_val, seed=seed)

        # Prediction
        preds, proba = self._predict_with_confidence(model, latest_features)
        probability = float(proba[0])
        direction = "up" if probability > 0.5 else "down"
        confidence = abs(probability - 0.5) + 0.5

        features_date = str(latest_features.index[0].date())

        # ATR-14d berechnen fuer SL/TP
        atr_14d = self._calculate_atr(ohlcv, period=14)
        last_close = float(close.iloc[-1])
        if last_close > 0 and atr_14d > 0:
            # SL = 2.0x ATR, TP = 2.0x ATR (symmetrisch, da Simple Target)
            sl_pct = min((2.0 * atr_14d) / last_close, 0.20)  # Max 20%
            tp_pct = min((2.0 * atr_14d) / last_close, 0.20)  # Max 20%
        else:
            sl_pct = 0.10  # Fallback
            tp_pct = 0.10

        # Quantil-Regression: Rendite-Intervall vorhersagen
        q10, q50, q90 = 0.0, 0.0, 0.0
        try:
            return_target = self._create_return_target(close, horizon_periods)
            ret_common = X.index.intersection(return_target.dropna().index)
            X_ret = X.loc[ret_common]
            y_ret = return_target.loc[ret_common]

            valid_ret = X_ret.notna().all(axis=1) & y_ret.notna()
            X_ret = X_ret[valid_ret]
            y_ret = y_ret[valid_ret]

            if len(X_ret) >= 200:
                ret_split = int(len(X_ret) * 0.8)
                q_models = self._train_quantile_models(
                    X_ret.iloc[:ret_split], y_ret.iloc[:ret_split],
                    X_ret.iloc[ret_split:], y_ret.iloc[ret_split:],
                    seed=seed,
                )
                q_preds = self._predict_quantiles(q_models, latest_features)
                if q_preds:
                    q10 = q_preds[0].q10
                    q50 = q_preds[0].q50
                    q90 = q_preds[0].q90
        except Exception:
            logger.warning("quantile_prediction_failed", coin=coin)

        logger.info(
            "coin_predicted",
            coin=coin,
            direction=direction,
            probability=round(probability, 4),
            confidence=round(confidence, 4),
            features_date=features_date,
            atr_14d=round(atr_14d, 4),
            sl_pct=round(sl_pct * 100, 1),
            tp_pct=round(tp_pct * 100, 1),
            q10=round(q10 * 100, 1),
            q50=round(q50 * 100, 1),
            q90=round(q90 * 100, 1),
        )

        return PredictionResult(
            coin=coin,
            direction=direction,
            probability=probability,
            confidence=confidence,
            features_date=features_date,
            atr_14d=atr_14d,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            q10=q10,
            q50=q50,
            q90=q90,
        )

    def _build_1h_features(self, ohlcv: "pd.DataFrame", data_dir: "Path", coin: str) -> "pd.DataFrame":
        """Baut Features direkt aus 1h-OHLCV-Daten (kein Umweg ueber Feature-Pipeline).

        Features sind optimiert fuer stuendliche Aufloesung:
        - Returns: 1h, 4h, 12h, 24h, 72h, 168h
        - Volatilitaet: 12h, 24h, 72h, 168h Standardabweichung
        - RSI: 14 Perioden (= 14 Stunden)
        - Volume: Ratio 24h/168h Durchschnitt
        - High/Low Range: 24h normalisiert
        - Funding Rate: taeglich, reindexed auf 1h (falls verfuegbar)
        """
        import numpy as np
        import pandas as pd

        close = ohlcv["close"].astype(float)
        volume = ohlcv["volume"].astype(float)
        high = ohlcv["high"].astype(float)
        low = ohlcv["low"].astype(float)

        features = pd.DataFrame(index=ohlcv.index)

        # Returns (verschiedene Lookback-Fenster)
        for p in [1, 4, 12, 24, 72, 168]:
            features[f"ret_{p}h"] = close.pct_change(p)

        # Volatilitaet (Rolling Std der stuendlichen Returns)
        hourly_ret = close.pct_change()
        for w in [12, 24, 72, 168]:
            features[f"vol_{w}h"] = hourly_ret.rolling(w).std()

        # RSI-14 (14 Stunden)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        features["rsi_14h"] = 100 - (100 / (1 + rs))

        # Volume-Ratio (kurzfristig vs langfristig)
        vol_24 = volume.rolling(24).mean()
        vol_168 = volume.rolling(168).mean()
        features["vol_ratio_24_168"] = vol_24 / vol_168.replace(0, np.nan)

        # High/Low Range (24h, normalisiert auf Close)
        features["hl_range_24h"] = (
            high.rolling(24).max() - low.rolling(24).min()
        ) / close

        # MACD (12/26/9 Stunden)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        features["macd"] = ema12 - ema26
        features["macd_signal"] = features["macd"].ewm(span=9, adjust=False).mean()
        features["macd_hist"] = features["macd"] - features["macd_signal"]

        # Bollinger Band Position
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        features["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

        # Funding Rate (falls verfuegbar)
        funding_path = data_dir / "raw" / f"{coin}_funding.parquet"
        if funding_path.exists():
            try:
                funding = pd.read_parquet(funding_path)
                if "timestamp" in funding.columns:
                    funding = funding.set_index("timestamp").sort_index()
                fr = funding["funding_rate"].reindex(features.index, method="ffill")
                features["funding_rate"] = fr
                features["funding_3d_ma"] = fr.rolling(72).mean()  # 3 Tage * 24h
            except Exception:
                pass

        # C6+C11: Macro/Cross-Market Features (DXY, VIX, MSTR, Gold, SPY)
        if self._build_macro_features:
            try:
                macro_features = self._build_macro_features(close, data_dir, interval="1h")
                if not macro_features.empty:
                    # Nur Spalten uebernehmen die auch Daten haben
                    valid_cols = macro_features.columns[macro_features.notna().any()]
                    features = pd.concat([features, macro_features[valid_cols]], axis=1)
            except Exception:
                logger.warning("macro_features_build_failed", coin=coin)

        return features

    def _train_and_predict_1h(
        self,
        coin: str,
        data_dir: "Path",
        seed: int,
    ) -> PredictionResult | None:
        """Training und Prediction mit 1h-Daten (inline Features)."""
        import numpy as np
        import pandas as pd

        ohlcv_path = data_dir / "raw" / f"{coin}_USDT_1h.parquet"
        if not ohlcv_path.exists():
            logger.warning("1h_data_missing", coin=coin)
            return None

        ohlcv = pd.read_parquet(ohlcv_path)
        if "timestamp" in ohlcv.columns:
            ohlcv = ohlcv.set_index("timestamp").sort_index()
        close = ohlcv["close"].astype(float)

        # Features inline berechnen
        features = self._build_1h_features(ohlcv, data_dir, coin)

        # Target: Preis in N Stunden hoeher?
        horizon_h = self._horizon_hours
        future_return = close.shift(-horizon_h) / close - 1
        target = (future_return > 0).astype(float)
        target[future_return.isna()] = float("nan")

        # Align und NaN entfernen
        common_idx = features.index.intersection(target.dropna().index)
        X = features.loc[common_idx]
        y = target.loc[common_idx]
        valid = X.notna().all(axis=1) & y.notna()
        X, y = X[valid], y[valid]

        if len(X) < 200:
            logger.warning("too_few_samples_1h", coin=coin, n=len(X))
            return None

        # Live-Prediction: neueste Feature-Zeile
        latest_features = features[X.columns].ffill().iloc[[-1]].copy()
        if latest_features.isna().any(axis=1).iloc[0]:
            for col in latest_features.columns[latest_features.isna().iloc[0]]:
                latest_features[col] = X[col].median()

        # Rolling Window: letzte N Stunden
        max_train = self._train_window_hours
        if len(X) > max_train:
            X = X.iloc[-max_train:]
            y = y.iloc[-max_train:]

        # Train/Val Split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
        X_val, y_val = X.iloc[split_idx:], y.iloc[split_idx:]

        # LightGBM trainieren (mit oder ohne Optuna)
        if self._optuna_enabled:
            model, self._best_params = self._tune_and_train(
                X_train, y_train, X_val, y_val,
                seed=seed, n_trials=self._optuna_n_trials,
                timeout=self._optuna_timeout,
            )
        else:
            model = self._train_lightgbm(X_train, y_train, X_val, y_val, seed=seed)

        # Prediction
        preds, proba = self._predict_with_confidence(model, latest_features)
        probability = float(proba[0])
        direction = "up" if probability > 0.5 else "down"
        confidence = abs(probability - 0.5) + 0.5

        features_date = str(latest_features.index[0])

        # Kein SL/TP — Backtests zeigen: Zeitbarriere (72h) reicht als Risikomanagement.
        # SL/TP zerstoert den schwachen ML-Edge (vgl. Story 20260406150000).
        atr = self._calculate_atr(ohlcv, period=14)
        last_close = float(close.iloc[-1])
        sl_pct = 0.0
        tp_pct = 0.0

        logger.info(
            "coin_predicted_1h",
            coin=coin,
            direction=direction,
            probability=round(probability, 4),
            confidence=round(confidence, 4),
            features_date=features_date,
            horizon_hours=horizon_h,
            atr=round(atr, 2),
            sl_pct=round(sl_pct * 100, 1),
            tp_pct=round(tp_pct * 100, 1),
        )

        return PredictionResult(
            coin=coin,
            direction=direction,
            probability=probability,
            confidence=confidence,
            features_date=features_date,
            atr_14d=atr,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
        )

    @staticmethod
    def _calculate_atr(ohlcv: "pd.DataFrame", period: int = 14) -> float:
        """Berechnet den Average True Range (ATR)."""
        import numpy as np

        high = ohlcv["high"].astype(float)
        low = ohlcv["low"].astype(float)
        close = ohlcv["close"].astype(float)

        # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        prev_close = close.shift(1)
        tr = np.maximum(
            high - low,
            np.maximum(abs(high - prev_close), abs(low - prev_close)),
        )

        # ATR = Gleitender Durchschnitt des True Range
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else 0.0
