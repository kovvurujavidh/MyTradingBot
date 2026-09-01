#!/usr/bin/env python3
"""
Advanced Strategy Mixer & Paper Trade Simulation Engine.
Combines top-performing models using ensemble voting, unanimous agreement filters,
regime gating, and selective trade execution.
Tracks: Total Trades, Wins, Losses, Success Rate (%), Money Made (Net PnL), Final Bankroll.
"""

import os
import csv
import math

def load_data(csv_path):
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                num = int(r["number"])
                records.append({
                    "period": str(r["period"]).strip(),
                    "number": num,
                    "is_big": 1 if num >= 5 else 0
                })
            except Exception:
                continue
    return sorted(records, key=lambda x: str(x["period"]))

# ==========================================
# BASE COMPONENT MODELS
# ==========================================

def model_volatility_gated_reversal(history):
    """Model 1: Volatility-Gated Streak Reversal"""
    if not history: return 1
    last_bs = history[-1]["is_big"]
    n = len(history)

    # Calculate streak
    streak = 1
    for r in reversed(history[:-1]):
        if r["is_big"] == last_bs: streak += 1
        else: break

    # Calculate chop volatility
    streaks = []
    cur_s = 1
    for idx in range(max(1, n - 14), n):
        if history[idx]["is_big"] == history[idx-1]["is_big"]: cur_s += 1
        else:
            streaks.append(cur_s)
            cur_s = 1
    streaks.append(cur_s)
    avg_s = sum(streaks) / len(streaks)

    if avg_s < 1.7 and streak >= 3:
        return 1 - last_bs
    return last_bs

def model_multi_signal_ensemble(history):
    """Model 2: Composite Multi-Signal Model"""
    if len(history) < 15: return history[-1]["is_big"] if history else 1
    last_bs = history[-1]["is_big"]
    n = len(history)

    # Signal A: 2nd order Markov
    s1, s2 = history[-2]["is_big"], history[-1]["is_big"]
    m_tot, m_big = 0, 0
    for i in range(n - 2):
        if history[i]["is_big"] == s1 and history[i+1]["is_big"] == s2:
            m_tot += 1
            if history[i+2]["is_big"] == 1: m_big += 1
    sig_markov = 1 if (m_big / max(1, m_tot)) >= 0.5 else 0

    # Signal B: 10-period Imbalance
    window = [r["is_big"] for r in history[-10:]]
    ratio = sum(window) / len(window)
    sig_imb = 0 if ratio > 0.6 else (1 if ratio < 0.4 else last_bs)

    # Signal C: Parity
    sig_parity = 1 if (history[-1]["number"] % 2 != 0) else 0

    # Signal D: Momentum 3
    sig_mom3 = 1 if sum(r["is_big"] for r in history[-3:]) >= 2 else 0

    score = 0.35 * sig_markov + 0.25 * sig_imb + 0.20 * sig_parity + 0.20 * sig_mom3
    return 1 if score >= 0.50 else 0

def model_reverse_after_streak_3(history):
    """Model 3: Reverse After Streak 3"""
    if not history: return 1
    last_bs = history[-1]["is_big"]
    streak = 1
    for r in reversed(history[:-1]):
        if r["is_big"] == last_bs: streak += 1
        else: break
    return (1 - last_bs) if streak >= 3 else last_bs

def model_streak_volatility_filter(history):
    """Model 4: Streak Volatility Regime Filter"""
    if len(history) < 15: return history[-1]["is_big"] if history else 1
    last_bs = history[-1]["is_big"]
    n = len(history)

    streaks = []
    cur_s = 1
    for idx in range(max(1, n - 14), n):
        if history[idx]["is_big"] == history[idx-1]["is_big"]: cur_s += 1
        else:
            streaks.append(cur_s)
            cur_s = 1
    streaks.append(cur_s)
    avg_s = sum(streaks) / len(streaks)

    return (1 - last_bs) if avg_s < 1.6 else last_bs


# ==========================================
# ADVANCED MIXED STRATEGIES
# ==========================================

def get_mixed_prediction(mix_id, history):
    """
    Returns (pred, take_trade)
    pred: 1 (Big) or 0 (Small)
    take_trade: True if trade condition met, False to skip (capital preservation)
    """
    if len(history) < 20:
        return (None, False)

    m1 = model_volatility_gated_reversal(history)
    m2 = model_multi_signal_ensemble(history)
    m3 = model_reverse_after_streak_3(history)
    m4 = model_streak_volatility_filter(history)

    votes = [m1, m2, m3, m4]
    big_votes = sum(votes)
    small_votes = 4 - big_votes

    # 1. Unanimous 4-Way Agreement Filter (Selective Trades)
    if mix_id == "MIX_UNANIMOUS_4WAY":
        if big_votes == 4:
            return (1, True)
        elif small_votes == 4:
            return (0, True)
        return (None, False) # Skip trade if any disagreement

    # 2. Strong Majority (3-of-4 Vote)
    elif mix_id == "MIX_MAJORITY_3OF4":
        if big_votes >= 3:
            return (1, True)
        elif small_votes >= 3:
            return (0, True)
        return (None, False) # Skip if 2-2 tie

    # 3. Hybrid Volatility Confirmation (M1 + M3 Gated)
    elif mix_id == "MIX_VOL_CONFIRMATION":
        if m1 == m3 and m1 == m4:
            return (m1, True)
        return (None, False)

    # 4. Weighted Probability Stacking
    elif mix_id == "MIX_WEIGHTED_STACKING":
        # Weights based on walk-forward stability
        weighted_score = 0.35 * m1 + 0.30 * m2 + 0.20 * m3 + 0.15 * m4
        if weighted_score >= 0.65:
            return (1, True)
        elif weighted_score <= 0.35:
            return (0, True)
        return (None, False) # Skip mid-range uncertainty

    # 5. Dual Momentum-Reversal Dynamic Switcher
    elif mix_id == "MIX_DYNAMIC_REGIME_SWITCH":
        # Check market state
        n = len(history)
        streaks = []
        cur_s = 1
        for idx in range(n - 14, n):
            if history[idx]["is_big"] == history[idx-1]["is_big"]: cur_s += 1
            else:
                streaks.append(cur_s)
                cur_s = 1
        streaks.append(cur_s)
        avg_s = sum(streaks) / len(streaks)

        if avg_s > 2.0: # Strong trend -> follow M2 ensemble
            return (m2, True)
        elif avg_s < 1.6: # Choppy market -> use M1/M3 reversal
            return (m1, True)
        else:
            return (m1 if m1 == m2 else None, m1 == m2)

    # 6. Full Always-Active Blended Vote
    elif mix_id == "MIX_ALWAYS_ACTIVE_VOTE":
        return (1 if big_votes >= 2 else 0, True)

    return (m1, True)


# ==========================================
# TRADE SIMULATOR
# ==========================================

def simulate_trades(records, mix_id, start_idx=200, initial_capital=2000.0, stake=20.0, payout_mult=1.96):
    """
    Simulates trades strictly on unseen chronological test sequence.
    """
    balance = initial_capital
    peak = initial_capital
    max_dd = 0.0
    wins = 0
    losses = 0
    trades = 0
    cur_loss_streak = 0
    max_loss_streak = 0
    cur_win_streak = 0
    max_win_streak = 0

    n = len(records)

    for t in range(start_idx, n):
        history = records[:t]
        actual = records[t]["is_big"]

        pred, take_trade = get_mixed_prediction(mix_id, history)
        if not take_trade or pred is None:
            continue

        trades += 1
        is_win = (pred == actual)

        if is_win:
            profit = (stake * payout_mult) - stake # +₹19.20
            balance += profit
            wins += 1
            cur_loss_streak = 0
            cur_win_streak += 1
            max_win_streak = max(max_win_streak, cur_win_streak)
        else:
            balance -= stake # -₹20.00
            losses += 1
            cur_loss_streak += 1
            cur_win_streak = 0
            max_loss_streak = max(max_loss_streak, cur_loss_streak)

        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    success_rate = (wins / trades * 100) if trades > 0 else 0.0
    money_made = balance - initial_capital

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "success_rate": round(success_rate, 2),
        "money_made": round(money_made, 2),
        "final_bankroll": round(balance, 2),
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "max_dd_pct": round(max_dd * 100, 2)
    }


def run_experiment():
    datasets = [
        ("WinGo 30S (Unseen Test N=300)", "wingo_30s_data.csv", 200),
        ("WinGo 1M (Unseen Test N=280)", "wingo_1m_data.csv", 200)
    ]

    mixed_strategies = [
        ("MIX_UNANIMOUS_4WAY", "Unanimous 4-Way Agreement Filter (High Confidence)", "Only trades when all 4 top models fully agree"),
        ("MIX_MAJORITY_3OF4", "3-of-4 Majority Voting Mix", "Trades when 3 out of 4 models agree; skips 2-2 ties"),
        ("MIX_VOL_CONFIRMATION", "Volatility-Streak Confirmation Hybrid", "Combines volatility index + streak >=3 reversal"),
        ("MIX_WEIGHTED_STACKING", "Confidence-Weighted Probability Stacking", "Trades only when weighted composite confidence > 65%"),
        ("MIX_DYNAMIC_REGIME_SWITCH", "Dynamic Trend/Chop Regime Switcher", "Trend -> Momentum follow; Chop -> Streak reversal"),
        ("MIX_ALWAYS_ACTIVE_VOTE", "Always-Active 4-Model Consensus", "Takes a trade on every single round by blended vote")
    ]

    print("=" * 112)
    print("                  ADVANCED STRATEGY MIXER & PAPER TRADE SIMULATION (₹2,000 BANKROLL)")
    print("=" * 112)
    print(f"{'Game & Test Window':30s} | {'Mixed Model Name':38s} | {'Trades':6s} | {'Wins':5s} | {'Loss':5s} | {'Success Rate':12s} | {'Money Made':12s} | {'Bankroll':10s}")
    print("-" * 112)

    for game_label, csv_file, start_idx in datasets:
        records = load_data(csv_file)
        for mix_id, mix_name, desc in mixed_strategies:
            res = simulate_trades(records, mix_id, start_idx=start_idx, initial_capital=2000.0, stake=20.0, payout_mult=1.96)

            pnl_str = f"+₹{res['money_made']:.2f}" if res['money_made'] >= 0 else f"-₹{abs(res['money_made']):.2f}"
            bankroll_str = f"₹{res['final_bankroll']:.2f}"

            print(f"{game_label:30s} | {mix_name:38s} | {res['trades']:6d} | {res['wins']:5d} | {res['losses']:5d} | {res['success_rate']:6.2f}%      | {pnl_str:12s} | {bankroll_str:10s}")
        print("-" * 112)

    print("=" * 112)
    print("\n* NOTE: All simulations use strictly unseen out-of-sample data, fixed ₹20 stakes, and ₹2,000 initial bankroll.")
    print("* House commission is exactly -2.0% (1.96x payout multiplier on wins).")

if __name__ == "__main__":
    run_experiment()
