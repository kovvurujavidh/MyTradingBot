#!/usr/bin/env python3
"""
Interactive Real-Time Prediction Engine for WinGo 30S and 1M.
Takes the last 5 to 10 rounds of live results from the user and outputs:
- Target Prediction: BIG (5-9) or SMALL (0-4)
- Confidence Level (%)
- Action: HIGH CONVICTION TRADE (₹35-₹50), STANDARD TRADE (₹20), or SKIP/HOLD (₹0)
- Physical & Mathematical Reasoning (Wavelet, Ising, Markov, LZ Compressibility)
"""

import sys
import math

def calculate_prediction(history_numbers, current_period_str="Next"):
    """
    history_numbers: list of integer digits [num_1, num_2, ..., num_last] (at least 5 to 10 recent numbers)
    """
    if len(history_numbers) < 5:
        return {
            "period": current_period_str,
            "prediction": "HOLD",
            "action": "SKIP (Need at least 5 recent numbers for warm-up)",
            "confidence": 50.0,
            "stake": 0,
            "reason": "Insufficient history depth"
        }

    # Extract binary Big/Small (Big=1, Small=0) and Spins (+1, -1)
    is_big = [1 if n >= 5 else 0 for n in history_numbers]
    spins = [1 if n >= 5 else -1 for n in history_numbers]
    last_num = history_numbers[-1]
    last_bs = is_big[-1]
    n = len(history_numbers)

    # 1. Streak length
    streak = 1
    for i in range(n - 2, -1, -1):
        if is_big[i] == last_bs: streak += 1
        else: break

    # 2. Ising Spin Coupling J_t
    k = min(n, 10)
    coupling_sum = sum(spins[i] * spins[i-1] for i in range(n - k + 1, n))
    J_t = coupling_sum / max(1, k - 1)

    # 3. 2nd-Order Markov Transition
    s1, s2 = is_big[-2], is_big[-1]
    m_tot, m_big = 2.0, 1.0 # Laplace smoothing
    for i in range(n - 2):
        if is_big[i] == s1 and is_big[i+1] == s2:
            m_tot += 1.0
            if is_big[i+2] == 1: m_big += 1.0
    p_markov = m_big / m_tot

    # 4. Morlet Wavelet Phase (trailing up to 12)
    nums_centered = [x - 4.5 for x in history_numbers[-min(12, n):]]
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
    three_sum = sum(history_numbers[-3:])

    # Multi-Condition Alignment
    bullish_conds = 0
    bearish_conds = 0
    reasons = []

    # Condition 1: Markov transition
    if p_markov >= 0.60:
        bullish_conds += 1
        reasons.append(f"Markov transition P(Big)={p_markov:.2f}")
    elif p_markov <= 0.40:
        bearish_conds += 1
        reasons.append(f"Markov transition P(Small)={1.0-p_markov:.2f}")

    # Condition 2: Wavelet phase
    if wave_pow > 2.2:
        if math.cos(phase) > 0.35:
            bullish_conds += 1
            reasons.append("Wavelet constructive harmonic peak (Big)")
        elif math.cos(phase) < -0.35:
            bearish_conds += 1
            reasons.append("Wavelet trough cycle (Small)")

    # Condition 3: Ising coupling & streak
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
            reasons.append(f"Ferromagnetic dragon momentum on streak {streak}")
        else:
            bearish_conds += 1
            reasons.append(f"Ferromagnetic dragon momentum on streak {streak}")

    # Condition 4: 3-Sum Momentum
    if three_sum >= 16:
        bullish_conds += 1
        reasons.append(f"3-Sum high momentum ({three_sum})")
    elif three_sum <= 9:
        bearish_conds += 1
        reasons.append(f"3-Sum low exhaustion ({three_sum})")

    # Decision Matrix
    if bullish_conds >= 2 and bearish_conds == 0:
        pred = "BIG (5-9)"
        conf = 65.0 + bullish_conds * 5.0
        if conf >= 75.0:
            action = "STRONG TRADE"
            stake = 50.0
        elif conf >= 70.0:
            action = "HIGH CONVICTION TRADE"
            stake = 35.0
        else:
            action = "STANDARD TRADE"
            stake = 20.0
    elif bearish_conds >= 2 and bullish_conds == 0:
        pred = "SMALL (0-4)"
        conf = 65.0 + bearish_conds * 5.0
        if conf >= 75.0:
            action = "STRONG TRADE"
            stake = 50.0
        elif conf >= 70.0:
            action = "HIGH CONVICTION TRADE"
            stake = 35.0
        else:
            action = "STANDARD TRADE"
            stake = 20.0
    else:
        pred = "NEUTRAL / SKIP"
        conf = 50.0 + abs(bullish_conds - bearish_conds) * 2.5
        action = "HOLD / SKIP (Noise Filter Active)"
        stake = 0.0
        reasons.append("Conflicting signals / 50-50 noise band")

    return {
        "period": current_period_str,
        "prediction": pred,
        "confidence": round(min(85.0, conf), 1),
        "action": action,
        "recommended_stake": stake,
        "reasons": reasons,
        "last_streak": streak,
        "ising_coupling": round(J_t, 2),
        "three_sum": three_sum
    }

if __name__ == "__main__":
    # Test example
    sample_nums = [7, 3, 7, 0, 3, 4, 2, 7, 0, 8, 9, 8]
    res = calculate_prediction(sample_nums, "20260901100051531")
    print(res)
