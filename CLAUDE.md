# JAVIDH ALGO PRO - Win Go (Dhaman / Daman Games) Multi-Timeframe Alpha Terminal

## Project Summary
This repository contains the complete quantitative engine for **JAVIDH ALGO PRO** — a dual-mode (30S + 1M) trading terminal with alternating pattern detection, adaptive strategy switching, and daily session analytics.

---

## 1. Dual-Mode Architecture

| Mode | Optimal Window | Strategy Focus | Wavelet Scale |
| :--- | :--- | :--- | :---: |
| **WinGo 30S** | **05:00 PM – 07:30 PM** | Fast Dragon Momentum | s = 2.5 |
| **WinGo 1M** | **08:30 PM – 11:00 PM** | Macro Harmonic Reversion | s = 4.0 |

---

## 2. Adaptive Strategy Switching

| Condition | Active Strategy | Action |
| :--- | :--- | :--- |
| Normal Pattern | 30S Quantum Dragon / 1M Macro Wave | Standard prediction |
| **Alternating (B-S-B-S)** | **Anti-Alternating Chop Sniper** | Bets OPPOSITE of last outcome |
| Loss Streak ≥ 3 | **Emergency Anti-Chop Sniper** | High-compression reversal |
| Loss Streak ≥ 6 | **Panic Reset** | Resets to Level 1, recalibrates |

---

## 3. Controlled Progression (D'Alembert)

- **Base Stake**: ₹50 minimum (adjustable +₹25)
- **Level 1**: ₹50 | **Level 2**: ₹100 | **Level 3**: ₹150 | **Level 4**: ₹200
- **Win → Reset to Level 1**
- **Loss → Advance one level**

---

## 4. Daily Session Summary Panel
Displays at bottom of dashboard:
- Today's Trades Count
- Win Rate %
- Net PnL (Green if profit, Red if loss)
- Total Wins / Total Losses
- Total Staked / Total Won Back

---

## 5. Run Command
```bash
python app.py
```
Open: **http://localhost:5000**
