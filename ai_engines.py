"""
Pattern AI Engine
=================
Production-oriented, dependency-light pattern engine for BIG/SMALL history.

Design goals:
- deterministic and explainable
- chronological-safe (DB returns newest first)
- multiple independent pattern detectors
- walk-forward backtesting (no future leakage)
- recent-performance weighting
- regime awareness
- calibrated confidence with a conservative WAIT state
- stable public interfaces for app.py
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict
from math import log2
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

BIG = "BIG"
SMALL = "SMALL"
WAIT = "WAIT"
VALID = {BIG, SMALL}

AI_MODE_EMOJIS = {"pattern": "🧩"}
AI_MODE_NAMES = {"pattern": "Pattern AI"}
AI_MODES = {"pattern": {"name": "Pattern AI", "description": "Multi-pattern walk-forward engine"}}
PRO_AI_MODE_NAMES = {}
PRO_AI_MODES = {}


@dataclass(frozen=True)
class PatternSignal:
    name: str
    prediction: str
    strength: float
    support: int
    reason: str


@dataclass
class BacktestStats:
    samples: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.samples if self.samples else 0.5


# ---------- input handling ----------

def _normalize_value(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("size") or value.get("result") or value.get("prediction")
    if value is None:
        return None
    s = str(value).strip().upper()
    if s in {"B", "BIG"}:
        return BIG
    if s in {"S", "SMALL"}:
        return SMALL
    return None


def normalize_history(history: Iterable[Any], newest_first: bool = True) -> List[str]:
    """Normalize history to chronological order: oldest -> newest."""
    values = [_normalize_value(x) for x in history]
    values = [x for x in values if x in VALID]
    if newest_first:
        values.reverse()
    return values


# ---------- basic pattern detectors ----------

def _alternation(seq: Sequence[str]) -> Optional[PatternSignal]:
    if len(seq) < 4:
        return None
    tail = list(seq[-6:])
    if all(tail[i] != tail[i - 1] for i in range(1, len(tail))):
        pred = SMALL if tail[-1] == BIG else BIG
        return PatternSignal("alternation", pred, 0.68, len(tail) - 1, "Recent sequence is alternating")
    return None


def _streak(seq: Sequence[str]) -> Optional[PatternSignal]:
    if not seq:
        return None
    last = seq[-1]
    run = 1
    for x in reversed(seq[:-1]):
        if x != last:
            break
        run += 1
    if run < 2:
        return None
    # A continuation is evidence only when the same run length historically continued.
    continuations = 0
    opportunities = 0
    for i in range(run, len(seq) - 1):
        window = seq[i-run:i]
        if len(window) == run and len(set(window)) == 1:
            opportunities += 1
            if seq[i] == window[-1]:
                continuations += 1
    rate = continuations / opportunities if opportunities else 0.5
    strength = min(0.88, 0.54 + abs(rate - 0.5) * 0.9)
    pred = last if rate >= 0.5 else (SMALL if last == BIG else BIG)
    return PatternSignal("streak", pred, strength, opportunities, f"Current run length={run}; historical continuation={rate:.1%}")


def _transition(seq: Sequence[str]) -> Optional[PatternSignal]:
    if len(seq) < 8:
        return None
    prev = seq[-1]
    counts = Counter()
    total = 0
    for a, b in zip(seq[:-1], seq[1:]):
        if a == prev:
            counts[b] += 1
            total += 1
    if total < 2:
        return None
    pred, count = counts.most_common(1)[0]
    rate = count / total
    strength = min(0.86, 0.50 + max(0.0, rate - 0.5) * 0.95)
    return PatternSignal("transition", pred, strength, total, f"After {prev}, {pred} occurred {rate:.1%} of the time")


def _n_gram(seq: Sequence[str], n: int) -> Optional[PatternSignal]:
    if len(seq) < n + 5:
        return None
    key = tuple(seq[-n:])
    counts = Counter()
    support = 0
    for i in range(n, len(seq) - 1):
        if tuple(seq[i-n:i]) == key:
            counts[seq[i]] += 1
            support += 1
    if support < 2:
        return None
    pred, count = counts.most_common(1)[0]
    rate = count / support
    strength = min(0.90, 0.52 + abs(rate - 0.5) * 0.95)
    return PatternSignal(f"sequence_{n}", pred, strength, support, f"Sequence {''.join(key)} → {pred} ({rate:.1%})")


def _window_bias(seq: Sequence[str], window: int) -> Optional[PatternSignal]:
    if len(seq) < window:
        return None
    c = Counter(seq[-window:])
    if c[BIG] == c[SMALL]:
        return None
    pred = BIG if c[BIG] > c[SMALL] else SMALL
    share = c[pred] / window
    strength = min(0.72, 0.50 + (share - 0.5) * 0.70)
    return PatternSignal(f"window_{window}", pred, strength, window, f"Last {window}: {pred}={c[pred]}, opposite={c[SMALL if pred == BIG else BIG]}")


def _pair_repeat(seq: Sequence[str]) -> Optional[PatternSignal]:
    if len(seq) < 6:
        return None
    pair = tuple(seq[-2:])
    matches = 0
    next_counts = Counter()
    for i in range(2, len(seq) - 1):
        if tuple(seq[i-2:i]) == pair:
            matches += 1
            next_counts[seq[i]] += 1
    if matches < 2:
        return None
    pred, count = next_counts.most_common(1)[0]
    rate = count / matches
    return PatternSignal("pair_repeat", pred, min(0.86, 0.50 + abs(rate-.5)*.9), matches, f"Pair {''.join(pair)} historically followed by {pred} {rate:.1%}")


def detect_patterns(seq: Sequence[str]) -> List[PatternSignal]:
    detectors = [
        _alternation,
        _streak,
        _transition,
        lambda s: _n_gram(s, 2),
        lambda s: _n_gram(s, 3),
        lambda s: _n_gram(s, 4),
        lambda s: _window_bias(s, 5),
        lambda s: _window_bias(s, 8),
        lambda s: _window_bias(s, 12),
        _pair_repeat,
    ]
    signals: List[PatternSignal] = []
    for detector in detectors:
        try:
            signal = detector(seq)
            if signal:
                signals.append(signal)
        except Exception:
            continue
    return signals


# ---------- regime + backtest ----------

def detect_regime(seq: Sequence[str]) -> str:
    if len(seq) < 8:
        return "insufficient_data"
    tail = seq[-12:]
    alternations = sum(a != b for a, b in zip(tail[:-1], tail[1:]))
    max_run = 1
    run = 1
    for a, b in zip(tail[:-1], tail[1:]):
        run = run + 1 if a == b else 1
        max_run = max(max_run, run)
    if alternations >= len(tail) - 2:
        return "alternating"
    if max_run >= 4:
        return "streak_heavy"
    c = Counter(tail)
    if max(c.values()) >= 9:
        return "dominant_side"
    return "mixed"


def _signal_prediction(seq: Sequence[str]) -> Tuple[str, float, List[PatternSignal]]:
    signals = detect_patterns(seq)
    if not signals:
        return WAIT, 0.0, []
    regime = detect_regime(seq)
    votes = {BIG: 0.0, SMALL: 0.0}
    for s in signals:
        regime_bonus = 1.12 if (
            (regime == "alternating" and s.name == "alternation") or
            (regime == "streak_heavy" and s.name == "streak")
        ) else 1.0
        support_bonus = min(1.25, 1.0 + log2(max(1, s.support)) * 0.05)
        votes[s.prediction] += s.strength * regime_bonus * support_bonus
    total = votes[BIG] + votes[SMALL]
    if total <= 0:
        return WAIT, 0.0, signals
    pred = BIG if votes[BIG] > votes[SMALL] else SMALL
    agreement = max(votes[BIG], votes[SMALL]) / total
    confidence = 0.50 + (agreement - 0.50) * 0.78
    if len(signals) < 2:
        confidence *= 0.88
    return pred, max(0.0, min(0.95, confidence)), signals


def walk_forward_backtest(seq: Sequence[str], min_train: int = 30, max_samples: int = 500) -> BacktestStats:
    stats = BacktestStats()
    start = max(min_train, 8)
    begin = max(start, len(seq) - max_samples)
    for i in range(begin, len(seq)):
        pred, conf, _ = _signal_prediction(seq[:i])
        if pred in VALID and conf >= 0.54:
            stats.samples += 1
            stats.correct += int(pred == seq[i])
    return stats


# ---------- public Pattern AI ----------

def pattern_ai_predict(history: Iterable[Any], *, newest_first: bool = True) -> Dict[str, Any]:
    seq = normalize_history(history, newest_first=newest_first)
    if len(seq) < 8:
        return {
            "prediction": WAIT,
            "confidence": 0,
            "reason": f"Need at least 8 valid BIG/SMALL results; received {len(seq)}",
            "display": "WAIT — insufficient history",
            "regime": "insufficient_data",
            "patterns": [],
            "backtest": {"samples": 0, "accuracy": 0.0},
        }

    prediction, raw_conf, signals = _signal_prediction(seq)
    bt = walk_forward_backtest(seq)
    regime = detect_regime(seq)

    # Calibration: historical accuracy adjusts, but cannot manufacture confidence.
    calibrated = raw_conf
    if bt.samples >= 20:
        calibrated *= 0.82 + 0.36 * bt.accuracy
    elif bt.samples >= 8:
        calibrated *= 0.90 + 0.20 * bt.accuracy

    # Conservative abstention for weak agreement / weak evidence.
    if prediction not in VALID or calibrated < 0.54:
        prediction = WAIT

    ranked = sorted(signals, key=lambda x: (x.strength, x.support), reverse=True)
    reasons = [s.reason for s in ranked[:3]]
    if not reasons:
        reasons = ["No reliable pattern evidence"]

    confidence_pct = round(calibrated * 100, 2) if prediction in VALID else 0
    display = f"{prediction} | confidence={confidence_pct:.2f}% | regime={regime}"
    return {
        "prediction": prediction,
        "confidence": confidence_pct,
        "reason": "; ".join(reasons),
        "display": display,
        "regime": regime,
        "patterns": [
            {"name": s.name, "prediction": s.prediction, "strength": round(s.strength, 4), "support": s.support, "reason": s.reason}
            for s in ranked
        ],
        "backtest": {"samples": bt.samples, "accuracy": round(bt.accuracy * 100, 2)},
    }


def psp_ai_predict(history_list: Iterable[Any]) -> Dict[str, Any]:
    """Compatibility wrapper used by the existing bot/app."""
    return pattern_ai_predict(history_list, newest_first=True)


def get_prediction(history_docs, mode, user_pattern=None, model_accuracies=None):
    """Stable generic interface expected by app.py."""
    result = pattern_ai_predict(history_docs, newest_first=True)
    pred = result["prediction"]
    return pred, result["reason"], result["confidence"], result["display"]
