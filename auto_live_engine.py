#!/usr/bin/env python3
"""
Auto-Incrementing Live Prediction & Real-Time Tracking Engine for WinGo.
Automatically calculates next period number, runs quantum-wavelet alpha algorithms,
and records live rounds to live_wingo_collected.csv.
"""

import os
import csv
import math
from datetime import datetime

CSV_FILE = "live_wingo_collected.csv"

def get_latest_history(game_filter=None, limit=30):
    records = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    num = int(r["number"])
                    g = r.get("game", "")
                    if game_filter and game_filter.lower() not in g.lower():
                        continue
                    records.append({
                        "period": str(r.get("period", "")).strip(),
                        "number": num,
                        "is_big": 1 if num >= 5 else 0,
                        "spin": 1 if num >= 5 else -1,
                        "color": r.get("color", "")
                    })
                except Exception:
                    continue
    return sorted(records, key=lambda x: str(x["period"]))[-limit:]

def predict_next_round(recent_numbers, last_period_str=None, game_type="WinGo 30S"):
    """
    recent_numbers: list of integer draw numbers (e.g. [7, 3, 2, 8, 9])
    last_period_str: string representation of the last completed period (e.g. '20260901100052016')
    """
    # 1. Calculate Next Period Number automatically
    if last_period_str and str(last_period_str).isdigit():
        next_period = str(int(last_period_str) + 1)
    else:
        # Generate standard timestamp-based period
        now = datetime.now()
        prefix = now.strftime("%Y%m%d")
        game_code = "5" if "30" in game_type else "1"
        next_period = f"{prefix}1000{game_code}0001"

    if len(recent_numbers) < 4:
        return {
            "target_period": next_period,
            "prediction": "HOLD / INSUFFICIENT DATA",
            "confidence": 50.0,
            "action": "SKIP (Send at least 4 numbers)",
            "stake": 0.0,
            "reasons": ["Awaiting initial data buffer"]
        }

    is_big = [1 if n >= 5 else 0 for n in recent_numbers]
    spins = [1 if n >= 5 else -1 for n in recent_numbers]
    last_bs = is_big[-1]
    n = len(recent_numbers)

    # 1. Calculate Streak
    streak = 1
    for i in range(n - 2, -1, -1):
        if is_big[i] == last_bs: streak += 1
        else: break

    # 2. 1D Ising Spin Coupling J_t
    k = min(n, 10)
    coupling_sum = sum(spins[i] * spins[i-1] for i in range(n - k + 1, n))
    J_t = coupling_sum / max(1, k - 1)

    # 3. 2nd-Order Markov Transition
    s1, s2 = is_big[-2], is_big[-1]
    m_tot, m_big = 2.0, 1.0
    for i in range(n - 2):
        if is_big[i] == s1 and is_big[i+1] == s2:
            m_tot += 1.0
            if is_big[i+2] == 1: m_big += 1.0
    p_markov = m_big / m_tot

    # 4. Morlet Wavelet Phase Transform
    nums_centered = [x - 4.5 for x in recent_numbers[-min(14, n):]]
    scale = 3.0
    re_sum, im_sum = 0.0, 0.0
    for tau in range(len(nums_centered)):
        dt = (len(nums_centered) - 1 - tau) / scale
        env = math.exp(-0.5 * (dt**2))
        re_sum += nums_centered[tau] * env * math.cos(5.0 * dt)
        im_sum -= nums_centered[tau] * env * math.sin(5.0 * dt)
    wave_pow = math.sqrt(re_sum**2 + im_sum**2) / math.sqrt(scale)
    phase = math.atan2(im_sum, re_sum)

    # 5. Trailing 3-Sum Momentum
    three_sum = sum(recent_numbers[-3:])

    # Multi-Condition Alignment
    bullish_conds = 0
    bearish_conds = 0
    reasons = []

    if p_markov >= 0.60:
        bullish_conds += 1
        reasons.append(f"Markov 2nd-order P(Big)={p_markov:.2f}")
    elif p_markov <= 0.40:
        bearish_conds += 1
        reasons.append(f"Markov 2nd-order P(Small)={1.0-p_markov:.2f}")

    if wave_pow > 2.0:
        if math.cos(phase) > 0.35:
            bullish_conds += 1
            reasons.append("Wavelet harmonic crest alignment (Big cycle)")
        elif math.cos(phase) < -0.35:
            bearish_conds += 1
            reasons.append("Wavelet trough cycle alignment (Small cycle)")

    if J_t < -0.20 and streak >= 3:
        if last_bs == 0:
            bullish_conds += 1
            reasons.append(f"Antiferromagnetic chop reversal after streak {streak}")
        else:
            bearish_conds += 1
            reasons.append(f"Antiferromagnetic chop reversal after streak {streak}")
    elif J_t > 0.20 and streak >= 3:
        if last_bs == 1:
            bullish_conds += 1
            reasons.append(f"Ferromagnetic dragon persistence on streak {streak}")
        else:
            bearish_conds += 1
            reasons.append(f"Ferromagnetic dragon persistence on streak {streak}")

    if three_sum >= 16:
        bullish_conds += 1
        reasons.append(f"3-Period moving velocity high ({three_sum})")
    elif three_sum <= 9:
        bearish_conds += 1
        reasons.append(f"3-Period moving velocity low ({three_sum})")

    # Decision Matrix
    if bullish_conds >= 2 and bearish_conds == 0:
        pred = "BIG (5-9)"
        conf = min(85.0, 68.0 + bullish_conds * 5.0)
        stake = 50.0 if conf >= 78.0 else (35.0 if conf >= 72.0 else 20.0)
        action = "STRONG TRADE" if stake >= 35.0 else "STANDARD TRADE"
    elif bearish_conds >= 2 and bullish_conds == 0:
        pred = "SMALL (0-4)"
        conf = min(85.0, 68.0 + bearish_conds * 5.0)
        stake = 50.0 if conf >= 78.0 else (35.0 if conf >= 72.0 else 20.0)
        action = "STRONG TRADE" if stake >= 35.0 else "STANDARD TRADE"
    else:
        pred = "NEUTRAL / HOLD"
        conf = 50.0 + abs(bullish_conds - bearish_conds) * 3.0
        stake = 0.0
        action = "HOLD / SKIP (Noise Filter Active)"
        reasons.append("Signals in 50-50 noise band")

    return {
        "target_period": next_period,
        "prediction": pred,
        "confidence": round(conf, 1),
        "action": action,
        "recommended_stake": stake,
        "reasons": reasons,
        "streak": streak,
        "ising_coupling": round(J_t, 2),
        "three_sum": three_sum
    }

def record_live_draw(period, number, game="WinGo 30S", color=""):
    """Appends live draw to live_wingo_collected.csv."""
    is_big = 1 if number >= 5 else 0
    bs_str = "Big" if is_big == 1 else "Small"
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "game": game,
        "period": str(period),
        "number": number,
        "is_big": is_big,
        "big_small": bs_str,
        "color": color
    }
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "game", "period", "number", "is_big", "big_small", "color"])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    return row

if __name__ == "__main__":
    res = predict_next_round([7, 2, 4, 1, 0], "20260901100052017", "WinGo 30S")
    print(res)
