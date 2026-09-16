# ai_engines.py
import numpy as np
import time
import random
import math
from collections import defaultdict

# ==========================================================
# 🌟 Premium Emojis for AI Messages
# ==========================================================
P_AI_CHECK      = '<tg-emoji emoji-id="6210787138267515780">✅</tg-emoji>'
P_AI_CROSS      = '<tg-emoji emoji-id="6210787138267515780">❌</tg-emoji>'
P_AI_INFO       = '<tg-emoji emoji-id="6210787138267515780">ℹ️</tg-emoji>'
P_AI_HOURGLASS  = '<tg-emoji emoji-id="6210787138267515780">⏳</tg-emoji>'
P_AI_UP         = '<tg-emoji emoji-id="6210787138267515780">⬆️</tg-emoji>'
P_AI_DOWN       = '<tg-emoji emoji-id="5875180111744995604">⬇️</tg-emoji>'
P_AI_LEFT_RIGHT = '<tg-emoji emoji-id="5848119413041431362">↔️</tg-emoji>'
P_AI_SPARKLES   = '<tg-emoji emoji-id="5884289942371401145">✨</tg-emoji>'
P_AI_PATTERN    = '<tg-emoji emoji-id="6210787138267515780">🎯</tg-emoji>'
P_AI_MARTINGALE = '<tg-emoji emoji-id="6210787138267515780">🎲</tg-emoji>'
P_AI_ANTIMARTINGALE = '<tg-emoji emoji-id="5868665489092263539">🔄</tg-emoji>'
P_AI_TREND      = '<tg-emoji emoji-id="6210787138267515780">📊</tg-emoji>'
P_AI_FIBONACCI  = '<tg-emoji emoji-id="5877260593903177342">🔢</tg-emoji>'
P_AI_GOLDEN     = '<tg-emoji emoji-id="5869547610204280761">🎯</tg-emoji>'
P_AI_MOMENTUM   = '<tg-emoji emoji-id="5884248697980608904">📈</tg-emoji>'
P_AI_MONTECARLO = '<tg-emoji emoji-id="5884041323843955199">🎲</tg-emoji>'
P_AI_NEURAL     = '<tg-emoji emoji-id="5875180111744995604">🧬</tg-emoji>'
P_AI_REVERSAL   = '<tg-emoji emoji-id="5890997763331591703">⚡</tg-emoji>'
P_AI_WAVE       = '<tg-emoji emoji-id="5967574255670399788">🌊</tg-emoji>'
P_AI_CHAOS      = '<tg-emoji emoji-id="5877443460725739250">🎪</tg-emoji>'
P_AI_STAR       = '<tg-emoji emoji-id="5807868868886009920">⭐</tg-emoji>'
P_AI_ROBOT      = '<tg-emoji emoji-id="5877652234091891383">🤖</tg-emoji>'
P_AI_BRAIN      = '<tg-emoji emoji-id="5868656545634689320">🧠</tg-emoji>'
P_AI_PRO        = '<tg-emoji emoji-id="5807868868886009920">👑</tg-emoji>'

class AIEmoji:
    CHECK = "✅"; CROSS = "❌"; INFO = "ℹ️"; HOURGLASS = "⏳"
    UP = "⬆️"; DOWN = "⬇️"; LEFT_RIGHT = "↔️"; SPARKLES = "✨"
    PATTERN = "🎯"; MARTINGALE = "🎲"; ANTIMARTINGALE = "🔄"
    TREND = "📊"; FIBONACCI = "🔢"; GOLDEN = "🎯"; MOMENTUM = "📈"
    MONTECARLO = "🎲"; NEURAL = "🧬"; REVERSAL = "⚡"; WAVE = "🌊"; CHAOS = "🎪"
    CHART_UP = "📈"; CHART_DOWN = "📉"; STAR = "⭐"
    ROBOT = "🤖"; BRAIN = "🧠"

# ==========================================================
# 🎨 AI Mode Emoji IDs for Reply Keyboard
# ==========================================================
AI_MODE_EMOJIS = {
    "Pattern AI":        "6114102463747332294",
    "Martingale AI":     "6113995669385515849",
    "Anti-Martingale AI":"6210747139237088236",
    "Trend Following":   "5431577498364158238",
    "Fibonacci AI":      "5884290437459480896",
    "Golden Ratio":      "6114102463747332294",
    "Momentum AI":       "5269460053651366623",
    "Monte Carlo":       "6113995669385515849",
    "Neural Pattern":    "5212936673423274058",
    "Quick Reversal":    "6210787138267515780",
    "Wave Analysis":     "5431685735835011215",
    "Chaos Theory":      "6251379582851614396",
    "Ensemble AI":       "6300674206703027915",
    "Bayesian AI":       "5366380461746563803",
    "Markov Chain":      "6210879046272682741",
    "ML Style AI":       "6190369920304289234",
    "Circle Rnd":        "5226711870492126219",
    "Custom Pattern":    "6300853298249336390",
    "AI Auto Swap":      "5868665489092263539",
    "🏆 Best AI Selector": "5884289942371401145"
}

# ==========================================================
# 🔧 Shared Utility Helpers
# ==========================================================
def _to_binary(history):
    return [1 if x == "BIG" else 0 for x in history]

def _label(pred):
    if pred == "wait": return "စောင့်မည်", "⚠️"
    burmese = "အကြီး" if pred == "BIG" else "အသေး"
    dot     = "🔴"    if pred == "BIG" else "🟢"
    return burmese, dot

def _entropy(seg):
    n = len(seg)
    if n == 0: return 0.0
    p = seg.count("BIG") / n
    q = 1 - p
    e = 0.0
    if p > 0: e -= p * np.log2(p)
    if q > 0: e -= q * np.log2(q)
    return e

def _streak(history):
    if not history: return None, 0
    side, count = history[-1], 1
    for r in reversed(history[:-1]):
        if r == side: count += 1
        else: break
    return side, count

def _ema_ratio(history, span):
    seg = history[-span:]
    if not seg: return 0.5
    alpha = 2 / (len(seg) + 1)
    w_sum = w_big = 0.0
    weight = 1.0
    for r in reversed(seg):
        w_big  += weight * (1 if r == "BIG" else 0)
        w_sum  += weight
        weight *= (1 - alpha)
    return w_big / w_sum if w_sum else 0.5

# ============================================================
# 1. Pattern AI
# ============================================================
def detect_active_pattern(history_list):
    if len(history_list) < 4: return None, None

    PATTERNS = [
        ("BB",   ["BIG","BIG"],                            "SMALL"),
        ("SS",   ["SMALL","SMALL"],                        "BIG"),
        ("BS",   ["BIG","SMALL"],                          "BIG"),
        ("SB",   ["SMALL","BIG"],                          "SMALL"),
        ("BBB",  ["BIG","BIG","BIG"],                      "BIG"),
        ("SSS",  ["SMALL","SMALL","SMALL"],                "SMALL"),
        ("BBS",  ["BIG","BIG","SMALL"],                    "BIG"),
        ("BSS",  ["BIG","SMALL","SMALL"],                  "BIG"),
        ("SBB",  ["SMALL","BIG","BIG"],                    "SMALL"),
        ("SSB",  ["SMALL","SMALL","BIG"],                  "SMALL"),
        ("BSB",  ["BIG","SMALL","BIG"],                    "BIG"),
        ("SBS",  ["SMALL","BIG","SMALL"],                  "SMALL"),
        ("BBSS", ["BIG","BIG","SMALL","SMALL"],            "BIG"),
        ("SSBB", ["SMALL","BIG","BIG","SMALL"],            "SMALL"),
        ("BSBS", ["BIG","SMALL","BIG","SMALL"],            "BIG"),
        ("SBSB", ["SMALL","BIG","SMALL","BIG"],            "SMALL"),
        ("BBBS", ["BIG","BIG","BIG","SMALL"],              "BIG"),
        ("SSSB", ["SMALL","SMALL","SMALL","BIG"],          "SMALL"),
        ("BSSS", ["BIG","SMALL","SMALL","SMALL"],          "BIG"),
        ("SBBB", ["SMALL","BIG","BIG","BIG"],              "SMALL"),
        ("BSSBS",["BIG","SMALL","SMALL","BIG","SMALL"],    "BIG"),
        ("SBBSB",["SMALL","BIG","BIG","SMALL","BIG"],      "SMALL"),
        ("BSBSB",["BIG","SMALL","BIG","SMALL","BIG"],      "SMALL"),
        ("SBSBS",["SMALL","BIG","SMALL","BIG","SMALL"],    "BIG"),
        ("BBBSS",["BIG","BIG","BIG","SMALL","SMALL"],      "BIG"),
        ("SSSBB",["SMALL","SMALL","SMALL","BIG","BIG"],    "SMALL"),
    ]

    recent = history_list[-30:]
    best_pattern, best_score, best_next = None, 0, None

    for name, seq, nxt in PATTERNS:
        plen = len(seq)
        if len(recent) < plen: continue
        score = 0.0
        for i in range(len(recent) - plen + 1):
            if recent[i:i+plen] == seq:
                recency_weight = 1.0 + (i / max(len(recent), 1))
                score += recency_weight * plen
        if score > best_score:
            best_score, best_pattern, best_next = score, name, nxt

    if best_score < len(best_next or "") * 1.5 if best_next else True:
        if best_score < 2.0:
            return None, None
    return best_pattern, best_next


def last4_pattern_predict(history_docs):
    """Simple Last-4 sequence mode used by the legacy bot UI.
    It predicts the opposite side when the latest four results are all the
    same; otherwise it follows the alternating/paired 4-result patterns.
    """
    if isinstance(history_docs, list) and history_docs and isinstance(history_docs[0], dict):
        seq = [str(d.get("size", "BIG")).upper() for d in history_docs]
    else:
        seq = [str(x).upper() for x in (history_docs or [])]
    if len(seq) < 4:
        return "wait", "Last 4 Pattern", 50.0, "Need at least 4 results"
    last4 = seq[-4:]
    if last4 == ["BIG", "SMALL", "BIG", "SMALL"]:
        pred = "BIG"
    elif last4 == ["SMALL", "BIG", "SMALL", "BIG"]:
        pred = "SMALL"
    elif last4 == ["BIG", "BIG", "SMALL", "SMALL"]:
        pred = "BIG"
    elif last4 == ["SMALL", "SMALL", "BIG", "BIG"]:
        pred = "SMALL"
    elif len(set(last4)) == 1:
        pred = "SMALL" if last4[-1] == "BIG" else "BIG"
    else:
        # Deterministic frequency fallback over the last 4.
        b = last4.count("BIG")
        s = last4.count("SMALL")
        pred = "BIG" if b <= s else "SMALL"
    return pred, "Last 4 Pattern", 60.0, f"Last 4: {' '.join(x[0] for x in last4)} → {pred}"

def pattern_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", f"{P_AI_PATTERN} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Pattern: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    active_pattern, next_pred = detect_active_pattern(all_history)
    if active_pattern and next_pred:
        burmese, dot = _label(next_pred)
        conf = min(60 + len(active_pattern) * 3, 82)
        return next_pred, f"{P_AI_PATTERN} {next_pred} ({burmese}) {dot}", conf, \
               f"{P_AI_PATTERN} Pattern: {active_pattern} → {next_pred}"
    b = all_history[-20:].count("BIG"); s = 20 - b
    pred = "BIG" if b >= s else "SMALL"
    burmese, dot = _label(pred)
    return pred, f"{P_AI_PATTERN} {pred} ({burmese}) {dot}", 55.0, \
           f"{P_AI_INFO} Freq BIG:{b} SMALL:{s}"

def martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", f"{P_AI_MARTINGALE} BIG (အကြီး) 🔴", 60.0, f"{P_AI_HOURGLASS} Martingale: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    windows   = [(5, 1.0), (10, 1.5), (20, 2.0)]
    big_score = small_score = 0.0

    for win, w in windows:
        seg = all_history[-win:]
        if len(seg) < win // 2: continue
        big_cnt = seg.count("BIG")
        if big_cnt > len(seg) / 2:
            small_score += w          
        elif big_cnt < len(seg) / 2:
            big_score   += w

    side, streak = _streak(all_history)
    if streak >= 3:
        if side == "BIG":   small_score += 1.5
        else:               big_score   += 1.5

    total = big_score + small_score
    if total == 0: total = 1
    if big_score > small_score:
        conf = min(55 + (big_score / total) * 30, 82)
        return "BIG", f"{P_AI_MARTINGALE} BIG (အကြီး) 🔴", conf, f"{P_AI_MARTINGALE} Multi-Win Contrarian → BIG ({conf:.0f}%)"
    else:
        conf = min(55 + (small_score / total) * 30, 82)
        return "SMALL", f"{P_AI_MARTINGALE} SMALL (အသေး) 🟢", conf, f"{P_AI_MARTINGALE} Multi-Win Contrarian → SMALL ({conf:.0f}%)"

def anti_martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", f"{P_AI_ANTIMARTINGALE} BIG (အကြီး) 🔴", 60.0, f"{P_AI_HOURGLASS} Anti-Martingale: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    side, streak = _streak(all_history)

    if streak >= 2:
        conf = min(65 + 5 * (streak - 1), 84)
        burmese, dot = _label(side)
        return side, f"{P_AI_ANTIMARTINGALE} {side} ({burmese}) {dot}", conf, f"{P_AI_ANTIMARTINGALE} Streak ×{streak} → Follow"
    else:
        recent = all_history[-6:]
        big_r  = recent.count("BIG") / len(recent)
        pred   = "BIG" if big_r >= 0.5 else "SMALL"
        burmese, dot = _label(pred)
        return pred, f"{P_AI_ANTIMARTINGALE} {pred} ({burmese}) {dot}", 60.0, f"{P_AI_ANTIMARTINGALE} No streak → Short trend"

def trend_following_predict(history_docs):
    if len(history_docs) < 8: 
        return "BIG", f"{P_AI_TREND} BIG (အကြီး) 🔴", 58.0, f"{P_AI_HOURGLASS} Trend: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    big_8 = all_history[-8:].count("BIG") / 8; big_4 = all_history[-4:].count("BIG") / 4; trend = big_4 - big_8
    if trend > 0.1: 
        return "BIG", f"{P_AI_TREND} BIG (အကြီး) 🔴", 72.0, f"{P_AI_TREND} BIG +{trend*100:.0f}%"
    elif trend < -0.1: 
        return "SMALL", f"{P_AI_TREND} SMALL (အသေး) 🟢", 72.0, f"{P_AI_TREND} SMALL +{abs(trend)*100:.0f}%"
    else:
        last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{P_AI_TREND} {last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 60.0, f"{P_AI_TREND} Sideways"

def fibonacci_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"{P_AI_FIBONACCI} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Fibonacci: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    fib_levels = [2, 3, 5, 8, 13, 21, 34, 55]
    big_w = small_w = 0.0

    for idx, level in enumerate(fib_levels):
        if len(all_history) < level: continue
        seg     = all_history[-level:]
        big_pct = seg.count("BIG") / level
        weight  = 1.0 / (idx + 1)

        if big_pct > 0.618:   small_w += weight
        elif big_pct < 0.382: big_w   += weight
        else:
            mid_trend = all_history[-min(level//2, len(all_history)):].count("BIG") / min(level//2, len(all_history))
            if mid_trend > 0.5: big_w   += weight * 0.5
            else:               small_w += weight * 0.5

    total = big_w + small_w
    if total == 0: total = 1
    if big_w >= small_w:
        conf = min(58 + (big_w / total) * 28, 84)
        return "BIG",   f"{P_AI_FIBONACCI} BIG (အကြီး) 🔴",   conf, f"{P_AI_FIBONACCI} Fib8 → BIG ({conf:.0f}%)"
    else:
        conf = min(58 + (small_w / total) * 28, 84)
        return "SMALL", f"{P_AI_FIBONACCI} SMALL (အသေး) 🟢", conf, f"{P_AI_FIBONACCI} Fib8 → SMALL ({conf:.0f}%)"

def golden_ratio_predict(history_docs):
    if len(history_docs) < 12:
        return "BIG", f"{P_AI_GOLDEN} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Golden Ratio: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    lookbacks = [8, 13, 21]
    votes_big = votes_small = 0

    for lb in lookbacks:
        seg = all_history[-min(lb, len(all_history)):]
        r   = seg.count("BIG") / len(seg)
        if   r > 0.618: votes_small += 1
        elif r < 0.382: votes_big   += 1

    slope = _ema_ratio(all_history, 5) - _ema_ratio(all_history, 13)

    if votes_big > votes_small or (votes_big == votes_small and slope > 0.05):
        conf = min(60 + votes_big * 8 + abs(slope) * 20, 84)
        return "BIG",   f"{P_AI_GOLDEN} BIG (အကြီး) 🔴",   conf, f"{P_AI_GOLDEN} φ-Scale {votes_big}:Oversold {P_AI_UP}"
    elif votes_small > votes_big or (votes_big == votes_small and slope < -0.05):
        conf = min(60 + votes_small * 8 + abs(slope) * 20, 84)
        return "SMALL", f"{P_AI_GOLDEN} SMALL (အသေး) 🟢", conf, f"{P_AI_GOLDEN} φ-Scale {votes_small}:Overbought {P_AI_DOWN}"
    else:
        last = all_history[-1]; burmese, dot = _label(last)
        r21  = all_history[-21:].count("BIG") / 21
        return last, f"{P_AI_GOLDEN} {last} ({burmese}) {dot}", 62.0, f"{P_AI_GOLDEN} φ-Zone {r21*100:.1f}% (Neutral)"

def momentum_predict(history_docs):
    if len(history_docs) < 6:
        return "BIG", f"{P_AI_MOMENTUM} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Momentum: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    window = all_history[-10:]
    n      = len(window)
    alpha  = 0.3
    score  = 0.0
    w      = 1.0
    for r in reversed(window):
        score += w * (1 if r == "BIG" else -1)
        w     *= (1 - alpha)

    if n >= 6:
        half = n // 2
        m1   = sum(1 if r == "BIG" else -1 for r in window[:half])
        m2   = sum(1 if r == "BIG" else -1 for r in window[half:])
        accel = m2 - m1
    else:
        accel = 0

    total_signal = score + accel * 0.3
    threshold    = 1.0

    if total_signal > threshold:
        conf = min(58 + abs(total_signal) * 5, 85)
        return "BIG",   f"{P_AI_MOMENTUM} BIG (အကြီး) 🔴",   conf, f"{P_AI_MOMENTUM} Momentum +{total_signal:.2f} {P_AI_UP}"
    elif total_signal < -threshold:
        conf = min(58 + abs(total_signal) * 5, 85)
        return "SMALL", f"{P_AI_MOMENTUM} SMALL (အသေး) 🟢", conf, f"{P_AI_MOMENTUM} Momentum {total_signal:.2f} {P_AI_DOWN}"
    else:
        last = all_history[-1]; burmese, dot = _label(last)
        return last, f"{P_AI_MOMENTUM} {last} ({burmese}) {dot}", 57.0, f"{P_AI_MOMENTUM} Weak signal ({total_signal:.2f})"

def monte_carlo_predict(history_docs):
    if len(history_docs) < 15:
        return "BIG", f"{P_AI_MONTECARLO} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Monte Carlo: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    half_life  = 10.0
    weights    = [np.exp(-np.log(2) * i / half_life) for i in range(len(all_history))][::-1]
    w_big      = sum(w for w, r in zip(weights, all_history) if r == "BIG")
    w_total    = sum(weights)
    big_prob   = w_big / w_total if w_total > 0 else 0.5

    np.random.seed(int(time.time()) % (2**31 - 1))
    sims     = np.random.random(5000)
    big_wins = int(np.sum(sims < big_prob))

    if big_wins > 2500:
        prob = big_wins / 5000 * 100
        return "BIG",   f"{P_AI_MONTECARLO} BIG (အကြီး) 🔴",   min(prob, 82), f"{P_AI_MONTECARLO} 5K-Sim BIG {prob:.1f}% (p={big_prob:.2f})"
    else:
        prob = (5000 - big_wins) / 5000 * 100
        return "SMALL", f"{P_AI_MONTECARLO} SMALL (အသေး) 🟢", min(prob, 82), f"{P_AI_MONTECARLO} 5K-Sim SMALL {prob:.1f}% (p={1-big_prob:.2f})"

def neural_pattern_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"{P_AI_NEURAL} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Neural: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    big_score = small_score = 0.0

    for win in [3, 5, 7]:
        if len(all_history) < win + 3: continue
        query = all_history[-win:]
        matches_big = matches_small = 0.0
        for i in range(len(all_history) - win):
            candidate = all_history[i:i+win]
            match_count = sum(a == b for a, b in zip(query, candidate))
            if match_count < win - 1: continue          
            weight = match_count / win                  
            nxt    = all_history[i + win]
            if   nxt == "BIG":   matches_big   += weight
            else:                matches_small  += weight
        total_w = matches_big + matches_small
        if total_w > 0:
            w_factor = 1.0 / win                       
            big_score   += (matches_big   / total_w) * w_factor
            small_score += (matches_small / total_w) * w_factor

    total = big_score + small_score
    if total > 0:
        if big_score > small_score:
            conf = min(58 + (big_score / total) * 30, 86)
            return "BIG",   f"{P_AI_NEURAL} BIG (အကြီး) 🔴",   conf, f"{P_AI_NEURAL} kNN-3W BIG {big_score/total*100:.0f}%"
        else:
            conf = min(58 + (small_score / total) * 30, 86)
            return "SMALL", f"{P_AI_NEURAL} SMALL (အသေး) 🟢", conf, f"{P_AI_NEURAL} kNN-3W SMALL {small_score/total*100:.0f}%"
    return "BIG", f"{P_AI_NEURAL} BIG (အကြီး) 🔴", 55.0, f"{P_AI_NEURAL} No match found"

def quick_reversal_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", f"{P_AI_REVERSAL} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Reversal: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    alt_scores = []
    for win in [4, 6, 8, 10]:
        seg = all_history[-win:]
        if len(seg) < win: continue
        alts      = sum(1 for i in range(1, len(seg)) if seg[i] != seg[i-1])
        alt_rate  = alts / (len(seg) - 1)
        alt_scores.append(alt_rate)

    avg_alt = sum(alt_scores) / len(alt_scores) if alt_scores else 0
    side, streak = _streak(all_history)

    if avg_alt > 0.70:                            
        predicted = "SMALL" if side == "BIG" else "BIG"
        conf      = min(60 + avg_alt * 25, 84)
        burmese, dot = _label(predicted)
        return predicted, f"{P_AI_REVERSAL} {predicted} ({burmese}) {dot}", conf, f"{P_AI_REVERSAL} Alt {avg_alt*100:.0f}% → Reverse"
    elif streak >= 3 and avg_alt < 0.40:          
        conf = min(62 + streak * 4, 80)
        burmese, dot = _label(side)
        return side, f"{P_AI_REVERSAL} {side} ({burmese}) {dot}", conf, f"{P_AI_REVERSAL} Streak ×{streak} (Low alt {avg_alt*100:.0f}%)"
    else:
        last = all_history[-1]; burmese, dot = _label(last)
        return last, f"{P_AI_REVERSAL} {last} ({burmese}) {dot}", 58.0, f"{P_AI_REVERSAL} Neutral alt {avg_alt*100:.0f}%"

def wave_analysis_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", f"{P_AI_WAVE} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Wave: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    waves = []
    current, count = all_history[0], 1
    for r in all_history[1:]:
        if r == current: count += 1
        else: waves.append((current, count)); current = r; count = 1
    waves.append((current, count))

    if len(waves) < 3:
        last = all_history[-1]; burmese, dot = _label(last)
        return last, f"{P_AI_WAVE} {last} ({burmese}) {dot}", 56.0, f"{P_AI_WAVE} Building waves..."

    last_w  = waves[-1]    
    prev_w  = waves[-2]

    if last_w[1] >= 3:
        momentum_confirm = _ema_ratio(all_history, 5) > 0.5 if last_w[0] == "BIG" else _ema_ratio(all_history, 5) < 0.5
        conf = min(65 + last_w[1] * 3 + (5 if momentum_confirm else 0), 84)
        burmese, dot = _label(last_w[0])
        return last_w[0], f"{P_AI_WAVE} {last_w[0]} ({burmese}) {dot}", conf, f"{P_AI_WAVE} Impulse W:{last_w[1]} → Continue"

    if last_w[1] <= 2 and prev_w[1] >= 3:
        predicted = "SMALL" if last_w[0] == "BIG" else "BIG"
        ratio = last_w[1] / prev_w[1]
        conf  = min(68 + (1 - ratio) * 20, 83)
        burmese, dot = _label(predicted)
        return predicted, f"{P_AI_WAVE} {predicted} ({burmese}) {dot}", conf, f"{P_AI_WAVE} Correction ({ratio:.0%}) → {predicted}"

    last = all_history[-1]; burmese, dot = _label(last)
    return last, f"{P_AI_WAVE} {last} ({burmese}) {dot}", 58.0, f"{P_AI_WAVE} W{len(waves)} tracking..."

def chaos_theory_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"{P_AI_CHAOS} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Chaos: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    scales  = [3, 5, 8, 13, 20]
    entropies = [_entropy(all_history[-s:]) for s in scales if len(all_history) >= s]

    if len(entropies) >= 3:
        e_trend = entropies[-1] - entropies[0]
    else:
        e_trend = 0

    run_lengths = []
    current, cnt = all_history[-20:][0], 1
    for r in all_history[-20:][1:]:
        if r == current: cnt += 1
        else: run_lengths.append(cnt); current = r; cnt = 1
    run_lengths.append(cnt)
    avg_run = sum(run_lengths) / len(run_lengths) if run_lengths else 1.5

    e_now  = entropies[-1] if entropies else 1.0
    side, streak = _streak(all_history)

    if e_now > 0.95 and avg_run < 1.5:          
        predicted = "SMALL" if side == "BIG" else "BIG"
        burmese, dot = _label(predicted)
        return predicted, f"{P_AI_CHAOS} {predicted} ({burmese}) {dot}", 67.0, f"{P_AI_CHAOS} MaxEntropy+AltMode → {predicted}"

    elif e_now < 0.6 and avg_run >= 2.5:         
        burmese, dot = _label(side)
        return side, f"{P_AI_CHAOS} {side} ({burmese}) {dot}", 70.0, f"{P_AI_CHAOS} OrderedMode run={avg_run:.1f} → {side}"

    elif e_trend > 0.2:                           
        predicted = "SMALL" if side == "BIG" else "BIG"
        burmese, dot = _label(predicted)
        return predicted, f"{P_AI_CHAOS} {predicted} ({burmese}) {dot}", 63.0, f"{P_AI_CHAOS} Entropy↑ {e_now:.2f} → {predicted}"

    else:
        majority = "BIG" if all_history[-8:].count("BIG") > 4 else "SMALL"
        burmese, dot = _label(majority)
        return majority, f"{P_AI_CHAOS} {majority} ({burmese}) {dot}", 58.0, f"{P_AI_CHAOS} Stable H={e_now:.2f}"

def bayesian_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"{P_AI_BRAIN} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Bayesian: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    recent = all_history[-30:]

    counts2 = defaultdict(lambda: {"BIG": 0, "SMALL": 0})
    for i in range(2, len(recent)):
        state = (recent[i-2], recent[i-1])
        counts2[state][recent[i]] += 1

    state2 = (recent[-2], recent[-1])
    c2 = counts2.get(state2, {"BIG": 0, "SMALL": 0})
    total2 = c2["BIG"] + c2["SMALL"]

    if total2 >= 3:                              
        p_big = c2["BIG"] / total2
        pred  = "BIG" if p_big >= 0.5 else "SMALL"
        conf  = min(55 + abs(p_big - 0.5) * 60 + 10, 84)
        burmese, dot = _label(pred)
        return pred, f"{P_AI_BRAIN} {pred} ({burmese}) {dot}", conf, f"{P_AI_BRAIN} 2nd-Order P={p_big*100:.0f}% (n={total2})"

    counts1 = defaultdict(lambda: {"BIG": 0, "SMALL": 0})
    for i in range(1, len(recent)):
        counts1[recent[i-1]][recent[i]] += 1

    state1 = recent[-1]
    c1     = counts1.get(state1, {"BIG": 0, "SMALL": 0})
    total1 = c1["BIG"] + c1["SMALL"]

    if total1 > 0:
        p_big = c1["BIG"] / total1
        pred  = "BIG" if p_big >= 0.5 else "SMALL"
        conf  = min(55 + abs(p_big - 0.5) * 50, 78)
        burmese, dot = _label(pred)
        return pred, f"{P_AI_BRAIN} {pred} ({burmese}) {dot}", conf, f"{P_AI_BRAIN} 1st-Order P(·|{state1})={p_big*100:.0f}%"

    last = all_history[-1]; burmese, dot = _label(last)
    return last, f"{P_AI_BRAIN} {last} ({burmese}) {dot}", 55.0, f"{P_AI_BRAIN} Bayesian: Insufficient data"

def markov_chain_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", f"{P_AI_INFO} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Markov: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    for order in [3, 2, 1]:
        trans = defaultdict(lambda: {"BIG": 0, "SMALL": 0})
        for i in range(order, len(all_history)):
            state = tuple(all_history[i-order:i])
            trans[state][all_history[i]] += 1

        current = tuple(all_history[-order:])
        c       = trans.get(current, {"BIG": 0, "SMALL": 0})
        total   = c["BIG"] + c["SMALL"]

        min_samples = max(2, 4 - order)         
        if total >= min_samples:
            p_big = c["BIG"] / total
            pred  = "BIG" if p_big >= 0.5 else "SMALL"
            conf  = min(55 + abs(p_big - 0.5) * 55 + order * 3, 85)
            burmese, dot = _label(pred)
            return pred, f"{P_AI_INFO} {pred} ({burmese}) {dot}", conf, f"{P_AI_INFO} Markov-{order}rd {p_big*100:.0f}% (n={total})"

    last = all_history[-1]; burmese, dot = _label(last)
    return last, f"{P_AI_INFO} {last} ({burmese}) {dot}", 56.0, f"{P_AI_INFO} Markov: sparse transitions"

def ml_style_predict(history_docs):
    if len(history_docs) < 12:
        return "BIG", f"{P_AI_SPARKLES} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} ML Style: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    r3  = all_history[-3:].count("BIG")  / 3
    r5  = all_history[-5:].count("BIG")  / 5
    r10 = all_history[-10:].count("BIG") / 10
    r20 = all_history[-min(20, len(all_history)):].count("BIG") / min(20, len(all_history))

    trend    = r5 - r10                          
    slope2   = r3 - r5                           

    _, streak = _streak(all_history)
    streak_feat = streak / 8.0                   

    alt_4 = sum(1 for i in range(1, 4) if all_history[-4:][i] != all_history[-4:][i-1]) / 3
    entropy_feat = _entropy(all_history[-8:])    

    score = (
        (r3  - 0.5) * 0.30 +
        (r5  - 0.5) * 0.22 +
        (r10 - 0.5) * 0.15 +
        (r20 - 0.5) * 0.08 +
        trend        * 0.12 +
        slope2       * 0.07 +
        (streak_feat * (1 if all_history[-1] == "BIG" else -1)) * 0.04 +
        (alt_4 - 0.5) * -0.02   
    )

    damp = 1 - (entropy_feat - 0.5) * 0.4

    threshold = 0.04
    if score > threshold:
        conf = min(55 + abs(score) * 100 * damp, 82)
        return "BIG",   f"{P_AI_SPARKLES} BIG (အကြီး) 🔴",   conf, f"{P_AI_SPARKLES} ML8F +{score:.3f}→BIG H={entropy_feat:.2f}"
    elif score < -threshold:
        conf = min(55 + abs(score) * 100 * damp, 82)
        return "SMALL", f"{P_AI_SPARKLES} SMALL (အသေး) 🟢", conf, f"{P_AI_SPARKLES} ML8F {score:.3f}→SMALL H={entropy_feat:.2f}"
    else:
        last = all_history[-1]; burmese, dot = _label(last)
        return last, f"{P_AI_SPARKLES} {last} ({burmese}) {dot}", 55.0, f"{P_AI_SPARKLES} ML8F Neutral {score:.4f}"

def circle_rnd_predict(history_docs):
    wheel = ["BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL"]
    # Deterministic fallback; this mode is heuristic, not random/ML.
    big = history_docs[-8:].count("BIG") if history_docs else 0
    small = history_docs[-8:].count("SMALL") if history_docs else 0
    predicted = "BIG" if big >= small else "SMALL"
    burmese, dot = _label(predicted)
    confidence = 50.0 + (abs(big - small) / max(big + small, 1)) * 15.0
    return predicted, f"{P_AI_STAR} {predicted} ({burmese}) {dot}", round(confidence, 1), "🎡 Circle: deterministic frequency fallback"

def custom_pattern_predict(history_docs, user_pattern="B"):
    if not user_pattern: user_pattern = "B"
    pattern    = user_pattern.upper()
    valid_chars = [c for c in pattern if c in ['B', 'S']]
    if not valid_chars: return "B", "🛠️ B (Custom Pattern)", 100.0, "Custom Pattern"
    clean_pattern = "".join(valid_chars)
    index = len(history_docs) % len(clean_pattern)
    c = clean_pattern[index]
    full = "BIG" if c == "B" else "SMALL"
    return full, f"🛠️ {full} (Custom Pattern)", 100.0, "Custom Pattern"

def auto_swap_predict(history_docs):
    if len(history_docs) < 4:
        return "BIG", f"🔄 BIG (အကြီး) 🔴", 55.0, "🔄 Auto Swap: Data စုဆောင်းဆဲ..."

    docs = list(reversed(history_docs))
    recent = [d.get('size', 'BIG')[0] for d in docs[-4:]]
    recent_str = "".join(recent)

    pattern_map = {
        "BBBB": "B", "SSSS": "S",       
        "BSBS": "B", "SBSB": "S",       
        "BBSS": "B", "SSBB": "S",       
        "BSSB": "B", "SBBS": "S",       
        "BBBS": "S", "SSSB": "B",       
        "BSSS": "S", "SBBB": "B",       
    }

    next_char = pattern_map.get(recent_str)
    if not next_char:
        next_char = recent_str[-1]

    predicted = "BIG" if next_char == "B" else "SMALL"
    burmese, dot = _label(predicted)
    conf = 75.0 if recent_str in pattern_map else 60.0

    return predicted, f"🔄 {predicted} ({burmese}) {dot}", conf, f"🔄 Auto Swap ({recent_str} → {predicted})"

def psp_ai_predict(history_list):
    """
    10-Pattern Dynamic Learning AI
    
    Parameters:
    - history_list: list of strings ["BIG", "SMALL", "BIG", ...]
                   (နောက်ဆုံးထွက်ပွဲမှ စ၍ ရှေ့သို့ စီထားရန်)
    
    Returns:
    - prediction: "BIG" or "SMALL"
    - confidence: float (55.0 - 85.0)
    - reason: string (အကြောင်းပြချက်)
    - display: "BIG (အကြီး) 🔴" or "SMALL (အသေး) 🟢"
    """
    
    # 1️⃣ Pattern Detection Logic
    predicted = "BIG (အကြီး) 🔴"
    base_prob = 55.0
    reason = "Pattern အသစ်ဖြစ်နေသဖြင့် သမိုင်းကြောင်းအရ တွက်ချက်ထားသည်"
    
    MAX_PATTERN_LENGTH = 5
    MIN_PATTERN_LENGTH = 5
    pattern_found = False
    
    # နောက်ဆုံး ပွဲစဉ်ကို ရယူပြီး pattern ရှာခြင်း
    if len(history_list) >= 4:
        for current_len in range(MAX_PATTERN_LENGTH, MIN_PATTERN_LENGTH - 1, -1):
            if len(history_list) > current_len:
                recent_pattern = history_list[-current_len:]
                big_next_count = 0
                small_next_count = 0
                
                # Pattern တွေ့ပါက နောက်ထွက်မည့် ရလဒ်ကို ရေတွက်ခြင်း
                for i in range(len(history_list) - current_len):
                    if history_list[i:i+current_len] == recent_pattern:
                        next_result = history_list[i+current_len]
                        if next_result == 'BIG':
                            big_next_count += 1
                        elif next_result == 'SMALL':
                            small_next_count += 1
                            
                total_pattern_matches = big_next_count + small_next_count
                if total_pattern_matches > 0:
                    big_prob = (big_next_count / total_pattern_matches) * 100
                    small_prob = (small_next_count / total_pattern_matches) * 100
                    pattern_str = "-".join(recent_pattern).replace('BIG', 'B').replace('SMALL', 'S')
                    
                    if big_prob > small_prob:
                        predicted = "BIG (အကြီး) 🔴"
                        base_prob = big_prob
                        reason = f"[{pattern_str}] လာလျှင် အကြီးဆက်ထွက်လေ့ရှိ၍"
                    elif small_prob > big_prob:
                        predicted = "SMALL (အသေး) 🟢"
                        base_prob = small_prob
                        reason = f"[{pattern_str}] လာလျှင် အသေးဆက်ထွက်လေ့ရှိ၍"
                    else:
                        predicted = "BIG (အကြီး) 🔴"
                        base_prob = 50.0
                        reason = f"[{pattern_str}] အရင်က မျှခြေထွက်ဖူး၍ အကြီးရွေးထားသည်"
                    
                    pattern_found = True
                    break
    
    # Pattern မတွေ့ပါက အများဆုံးထွက်ထားသော ရလဒ်ကို ရွေးချယ်ခြင်း
    if not pattern_found:
        if history_list.count("SMALL") > history_list.count("BIG"):
            predicted = "SMALL (အသေး) 🟢"
        else:
            predicted = "BIG (အကြီး) 🔴"
        base_prob = 55.0
        reason = "Pattern အသစ်ဖြစ်နေသဖြင့် သမိုင်းကြောင်းအရ တွက်ချက်ထားသည်"

    # Confidence ကို 85% အထိ ကန့်သတ်ခြင်း
    final_prob = min(round(base_prob, 1), 85.0)
    prediction = "BIG" if "BIG" in predicted else "SMALL"

    return {
        "prediction": prediction,
        "confidence": final_prob,
        "reason": reason,
        "display": predicted
    }

# ============================================================
# 👑 PRO AI FEATURES & NEW ADVANCED MODELS
# ============================================================
def pro_lstm_predict(history_docs):
    if len(history_docs) < 15: return "BIG", f"🧠 LSTM (အကြီး) 🔴", 55.0, "🧠 LSTM: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    recent = all_hist[-5:]
    f_t = sum(1 for i in range(1, 5) if recent[i] != recent[i-1]) / 4.0
    trend = all_hist[-10:].count("BIG") / 10.0
    i_t = abs(trend - 0.5) * 2 
    c_t = (1 - f_t) * (1 if all_hist[-1] == "BIG" else -1) + i_t * (1 if trend > 0.5 else -1)
    pred = "BIG" if c_t > 0 else "SMALL"
    burmese, dot = _label(pred)
    conf = min(60 + abs(c_t) * 20, 88)
    return pred, f"🧠 LSTM {pred} ({burmese}) {dot}", conf, f"🧠 LSTM Cell State: {c_t:.2f}"

def pro_gru_predict(history_docs):
    if len(history_docs) < 10: return "BIG", f"⚡ GRU (အကြီး) 🔴", 55.0, "⚡ GRU: Data စုဆောင်းဆဲ..."
    all_hist = [1 if d.get('size', 'BIG') == "BIG" else 0 for d in reversed(history_docs)]
    h_prev = 0.5
    for x_t in all_hist[-10:]:
        z_t = 0.2 * x_t + 0.8 * h_prev
        r_t = 0.5 
        h_tilde = x_t + r_t * h_prev
        h_prev = (1 - z_t) * h_prev + z_t * h_tilde
    pred = "BIG" if h_prev > 0.5 else "SMALL"
    burmese, dot = _label(pred)
    conf = min(50 + abs(h_prev - 0.5) * 60, 87)
    return pred, f"⚡ GRU {pred} ({burmese}) {dot}", conf, f"⚡ GRU Hidden State: {h_prev:.2f}"

def pro_xgboost_predict(history_docs):
    if len(history_docs) < 12: return "BIG", f"🌲 XGBoost (အကြီး) 🔴", 55.0, "🌲 XGBoost: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    t1 = 1 if all_hist[-3:].count("BIG") >= 2 else -1
    t2 = -1 if all_hist[-1] != all_hist[-2] else 1
    t3 = 1 if all_hist[-10:].count("BIG") >= 5 else -1
    score = (t1 * 0.5) + (t2 * 0.3) + (t3 * 0.2)
    pred = "BIG" if score > 0 else "SMALL"
    burmese, dot = _label(pred)
    conf = min(60 + abs(score) * 25, 90)
    return pred, f"🌲 XGB {pred} ({burmese}) {dot}", conf, f"🌲 XGBoost Score: {score:.2f}"

def pro_lightgbm_predict(history_docs):
    if len(history_docs) < 15: return "BIG", f"🌿 LightGBM (အကြီး) 🔴", 55.0, "🌿 LightGBM: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    bins = {"BB": 0, "BS": 0, "SB": 0, "SS": 0}
    for i in range(1, len(all_hist)-1):
        leaf = all_hist[i-1][0] + all_hist[i][0]
        if all_hist[i+1] == "BIG": bins[leaf] += 1
        else: bins[leaf] -= 1
    current_leaf = all_hist[-2][0] + all_hist[-1][0]
    leaf_score = bins.get(current_leaf, 0)
    pred = "BIG" if leaf_score >= 0 else "SMALL"
    burmese, dot = _label(pred)
    conf = min(55 + abs(leaf_score) * 5, 85)
    return pred, f"🌿 LGBM {pred} ({burmese}) {dot}", conf, f"🌿 LGBM Leaf [{current_leaf}] = {leaf_score}"

def pro_rl_predict(history_docs):
    if len(history_docs) < 20: return "BIG", f"🎮 RL Agent (အကြီး) 🔴", 55.0, "🎮 RL: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    q_table = {
        "BB": {"BIG": 0, "SMALL": 0}, "BS": {"BIG": 0, "SMALL": 0},
        "SB": {"BIG": 0, "SMALL": 0}, "SS": {"BIG": 0, "SMALL": 0}
    }
    alpha, gamma = 0.1, 0.9 
    for i in range(2, len(all_hist)-1):
        state = all_hist[i-2][0] + all_hist[i-1][0]
        actual_next = all_hist[i]
        next_state = all_hist[i-1][0] + actual_next[0]
        for action in ["BIG", "SMALL"]:
            reward = 1 if action == actual_next else -1
            max_future_q = max(q_table[next_state].values())
            q_table[state][action] = q_table[state][action] + alpha * (reward + gamma * max_future_q - q_table[state][action])
    current_state = all_hist[-2][0] + all_hist[-1][0]
    q_big = q_table[current_state]["BIG"]
    q_small = q_table[current_state]["SMALL"]
    pred = "BIG" if q_big > q_small else "SMALL"
    burmese, dot = _label(pred)
    conf = min(60 + abs(q_big - q_small) * 15, 89)
    return pred, f"🎮 RL {pred} ({burmese}) {dot}", conf, f"🎮 RL Q-Value (B:{q_big:.2f} S:{q_small:.2f})"

def pro_ensemble_stacking_predict(history_docs):
    if len(history_docs) < 15: return "BIG", f"📚 Stacking (အကြီး) 🔴", 55.0, "📚 Stacking: Data စုဆောင်းဆဲ..."
    p_xgb, _, conf_xgb, _ = pro_xgboost_predict(history_docs)
    p_lgb, _, conf_lgb, _ = pro_lightgbm_predict(history_docs)
    p_lstm, _, conf_lstm, _ = pro_lstm_predict(history_docs)
    big_w = small_w = 0.0
    for p, c in [(p_xgb, conf_xgb), (p_lgb, conf_lgb), (p_lstm, conf_lstm)]:
        if p == "BIG": big_w += c
        else: small_w += c
    pred = "BIG" if big_w > small_w else "SMALL"
    burmese, dot = _label(pred)
    conf = min(50 + (max(big_w, small_w) / (big_w + small_w)) * 40, 92)
    return pred, f"📚 Stack {pred} ({burmese}) {dot}", conf, f"📚 Stacking Vote: {pred}"

def pro_rolling_stats_predict(history_docs):
    import math
    if len(history_docs) < 10: return "BIG", f"📈 Roll Stats (အကြီး) 🔴", 55.0, "📈 Stats: Data စုဆောင်းဆဲ..."
    all_hist = [1 if d.get('size', 'BIG') == "BIG" else 0 for d in reversed(history_docs)]
    n = len(all_hist[-10:])
    mean = sum(all_hist[-10:]) / n
    variance = sum((x - mean) ** 2 for x in all_hist[-10:]) / n
    std_dev = math.sqrt(variance) if variance > 0 else 0.01
    z_score = (all_hist[-1] - mean) / std_dev
    if z_score > 1.0: pred = "SMALL"  
    elif z_score < -1.0: pred = "BIG" 
    else: pred = "BIG" if mean > 0.5 else "SMALL" 
    burmese, dot = _label(pred)
    conf = min(58 + abs(z_score) * 10, 83)
    return pred, f"📈 Stats {pred} ({burmese}) {dot}", conf, f"📈 Z-Score: {z_score:.2f} (Mean Reversion)"

def pro_entropy_predict(history_docs):
    import math
    if len(history_docs) < 10: return "BIG", f"🌀 Entropy (အကြီး) 🔴", 55.0, "🌀 Entropy: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    recent = all_hist[-8:]
    p_big = recent.count("BIG") / 8.0
    p_small = 1 - p_big
    h = 0.0
    if p_big > 0: h -= p_big * math.log2(p_big)
    if p_small > 0: h -= p_small * math.log2(p_small)
    last = all_hist[-1]
    if h > 0.9: 
        pred = "SMALL" if last == "BIG" else "BIG"
    else:       
        pred = last
    burmese, dot = _label(pred)
    conf = min(60 + abs(0.5 - h) * 40, 85)
    return pred, f"🌀 Entropy {pred} ({burmese}) {dot}", conf, f"🌀 Shannon H: {h:.2f}"

def pro_streak_momentum_predict(history_docs):
    if len(history_docs) < 8: return "BIG", f"🚀 Momentum (အကြီး) 🔴", 55.0, "🚀 Momentum: Data စုဆောင်းဆဲ..."
    all_hist = [d.get('size', 'BIG') for d in reversed(history_docs)]
    _, current_streak = _streak(all_hist)
    _, prev_streak = _streak(all_hist[:-current_streak]) if current_streak < len(all_hist) else ("BIG", 0)
    dv = current_streak - prev_streak
    if dv > 0: 
        pred = all_hist[-1] 
    else:      
        pred = "SMALL" if all_hist[-1] == "BIG" else "BIG"
    burmese, dot = _label(pred)
    conf = min(60 + abs(dv) * 8, 86)
    return pred, f"🚀 Momentum {pred} ({burmese}) {dot}", conf, f"🚀 Streak Δv: {dv}"

def extract_advanced_features(history_docs):
    features = []
    for doc in history_docs:
        num = int(doc.get('number', 0))
        is_even = 1 if num % 2 == 0 else 0
        if num in [2, 4, 6, 8]: color = 1
        elif num in [1, 3, 7, 9]: color = -1
        else: color = 0
        size_val = 1 if doc.get('size', 'BIG') == "BIG" else 0
        features.append([size_val, is_even, color])
    return features

def pro_real_ml_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"🧠 Real ML (အကြီး) 🔴", 55.0, "🧠 Real ML: Data စုဆောင်းဆဲ..."
    
    features = extract_advanced_features(list(reversed(history_docs))[-20:])
    if not features:
        return "wait", "⚠️ Feature Ensemble Wait", 50.0, "⚠️ No features available"
    # Deterministic feature score; no random number and no false claim of a trained ML model.
    size_score = sum(row[0] for row in features) / len(features)
    even_score = sum(row[1] for row in features) / len(features)
    color_score = sum(row[2] for row in features) / max(len(features), 1)
    prob_big = min(max(0.50 + (size_score - 0.50) * 0.60 + color_score * 0.08 + (even_score - 0.50) * 0.04, 0.05), 0.95)
    pred = "BIG" if prob_big >= 0.5 else "SMALL"
    burmese, dot = _label(pred)
    conf = min(50.0 + abs(prob_big - 0.5) * 60.0, 80.0)
    return pred, f"🧠 Feature Ensemble {pred} ({burmese}) {dot}", conf, f"🧠 Deterministic feature probability: {prob_big:.3f}"

def pro_dynamic_ensemble_predict(history_docs, model_accuracies=None):
    if len(history_docs) < 10:
        return "BIG", f"📚 Dynamic Stacking (အကြီး) 🔴", 55.0, "📚 Dynamic: Data စုဆောင်းဆဲ..."

    if not model_accuracies: 
        model_accuracies = {}

    big_score = 0.0
    small_score = 0.0
    
    predictors = [
        ("pattern", pattern_predict),
        ("martingale", martingale_predict),
        ("anti_martingale", anti_martingale_predict),
        ("trend_following", trend_following_predict),
        ("fibonacci", fibonacci_predict)
    ]
    
    for name, predictor_func in predictors:
        try:
            size, _, conf, _ = predictor_func(history_docs)
            accuracy = model_accuracies.get(name, 0.5) 
            weight = (conf / 100.0) * accuracy 
            
            if size == "BIG":
                big_score += weight
            elif size == "SMALL":
                small_score += weight
        except Exception:
            pass

    total = big_score + small_score
    if total == 0: total = 1
    
    pred = "BIG" if big_score > small_score else "SMALL"
    burmese, dot = _label(pred)
    final_conf = min(50 + (max(big_score, small_score) / total) * 45, 95)
    
    if final_conf < 58.0:
        return "wait", f"⚠️ {pred} (Confidence {final_conf:.1f}%)", final_conf, "⚠️ Dynamic Ensemble: မသေချာသဖြင့် ကျော်ပါမည် (Wait)"
        
    return pred, f"📚 Dynamic {pred} ({burmese}) {dot}", final_conf, f"📚 Dynamic Weight Score (B:{big_score:.1f} S:{small_score:.1f})"

# ============================================================
# 🔮 BABATHAPAI Deep Memory AI (9000+ Database Scan Simulation)
# ============================================================
def babathapai_predict(history_docs):
    if len(history_docs) < 15:
        return "BIG", f"🔮 BABATHAPAI (အကြီး) 🔴", 55.0, "🔮 ʙᴀʙᴀᴛʜᴀᴘᴧɪ: Data စုဆောင်းဆဲ..."

    docs = list(reversed(history_docs)) # oldest to newest
    all_history = [d.get('size', 'BIG') for d in docs]
    
    total_len = len(all_history)
    
    recent_10 = all_history[-10:]
    older_100 = all_history[-100:] if total_len >= 100 else all_history
    all_time = all_history
    
    recent_big_ratio = recent_10.count("BIG") / max(len(recent_10), 1)
    older_big_ratio = older_100.count("BIG") / max(len(older_100), 1)
    all_time_big_ratio = all_time.count("BIG") / max(total_len, 1)

    deep_score = 0.0

    # Mean Reversion on Deep History
    if all_time_big_ratio > 0.52:
        deep_score -= 2.0  
    elif all_time_big_ratio < 0.48:
        deep_score += 2.0  
        
    # Medium Term 
    if older_big_ratio > 0.6:
        deep_score -= 1.5
    elif older_big_ratio < 0.4:
        deep_score += 1.5

    # Short Term Momentum
    if recent_big_ratio > 0.7:
        deep_score += 1.0
    elif recent_big_ratio < 0.3:
        deep_score -= 1.0

    # Deep Pattern Match
    if len(all_history) >= 4:
        last_4 = all_history[-4:]
        if last_4 == ["BIG", "SMALL", "BIG", "SMALL"]: 
            deep_score += 2.0  
        elif last_4 == ["SMALL", "BIG", "SMALL", "BIG"]: 
            deep_score -= 2.0  
        elif last_4 == ["BIG", "BIG", "SMALL", "SMALL"]: 
            deep_score += 1.5  
        elif last_4 == ["SMALL", "SMALL", "BIG", "BIG"]: 
            deep_score -= 1.5  

    base_prob = 50.0 + (deep_score * 8.0)
    final_prob = max(10.0, min(base_prob, 95.0))

    pred = "BIG" if final_prob >= 50 else "SMALL"
    confidence = final_prob if pred == "BIG" else 100 - final_prob

    burmese, dot = _label(pred)
    
    if confidence < 56.0:
        return "wait", f"⚠️ ʙᴀʙᴀᴛʜᴀᴘᴧɪ Wait", confidence, f"⚠️ ʙᴀʙᴀᴛʜᴀᴘᴧɪ: {total_len} ပွဲစာတွက်ချက်မှုအရ ရလဒ်မသေချာပါ ({confidence:.1f}%)"

    return pred, f"🔮 ʙᴀʙᴀᴛʜᴀᴘᴧɪ {pred} ({burmese}) {dot}", confidence, f"🔮 Deep Scan ({total_len} ပွဲ): {confidence:.1f}%"

def ensemble_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", f"{P_AI_ROBOT} BIG (အကြီး) 🔴", 55.0, f"{P_AI_HOURGLASS} Ensemble: Data စုဆောင်းဆဲ..."

    predictors = [
        pattern_predict, martingale_predict, anti_martingale_predict,
        trend_following_predict, fibonacci_predict, golden_ratio_predict,
        momentum_predict, monte_carlo_predict, neural_pattern_predict,
        quick_reversal_predict, wave_analysis_predict, chaos_theory_predict,
        bayesian_predict, markov_chain_predict, ml_style_predict,
        auto_swap_predict,
    ]
    big_w = small_w = 0.0
    big_n = small_n = 0

    for predictor in predictors:
        try:
            size, _, prob, _ = predictor(history_docs)
            weight = max(prob - 50, 0) / 50    
            if size == "BIG":
                big_w   += weight; big_n   += 1
            else:
                small_w += weight; small_n += 1
        except:
            pass

    total_w = big_w + small_w
    if total_w == 0: total_w = 1

    if big_w >= small_w:
        conf = min(58 + (big_w / total_w) * 30, 90)
        return "BIG",   f"{P_AI_ROBOT} BIG (အကြီး) 🔴",   conf, f"{P_AI_ROBOT} Ensemble {big_n}AI→BIG W:{big_w:.1f}:{small_w:.1f}"
    else:
        conf = min(58 + (small_w / total_w) * 30, 90)
        return "SMALL", f"{P_AI_ROBOT} SMALL (အသေး) 🟢", conf, f"{P_AI_ROBOT} Ensemble {small_n}AI→SMALL W:{small_w:.1f}:{big_w:.1f}"

def pro_max_predict(history_docs):
    if len(history_docs) < 15:
        return "BIG", f"👑 Pro Max (အကြီး) 🔴", 55.0, "👑 Pro Max: Data စုဆောင်းဆဲ..."

    # Pro AI Model များစာရင်း
    pro_predictors = [
        pro_lstm_predict,
        pro_gru_predict,
        pro_xgboost_predict,
        pro_lightgbm_predict,
        pro_rl_predict,
        pro_ensemble_stacking_predict,
        pro_rolling_stats_predict,
        pro_entropy_predict,
        pro_streak_momentum_predict,
        pro_real_ml_predict,
        ml_style_predict,
        markov_chain_predict,
        bayesian_predict,
        chaos_theory_predict,
        wave_analysis_predict,
        quick_reversal_predict,
        neural_pattern_predict,
        monte_carlo_predict,
        momentum_predict,
        golden_ratio_predict,
        fibonacci_predict,
        trend_following_predict,
        babathapai_predict
    ]

    big_count = 0
    small_count = 0
    total_conf_big = 0.0
    total_conf_small = 0.0

    # Model တစ်ခုချင်းစီ၏ ခန့်မှန်းချက်များကို စစ်ဆေးခြင်း
    for predictor in pro_predictors:
        try:
            pred, _, conf, _ = predictor(history_docs)
            if pred == "BIG":
                big_count += 1
                total_conf_big += conf
            elif pred == "SMALL":
                small_count += 1
                total_conf_small += conf
        except Exception:
            pass

    # အများစု ခန့်မှန်းထားသော ရလဒ်ကို တွက်ချက်ခြင်း
    if big_count > small_count:
        final_pred = "BIG"
        avg_conf = total_conf_big / big_count if big_count > 0 else 55.0
    elif small_count > big_count:
        final_pred = "SMALL"
        avg_conf = total_conf_small / small_count if small_count > 0 else 55.0
    else:
        # မဲအရေအတွက် တူညီနေပါက Confidence အများဆုံးဘက်ကို ရွေးချယ်ခြင်း
        final_pred = "BIG" if total_conf_big >= total_conf_small else "SMALL"
        total_votes = big_count + small_count
        avg_conf = (total_conf_big + total_conf_small) / total_votes if total_votes > 0 else 55.0

    burmese, dot = _label(final_pred)
    
    # Vote အသာစီးရမှုပေါ်မူတည်၍ Confidence ကို မြှင့်တင်ပေးခြင်း (Maximum 98%)
    confidence_boost = abs(big_count - small_count) * 2.5
    final_conf = min(avg_conf + confidence_boost, 98.0)

    # Output ပြန်ထုတ်ပေးခြင်း
    return final_pred, f"👑 Pro Max {final_pred} ({burmese}) {dot}", final_conf, f"👑 Pro Max Vote: B({big_count}) S({small_count})"

# ==========================================================
# 🏆 BEST AI SELECTOR (Auto-Optimizer from 9000+ Database)
# ==========================================================
def _binary_features(seq, order=4):
    """Leakage-safe feature vector for adaptive next-step estimation."""
    if not seq:
        return 0.5
    b = [1.0 if x == "BIG" else 0.0 for x in seq]
    n = len(b)
    # exponentially weighted base rate
    alpha = 0.12
    ew = b[0]
    for x in b[1:]:
        ew = alpha * x + (1 - alpha) * ew

    # recent windows with stronger weight on short windows
    probs = []
    for w in (5, 10, 20, 40, 80):
        if n >= w:
            probs.append((sum(b[-w:]) + 1.0) / (w + 2.0))
    p = 0.35 * ew + 0.45 * (probs[0] if probs else 0.5)
    if len(probs) > 1:
        p += 0.20 * sum(probs[1:]) / (len(probs) - 1)

    # conditional probability of BIG after the latest k outcomes
    for k, weight in ((1, 0.15), (2, 0.20), (3, 0.25), (4, 0.30)):
        if n <= k:
            continue
        pattern = tuple(seq[-k:])
        hits = next_big = 0
        # Laplace smoothing prevents extreme 0/1 probabilities on tiny samples.
        for i in range(k, n):
            if tuple(seq[i-k:i]) == pattern:
                hits += 1
                next_big += b[i]
        if hits:
            cond = (next_big + 2.0) / (hits + 4.0)
            p = (1.0 - weight) * p + weight * cond
    return float(np.clip(p, 0.05, 0.95))


def _adaptive_prediction(seq):
    """Adaptive probability estimator; no claim of guaranteed predictability."""
    p = _binary_features(seq)
    # Only issue a directional signal when evidence clears a meaningful margin.
    if abs(p - 0.5) < 0.055:
        return "wait", p, 0.0
    pred = "BIG" if p > 0.5 else "SMALL"
    confidence = 50.0 + min(abs(p - 0.5) * 100.0, 42.0)
    return pred, p, confidence


def _walk_forward_score(seq, min_train=120, max_eval=2500):
    """Leakage-safe rolling evaluation of the adaptive estimator."""
    n = len(seq)
    if n <= min_train + 10:
        return 50.0, 0
    start = max(min_train, n - max_eval)
    correct = total = 0
    for i in range(start, n):
        pred, _, _ = _adaptive_prediction(seq[:i])
        if pred == "wait":
            continue
        total += 1
        correct += pred == seq[i]
    return (100.0 * correct / total if total else 50.0), total


def best_ai_selector_predict(history_docs):
    """Walk-forward adaptive selector.

    This replaces the old selector that repeatedly ran every heuristic over
    thousands of prefixes. It evaluates a leakage-safe estimator and combines
    its probability with the recent empirical base rate. Backtest accuracy is
    reported honestly; it is not a guarantee of future outcomes.
    """
    docs = list(reversed(history_docs))
    seq = [d.get("size") for d in docs if d.get("size") in ("BIG", "SMALL")]
    if len(seq) < 120:
        return "BIG", "🏆 BEST AI (အကြီး) 🔴", 55.0, "Data မလုံလောက်သေး (Need 120+ valid games)"

    wf_acc, evaluated = _walk_forward_score(seq)
    pred, p_big, conf = _adaptive_prediction(seq)
    if pred == "wait":
        # Preserve a deterministic display prediction while explicitly flagging weak evidence.
        fallback = "BIG" if p_big >= 0.5 else "SMALL"
        return "wait", "🏆 BEST AI ⏸️ WAIT", 50.0, f"Weak evidence; walk-forward accuracy {wf_acc:.1f}% over {evaluated} signals"

    label, dot = _label(pred)
    # Confidence is calibrated from probability distance and capped; it is NOT a win-rate claim.
    final_conf = min(max(conf, 50.0), 92.0)
    return pred, f"🏆 BEST AI {pred} ({label}) {dot}", final_conf, (
        f"Adaptive probability BIG={p_big:.3f}; walk-forward accuracy={wf_acc:.1f}% "
        f"over {evaluated} signals"
    )

# ==========================================
# 📊 AI Modes Dictionary Update
# ==========================================
AI_MODE_NAMES = {
    "pattern":          "Pattern AI",
    "last4_pattern":    "Last 4 Pattern",
    "martingale":       "Martingale AI",
    "anti_martingale":  "Anti-Martingale AI",
    "trend_following":  "Trend Following",
    "fibonacci":        "Fibonacci AI",
    "golden_ratio":     "Golden Ratio",
    "momentum":         "Momentum AI",
    "monte_carlo":      "Monte Carlo",
    "neural_pattern":   "Neural Pattern",
    "quick_reversal":   "Quick Reversal",
    "wave_analysis":    "Wave Analysis",
    "chaos_theory":     "Chaos Theory",
    "ensemble":         "Ensemble AI",
    "bayesian":         "Bayesian AI",
    "markov_chain":     "Markov Chain",
    "ml_style":         "ML Style AI",
    "circle_rnd":       "Circle Rnd",
    "custom_pattern":   "Set Pattern",
    "auto_swap":        "AI Auto Swap",
}

AI_MODES = {
    "last4_pattern":    {"func": last4_pattern_predict, "name": AI_MODE_NAMES["last4_pattern"], "desc": "Last 4 sequence pattern"},
    "pattern":          {"func": pattern_predict,           "name": AI_MODE_NAMES["pattern"],         "desc": "Pattern v2 (26 patterns, recency)"},
    "martingale":       {"func": martingale_predict,        "name": AI_MODE_NAMES["martingale"],      "desc": "Multi-Win Contrarian"},
    "anti_martingale":  {"func": anti_martingale_predict,   "name": AI_MODE_NAMES["anti_martingale"], "desc": "Exp-Streak Follow"},
    "trend_following":  {"func": trend_following_predict,   "name": AI_MODE_NAMES["trend_following"], "desc": "EMA 3-Timeframe"},
    "fibonacci":        {"func": fibonacci_predict,         "name": AI_MODE_NAMES["fibonacci"],       "desc": "Fib8 Weighted"},
    "golden_ratio":     {"func": golden_ratio_predict,      "name": AI_MODE_NAMES["golden_ratio"],    "desc": "φ 3-Scale Consensus"},
    "momentum":         {"func": momentum_predict,          "name": AI_MODE_NAMES["momentum"],        "desc": "ExpDecay+Acceleration"},
    "monte_carlo":      {"func": monte_carlo_predict,       "name": AI_MODE_NAMES["monte_carlo"],     "desc": "5000-Sim Recency-Weighted"},
    "neural_pattern":   {"func": neural_pattern_predict,    "name": AI_MODE_NAMES["neural_pattern"],  "desc": "kNN Multi-Window"},
    "quick_reversal":   {"func": quick_reversal_predict,    "name": AI_MODE_NAMES["quick_reversal"],  "desc": "Multi-Win Alternation"},
    "wave_analysis":    {"func": wave_analysis_predict,     "name": AI_MODE_NAMES["wave_analysis"],   "desc": "Impulse/Correction v2"},
    "chaos_theory":     {"func": chaos_theory_predict,      "name": AI_MODE_NAMES["chaos_theory"],    "desc": "Entropy+RunLength"},
    "ensemble":         {"func": ensemble_predict,          "name": AI_MODE_NAMES["ensemble"],        "desc": "15 AI Confidence-Weighted"},
    "bayesian":         {"func": bayesian_predict,          "name": AI_MODE_NAMES["bayesian"],        "desc": "2nd-Order Conditional"},
    "markov_chain":     {"func": markov_chain_predict,      "name": AI_MODE_NAMES["markov_chain"],    "desc": "3rd-Order Hierarchical"},
    "ml_style":         {"func": ml_style_predict,          "name": AI_MODE_NAMES["ml_style"],        "desc": "8-Feature Weighted"},
    "circle_rnd":       {"func": circle_rnd_predict,        "name": AI_MODE_NAMES["circle_rnd"],      "desc": "Deterministic frequency fallback"},
    "custom_pattern":   {"func": custom_pattern_predict,    "name": AI_MODE_NAMES["custom_pattern"],  "desc": "User စိတ်ကြိုက် Pattern"},
    "auto_swap":        {"func": auto_swap_predict,         "name": AI_MODE_NAMES["auto_swap"],       "desc": "4-Pattern Auto Change"},
    "psp_ai": {
        "func": psp_ai_predict,
        "name": "PSP_AI_PREDICT",
        "desc": "10-Pattern Dynamic Learning"
    },
}

PRO_AI_MODE_NAMES = {
    "pro_lstm": "📊 Pro Sequence Heuristic",
    "pro_gru": "📊 Pro State Heuristic",
    "pro_xgb": "🌲 Pro Tree Heuristic",
    "pro_lgbm": "🌿 Pro Binning Heuristic",
    "pro_rl": "🎮 Pro RL Agent",
    "pro_stacking": "📚 Pro Ensemble Stacking",
    "pro_rolling": "📈 Pro Rolling Stats",
    "pro_entropy": "🌀 Pro Entropy Analysis",
    "pro_streak": "🚀 Pro Streak Momentum",
    "pro_real_ml": "🧠 Pro Feature Ensemble",
    "pro_dynamic": "📚 Pro Dynamic Ensemble",
    "babathapai": "🔮 ʙᴀʙᴀᴛʜᴀᴘᴧɪ",
    "pro_max": "👑 AI Pro Max",
}
AI_MODE_NAMES.update(PRO_AI_MODE_NAMES)
AI_MODE_NAMES["best_ai_selector"] = "🏆 Best AI Selector"

PRO_AI_MODES = {
    "pro_lstm": {"func": pro_lstm_predict, "name": PRO_AI_MODE_NAMES["pro_lstm"], "desc": "Sequence heuristic (not a trained LSTM)"},
    "pro_gru": {"func": pro_gru_predict, "name": PRO_AI_MODE_NAMES["pro_gru"], "desc": "State heuristic (not a trained GRU)"},
    "pro_xgb": {"func": pro_xgboost_predict, "name": PRO_AI_MODE_NAMES["pro_xgb"], "desc": "Tree-style heuristic (not XGBoost)"},
    "pro_lgbm": {"func": pro_lightgbm_predict, "name": PRO_AI_MODE_NAMES["pro_lgbm"], "desc": "Binning heuristic (not LightGBM)"},
    "pro_rl": {"func": pro_rl_predict, "name": PRO_AI_MODE_NAMES["pro_rl"], "desc": "Q-Learning Algorithm"},
    "pro_stacking": {"func": pro_ensemble_stacking_predict, "name": PRO_AI_MODE_NAMES["pro_stacking"], "desc": "Meta-Model Stacking"},
    "pro_rolling": {"func": pro_rolling_stats_predict, "name": PRO_AI_MODE_NAMES["pro_rolling"], "desc": "Z-Score & Variance"},
    "pro_entropy": {"func": pro_entropy_predict, "name": PRO_AI_MODE_NAMES["pro_entropy"], "desc": "Shannon Entropy Chaos Analysis"},
    "pro_streak": {"func": pro_streak_momentum_predict, "name": PRO_AI_MODE_NAMES["pro_streak"], "desc": "Streak Velocity"},
    "pro_real_ml": {"func": pro_real_ml_predict, "name": PRO_AI_MODE_NAMES["pro_real_ml"], "desc": "Feature-based ensemble; no trained ML model"},
    "pro_dynamic": {"func": pro_dynamic_ensemble_predict, "name": PRO_AI_MODE_NAMES["pro_dynamic"], "desc": "Dynamic Accuracy Tracking"},
    "babathapai": {"func": babathapai_predict, "name": PRO_AI_MODE_NAMES["babathapai"], "desc": "Deep Historical Memory Simulation"},
    "pro_max": {"func": pro_max_predict, "name": PRO_AI_MODE_NAMES["pro_max"], "desc": "Ultimate Pro AI Aggregator"},
}
AI_MODES.update(PRO_AI_MODES)
AI_MODES["best_ai_selector"] = {"func": best_ai_selector_predict, "name": AI_MODE_NAMES["best_ai_selector"], "desc": "Leakage-safe adaptive walk-forward selector"}

def get_prediction(history_docs, mode, user_pattern=None, model_accuracies=None):
    if mode == "custom_pattern":
        return custom_pattern_predict(history_docs, user_pattern)
    elif mode == "pro_dynamic":
        return pro_dynamic_ensemble_predict(history_docs, model_accuracies)
        
    mode_info = AI_MODES.get(mode)
    if mode_info: return mode_info["func"](history_docs)
    return AI_MODES["pattern"]["func"](history_docs)
