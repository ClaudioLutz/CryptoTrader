# B) ML / Modell-Verbesserungen — Vertiefte Recherche

> Zurueck zur Uebersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

**Datum:** 2026-04-06 (aktualisiert 2026-04-07)
**Kontext:** CryptoTrader 3.0 — BTC-only, LightGBM 1h, 19+27 Features, 720h Trainingsfenster, ~55-58% Win-Rate, Feature-Korrelation ~0.045

> **Status-Update 2026-04-07:** B8 (Optuna/AutoML) wurde am 2026-04-06 implementiert und deployed. TPE-Tuning mit 30 Trials optimiert 9 Hyperparameter inkl. reg_alpha/reg_lambda. Erster Produktions-Run: 30 Trials in 35s, best_loss=0.644.

---

## B1: XGBoost Ensemble — LightGBM + XGBoost Kombination

### Was es ist

Ein Ensemble-Modell, das die Vorhersagen von LightGBM und XGBoost (und optional RandomForest) kombiniert. Durch Soft-Voting oder Stacking werden die Staerken beider Gradient-Boosting-Varianten genutzt: LightGBM ist schneller und oft besser bei kleinen Datenmengen, XGBoost ist robuster gegen Overfitting.

### Konkrete Implementierungsdetails

**Bereits vorhanden im Code:** In `coin_prediction/src/models/ensemble.py` existieren drei Ansaetze:
- **VotingClassifier** (Soft-Voting, LightGBM 2x gewichtet, XGBoost 1x, RF 1x)
- **StackingEnsemble** (2-Level: Basis-Modelle -> Logistic Regression als Meta-Learner, 70/30 Split)
- **RegimeSplitEnsemble** (separate LightGBM-Modelle fuer ruhige vs volatile Maerkte)

**Architektur fuer Integration in Live-Bot:**
```
LightGBM (lr=0.03, depth=5, 500 trees)  ─┐
XGBoost  (lr=0.03, depth=5, 500 trees)  ─┼─> Soft-Voting (gewichtet) -> Prediction
RandomForest (300 trees, depth=8)        ─┘
```

**Libraries:** `scikit-learn` (VotingClassifier, StackingClassifier), `lightgbm`, `xgboost`

**Kritische Hyperparameter:**
- Voting-Gewichte: LightGBM sollte staerker gewichtet werden (2:1:1 ist sinnvoller Start)
- Stacking: Meta-Learner muss auf Out-of-Sample-Predictions trainiert werden (Datenleck vermeiden!)
- Early Stopping pro Basis-Modell: 50 Runden Geduld

### Akademische/praktische Evidenz

- **Sun et al. (2024):** "Cryptocurrency price prediction based on XGBoost, LightGBM and BNN" — XGBoost zeigte leicht bessere Ergebnisse als LightGBM bei Crypto-Preisvorhersage, BNN ergaenzte als dritter Learner ([ResearchGate](https://www.researchgate.net/publication/379180753_Cryptocurrency_price_prediction_based_on_Xgboost_LightGBM_and_BNN))
- **PMC (2025):** Random Forest erzielte hoechsten Cross-Validated ROC-AUC (0.6086) in Crypto-Klassifikation, XGBoost erreichte bei Confidence-Threshold 70% eine Hit-Ratio von 70% ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12571449/))
- **Johal.in (2025):** Stacking von XGBoost + LightGBM verbesserte Accuracy um bis zu 15% gegenueber Einzelmodellen, F1-Score +18% ([Johal.in](https://johal.in/ensemble-learning-methods-xgboost-and-lightgbm-stacking-for-improved-predictive-accuracy-2025/))
- **Benchmarks:** LightGBM trainiert 1.99x schneller als XGBoost (1.23s vs 2.45s), bei vergleichbarer Accuracy ([MarkAICode](https://markaicode.com/lightgbm-vs-xgboost-2025-performance-benchmarks/))

### Relevanz fuer dieses Projekt

**Hoch.** Der Code existiert bereits, XGBoost ist installiert, die Integration in die Live-Pipeline erfordert minimalen Aufwand. Der Hauptvorteil: Ensemble-Modelle reduzieren Varianz und koennen bei einem schwachen Signal (0.045 Korrelation) den Unterschied zwischen 55% und 57% Win-Rate ausmachen.

**Wichtig:** Bei nur 720h Trainingsdaten (ca. 576 Samples nach 80/20-Split) ist das Risiko von Overfitting bei Stacking erhoeht. Soft-Voting ist hier der sicherere Ansatz als Stacking.

### Risiken und Fallstricke

- **Trainingszeit verdreifacht:** Statt 1 Modell werden 3 trainiert (alle 1h Retraining!). Auf der e2-small VM (2 vCPU, 2 GB RAM) koennte das eng werden.
- **Korrelierte Modelle:** LightGBM und XGBoost sind sich algorithmisch aehnlich — der Diversitaetsvorteil ist begrenzt. RandomForest bringt etwas Diversitaet.
- **Stacking-Datenleck:** Das Meta-Modell muss auf Out-of-Sample-Predictions trainiert werden, sonst misst man nur Overfitting.
- **Kein Garantie-Gewinn:** Bei extrem schwachem Signal kann Ensemble die Noise-Korrelationen verstaerken statt den echten Edge.

### Geschaetzter Aufwand

**1-2 Tage.** Code existiert bereits in `ensemble.py`. Hauptarbeit: Integration in `prediction_pipeline.py`, Backtest-Validierung, VM-Performance-Test.

---

## B2: Neural Networks — LSTM, Transformer (TFT), 1D-CNN

### Was es ist

Deep-Learning-Architekturen, die speziell fuer Zeitreihen-Daten entwickelt wurden:
- **LSTM (Long Short-Term Memory):** Recurrent Neural Network das langfristige Abhaengigkeiten in Sequenzen lernt
- **Temporal Fusion Transformer (TFT):** Attention-basiertes Modell mit interpretierbaren Feature-Gewichten und Multi-Horizon-Forecasting
- **1D-CNN (Convolutional Neural Network):** Erkennt lokale Muster (z.B. Candlestick-Patterns) durch Filteroperationen ueber die Zeitachse

### Konkrete Implementierungsdetails

**LSTM-Architektur fuer 1h BTC:**
```python
# PyTorch
model = nn.Sequential(
    nn.LSTM(input_size=19, hidden_size=64, num_layers=2, dropout=0.3, batch_first=True),
    nn.Linear(64, 32),
    nn.ReLU(),
    nn.Linear(32, 1),
    nn.Sigmoid()
)
# Input: (batch, seq_len=72, features=19) -> 72h Lookback
# Learning Rate: 1e-3 mit ReduceLROnPlateau
# Epochs: 50-100 mit Early Stopping (patience=10)
```

**TFT-Architektur:**
```python
# pytorch-forecasting / darts
from pytorch_forecasting import TemporalFusionTransformer
tft = TemporalFusionTransformer.from_dataset(
    training,
    hidden_size=32,          # Klein halten bei 720h Daten!
    attention_head_size=4,
    dropout=0.3,
    hidden_continuous_size=16,
    learning_rate=1e-3,
    reduce_on_plateau_patience=5,
)
# Vorteil: Variable Selection Network zeigt automatisch Feature-Wichtigkeit
```

**1D-CNN-Architektur:**
```python
model = nn.Sequential(
    nn.Conv1d(19, 32, kernel_size=5, padding=2),  # 5h-Muster erkennen
    nn.ReLU(),
    nn.MaxPool1d(2),
    nn.Conv1d(32, 64, kernel_size=3, padding=1),
    nn.ReLU(),
    nn.AdaptiveAvgPool1d(1),
    nn.Flatten(),
    nn.Linear(64, 1),
    nn.Sigmoid()
)
# Input: (batch, features=19, seq_len=48) -> 48h Lookback
```

**Libraries:**
- LSTM/CNN: `torch` (PyTorch), `pytorch-lightning`
- TFT: `pytorch-forecasting` oder `darts` (Nixtla-Stack)
- Preprocessing: `sklearn.preprocessing.StandardScaler` (zwingend fuer NN!)

### Akademische/praktische Evidenz

- **Murray et al. (2025):** TFT-basiertes Framework mit On-Chain + TA-Indikatoren outperformte LSTM, GRU, SVR und XGBoost fuer Multi-Crypto-Forecasting ([MDPI Systems](https://www.mdpi.com/2079-8954/13/6/474))
- **Adaptive TFT (2025):** Dynamische Subseries-Laengen verbesserten Short-Term-Forecasting signifikant gegenueber Fixed-Length TFT und LSTM (ETH-USDT 10min-Daten) ([arXiv:2509.10542](https://arxiv.org/abs/2509.10542))
- **TFT + Kategorisierung (2024):** Kategorisierter TFT erzielte >4% Profit in 2 Wochen, 6% mehr als Buy-and-Hold ([arXiv:2412.14529](https://arxiv.org/html/2412.14529v1))
- **LSTM Performance:** Bestes RMSE (0.0222) unter DL-Ansaetzen, 2.7% besser als zweitbestes Modell ([Preprints.org](https://www.preprints.org/frontend/manuscript/5e283185e515d3bdcf84a01097c75f26/download_pub))
- **1D-CNN fuer Chart Patterns:** CNN identifiziert lokale Patterns (Momentum-Surges, Candlestick-Patterns) effektiv in 1D-Zeitreihen ([Springer](https://link.springer.com/article/10.1007/s11227-022-04431-5))
- **Hybrid CNN+Transformer (2025):** Parallele CNN- und Transformer-Bloecke zeigten verbesserte Performance bei Crypto-Zeitreihen ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S156849462500540X))

### Relevanz fuer dieses Projekt

**Mittel bis Niedrig.** Grundsaetzliches Problem: Mit nur 720 Trainingsstunden (576 Samples nach Split) sind Deep-Learning-Modelle stark overfitting-gefaehrdet. Die meisten Papers arbeiten mit 10'000+ Samples. TFT waere am interessantesten wegen der interpretierbaren Feature-Wichtigkeit, aber die Mindestdatenmenge ist hoch.

**Empfehlung:** Erst bei Erweiterung auf Multi-Coin (18 Coins * 720h = ~13'000 Samples) oder laengerem Trainingsfenster (2'000-4'000h) sinnvoll. 1D-CNN hat den niedrigsten Datenbedarf der drei Optionen.

### Risiken und Fallstricke

- **Datenmenge:** 576 Trainingssamples sind fuer NNs extrem wenig. LightGBM braucht typischerweise 10x weniger Daten als LSTM.
- **GPU-Anforderung:** e2-small hat keine GPU. Training auf CPU ist 10-50x langsamer. TFT-Training koennte 10+ Minuten dauern (vs. 2s fuer LightGBM).
- **Hyperparameter-Sensitivitaet:** NNs haben deutlich mehr Hyperparameter (Lernrate, Hidden Size, Dropout, Batch Size, Sequence Length, ...) — ohne Optuna ist das ein Blindflug.
- **Non-Stationaritaet:** NNs reagieren empfindlicher auf Distribution Shifts als Tree-Modelle.
- **Overfitting:** Ohne sorgfaeltige Regularisierung (Dropout, Weight Decay, Early Stopping) lernen NNs bei wenig Daten den Noise.
- **Deployment-Komplexitaet:** PyTorch als Docker-Dependency vergroessert das Image erheblich (~500 MB+).

### Geschaetzter Aufwand

**5-10 Tage** (pro Architektur). LSTM: 5 Tage. TFT: 7-8 Tage (Datenformatierung komplex). 1D-CNN: 4-5 Tage. Backtest-Integration und VM-Deployment zusaetzlich 2-3 Tage.

---

## B3: Reinforcement Learning — Agent lernt Trading direkt

### Was es ist

Statt einer Klassifikation (up/down) lernt ein RL-Agent direkt die optimale Trading-Aktion (Buy/Sell/Hold) durch Interaktion mit einer simulierten Marktumgebung. Der Agent maximiert kumulativen Reward (z.B. Portfolio-Return) ueber einen Trainingszeitraum.

### Konkrete Implementierungsdetails

**Framework: FinRL + Stable-Baselines3**
```python
# Environment (OpenAI Gym)
class CryptoBTCEnv(gym.Env):
    observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(19,))  # Features
    action_space = spaces.Discrete(3)  # 0=Hold, 1=Buy, 2=Sell

    def step(self, action):
        # Ausfuehren der Aktion, naechsten State berechnen
        reward = portfolio_return - transaction_cost  # Sharpe-basiert
        return obs, reward, done, info
```

**Empfohlene Algorithmen (nach Evidenz):**
1. **PPO (Proximal Policy Optimization):** Bester Allrounder, outperformt TD3/SAC bei Crypto, aggressiver in Bullish-Phasen
2. **SAC (Soft Actor-Critic):** 152% Excess Returns (Sharpe 2.81) in ETH/USDT-Tests
3. **DQN (Deep Q-Network):** Selektiver, stabiler in Seitwärtsmaerkten, 120-faches NAV-Wachstum in einem Test

**Hyperparameter (PPO):**
```python
from stable_baselines3 import PPO
model = PPO(
    "MlpPolicy",
    env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    clip_range=0.2,
    ent_coef=0.01,
    verbose=1,
)
model.learn(total_timesteps=100_000)
```

**Libraries:**
- `stable-baselines3` (PPO, SAC, DQN)
- `gymnasium` (Environment)
- `FinRL` (Vorgefertigte Crypto-Environments, Benchmarks)

### Akademische/praktische Evidenz

- **FinRL Contests 2023-2025:** Standardisierte Benchmarks fuer Crypto-RL-Trading, PPO und SAC zeigen konsistent gute Performance ([Wiley](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/aie2.12004))
- **DQN fuer Bitcoin (2025):** DQN-Agent erzielte >120x NAV-Wachstum, signifikant besser als Buy-and-Hold ([Tandfonline](https://www.tandfonline.com/doi/full/10.1080/23322039.2025.2594873))
- **PPO Limit Orders:** Reduzierte Transaktionskosten um bis zu 36.93% gegenueber Market Orders ([arXiv:2504.02281](https://www.arxiv.org/pdf/2504.02281))
- **IFF-DRL (2025):** Inkrementelles RL mit Self-Supervised-Learning passt sich dynamisch an Markttrends an ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417425019165))
- **Rainbow DQN:** 287% Returns in Trend-Maerkten — aber hohe Varianz ([NeuralArb](https://www.neuralarb.com/2025/11/20/reinforcement-learning-in-dynamic-crypto-markets/))

**Vorsicht bei der Interpretation:** Viele RL-Papers zeigen beeindruckende Backtests, scheitern aber im Live-Trading an Slippage, Transaction Costs und Regime-Changes.

### Relevanz fuer dieses Projekt

**Niedrig bis Mittel.** Das aktuelle Setup (binaere Klassifikation + Zeitbarriere) ist konzeptionell einfacher und nachvollziehbarer. RL bietet potenziell bessere Ergebnisse, aber:
- Die aktuelle Kapitalgroesse (~454 USDT) limitiert den Nutzen von komplexem Position Sizing
- Der 1-Coin-Ansatz (BTC-only) bietet wenig Aktionsraum fuer RL (kein Portfolio-Management)
- RL braucht deutlich mehr Daten und Compute

**Sinnvoller Einsatzzeitpunkt:** Bei Multi-Coin-Erweiterung (Portfolio-Allokation ueber 18 Coins) waere RL ein starker Kandidat.

### Risiken und Fallstricke

- **Hyperparameter-Hoelle:** RL ist extrem sensitiv auf Reward-Shaping, Lernrate, Discount-Factor. Eine kleine Aenderung kann die Performance komplett zerstoeren.
- **Sim-to-Real Gap:** Backtests ignorieren Slippage, Latenz, Order-Book-Tiefe. Live-Performance ist typischerweise 30-50% schlechter.
- **Sample Inefficiency:** PPO braucht ~100'000+ Timesteps fuer stabiles Training. Bei 1h-Daten sind das ~11 Jahre.
- **Non-Stationaritaet:** RL-Policies degradieren bei Marktregime-Wechseln stark. Staendiges Retraining ist noetig.
- **Black-Box:** Entscheidungen sind schwer nachvollziehbar — schlecht fuer Debugging und Vertrauensbildung.
- **Compute:** Training dauert Stunden auf CPU, nicht kompatibel mit stuendlichem Retraining auf e2-small.

### Geschaetzter Aufwand

**10-15 Tage.** Environment-Design: 3-4 Tage. Training + Tuning: 4-5 Tage. Backtesting mit realistischen Kosten: 2-3 Tage. Live-Integration: 2-3 Tage.

---

## B4: Meta-Learning — Modell das lernt WANN das Hauptmodell zuverlaessig ist

### Was es ist

Ein zweites Modell (das "Meta-Modell" oder "Gating Network"), das die Zuverlaessigkeit des Hauptmodells bewertet. Es lernt aus historischen Situationen, wann die LightGBM-Predictions vertrauenswuerdig waren und wann nicht. Trades werden nur ausgefuehrt, wenn das Meta-Modell hohe Zuverlaessigkeit signalisiert.

### Konkrete Implementierungsdetails

**Ansatz 1: Confidence Calibration Meta-Learner**
```python
# Meta-Features pro Prediction-Zeitpunkt:
meta_features = [
    lgb_confidence,          # Rohe LightGBM-Confidence
    lgb_confidence_rolling,  # 24h-Durchschnitt der Confidences
    feature_drift_score,     # PSI der Input-Features vs Training
    vol_regime,              # Aktuelle Marktvolatilitaet
    spread_regime,           # Bid-Ask-Spread
    recent_accuracy_24h,     # Accuracy der letzten 24 Predictions
    model_agreement,         # Uebereinstimmung LGB + XGB (falls Ensemble)
    funding_rate_extreme,    # Ist Funding Rate extrem?
]

# Meta-Modell: LightGBM (oder Logistic Regression fuer Interpretierbarkeit)
meta_target = (hauptmodell_prediction_war_korrekt).astype(int)
meta_model = lgb.LGBMClassifier(max_depth=3, n_estimators=100)
meta_model.fit(meta_features_train, meta_target_train)

# Live: Trade nur wenn meta_model.predict_proba(current_meta) > 0.6
```

**Ansatz 2: Mixture of Experts (MoE)**
```python
# Gating Network entscheidet welches Expert-Modell (calm vs stress) genutzt wird
class GatingNetwork(nn.Module):
    def __init__(self, n_features, n_experts=2):
        self.gate = nn.Sequential(
            nn.Linear(n_features, 16),
            nn.ReLU(),
            nn.Linear(16, n_experts),
            nn.Softmax(dim=-1)
        )
```

**Ansatz 3: DoubleAdapt (Meta-Learning fuer Distribution Shifts)**
```python
# arXiv:2306.09862 — Zwei Adapter:
# 1. Data Adapter: transformiert Features um Shift zu kompensieren
# 2. Model Adapter: passt Modellparameter an neues Regime an
# Implementierung: qlib Framework (Microsoft)
```

**Libraries:** `scikit-learn`, `lightgbm`, Optional: `qlib` (Microsoft), `pytorch`

### Akademische/praktische Evidenz

- **DoubleAdapt (2023/2025):** Meta-Learning fuer inkrementelles Lernen bei Aktientrend-Forecasting. Automatische Adaption an Distribution Shifts via Dual-Adapter. State-of-the-Art auf mehreren Aktien-Benchmarks ([arXiv:2306.09862](https://arxiv.org/html/2306.09862v3))
- **MAML fuer Zero-Shot Financial Forecasting (2025):** MAML-basiertes Meta-Learning fuer robuste Predictions bei sparsamer Historie ([arXiv:2504.09664](https://arxiv.org/html/2504.09664v1))
- **Confidence Estimation (2022):** Meta-Learning-Framework verbessert gleichzeitig Accuracy und Kalibrierung von Confidence-Scores ([arXiv:2210.06776](https://arxiv.org/abs/2210.06776))
- **MoE-Konzept:** Gating Networks lernen pro Sample den zuverlaessigsten Experten auszuwaehlen — besonders stark bei heterogenen Daten ([MachineLearningMastery](https://machinelearningmastery.com/mixture-of-experts/))
- **Meta (2024):** Praxisbericht zu Prediction Robustness — systematisches Monitoring und Meta-Features fuer Zuverlaessigkeitsbewertung ([Meta Engineering](https://engineering.fb.com/2024/07/10/data-infrastructure/machine-learning-ml-prediction-robustness-meta/))

### Relevanz fuer dieses Projekt

**Hoch.** Das ist einer der vielversprechendsten Ansaetze fuer dieses Projekt. Aktuell wird bei 65% Min-Confidence getradet, aber die Confidence ist nicht kalibriert — ein Meta-Modell koennte lernen, dass z.B. bei hoher Volatilitaet + extremem Funding Rate die 70%-Confidence des LightGBM in Wahrheit nur 52% wert ist.

**Konkreter Nutzen:** Statt pauschal 65% Min-Confidence koennte das Meta-Modell situativ entscheiden: "In diesem Marktumfeld ist 68% Confidence zuverlaessig" vs. "In diesem Regime braeuchte man 80%".

### Risiken und Fallstricke

- **Daten fuer Meta-Modell:** Braucht historische Predictions + deren Outcomes. Bei stuendlichem Retraining aendert sich das Hauptmodell staendig — das Meta-Modell muss darauf trainiert werden.
- **Zirkularitaet:** Das Meta-Modell filtert Predictions, aber sein Training haengt von den Predictions ab. Sorgfaeltige temporale Trennung noetig.
- **Ueberanpassung:** Mit wenig Daten kann das Meta-Modell zufaellige Muster lernen ("nach Vollmond ist LightGBM besser").
- **Implementierungskomplexitaet:** Logging aller Predictions + Outcomes braucht persistentes Tracking ueber Wochen/Monate.

### Geschaetzter Aufwand

**5-7 Tage.** Ansatz 1 (einfaches Meta-Modell): 3-4 Tage. Ansatz 2 (MoE): 5-6 Tage. Ansatz 3 (DoubleAdapt): 7-10 Tage. Voraussetzung: Mindestens 2-4 Wochen historische Predictions sammeln.

---

## B5: Online Learning — Kontinuierliches Update statt volles Retraining

### Was es ist

Statt alle 1h das Modell komplett neu zu trainieren (720h Fenster, ~2s Training), wird das bestehende Modell inkrementell mit neuen Daten aktualisiert. Das Modell "verlernt" alte Patterns graduell und adaptiert sich schneller an neue Marktbedingungen.

### Konkrete Implementierungsdetails

**Ansatz 1: LightGBM Warm-Start (init_model)**
```python
import lightgbm as lgb

# Initial-Training (einmalig)
model = lgb.train(params, train_data, num_boost_round=500)
model.save_model("model.txt")

# Inkrementelles Update (jede Stunde, nur neue Daten)
old_model = lgb.Booster(model_file="model.txt")
new_data = lgb.Dataset(X_new, label=y_new)  # Nur letzte 24h
updated_model = lgb.train(
    params,
    new_data,
    num_boost_round=50,       # Nur 50 neue Baeume
    init_model=old_model,     # Weiter trainieren
    keep_training_booster=True,
)
# Optional: Alte Baeume droppen (Issue #4455 auf GitHub)
```

**Ansatz 2: River-Library (echtes Online Learning)**
```python
from river import ensemble, tree, preprocessing
from river.drift import ADWIN

model = preprocessing.StandardScaler() | ensemble.AdaptiveRandomForestClassifier(
    n_models=10,
    max_depth=8,
    drift_detector=ADWIN(),  # Automatische Drift-Erkennung
    seed=42,
)

# Pro Stunde: ein Sample lernen
for x, y in stream:
    pred = model.predict_proba_one(x)  # Prediction
    model.learn_one(x, y)              # Update mit echtem Label
```

**Ansatz 3: Sliding Window + Partial Retraining**
```python
# Kompromiss: Alle 4h nur die letzten 200 Baeume neu trainieren
# und die aelteren 300 behalten
model = lgb.train(params, recent_data, num_boost_round=200,
                   init_model=old_model_first_300_trees)
```

**Libraries:**
- LightGBM Warm-Start: `lightgbm` (bereits installiert)
- River: `river` (online-ml), `deep-river` (Deep Learning on Streams)
- Drift Detection: `river.drift` (ADWIN, KSWIN, PageHinkley)

### Akademische/praktische Evidenz

- **LightGBM init_model:** Offiziell unterstuetzt via `init_model`-Parameter. Problem: Alte Baeume bleiben erhalten, nur neue werden angeheangt. Kein natives "Vergessen" alter Patterns ([GitHub #3747](https://github.com/microsoft/LightGBM/issues/3747))
- **River Library (JMLR 2021):** Standard fuer Online-ML in Python. ADWIN detektiert Concept Drift automatisch und passt das Modell an. 14'000+ GitHub Stars ([River](https://riverml.xyz/))
- **Deep-River (2025):** Erweiterung fuer Deep Learning auf Streaming-Daten, basierend auf River's Design-Prinzipien ([GitHub](https://github.com/online-ml/deep-river))
- **IFF-DRL (2025):** Inkrementelles Learning dynamisch verfeinert Prognosemodell fuer Alignment mit Markttrends ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417425019165))
- **Signature-Based LightGBM (2022):** Path Signatures als Features + inkrementelles LightGBM zeigten verbesserte Adaptionsfaehigkeit ([ResearchGate](https://www.researchgate.net/publication/366226889_Signature-Based_LightGBM_with_incremental_Learning))

### Relevanz fuer dieses Projekt

**Mittel.** Das aktuelle Retraining (alle 1h, 720h Fenster, ~2s) ist bereits sehr haeufig. Der Hauptvorteil von Online Learning waere:
- **Schnellere Adaption:** Neue Marktphasen werden sofort gelernt, nicht erst nach Stunden
- **Weniger Compute:** 50 neue Baeume statt 500 komplette = 10x weniger Trainingszeit
- **Label-Verfuegbarkeit:** Problem! Das echte Label (Preis nach 72h) ist erst 72h spaeter bekannt. Online Learning mit 72h Delay ist konzeptionell schwierig.

**Empfehlung:** LightGBM Warm-Start (Ansatz 1) als pragmatischer Kompromiss. Volles River-basiertes Online Learning ist wegen des 72h-Label-Delays wenig sinnvoll.

### Risiken und Fallstricke

- **Label-Delay:** Bei 72h Horizont sind Labels erst 72h nach der Prediction verfuegbar. Online Learning verliert seinen Hauptvorteil (sofortige Adaption).
- **Catastrophic Forgetting:** Bei inkrementellem Training kann das Modell alte, aber wichtige Patterns vergessen.
- **Keine Pruning-Option:** LightGBM's init_model fuegt Baeume hinzu, entfernt aber keine alten. Das Modell waechst unbegrenzt.
- **Evaluation schwierig:** Wie misst man ob Online Learning besser ist? Walk-Forward-Backtests werden komplexer.
- **River-Modelle sind schwaecher:** Online-ML-Algorithmen (Hoeffding Trees) erreichen typischerweise nicht die Accuracy von Batch-LightGBM.

### Geschaetzter Aufwand

**2-4 Tage.** LightGBM Warm-Start: 2 Tage. River-Integration: 4-5 Tage. Hauptaufwand: Evaluation ob Online besser ist als Batch.

---

## B6: Feature Importance Drift Detection

### Was es ist

Automatisches Monitoring, ob die Features des Modells ihre Vorhersagekraft verlieren. Wenn z.B. "RSI-14h" bisher wichtigstes Feature war und ploetzlich keine Korrelation mehr zum Target hat, ist das ein Warnsignal. Das System erkennt solche Shifts und kann reagieren (Retraining auslosen, Features austauschen, Trading pausieren).

### Konkrete Implementierungsdetails

**Ansatz 1: Population Stability Index (PSI) pro Feature**
```python
import numpy as np

def calculate_psi(expected, actual, bins=10):
    """PSI zwischen Training-Distribution und aktuellen Daten."""
    expected_perc = np.histogram(expected, bins=bins)[0] / len(expected)
    actual_perc = np.histogram(actual, bins=bins)[0] / len(actual)
    # Epsilon fuer Division-by-Zero
    expected_perc = np.clip(expected_perc, 1e-6, None)
    actual_perc = np.clip(actual_perc, 1e-6, None)
    psi = np.sum((actual_perc - expected_perc) * np.log(actual_perc / expected_perc))
    return psi  # < 0.1: stabil, 0.1-0.25: moderat, > 0.25: signifikanter Drift

# Pro Feature ueberwachen
for feature in model_features:
    psi = calculate_psi(train_data[feature], live_data[feature])
    if psi > 0.25:
        alert(f"Feature Drift: {feature}, PSI={psi:.3f}")
```

**Ansatz 2: Evidently AI (umfassende Reports)**
```python
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset

report = Report(metrics=[DataDriftPreset()])
report.run(reference_data=train_df, current_data=live_df)
# Generiert HTML-Report mit Drift pro Feature (KS-Test, Wasserstein-Distance)
```

**Ansatz 3: Feature Importance Tracking**
```python
# Jede Stunde Feature Importance speichern und Trend ueberwachen
importance = model.feature_importances_
importance_history.append({
    "timestamp": now,
    "importances": dict(zip(feature_names, importance))
})

# Drift Alert wenn sich Top-5 Features aendern
current_top5 = set(sorted_features[:5])
if current_top5 != previous_top5:
    alert("Feature Importance Shift detected!")
```

**Libraries:**
- **Evidently AI:** Umfassendste Open-Source-Loesung, HTML-Reports, 100+ Metriken, effizient und stabil ([GitHub](https://github.com/evidentlyai/evidently))
- **Alibi Detect:** Reicherer Satz an statistischen Tests, unterstuetzt auch Text/Images, Online-Detektoren ([GitHub](https://github.com/SeldonIO/alibi-detect))
- **NannyML:** Spezialisiert auf Timing von Shifts und deren Impact auf Performance ([NannyML](https://nannyml.com/))
- Minimalistisch: `scipy.stats` (KS-Test), `numpy` (PSI manuell)

### Akademische/praktische Evidenz

- **Evidently AI:** De-facto-Standard fuer Data Drift Detection, effizienteste Laufzeit und geringstes RAM in Vergleichsstudien ([arXiv:2404.18673](https://arxiv.org/abs/2404.18673))
- **Drift-Typen:** Data Drift (Feature-Verteilungen aendern sich) und Concept Drift (Zusammenhang Feature->Target aendert sich) muessen separat ueberwacht werden ([EvidentlyAI](https://www.evidentlyai.com/ml-in-production/concept-drift))
- **Unsupervised Concept Drift Detection (2024):** Drift-Erkennung ohne Labels durch Analyse von Deep-Learning-Repraesentationen — relevant weil Labels bei 72h-Horizont verzögert sind ([arXiv:2406.17813](https://arxiv.org/abs/2406.17813))
- **Drift Adversarials (2025):** Warnung: Drift-Detektoren koennen durch adversariale Inputs umgangen werden — System muss robust sein ([ESANN 2025](https://www.esann.org/sites/default/files/proceedings/2025/ES2025-82.pdf))

### Relevanz fuer dieses Projekt

**Hoch.** Bei nur 0.045 Korrelation zwischen Features und Target ist Feature Drift ein existenzielles Risiko. Wenn ein Feature seine ohnehin schwache Vorhersagekraft verliert, kann das den gesamten Edge zerstoeren. Ein einfaches PSI-Monitoring pro Feature (Ansatz 1) ist mit minimalem Aufwand umsetzbar und liefert fruehe Warnsignale.

**Konkreter Use Case:** Das Modell retraint stuendlich — aber ob die Features noch funktionieren, wird nie geprueft. Ein PSI > 0.25 auf einem Top-5-Feature sollte ein Alert ausloesen.

### Risiken und Fallstricke

- **False Positives:** Crypto-Maerkte sind inherent nicht-stationaer. Volatilitaets-Features werden "immer" Drift zeigen. Schwellenwerte muessen sorgfaeltig kalibriert werden.
- **Concept Drift vs Data Drift:** PSI misst nur Feature-Verteilungen, nicht ob der Zusammenhang Feature->Target sich geaendert hat. Fuer Concept Drift braucht man Labels (72h Delay).
- **Alert Fatigue:** Zu viele Alerts fuehren dazu, dass echte Warnsignale ignoriert werden.
- **Reaktion unklar:** Was tut man wenn Drift erkannt wird? Trading pausieren? Retraining mit anderem Fenster? Feature austauschen? Die Reaktionsstrategie muss vordefiniert sein.

### Geschaetzter Aufwand

**2-3 Tage.** PSI-basiertes Monitoring: 1 Tag. Evidently-Integration: 2 Tage. Alert-System (via bestehende `alerting.py`): 0.5 Tage. Reaktionsstrategie definieren: 0.5 Tage.

---

## B7: Adversarial Validation — Train/Test-Distribution-Drift erkennen

### Was es ist

Eine Technik aus Kaggle-Wettbewerben: Ein Klassifikator wird trainiert, um zu unterscheiden ob ein Datenpunkt aus dem Trainings- oder dem Test-Set stammt. Wenn der Klassifikator dies gut kann (AUC > 0.5), besteht ein Distribution Shift zwischen Training und aktueller Marktphase — das Modell wird auf "alten" Daten trainiert, die nicht mehr repraesentativ sind.

### Konkrete Implementierungsdetails

**Implementierung:**
```python
import lightgbm as lgb
import numpy as np
import pandas as pd

def adversarial_validation(X_train, X_live, feature_names=None):
    """Testet ob Train und Live aus gleicher Verteilung stammen.

    Returns:
        auc: < 0.55 = kein Drift, > 0.70 = signifikanter Drift
        top_drift_features: Features die am meisten zum Drift beitragen
    """
    # Label: 0 = Training, 1 = Live
    y = np.concatenate([np.zeros(len(X_train)), np.ones(len(X_live))])
    X = pd.concat([X_train, X_live], ignore_index=True)

    # 5-Fold CV fuer robuste AUC-Schaetzung
    from sklearn.model_selection import cross_val_score
    clf = lgb.LGBMClassifier(
        n_estimators=100, max_depth=3,
        subsample=0.8, verbose=-1, n_jobs=4,
    )
    auc_scores = cross_val_score(clf, X, y, cv=5, scoring="roc_auc")
    mean_auc = np.mean(auc_scores)

    # Feature Importance fuer Drift-Ursachen
    clf.fit(X, y)
    importances = pd.DataFrame({
        "feature": X.columns,
        "importance": clf.feature_importances_,
    }).sort_values("importance", ascending=False)

    return mean_auc, importances

# Integration in Pipeline (vor jedem Trade):
auc, drift_features = adversarial_validation(
    X_train=training_data,       # Letzte 720h
    X_live=last_24h_features,    # Letzte 24h
)
if auc > 0.70:
    logger.warning("distribution_drift_detected", auc=auc,
                   top_feature=drift_features.iloc[0]["feature"])
    # Option: Trainingsfenster verkuerzen, Features filtern, oder pausieren
```

**Erweiterte Nutzung — Feature-Filtering:**
```python
# Features die am meisten zum Drift beitragen entfernen
drift_features_to_drop = importances[importances["importance"] > threshold]["feature"]
X_train_clean = X_train.drop(columns=drift_features_to_drop)
# Modell ohne driftende Features trainieren
```

**Libraries:** `lightgbm` oder `xgboost` (beide geeignet), `sklearn.model_selection` fuer CV

### Akademische/praktische Evidenz

- **Kaggle Best Practice:** Adversarial Validation ist Standard in Top-Kaggle-Loesungen um Train/Test-Leakage und Distribution Shift zu identifizieren ([Kaggle Notebook](https://www.kaggle.com/code/nnjjpp/adversarial-validation-detecting-data-drift))
- **Vorsev & Burnaev (2020):** Formale Analyse von Adversarial Validation als Concept-Drift-Detektor. AV erfasst Aenderungen in der Joint Distribution von Features, inklusive Korrelationen, die univariate Methoden (PSI) verpassen ([arXiv:2004.03045](https://arxiv.org/pdf/2004.03045))
- **APXML (2025):** Praxis-Tutorial fuer AV als Drift-Assessment-Tool in ML-Monitoring, mit scikit-learn und LightGBM ([APXML](https://apxml.com/courses/monitoring-managing-ml-models-production/chapter-2-advanced-drift-detection/adversarial-validation-drift))
- **Drift Adversarials (2025):** Warnung: Adversarial Attacks koennen Drift-Detektoren taeuschen — wichtig fuer das Verstaendnis der Grenzen ([arXiv:2411.16591](https://arxiv.org/abs/2411.16591))

### Relevanz fuer dieses Projekt

**Hoch.** Adversarial Validation ist ein idealer Komplementaer zu B6 (Feature Drift). Waehrend PSI einzelne Features ueberwacht, erfasst AV Shifts in der gesamten Feature-Verteilung — inklusive Interaktionen zwischen Features.

**Konkreter Use Case:** Vor jedem Trade pruefen: "Sehen die aktuellen Features aehnlich aus wie die Trainings-Daten?" Wenn AUC > 0.70, ist das Modell auf einer Verteilung trainiert, die nicht mehr gilt. Dann: Trainingsfenster verkuerzen (z.B. 360h statt 720h) oder Trading pausieren.

**Vorteil gegenueber B6:** AV erkennt multivariate Shifts (z.B. "RSI und Volatilitaet haben gleichzeitig ihre Beziehung geaendert"), die univariate Tests wie PSI nicht sehen.

### Risiken und Fallstricke

- **Compute-Overhead:** AV braucht ein separates LightGBM-Training vor jedem Trade. Bei stuendlichem Trading sind das 24 zusaetzliche Trainings pro Tag.
- **Kleine Live-Samples:** Wenn X_live nur 24h hat (24 Samples), ist der CV-AUC-Schaetzer sehr verrauscht. Mindestens 48-72h Live-Daten verwenden.
- **Interpretierbarkeit:** Ein hoher AUC sagt "es gibt Drift", aber nicht was man dagegen tun soll. Die Feature-Importance gibt Hinweise, aber die optimale Reaktion ist unklar.
- **Schwellenwert-Kalibrierung:** Was ist "zu viel" Drift? In Crypto-Maerkten gibt es natuerliche Regime-Wechsel — nicht jeder Drift ist schlecht.

### Geschaetzter Aufwand

**2-3 Tage.** Core AV-Funktion: 0.5 Tage. Integration in Pipeline mit Schwellenwerten: 1 Tag. Backtest-Validierung: 1-1.5 Tage.

---

## B8: AutoML / Optuna — UMGESETZT 2026-04-06

### Was es ist

Ersetzt den manuellen Grid Search (aktuell in `tuning.py`) durch intelligentere, bayesianische Hyperparameter-Optimierung. Optuna nutzt TPE (Tree-structured Parzen Estimators) um den Suchraum effizient zu explorieren — findet typischerweise bessere Hyperparameter in weniger Versuchen als Grid Search.

### Konkrete Implementierungsdetails

**Ansatz 1: Optuna fuer LightGBM (allgemein)**
```python
import optuna
import lightgbm as lgb
from sklearn.metrics import accuracy_score

def objective(trial):
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1500),
        "num_leaves": trial.suggest_int("num_leaves", 8, 128),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }

    # Walk-Forward Evaluation (NICHT random CV!)
    accuracies = []
    for X_train, y_train, X_test, y_test in walk_forward_splits(...):
        model = lgb.LGBMClassifier(**params, random_state=42, verbose=-1)
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        accuracies.append(accuracy_score(y_test, pred))

    return np.mean(accuracies)

study = optuna.create_study(
    direction="maximize",
    sampler=optuna.samplers.TPESampler(seed=42),
    pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
)
study.optimize(objective, n_trials=100, timeout=3600)  # Max 1h
best_params = study.best_params
```

**Ansatz 2: LightGBMTuner (Optuna-Integration, step-wise)**
```python
from optuna_integration import LightGBMTunerCV

dtrain = lgb.Dataset(X_train, label=y_train)
tuner = LightGBMTunerCV(
    params={"objective": "binary", "metric": "binary_logloss", "verbose": -1},
    train_set=dtrain,
    folds=TimeSeriesSplit(n_splits=5),  # Zeitreihen-CV!
    optuna_seed=42,
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
)
tuner.run()
best_params = tuner.best_params
# Optimiert step-wise: lambda_l1 -> lambda_l2 -> num_leaves -> feature_fraction -> ...
```

**Ansatz 3: Feature Selection mit Optuna**
```python
def objective_with_features(trial):
    # Feature-Auswahl als Hyperparameter
    selected = []
    for feat in all_features:
        if trial.suggest_categorical(f"use_{feat}", [True, False]):
            selected.append(feat)
    if len(selected) < 3:
        return 0.0  # Minimum 3 Features
    # ... Training + Evaluation mit selected Features
```

**Libraries:**
- `optuna` (v4.7.0, Jan 2026)
- `optuna-integration` (LightGBMTuner, LightGBMTunerCV)
- `optuna-dashboard` (Visualisierung der Studien)

**Hyperparameter fuer Optuna selbst:**
- Sampler: TPESampler (default, best fuer <500 Trials)
- Pruner: MedianPruner (pruned schlechte Trials frueh)
- n_trials: 50-100 (guter Kompromiss Speed/Quality)
- timeout: 1800-3600s (30min-1h Obergrenze)

### Akademische/praktische Evidenz

- **Optuna (JMLR 2020):** 16'000+ GitHub Stars, Standard fuer Hyperparameter-Optimierung. Unterstuetzt Multi-Objective, Constrained, Distributed Optimization ([Optuna.org](https://optuna.org/))
- **LightGBMTuner:** Step-wise Optimierung reduziert Suchraum erheblich: optimiert lambda_l1, lambda_l2, num_leaves, feature_fraction, bagging_fraction, bagging_freq, min_child_samples in sinnvoller Reihenfolge ([Optuna-Integration Docs](https://optuna-integration.readthedocs.io/en/stable/reference/generated/optuna_integration.lightgbm.LightGBMTuner.html))
- **TPE vs Grid/Random Search:** TPE findet typischerweise in 30 Trials bessere Parameter als Grid Search mit 100+ Kombinationen ([Medium/Optuna](https://medium.com/optuna/lightgbm-tuner-new-optuna-integration-for-hyperparameter-optimization-8b7095e99258))
- **DeepWiki LightGBM (2025):** Offizielle Empfehlung: FLAML oder Optuna als primaere Tuning-Tools fuer LightGBM ([DeepWiki](https://deepwiki.com/lightgbm-org/LightGBM/8.1-hyperparameter-optimization))

### Relevanz fuer dieses Projekt

**Sehr Hoch.** Das ist wahrscheinlich der groesste Quick-Win. Das aktuelle `tuning.py` nutzt Grid Search mit festem Parameterraum (bis zu 864 Kombinationen bei vollem Grid). Optuna wuerde:
1. **In weniger Versuchen bessere Parameter finden** (30 TPE-Trials ~ 100 Grid-Search-Trials)
2. **Regularisierung (reg_alpha, reg_lambda) mit-optimieren** — aktuell nicht im Grid!
3. **Feature Selection automatisieren** — welche der 19 Features sollen rein?
4. **Pruning**: Schlechte Trials frueh abbrechen spart ~50% Compute

**Wichtig:** Optuna MUSS mit Walk-Forward-Validation (nicht Random-CV!) verwendet werden, da die Daten zeitlich korreliert sind. Standard-CV wuerde massiv overfittet Parameter liefern.

### Risiken und Fallstricke

- **Overfitting auf Validation-Set:** Optuna optimiert auf ein bestimmtes Walk-Forward-Setup. Wenn dieses zu wenig Folds hat, werden die "besten" Parameter nur fuer dieses Setup gut sein.
- **Nicht fuer Live-Retraining:** Optuna-Studien dauern Minuten bis Stunden. Nicht fuer stuendliches Retraining geeignet. Optuna-Parameter sollten periodisch (woechentlich/monatlich) neu optimiert und dann fest im Config gespeichert werden.
- **Suchraum-Design:** Ein zu grosser Suchraum fuehrt zu ineffizienter Suche. Ein zu kleiner verpasst gute Konfigurationen.
- **LightGBMTunerCV Limitierung:** Nutzt intern `lightgbm.cv()`, nicht das sklearn-Interface. Kompatibilitaet mit bestehendem Code pruefen.
- **Compute auf VM:** 100 Trials * Walk-Forward braucht signifikante CPU-Zeit. Optuna-Studien besser lokal laufen lassen und Ergebnisse zur VM deployen.

### Geschaetzter Aufwand

**2-3 Tage** → **Tatsaechlich: 0.5 Tage (als Teil des 5-Quick-Wins Pakets)**

### Umsetzung (2026-04-06)

- Neues Modul `coin_prediction_src/src/models/optuna_tuner.py`
- TPE-Sampler (Tree-structured Parzen Estimator), 30 Trials, 5 Min Timeout
- 9 optimierte Parameter: learning_rate, max_depth, num_leaves, n_estimators, subsample, colsample_bytree, min_child_samples, **reg_alpha**, **reg_lambda** (letzte zwei NEU)
- Integration in `prediction_pipeline.py` (beide Pfade: 1h und 1d)
- Erster Produktions-Run auf VM: 30 Trials in 35s, best_loss=0.644
- Beste gefundene Params: lr=0.104, depth=5, leaves=33, reg_alpha=0.10, reg_lambda=0.33
- Backtest: Win-Rate +4.5 PP (40.8% → 45.3%), Total P&L verbessert um +78.5%
- Config-Felder: `optuna_enabled`, `optuna_n_trials`, `optuna_timeout_seconds`

---

## Priorisierungs-Empfehlung (aktualisiert 2026-04-07)

| # | Massnahme | Impact | Aufwand | Prioritaet |
|---|-----------|--------|---------|------------|
| B8 | ~~AutoML/Optuna~~ | ~~Hoch~~ | ~~2-3 Tage~~ | ~~1~~ **UMGESETZT** |
| B6 | Feature Drift Detection | Hoch | 2-3 Tage | 2 (Risikominimierung) |
| B7 | Adversarial Validation | Hoch | 2-3 Tage | 3 (Komplementaer zu B6) |
| B1 | XGBoost Ensemble | Mittel-Hoch | 1-2 Tage | 4 (Code existiert) |
| B4 | Meta-Learning | Hoch | 5-7 Tage | 5 (braucht Datensammlung) |
| B5 | Online Learning | Mittel | 2-4 Tage | 6 (Label-Delay-Problem) |
| B2 | Neural Networks | Mittel-Niedrig | 5-10 Tage | 7 (zu wenig Daten) |
| B3 | Reinforcement Learning | Niedrig-Mittel | 10-15 Tage | 8 (falsche Architektur) |

**Empfohlene Reihenfolge:** B8 -> B6+B7 -> B1 -> B4 (spaeter)

**Begruendung:** B8 (Optuna) hat das beste Aufwand-/Ertrag-Verhaeltnis und verbessert das bestehende Modell ohne Architektur-Aenderung. B6+B7 sind Risikominimierung — sie verhindern, dass der Bot in Phasen tradet, in denen sein Edge nicht existiert. B1 ist fast fertig implementiert. B4 ist langfristig am vielversprechendsten, braucht aber Vorlauf fuer Datensammlung.

B2 und B3 sind bei der aktuellen Datenmenge (720h Training, 1 Coin, ~454 USDT) nicht sinnvoll.
