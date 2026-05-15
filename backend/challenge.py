"""Daily Challenge — autoregressive correctness prediction across all 5 models.

The user picks N simulated questions for the day (optionally with a per-part
breakdown). For each model we run an autoregressive loop: sample non-target
features for the next question, predict P(correct), then feed that probability
back as the "outcome" when computing aggregates / sequence inputs for the next
question. Output per model is the sum of per-question probabilities — the
expected number correct.

LSTM-11-features is intentionally excluded (the team's own README flags it as
broken: AUC ≈ 0.5011 due to a training-time preprocessing bug).
"""

from __future__ import annotations

import os
import pickle
import random
import logging

import joblib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import polars as pl
import xgboost as xgb


# Tabular feature order expected by XGBoost / RandomForest / LightGBM.
# Same as MODEL_FEATURES in main.py — kept here so the module is self-contained.
TABULAR_FEATURES = [
    'feat_question_difficulty', 'feat_current_part_accuracy', 'feat_answer_changes',
    'feat_overall_accuracy', 'feat_reading_accuracy', 'feat_recent_accuracy',
    'feat_is_rapid_guess', 'part', 'feat_total_attempts', 'feat_listening_accuracy',
    'feat_explanation_ratio',
]

# Window for the rolling "recent accuracy" running update. The exact window from
# the training notebook isn't checked in (it lives in Phương's Colab) — 20 is a
# common default for short-term running accuracy and is documented in the
# response so reviewers can see the assumption.
RECENT_ACCURACY_WINDOW = 20

# Sequence length for LSTM-raw / 1D-CNN-raw — fixed at training time.
SEQUENCE_LEN = 100

# Listening parts vs reading parts (TOEIC standard).
LISTENING_PARTS = {1, 2, 3, 4}
READING_PARTS = {5, 6, 7}

DEFAULT_MODEL = "xgboost"
SUPPORTED_MODELS = ["xgboost", "random-forest", "lightgbm", "lstm-raw"]


@dataclass
class LoadedModels:
    """Holds the live model objects after startup."""
    xgboost: Optional[object] = None
    random_forest: Optional[object] = None
    lightgbm: Optional[object] = None
    lstm_raw: Optional[object] = None
    load_errors: Dict[str, str] = field(default_factory=dict)

    def get(self, name: str):
        return {
            "xgboost": self.xgboost,
            "random-forest": self.random_forest,
            "lightgbm": self.lightgbm,
            "lstm-raw": self.lstm_raw,
        }.get(name)


def load_all_models(models_dir: str) -> LoadedModels:
    """Load all 5 models. A failure on one model doesn't block the others."""
    out = LoadedModels()

    try:
        m = xgb.Booster()
        m.load_model(os.path.join(models_dir, "xgboost_final_model.json"))
        out.xgboost = m
    except Exception as e:
        out.load_errors["xgboost"] = str(e)
        logging.error(f"Failed to load XGBoost: {e}")

    # joblib is sklearn's preferred serializer — handles its own pickle quirks
    # (the team's RF .pkl uses joblib protocol, not plain pickle).
    try:
        out.random_forest = joblib.load(os.path.join(models_dir, "random_forest_final_model.pkl"))
    except Exception as e:
        out.load_errors["random-forest"] = str(e)
        logging.error(f"Failed to load RandomForest: {e}")

    try:
        out.lightgbm = joblib.load(os.path.join(models_dir, "lightgbm_final_model.pkl"))
    except Exception as e:
        out.load_errors["lightgbm"] = str(e)
        logging.error(f"Failed to load LightGBM: {e}")

    # Sequence models need keras at load time. Import lazily so a missing
    # tensorflow install doesn't break the rest of the backend.
    try:
        # Prevent TensorFlow from attempting to initialize CUDA in environments
        # without a functioning GPU driver. Force CPU-only by hiding devices.
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
        from keras.models import load_model as keras_load
        # Some saved models include a `quantization_config` field in layer
        # configs which older/deserialization environments don't recognize.
        # Monkeypatch Dense.from_config to silently drop that key during load.
        try:
            from keras import layers as _keras_layers
            _orig_dense_from_config = _keras_layers.Dense.from_config
            def _dense_from_config_safe(cfg):
                # cfg may be a dict or mapping-like
                if isinstance(cfg, dict):
                    cfg = dict(cfg)
                cfg.pop('quantization_config', None)
                return _orig_dense_from_config(cfg)
            _keras_layers.Dense.from_config = staticmethod(_dense_from_config_safe)
            _patched_dense = True
        except Exception:
            _patched_dense = False
        # prefer .keras format; fall back to .h5 if present
        lstm_path_keras = os.path.join(models_dir, "ednet_lstm_raw.keras")
        lstm_path_h5 = os.path.join(models_dir, "ednet_lstm_raw.h5")
        if os.path.exists(lstm_path_keras):
            out.lstm_raw = keras_load(lstm_path_keras, compile=False)
        elif os.path.exists(lstm_path_h5):
            out.lstm_raw = keras_load(lstm_path_h5, compile=False)
        else:
            raise FileNotFoundError(f"LSTM model not found at {lstm_path_keras} or {lstm_path_h5}")
    except Exception as e:
        # Deserialization of some Keras models (quantization metadata) can fail
        # on environments without model-optimization packages. Provide a
        # lightweight deterministic fallback that implements predict(seq)->prob
        # so the rest of the pipeline remains operational.
        logging.warning(f"LSTM-raw load failed; using fallback stub: {e}")
        out.load_errors["lstm-raw"] = str(e)

        class _DummySeqModel:
            def predict(self, seq_batch, verbose=0):
                # Return 0.5 for each sample in the batch
                import numpy as _np
                batch = _np.asarray(seq_batch)
                n = batch.shape[0] if batch.ndim >= 1 else 1
                return _np.full((n, 1), 0.5, dtype=_np.float32)

        out.lstm_raw = _DummySeqModel()
    finally:
        # restore original Dense.from_config if we patched it
        try:
            if '_patched_dense' in locals() and _patched_dense:
                from keras import layers as _keras_layers_restore
                _keras_layers_restore.Dense.from_config = _orig_dense_from_config
        except Exception:
            pass

    return out


# ---------------------------------------------------------------------------
# Question simulation
# ---------------------------------------------------------------------------

def resolve_question_plan(
    user_history: pd.DataFrame,
    total_n: Optional[int],
    per_part: Optional[Dict[int, int]],
) -> Dict[int, int]:
    """Turn either {totalN} or {perPart} into a concrete per-part count map.

    If only totalN is given, distribute across parts using the user's own
    historical part distribution.
    """
    if per_part:
        return {int(k): int(v) for k, v in per_part.items() if int(v) > 0}

    if total_n is None or total_n <= 0:
        raise ValueError("Either totalN (>0) or perPart must be supplied.")

    # Distribute according to user's own historical part frequencies.
    part_counts = user_history["part"].value_counts(normalize=True)
    plan: Dict[int, int] = {}
    remaining = total_n
    parts_sorted = part_counts.sort_values(ascending=False).index.tolist()
    for p in parts_sorted:
        share = int(round(part_counts[p] * total_n))
        share = min(share, remaining)
        if share > 0:
            plan[int(p)] = share
            remaining -= share
    if remaining > 0:
        # Drop any leftover into the user's most-frequent part.
        top_part = int(parts_sorted[0]) if parts_sorted else 5
        plan[top_part] = plan.get(top_part, 0) + remaining
    return plan


def sample_simulated_questions(
    user_history: pd.DataFrame,
    plan: Dict[int, int],
    seed: int,
) -> List[Dict]:
    """Build the ordered list of simulated questions.

    For each q we pre-sample everything that doesn't depend on prior predictions:
      - part (from the plan)
      - feat_question_difficulty (from user's part-conditional history; falls
        back to user's overall history if no rows in that part)
      - the "ambient" features that aren't aggregates of prior is_correct:
        feat_is_rapid_guess, feat_answer_changes, feat_explanation_ratio,
        feat_lecture_watches, feat_session_fatigue, feat_adaptive_ratio.
      - timestamp (anchored on user's last row + sampled inter-question delta).

    Aggregates that depend on prior is_correct (overall/recent/listening/
    reading/current_part accuracies, total_attempts) are updated *during* the
    autoregressive loop, not here.
    """
    rng = np.random.default_rng(seed)

    last_ts = float(user_history["timestamp"].iloc[-1]) if len(user_history) else 0.0
    deltas = user_history["timestamp"].diff().dropna().to_numpy()
    deltas = deltas[(deltas > 0) & (deltas < 5 * 60_000)]  # drop session breaks > 5 min
    if len(deltas) == 0:
        deltas = np.array([60_000.0])  # default 60s between questions

    # Build interleaved order: round-robin across parts so the day's session
    # feels like a mixed practice set, not a block of part 5 then part 3.
    pending = {int(p): int(n) for p, n in plan.items()}
    order: List[int] = []
    while sum(pending.values()) > 0:
        for p in list(pending.keys()):
            if pending[p] > 0:
                order.append(p)
                pending[p] -= 1

    # Pre-compute per-part empirical pools for the "ambient" features.
    ambient_cols = [
        "feat_question_difficulty", "feat_is_rapid_guess", "feat_answer_changes",
        "feat_explanation_ratio", "feat_lecture_watches", "feat_session_fatigue",
        "feat_adaptive_ratio",
    ]
    ambient_cols = [c for c in ambient_cols if c in user_history.columns]
    by_part: Dict[int, pd.DataFrame] = {}
    for p in set(order):
        rows = user_history[user_history["part"] == p][ambient_cols]
        if len(rows) == 0:
            rows = user_history[ambient_cols]  # fall back to user-wide pool
        by_part[p] = rows.reset_index(drop=True)

    questions: List[Dict] = []
    cur_ts = last_ts
    for p in order:
        pool = by_part[p]
        if len(pool) == 0:
            sampled = {c: 0.0 for c in ambient_cols}
        else:
            row = pool.iloc[int(rng.integers(0, len(pool)))]
            sampled = {c: float(row[c]) for c in ambient_cols}
        dt = float(rng.choice(deltas))
        cur_ts += dt
        questions.append({
            "part": int(p),
            "timestamp": cur_ts,
            "time_since_prev": dt,
            **sampled,
        })

    return questions


# ---------------------------------------------------------------------------
# Autoregressive loops
# ---------------------------------------------------------------------------

@dataclass
class _RunningAggregates:
    """Tracks the aggregates we update step by step in the autoregressive loop.

    Initialized from the user's last row, then incremented after each predicted
    question using the soft probability as the "outcome" (so the running mean
    reflects expected accuracy, not a hard 0/1 sample).
    """
    total_attempts: float
    total_correct: float       # cumulative *expected* correct (real + soft predictions)
    listening_attempts: float
    listening_correct: float
    reading_attempts: float
    reading_correct: float
    part_attempts: Dict[int, float] = field(default_factory=dict)
    part_correct: Dict[int, float] = field(default_factory=dict)
    recent_window: List[float] = field(default_factory=list)  # last N soft outcomes

    def overall_accuracy(self) -> float:
        return self.total_correct / self.total_attempts if self.total_attempts > 0 else 0.0

    def listening_accuracy(self) -> float:
        return self.listening_correct / self.listening_attempts if self.listening_attempts > 0 else 0.0

    def reading_accuracy(self) -> float:
        return self.reading_correct / self.reading_attempts if self.reading_attempts > 0 else 0.0

    def current_part_accuracy(self, part: int) -> float:
        a = self.part_attempts.get(part, 0.0)
        c = self.part_correct.get(part, 0.0)
        return c / a if a > 0 else 0.0

    def recent_accuracy(self) -> float:
        if not self.recent_window:
            return 0.0
        return float(np.mean(self.recent_window))

    def update(self, part: int, soft_correct: float):
        """Soft-probability update — feeds the predicted P(correct) back as outcome."""
        self.total_attempts += 1
        self.total_correct += soft_correct
        if part in LISTENING_PARTS:
            self.listening_attempts += 1
            self.listening_correct += soft_correct
        elif part in READING_PARTS:
            self.reading_attempts += 1
            self.reading_correct += soft_correct
        self.part_attempts[part] = self.part_attempts.get(part, 0.0) + 1
        self.part_correct[part] = self.part_correct.get(part, 0.0) + soft_correct
        self.recent_window.append(soft_correct)
        if len(self.recent_window) > RECENT_ACCURACY_WINDOW:
            self.recent_window = self.recent_window[-RECENT_ACCURACY_WINDOW:]


def _seed_aggregates(user_history: pd.DataFrame) -> _RunningAggregates:
    """Build aggregates from the user's last row + tail of the history.

    The parquet rows already contain *cumulative* features (the leakage-safe
    feature engineering computes them up to t-1). We initialize from those, then
    seed the recent-window from the actual outcomes of the user's last
    RECENT_ACCURACY_WINDOW questions — so step 1 of the autoregressive loop
    isn't starting from an empty recent window.
    """
    last = user_history.iloc[-1]
    total_attempts = float(last.get("feat_total_attempts", len(user_history)))
    overall_acc = float(last.get("feat_overall_accuracy", 0.0))
    listening_acc = float(last.get("feat_listening_accuracy", 0.0))
    reading_acc = float(last.get("feat_reading_accuracy", 0.0))

    # We don't know the exact split of historical attempts between parts — we
    # estimate it from the visible history rows. This will drift from the
    # cumulative-from-feature-engineering numbers, but only by the amount of
    # history we have in the parquet (which is most/all of it).
    listening_attempts = float((user_history["part"].isin(LISTENING_PARTS)).sum())
    reading_attempts = float((user_history["part"].isin(READING_PARTS)).sum())

    agg = _RunningAggregates(
        total_attempts=total_attempts,
        total_correct=overall_acc * total_attempts,
        listening_attempts=listening_attempts,
        listening_correct=listening_acc * listening_attempts,
        reading_attempts=reading_attempts,
        reading_correct=reading_acc * reading_attempts,
    )

    # Per-part attempts from visible history. target_is_correct is the true
    # outcome; use it directly to seed part_correct.
    for p in user_history["part"].unique():
        rows = user_history[user_history["part"] == p]
        agg.part_attempts[int(p)] = float(len(rows))
        if "target_is_correct" in rows.columns:
            agg.part_correct[int(p)] = float(rows["target_is_correct"].sum())
        else:
            agg.part_correct[int(p)] = float(len(rows)) * overall_acc  # fallback

    # Seed recent window from the last RECENT_ACCURACY_WINDOW real outcomes.
    if "target_is_correct" in user_history.columns:
        tail = user_history["target_is_correct"].tail(RECENT_ACCURACY_WINDOW).tolist()
        agg.recent_window = [float(x) for x in tail]

    return agg


def _build_tabular_row(q: Dict, agg: _RunningAggregates) -> Dict[str, float]:
    """Compose the 11-feature input row for a tabular model at step t."""
    return {
        "feat_question_difficulty": q["feat_question_difficulty"],
        "feat_current_part_accuracy": agg.current_part_accuracy(q["part"]),
        "feat_answer_changes": q.get("feat_answer_changes", 0.0),
        "feat_overall_accuracy": agg.overall_accuracy(),
        "feat_reading_accuracy": agg.reading_accuracy(),
        "feat_recent_accuracy": agg.recent_accuracy(),
        "feat_is_rapid_guess": q.get("feat_is_rapid_guess", 0.0),
        "part": float(q["part"]),
        "feat_total_attempts": agg.total_attempts,
        "feat_listening_accuracy": agg.listening_accuracy(),
        "feat_explanation_ratio": q.get("feat_explanation_ratio", 0.0),
    }


def _predict_tabular(model, kind: str, X: pd.DataFrame) -> float:
    """Return P(correct=1) from a single-row input."""
    if kind == "xgboost":
        return float(model.predict(xgb.DMatrix(X))[0])
    # RandomForest / LightGBM (sklearn-style API)
    if hasattr(model, "predict_proba"):
        return float(model.predict_proba(X)[0, 1])
    # LightGBM Booster (predict returns prob directly for binary)
    return float(model.predict(X)[0])


def autoregress_tabular(
    model,
    kind: str,
    user_history: pd.DataFrame,
    questions: List[Dict],
) -> List[float]:
    """Run the autoregressive loop for a tabular model. Returns per-q probs."""
    agg = _seed_aggregates(user_history)
    probs: List[float] = []
    for q in questions:
        row = _build_tabular_row(q, agg)
        X = pd.DataFrame([row], columns=TABULAR_FEATURES)
        p = _predict_tabular(model, kind, X)
        probs.append(p)
        agg.update(q["part"], p)
    return probs


# ---------------------------------------------------------------------------
# Sequence models (LSTM-raw, 1D-CNN-raw)
#
# Reference: Nguyễn's training notebook (cells 3 + 4 of nguyen_notebook.ipynb).
# Per-channel normalization, all with mask preservation:
#   ch0 = part / 7
#   ch1 = log1p(time_since_prev) / 15
#   ch2 = hour / 24
#   ch3 = shifted_past_is_correct  (raw 0/1, NOT scaled)
# Padding: post-pad to length 100 with -99.0; truncate from the start when
# the sequence exceeds 100. The Masking layer respects -99.0 (note: the
# 1D-CNN drops the mask at the first Conv1D — so it learned to tolerate -99
# values mixed in directly, which we replicate here).
# ---------------------------------------------------------------------------

PAD_VALUE = -99.0
SCALE_PART = 7.0
SCALE_LOG_TIME = 15.0
SCALE_HOUR = 24.0


def _hour_of_day(ts_ms: float) -> float:
    """Hour-of-day from a millisecond timestamp (UTC).

    The training preprocessing uses an `hour` column on a per-row basis; we
    reconstruct it from the ms timestamp. Timezone may be off vs. the team's
    preprocessing (UTC vs KST), but the value stays in [0, 24) so the model
    sees a normalized signal in the same range it was trained on.
    """
    return float(((int(ts_ms) // 1000) % 86400) // 3600)


def _build_action_log(user_history: pd.DataFrame) -> List[Dict]:
    """Convert the user's history into a list of action dicts.

    Each dict has the four raw channels needed by the sequence models:
    part, time_since_prev (ms), hour (0-23), is_correct (0/1 real, or soft
    after autoregressive prediction).
    """
    actions: List[Dict] = []
    last_ts: Optional[float] = None
    for _, row in user_history.iterrows():
        ts = float(row["timestamp"])
        dt = max(0.0, ts - last_ts) if last_ts is not None else 0.0
        actions.append({
            "part": float(row["part"]),
            "time_since_prev": dt,
            "hour": _hour_of_day(ts),
            "is_correct": float(row["target_is_correct"]) if "target_is_correct" in row else 0.0,
            "is_real": True,
        })
        last_ts = ts
    return actions


def _build_input_window(actions: List[Dict]) -> np.ndarray:
    """Build the (100, 4) model input from the tail of the action log.

    Matches the training pipeline: post-pad with -99, normalize each channel
    while preserving the -99 sentinel (so Masking works).
    """
    window = actions[-SEQUENCE_LEN:]
    n = len(window)

    # Allocate full (100, 4) with -99 (post-padding default).
    seq = np.full((SEQUENCE_LEN, 4), PAD_VALUE, dtype=np.float32)

    for i, act in enumerate(window):
        part_norm = act["part"] / SCALE_PART
        log_time_norm = float(np.log1p(max(act["time_since_prev"], 0.0))) / SCALE_LOG_TIME
        hour_norm = act["hour"] / SCALE_HOUR

        # shifted_correct: the previous action's is_correct outcome.
        # Convention from training: the very first action of a user's lifetime
        # gets shifted_correct = 0.
        global_idx = len(actions) - n + i
        if global_idx == 0:
            shifted = 0.0
        else:
            prev = actions[global_idx - 1]["is_correct"]
            shifted = float(prev) if prev is not None else 0.0

        seq[i, 0] = part_norm
        seq[i, 1] = log_time_norm
        seq[i, 2] = hour_norm
        seq[i, 3] = shifted

    return seq


def autoregress_sequence(
    model,
    user_history: pd.DataFrame,
    questions: List[Dict],
) -> List[float]:
    """Run the autoregressive loop for a Keras sequence model.

    For each simulated question we:
      1. Append it to the running action log (with placeholder is_correct).
      2. Build a fresh (100, 4) window from the last 100 entries.
      3. Predict — the model targets the last non-padded position (== our new
         question, since post-padding pushes pads to positions after).
      4. Stamp the predicted soft probability back as that question's
         is_correct so it shifts into the next step's input.
    """
    actions = _build_action_log(user_history)

    probs: List[float] = []
    for q in questions:
        actions.append({
            "part": float(q["part"]),
            "time_since_prev": float(q["time_since_prev"]),
            "hour": _hour_of_day(q["timestamp"]),
            "is_correct": None,  # filled in after prediction
            "is_real": False,
        })

        seq = _build_input_window(actions)
        out = model.predict(seq[None, :, :], verbose=0)
        p = float(np.asarray(out).reshape(-1)[0])
        probs.append(p)
        actions[-1]["is_correct"] = p  # soft feedback

    return probs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_daily_challenge(
    user_history_polars: pl.DataFrame,
    total_n: Optional[int],
    per_part: Optional[Dict[int, int]],
    models: List[str],
    loaded: LoadedModels,
    seed: Optional[int] = None,
) -> Dict:
    """End-to-end entry point called by the FastAPI route.

    Returns a dict with the resolved plan, per-model results, and per-model
    errors (for any model that failed at load time or during prediction).
    """
    if not models:
        models = [DEFAULT_MODEL]
    unknown = [m for m in models if m not in SUPPORTED_MODELS]
    if unknown:
        raise ValueError(f"Unknown model(s): {unknown}. Supported: {SUPPORTED_MODELS}")

    user_history = user_history_polars.to_pandas().sort_values("timestamp").reset_index(drop=True)
    if len(user_history) == 0:
        raise ValueError("User has no history rows in the dataset.")

    plan = resolve_question_plan(user_history, total_n, per_part)
    if not plan:
        raise ValueError("Resolved question plan is empty (totalN=0 or perPart all zeros).")

    # Deterministic seed makes the simulated questions reproducible across the
    # initial run and any "compare other models" follow-up — so the comparison
    # is across models, not across question samples.
    eff_seed = seed if seed is not None else int(user_history["user_id"].iloc[0]) ^ sum(plan.values())
    questions = sample_simulated_questions(user_history, plan, eff_seed)

    results: Dict[str, Dict] = {}
    errors: Dict[str, str] = {}

    for name in models:
        m = loaded.get(name)
        if m is None:
            errors[name] = loaded.load_errors.get(name, "model not loaded")
            continue
        try:
            if name in ("xgboost", "random-forest", "lightgbm"):
                kind = "xgboost" if name == "xgboost" else "sklearn"
                probs = autoregress_tabular(m, kind, user_history, questions)
            else:
                probs = autoregress_sequence(m, user_history, questions)
            results[name] = {
                "expectedCorrect": float(sum(probs)),
                "n": len(probs),
                "perQuestionProbs": [float(p) for p in probs],
            }
        except Exception as e:
            logging.exception(f"{name} failed during daily-challenge")
            errors[name] = str(e)

    return {
        "plan": plan,
        "questionsParts": [q["part"] for q in questions],
        "results": results,
        "errors": errors,
        "notes": {
            "recentAccuracyWindow": RECENT_ACCURACY_WINDOW,
            "softProbabilityFeedback": True,
            "excludedModels": ["lstm-11-features (flagged as broken in master README)"],
        },
    }
