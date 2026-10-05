from __future__ import annotations

import math
import threading
from collections import OrderedDict
from typing import Any

import numpy as np
from sklearn.ensemble import (
    AdaBoostClassifier, BaggingClassifier, ExtraTreesClassifier,
    GradientBoostingClassifier, HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
from sklearn.linear_model import (
    LogisticRegression, PassiveAggressiveClassifier, Perceptron,
    RidgeClassifier, SGDClassifier,
)
from sklearn.naive_bayes import BernoulliNB, GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC, SVC
from sklearn.tree import DecisionTreeClassifier, ExtraTreeClassifier

MIN_SAMPLES = 40
LOOKBACK = 32
MAX_TRAIN = 2200
_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 4

MODEL_NAMES = [
    "Logistic Regression", "Random Forest", "Extra Trees", "Gradient Boosting",
    "Hist Gradient Boosting", "AdaBoost", "Decision Tree", "Extra Tree",
    "Bagging", "K-Nearest Neighbors", "Gaussian Naive Bayes", "Bernoulli Naive Bayes",
    "SGD Log Loss", "SGD Modified Huber", "Perceptron", "Passive Aggressive",
    "Linear SVM", "RBF SVM", "MLP Neural Network", "Ridge Classifier",
]


def _normalize_docs(history_docs):
    if not history_docs:
        return []
    if isinstance(history_docs[0], dict):
        docs = list(reversed(history_docs))  # DB normally returns newest first.
        out = []
        for d in docs:
            try:
                size = str(d.get("size", "BIG")).upper()
                if size not in ("BIG", "SMALL"):
                    continue
                num = int(d.get("number", 0))
                out.append((size, num))
            except Exception:
                continue
        return out
    return [(str(x).upper(), 0) for x in history_docs if str(x).upper() in ("BIG", "SMALL")]


def _features(past):
    """Build fixed-length features from past observations only."""
    sizes = [1.0 if s == "BIG" else 0.0 for s, _ in past]
    nums = [float(n) / 9.0 for _, n in past]
    if not sizes:
        return np.zeros(LOOKBACK + 18, dtype=float)
    pad = [0.5] * max(0, LOOKBACK - len(sizes))
    lag = (pad + sizes[-LOOKBACK:])[-LOOKBACK:]
    recent = sizes[-min(10, len(sizes)):]
    recent20 = sizes[-min(20, len(sizes)):]
    recent40 = sizes[-min(40, len(sizes)):]
    recent_nums = nums[-min(10, len(nums)):]
    last = sizes[-1]
    run = 1
    while run < len(sizes) and sizes[-1-run] == last:
        run += 1
    transitions = sum(1 for a, b in zip(sizes[-20:-1], sizes[-19:]) if a != b) if len(sizes) > 1 else 0
    def mean(xs): return float(np.mean(xs)) if xs else 0.5
    def std(xs): return float(np.std(xs)) if xs else 0.0
    # Number-derived features are historical only; they are not the target.
    evens = [1.0 if int(n) % 2 == 0 else 0.0 for _, n in past[-20:]]
    colors = []
    for _, n in past[-20:]:
        colors.append(1.0 if n in (2, 4, 6, 8) else (-1.0 if n in (1, 3, 7, 9) else 0.0))
    extras = [
        mean(recent), mean(recent20), mean(recent40),
        std(recent), std(recent20),
        run / max(1.0, len(sizes)), min(run, 12) / 12.0,
        transitions / max(1.0, len(sizes[-20:])),
        mean(evens), mean(colors), mean(recent_nums),
        sizes[-1],
        1.0 if len(sizes) >= 2 and sizes[-1] != sizes[-2] else 0.0,
        1.0 if len(sizes) >= 3 and sizes[-1] == sizes[-3] else 0.0,
        1.0 if len(sizes) >= 4 and sizes[-1] == sizes[-2] == sizes[-3] else 0.0,
        mean(sizes[-5:]), mean(sizes[-8:]), mean(sizes[-15:]),
    ]
    return np.asarray(lag + extras, dtype=float)


def _dataset(obs):
    X, y = [], []
    # Each target y[t] is predicted from obs[:t], never from obs[t:].
    for t in range(1, len(obs)):
        X.append(_features(obs[:t]))
        y.append(1 if obs[t][0] == "BIG" else 0)
    return np.asarray(X, dtype=float), np.asarray(y, dtype=int)


def _models():
    return [
        ("Logistic Regression", make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.5, random_state=42))),
        ("Random Forest", RandomForestClassifier(n_estimators=120, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1)),
        ("Extra Trees", ExtraTreesClassifier(n_estimators=120, max_depth=10, min_samples_leaf=2, random_state=42, n_jobs=-1)),
        ("Gradient Boosting", GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, random_state=42)),
        ("Hist Gradient Boosting", HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, learning_rate=0.05, random_state=42)),
        ("AdaBoost", AdaBoostClassifier(n_estimators=80, learning_rate=0.05, random_state=42)),
        ("Decision Tree", DecisionTreeClassifier(max_depth=6, min_samples_leaf=4, random_state=42)),
        ("Extra Tree", ExtraTreeClassifier(max_depth=7, min_samples_leaf=4, random_state=42)),
        ("Bagging", BaggingClassifier(n_estimators=80, max_samples=0.8, random_state=42, n_jobs=-1)),
        ("K-Nearest Neighbors", make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=9, weights="distance"))),
        ("Gaussian Naive Bayes", GaussianNB()),
        ("Bernoulli Naive Bayes", BernoulliNB(alpha=0.5)),
        ("SGD Log Loss", make_pipeline(StandardScaler(), SGDClassifier(loss="log_loss", alpha=0.0005, max_iter=800, random_state=42))),
        ("SGD Modified Huber", make_pipeline(StandardScaler(), SGDClassifier(loss="modified_huber", alpha=0.0005, max_iter=800, random_state=42))),
        ("Perceptron", make_pipeline(StandardScaler(), Perceptron(max_iter=600, random_state=42))),
        ("Passive Aggressive", make_pipeline(StandardScaler(), PassiveAggressiveClassifier(max_iter=600, random_state=42, C=0.2))),
        ("Linear SVM", make_pipeline(StandardScaler(), LinearSVC(C=0.25, random_state=42, max_iter=2000))),
        ("RBF SVM", make_pipeline(StandardScaler(), SVC(C=0.7, gamma="scale", probability=True, random_state=42))),
        ("MLP Neural Network", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), alpha=0.002, max_iter=350, early_stopping=True, random_state=42))),
        ("Ridge Classifier", make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0))),
    ]


def _prob_big(model, x):
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(x)[0]
        classes = getattr(model, "classes_", np.array([0, 1]))
        try:
            idx = list(classes).index(1)
            return float(p[idx])
        except Exception:
            return float(p[-1])
    if hasattr(model, "decision_function"):
        score = float(np.asarray(model.decision_function(x)).ravel()[0])
        return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, score))))
    return 1.0 if int(model.predict(x)[0]) == 1 else 0.0


def predict(history_docs):
    obs = _normalize_docs(history_docs)
    if len(obs) < MIN_SAMPLES:
        return "wait", "🤖 Real ML 20 Models: Data စုဆောင်းဆဲ", 50.0, f"Need at least {MIN_SAMPLES} historical results"

    # Cache only by the current history tail; new result => new training set.
    issue_key = tuple((s, n) for s, n in obs[-LOOKBACK:])
    with _CACHE_LOCK:
        cached = _CACHE.get(issue_key)
        if cached is not None:
            return cached

    X, y = _dataset(obs[-(MAX_TRAIN + LOOKBACK):])
    if len(X) < MIN_SAMPLES - 1 or len(np.unique(y)) < 2:
        return "wait", "🤖 Real ML 20 Models: insufficient class diversity", 50.0, "Need both BIG and SMALL labels"

    # Chronological holdout: no random shuffling across time.
    split = max(int(len(X) * 0.8), MIN_SAMPLES - 1)
    split = min(split, len(X) - 5)
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]
    x_now = _features(obs).reshape(1, -1)

    votes = []
    details = []
    for name, model in _models():
        try:
            model.fit(X_train, y_train)
            val_acc = float(model.score(X_val, y_val)) if len(X_val) else 0.5
            p = _prob_big(model, x_now)
            # Accuracy is used only as a modest ensemble weight; it is not a win-rate claim.
            weight = 0.5 + max(0.0, min(1.0, val_acc) - 0.5) * 1.5
            votes.append((p, weight))
            details.append((name, p, val_acc))
        except Exception as exc:
            details.append((name, None, None))

    if not votes:
        return "wait", "🤖 Real ML 20 Models: training failed", 50.0, "No model completed training"

    weighted_p = sum(p * w for p, w in votes) / sum(w for _, w in votes)
    pred = "BIG" if weighted_p >= 0.5 else "SMALL"
    # This is model probability, not guaranteed outcome probability.
    confidence = 50.0 + abs(weighted_p - 0.5) * 90.0
    confidence = max(50.0, min(90.0, confidence))
    big_votes = sum(1 for p, _ in votes if p >= 0.5)
    small_votes = len(votes) - big_votes
    avg_val = sum(a for _, _, a in details if a is not None) / max(1, sum(1 for _, _, a in details if a is not None))
    reason = (
        f"20-model chronological ensemble | BIG votes {big_votes} / SMALL votes {small_votes} | "
        f"weighted P(BIG)={weighted_p:.3f} | holdout mean accuracy={avg_val:.1%}"
    )
    result = (pred, f"🤖 Real ML 20 → {pred} {'🔴' if pred == 'BIG' else '🟢'}", confidence, reason)
    with _CACHE_LOCK:
        _CACHE[issue_key] = result
        _CACHE.move_to_end(issue_key)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return result
