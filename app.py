#!/usr/bin/env python3
"""
JAVIDH ALGO PRO — Elegant Trading Terminal v3
Design inspired by premium event halls: warm golds, deep purples, soft glows.
Fixes: Simple reliable algo, structured CSV export, period lockout, cooldown freeze, daily summary.
"""

import os, sys, json, math, csv, time
from datetime import datetime, date
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

PORT = 5000
DATA_FILE = "live_wingo_collected.csv"
EXCEL_FILE = "javidh_trades_log.csv"

# ─── PRE-LOADED HISTORY (170 rounds from blocks B-Z) ───
PRELOADED = [
    6,0,1,6,4,0,8,9,6,4, 8,9,4,7,2,0,4,8,7,6,
    6,2,0,4,9,6,0,1,5,1, 1,1,8,9,2,3,3,6,6,5,
    6,5,4,4,0,7,3,2,7,3, 4,8,0,7,7,7,1,9,9,6,
    6,6,8,7,6,8,8,8,9,5, 6,3,3,3,6,1,2,3,3,3,
    9,0,2,1,1,1,9,6,4,2, 2,2,5,1,5,8,8,8,3,6,
    5,9,9,9,3,8,3,4,4,4, 6,4,7,3,3,3,6,9,8,8,
    8,8,8,3,3,6,6,6,5,7, 4,2,2,2,3,3,9,1,1,1,
    2,5,1,2,2,2,2,7,3,8, 8,8,8,5,1,2,2,2,5,1,
    6,0,0,0,8,1,1,6,6,6
]

state = {
    "bankroll": 2000.00,
    "initial_capital": 2000.00,
    "base_stake": 50.00,
    "wins": 0, "losses": 0, "trades": 0,
    "max_loss_streak": 0, "current_loss_streak": 0,
    "current_period": "52436", "target_period": "52437",
    "game_mode": "30S",
    "locked_period": None,   # Prevent duplicate answers
    "freeze_until": 0,       # Unix timestamp when betting closes
    "history": [],
    "trade_log": []
}

def color_of(num):
    if num == 0: return "red,violet"
    if num == 5: return "green,violet"
    if num in [1,3,7,9]: return "green"
    return "red"

def init():
    base_p = 52267
    state["history"] = []
    for i, n in enumerate(PRELOADED):
        state["history"].append({
            "period": str(base_p + i), "number": n,
            "is_big": 1 if n >= 5 else 0,
            "color": color_of(n),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    state["current_period"] = str(base_p + len(PRELOADED) - 1)
    state["target_period"] = str(base_p + len(PRELOADED))

init()

# ═══════════════════════════════════════════════════════════
# SIMPLE RELIABLE ALGORITHM — No over-complication
# ═══════════════════════════════════════════════════════════
def predict():
    h = state["history"]
    if len(h) < 3:
        return make_dummy()

    nums = [r["number"] for r in h]
    bigs = [1 if n >= 5 else 0 for n in nums]
    spins = [1 if n >= 5 else -1 for n in nums]
    n = len(nums)
    last = nums[-1]
    last_bs = bigs[-1]

    # 1. Current streak
    streak = 1
    for i in range(n-2, -1, -1):
        if bigs[i] == last_bs: streak += 1
        else: break

    # 2. Ising coupling (momentum strength)
    k = min(n, 10)
    J = sum(spins[i]*spins[i-1] for i in range(n-k+1, n)) / max(1, k-1)

    # 3. Markov 2nd order, with a recency bias so stale history cannot dominate
    s1, s2 = bigs[-2] if n>=2 else 0, last_bs
    mt, mb = 2.0, 1.0
    start = max(0, n - 62)
    for i in range(start, n-2):
        if bigs[i]==s1 and bigs[i+1]==s2:
            weight = 0.96 ** max(0, (n-3)-i)
            mt += weight
            if bigs[i+2]==1: mb += weight
    pm = mb / mt

    # Exponentially weighted recent baseline (latest rounds matter most).
    recent = bigs[-12:]
    rw = [0.86 ** (len(recent)-1-i) for i in range(len(recent))]
    recent_p = sum(v*w for v,w in zip(recent,rw)) / max(0.001,sum(rw))

    # 4. Wavelet phase
    sc = 2.5 if state["game_mode"]=="30S" else 4.0
    c = [x-4.5 for x in nums[-14:]]
    rs, im = 0.0, 0.0
    for t in range(len(c)):
        dt = (len(c)-1-t)/sc
        e = math.exp(-0.5*dt*dt)
        rs += c[t]*e*math.cos(5*dt)
        im -= c[t]*e*math.sin(5*dt)
    wp = math.sqrt(rs**2+im**2)/math.sqrt(sc)
    ph = math.atan2(im, rs)
    cos_ph = math.cos(ph)

    # 5. Digit probs
    dc = [1]*10
    for i in range(n-1):
        if bigs[i]==last_bs: dc[nums[i+1]] += 2
        if nums[i]==last: dc[nums[i+1]] += 3
    td = sum(dc)
    dp = [round(v/td*100,1) for v in dc]

    # ─── DECISION ENGINE (simple & robust) ───
    bs, bss = 0.0, 0.0
    reasons = []

    if recent_p >= 0.59:
        bs += 1.5; reasons.append(f"Recent weighted trend: Big {recent_p:.0%}")
    elif recent_p <= 0.41:
        bss += 1.5; reasons.append(f"Recent weighted trend: Small {1-recent_p:.0%}")

    # Signal 1: Wavelet direction
    if wp > 1.5:
        if cos_ph > 0.2:
            bs += 1; reasons.append("Wavelet crest → bullish momentum")
        elif cos_ph < -0.2:
            bss += 1; reasons.append("Wavelet trough → bearish cycle")

    # Signal 2: Ising coupling + streak
    if J > 0.15 and streak >= 2:
        if last_bs == 1:
            bs += 2; reasons.append(f"Dragon momentum ×{streak}")
        else:
            bss += 2; reasons.append(f"Small dragon ×{streak}")
    elif J < -0.15 and streak >= 3:
        if last_bs == 0:
            bs += 2; reasons.append(f"Chop reversal after {streak} smalls")
        else:
            bss += 2; reasons.append(f"Chop reversal after {streak} bigs")

    # Signal 3: Markov
    if pm >= 0.58:
        bs += 1; reasons.append(f"Markov P(Big)={pm:.2f}")
    elif pm <= 0.42:
        bss += 1; reasons.append(f"Markov P(Small)={1-pm:.2f}")

    # Signal 4: Recent 3-sum
    ts = sum(nums[-3:])
    if ts >= 15:
        bs += 1; reasons.append(f"High velocity (sum={ts})")
    elif ts <= 8:
        bss += 1; reasons.append(f"Low velocity (sum={ts})")

    # Alternate pattern check (B-S-B-S)
    alt = sum(1 for i in range(max(0,n-5),n-1) if bigs[i]!=bigs[i+1])
    if alt >= 4:
        # Strong alternating — bet opposite
        if last_bs == 1:
            bss += 2; reasons.append("Alternating pattern → bet Small")
        else:
            bs += 2; reasons.append("Alternating pattern → bet Big")

    margin = abs(bs - bss)
    if margin < 0.6:
        side = "BIG" if recent_p >= 0.5 else "SMALL"
        conf = 51 + min(8, margin * 4)
        reasons.append("No strong edge - reduced confidence")
        top = sorted([(d,dp[d]) for d in (range(5,10) if side=="BIG" else range(0,5))], key=lambda x:-x[1])[:3]
    elif bs > bss:
        side, conf = "BIG", min(78, 52 + margin * 7)
        top = sorted([(d,dp[d]) for d in range(5,10)], key=lambda x:-x[1])[:3]
    else:
        side, conf = "SMALL", min(78, 52 + margin * 7)
        top = sorted([(d,dp[d]) for d in range(0,5)], key=lambda x:-x[1])[:3]

    mult = min(4, state["current_loss_streak"]+1)
    stake = state["base_stake"] * mult
    next_p = str(int(state["current_period"])+1) if state["current_period"].isdigit() else "52437"
    state["target_period"] = next_p

    return {
        "target_period": next_p,
        "prediction": f"{side} ({'5-9' if side=='BIG' else '0-4'})",
        "side": side,
        "confidence": round(conf,1),
        "top_numbers": [{"num":d,"prob":p} for d,p in top],
        "action": f"LEVEL {mult} × ₹{stake:.0f}",
        "multiplier": mult,
        "base_stake": state["base_stake"],
        "recommended_stake": stake,
        "loss_streak": state["current_loss_streak"],
        "strategy_name": "Javidh Quantum Core v3",
        "reasons": reasons,
        "streak": streak
    }

def make_dummy():
    return {"target_period":"52437","prediction":"BIG (5-9)","side":"BIG","confidence":60.0,
            "top_numbers":[{"num":7,"prob":26.0},{"num":8,"prob":24.0},{"num":9,"prob":22.0}],
            "action":"LEVEL 1 × ₹50","multiplier":1,"base_stake":50.0,
            "recommended_stake":50.0,"loss_streak":0,"strategy_name":"Initializing...",
            "reasons":["Loading history..."],"streak":0}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Javidh Algo Pro — Premium Trading Terminal</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #050505;
  --card: rgba(14, 14, 16, 0.9);
  --card2: rgba(22, 22, 26, 0.8);
  --gold: #E5A93C;
  --gold-light: #F7D488;
  --gold-dim: rgba(229, 169, 60, 0.12);
  --purple: #9D68F7;
  --purple-glow: rgba(157, 104, 247, 0.15);
  --green: #10B981;
  --red: #EF4444;
  --white: #FFFFFF;
  --text: #F3F4F6;
  --muted: #9CA3AF;
  --border: rgba(255, 255, 255, 0.08);
  --radius: 14px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  background:var(--bg);
  background-image:
    radial-gradient(ellipse at 50% 0%, rgba(229, 169, 60, 0.06) 0%, transparent 60%),
    radial-gradient(ellipse at 10% 40%, rgba(157, 104, 247, 0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 80%, rgba(16, 185, 129, 0.03) 0%, transparent 50%);
  background-attachment:fixed;
  color:var(--text);font-family:'Outfit',sans-serif;
  padding:12px;min-height:100vh;
}

.container{max-width:1100px;margin:0 auto}

/* ── NAVBAR ── */
.navbar{
  display:flex;justify-content:space-between;align-items:center;
  background:var(--card);backdrop-filter:blur(20px);
  border:1px solid var(--border);border-radius:var(--radius);
  padding:14px 20px;margin-bottom:14px;
  box-shadow:0 8px 32px rgba(139,92,246,0.15);
}
.brand{
  font-family:'Outfit',sans-serif;
  font-size:22px;font-weight:900;letter-spacing:3px;text-transform:uppercase;
  background:linear-gradient(135deg,var(--gold-light),var(--gold),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.nav-right{display:flex;align-items:center;gap:8px}

.mode-toggle{
  display:flex;background:rgba(0,0,0,0.4);
  border:1px solid var(--border);border-radius:25px;padding:3px;
}
.mbtn{
  border:none;background:transparent;color:var(--muted);
  padding:6px 14px;border-radius:20px;
  font-family:'Outfit',sans-serif;font-size:11px;font-weight:700;
  cursor:pointer;transition:all .3s;
}
.mbtn.active{
  background:linear-gradient(135deg,var(--gold),#B8860B);
  color:#0D0A1A;box-shadow:0 0 15px var(--gold-dim);
}
.btn-pill{
  background:var(--card2);border:1px solid var(--border);
  color:var(--text);padding:6px 12px;border-radius:20px;
  font-family:'Outfit',sans-serif;font-size:11px;font-weight:700;
  cursor:pointer;transition:all .2s;
}
.btn-pill:hover{border-color:var(--gold);color:var(--gold)}
.clock-pill{
  background:var(--gold-dim);border:1px solid var(--gold);
  color:var(--gold-light);padding:6px 14px;border-radius:20px;
  font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;
}
.clock-freeze{color:var(--red)!important;border-color:var(--red)!important;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}

/* ── ADVISOR BAR ── */
.advisor{
  background:linear-gradient(135deg,rgba(212,168,67,0.12),rgba(139,92,246,0.08));
  border:1px solid var(--border);border-radius:12px;
  padding:10px 18px;margin-bottom:14px;
  display:flex;justify-content:space-between;align-items:center;
  font-size:13px;flex-wrap:wrap;gap:8px;
}
.advisor span.gold{color:var(--gold);font-weight:700;font-family:'Outfit',sans-serif}

/* ── CONTROLS ── */
.controls{
  background:var(--card);border:1px solid var(--border);
  border-radius:14px;padding:12px 18px;margin-bottom:14px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;
}
.stakes{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.schip{
  background:rgba(0,0,0,0.4);border:1px solid var(--border);
  color:var(--text);padding:5px 10px;border-radius:8px;
  font-family:'Outfit',sans-serif;font-size:11px;font-weight:700;
  cursor:pointer;transition:all .15s;
}
.schip:hover{border-color:var(--gold)}
.schip.sel{background:var(--gold);color:#0D0A1A;border-color:var(--gold)}
.sync-grp{display:flex;align-items:center;gap:6px}
.pinp{
  background:rgba(0,0,0,0.4);border:1px solid var(--border);
  color:#fff;padding:7px 12px;border-radius:8px;
  font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;
  width:130px;outline:none;
}
.pinp:focus{border-color:var(--gold)}
.bsync{
  background:linear-gradient(135deg,var(--gold),#B8860B);
  color:#0D0A1A;border:none;padding:7px 16px;border-radius:8px;
  font-family:'Outfit',sans-serif;font-weight:800;font-size:12px;
  cursor:pointer;transition:all .2s;
}
.bsync:hover{transform:translateY(-1px);box-shadow:0 4px 15px rgba(212,168,67,0.4)}

/* ── GRID ── */
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:14px}
@media(max-width:860px){.grid{grid-template-columns:1fr}}

.card{
  background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px;margin-bottom:14px;
  box-shadow:0 4px 25px rgba(0,0,0,0.3);
  transition:all .3s;
}
.card:hover{box-shadow:0 8px 35px rgba(139,92,246,0.2)}

/* ── HERO ── */
.hero{
  background:linear-gradient(180deg,rgba(139,92,246,0.12) 0%,var(--card) 100%);
  border:2px solid var(--gold);
  text-align:center;padding:28px 20px;position:relative;overflow:hidden;
}
.hero::before{
  content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;
  background:radial-gradient(circle,rgba(212,168,67,0.05) 0%,transparent 60%);
  animation:rotate 30s linear infinite;
}
@keyframes rotate{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}

.peri-pill{
  display:inline-block;background:var(--gold-dim);border:1px solid var(--gold);
  color:var(--gold-light);padding:5px 16px;border-radius:20px;
  font-family:'Outfit',sans-serif;font-size:12px;font-weight:700;
  margin-bottom:10px;position:relative;z-index:1;
}
.pred-main{
  font-family:'Outfit',sans-serif;
  font-size:52px;font-weight:800;letter-spacing:3px;margin-bottom:4px;
  position:relative;z-index:1;text-transform:uppercase;
}
.is-big{color:var(--green);text-shadow:0 0 30px rgba(52,211,153,0.5)}
.is-small{color:var(--red);text-shadow:0 0 30px rgba(248,113,113,0.5)}

.level-chip{
  display:inline-block;background:rgba(139,92,246,0.15);
  border:1px solid var(--purple);color:var(--purple);
  padding:5px 16px;border-radius:20px;
  font-family:'Outfit',sans-serif;font-size:12px;font-weight:700;
  margin-bottom:12px;position:relative;z-index:1;
}
.stake-row{font-size:14px;color:var(--muted);margin-bottom:14px;position:relative;z-index:1;text-transform:uppercase;letter-spacing:1px}
.stake-b{color:#fff;font-size:22px;font-weight:800;font-family:'Outfit',sans-serif;letter-spacing:1px}

.digits-row{display:flex;justify-content:center;gap:12px;margin:12px 0;position:relative;z-index:1}
.dball{
  width:66px;height:66px;
  background:rgba(0,0,0,0.5);border:2px solid var(--border);
  border-radius:12px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  font-family:'Outfit',sans-serif;font-weight:800;
  transition:all .3s;
}
.dball:hover{transform:translateY(-4px)}
.dball.g{border-color:var(--green);color:var(--green)}
.dball.r{border-color:var(--red);color:var(--red)}
.dball.v{border-color:var(--purple);color:var(--purple)}
.dnum{font-size:22px;font-weight:800;text-transform:uppercase}
.dpct{font-size:10px;color:var(--muted)}

.reasons{
  background:rgba(0,0,0,0.4);border-left:3px solid var(--gold);
  border-radius:6px;padding:10px 14px;margin-top:14px;
  text-align:left;font-size:12px;color:var(--muted);line-height:1.6;
  position:relative;z-index:1;
}

/* ── NUMPAD ── */
.numpad{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}
.kbtn{
  background:rgba(0,0,0,0.5);border:2px solid var(--border);
  color:#fff;padding:12px 0;border-radius:10px;
  font-family:'Outfit',sans-serif;font-size:20px;font-weight:800;
  cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px;
  transition:all .15s;position:relative;overflow:hidden;text-transform:uppercase;
}
.kbtn::after{
  content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent);
  transition:left .5s;
}
.kbtn:hover::after{left:100%}
.kbtn:hover{transform:translateY(-2px)}
.kbtn:active{transform:scale(0.95)}
.kbtn.g{border-color:rgba(52,211,153,0.4)}
.kbtn.g:hover{border-color:var(--green);background:rgba(52,211,153,0.1)}
.kbtn.r{border-color:rgba(248,113,113,0.4)}
.kbtn.r:hover{border-color:var(--red);background:rgba(248,113,113,0.1)}
.kbtn.v{border-color:rgba(139,92,246,0.4)}
.kbtn.v:hover{border-color:var(--purple);background:rgba(139,92,246,0.1)}
.ksub{font-size:9px;color:var(--muted);font-weight:600;text-transform:uppercase}
.kbtn:disabled{opacity:0.4;cursor:not-allowed;transform:none!important}
.kbtn:disabled::after{display:none}

/* ── STATS ── */
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.sbox{
  background:rgba(0,0,0,0.4);border:1px solid var(--border);
  border-radius:10px;padding:10px 8px;text-align:center;
}
.stit{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;letter-spacing:.5px}
.sval{font-size:17px;font-weight:800;font-family:'Outfit',sans-serif;margin-top:2px;letter-spacing:0.5px}
.tgrn{color:var(--green)}.tred{color:var(--red)}.tog{color:var(--gold)}

/* ── TRADE LOG ── */
.tlog{max-height:160px;overflow-y:auto;margin-bottom:10px}
.tcard{
  background:rgba(0,0,0,0.4);border:1px solid var(--border);
  border-radius:8px;padding:8px 12px;margin-bottom:6px;
  display:flex;justify-content:space-between;align-items:center;
  font-family:'Outfit',sans-serif;font-size:11px;text-transform:uppercase;
}
.tw{background:rgba(52,211,153,0.15);color:var(--green);border:1px solid var(--green);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10px}
.tl{background:rgba(248,113,113,0.15);color:var(--red);border:1px solid var(--red);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10px}

/* ── DAILY SUMMARY ── */
.dsummary{
  background:linear-gradient(135deg,rgba(212,168,67,0.10),rgba(139,92,246,0.08));
  border:1px solid var(--border);border-radius:12px;padding:14px;
}
.dst{font-size:10px;color:var(--gold);font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.dgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px}
.dcell{text-align:center}
.dlbl{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700}
.dval{font-size:17px;font-weight:800;font-family:'Outfit',sans-serif;letter-spacing:0.5px}
.dbot{margin-top:8px;padding-top:8px;border-top:1px solid var(--border);display:flex;justify-content:space-between;font-size:11px}
.dbot span{color:var(--muted)}
.dbot strong{color:#fff;font-family:'Outfit',sans-serif}

/* ── RESET BANNER ── */
.reset-banner{
  background:rgba(248,113,113,0.1);border:1px solid var(--red);
  border-radius:10px;padding:10px 14px;margin-bottom:14px;
  display:none;justify-content:space-between;align-items:center;font-size:12px;
}

/* ── MODAL ── */
.modal-bg{
  position:fixed;top:0;left:0;width:100vw;height:100vh;
  background:rgba(0,0,0,0.8);backdrop-filter:blur(10px);
  display:none;align-items:center;justify-content:center;z-index:1000;padding:16px;
}
.modal-box{
  background:linear-gradient(180deg,#1A1035,#0D0A1A);
  border:2px solid var(--gold);border-radius:20px;
  padding:30px;max-width:400px;width:100%;text-align:center;
  box-shadow:0 20px 60px rgba(139,92,246,0.3);
}
.mtitle{font-family:'Outfit',sans-serif;font-size:22px;font-weight:900;color:var(--gold-light);margin-bottom:8px;text-transform:uppercase;letter-spacing:2px}
.mdesc{font-size:13px;color:var(--muted);margin-bottom:18px;line-height:1.5}
.minp{
  width:100%;background:rgba(0,0,0,0.5);border:1px solid var(--border);
  color:#fff;padding:12px;border-radius:10px;font-size:18px;font-weight:700;
  text-align:center;font-family:'Outfit',sans-serif;margin-bottom:16px;outline:none;
}
.minp:focus{border-color:var(--gold)}
.mbtn{
  width:100%;background:linear-gradient(135deg,var(--gold),#B8860B);
  color:#0D0A1A;border:none;padding:13px;border-radius:10px;
  font-size:14px;font-weight:800;font-family:'Outfit',sans-serif;
  cursor:pointer;transition:all .2s;
}
.mbtn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(212,168,67,0.4)}
/* Quiet luxury visual system */
:root{--bg:#F9F8F6;--card:#FFFFFF;--card2:#F2F0ED;--gold:#C5A059;--gold-light:#A27D3F;--gold-dim:rgba(197,160,89,.12);--purple:#8F8069;--green:#3F765F;--red:#A95D56;--text:#1A1A1A;--muted:#595959;--border:rgba(26,26,26,.13);--radius:2px}
html{scroll-behavior:smooth}body{background:var(--bg);background-image:none;color:var(--text);font-family:'Inter',sans-serif;line-height:1.5;padding:0}.container{max-width:1180px;padding:22px 20px 60px}
.navbar{background:transparent;border:0;border-bottom:1px solid var(--border);border-radius:0;box-shadow:none;padding:12px 0 18px;margin-bottom:30px;backdrop-filter:none}.brand,.pred-main,.mtitle{font-family:'Playfair Display',serif;background:none;-webkit-text-fill-color:initial;color:var(--text);letter-spacing:.02em;text-transform:none}.brand{font-size:23px;font-weight:600}.nav-right{gap:10px}.mode-toggle{background:transparent;border:1px solid var(--border);border-radius:2px}.mbtn{border-radius:0;color:var(--muted);font-family:'Inter',sans-serif;min-height:40px}.mbtn.active{background:var(--text);color:var(--bg);box-shadow:none}
.btn-pill,.clock-pill,.schip,.pinp,.bsync,.card,.advisor,.controls,.hero,.dball,.kbtn,.sbox,.tcard,.dsummary,.reset-banner,.modal-box,.minp{border-radius:2px;box-shadow:none}.btn-pill{background:transparent;color:var(--text);border-color:var(--border);min-height:40px}.clock-pill{background:transparent;border-color:var(--gold);color:var(--gold-light);min-height:40px;display:flex;align-items:center}.advisor{background:transparent;border:0;border-left:2px solid var(--gold);padding:4px 14px;margin-bottom:28px;color:var(--muted)}.controls{background:var(--card);border-color:var(--border);padding:16px 18px;margin-bottom:28px}.schip{background:var(--card2);color:var(--text);min-height:40px}.schip.sel{background:var(--text);color:var(--bg);border-color:var(--text)}.pinp{background:var(--bg);color:var(--text);min-height:40px}.bsync{background:var(--text);color:var(--bg);min-height:40px}
.grid{gap:28px}.card{background:var(--card);border:1px solid var(--border);padding:24px;margin-bottom:28px}.card:hover{box-shadow:none}.hero{background:var(--card);border:1px solid var(--gold);padding:42px 24px}.hero::before{display:none}.peri-pill,.level-chip{background:transparent;border:0;border-bottom:1px solid var(--gold);border-radius:0;color:var(--gold-light);padding:4px 0}.pred-main{font-size:clamp(42px,8vw,68px);font-weight:600}.is-big,.is-small{color:var(--text);text-shadow:none}.stake-b{color:var(--text)}.dball{background:var(--card2);border:1px solid var(--border);width:68px;height:68px}.dball.g{border-color:var(--green);color:var(--green)}.dball.r{border-color:var(--red);color:var(--red)}.dball.v{border-color:var(--gold);color:var(--gold-light)}.reasons{background:var(--card2);border-left:2px solid var(--gold);border-radius:0;color:var(--muted)}.kbtn{background:var(--card2);color:var(--text);border-color:var(--border);min-height:70px}.kbtn:hover{transform:none;background:var(--bg)}.sbox,.tcard{background:var(--card2)}.tgrn{color:var(--green)}.tred{color:var(--red)}.tog{color:var(--gold-light)}.dsummary{background:var(--card2);border-color:var(--border)}.dst{color:var(--gold-light)}.dbot strong{color:var(--text)}.reset-banner{background:rgba(169,93,86,.08);border-color:var(--red)}
.modal-bg{background:rgba(26,26,26,.38);backdrop-filter:blur(5px)}.modal-box{background:var(--card);border:1px solid var(--gold);padding:32px;box-shadow:none}.mtitle{color:var(--text);font-size:27px;text-transform:none;letter-spacing:0}.mdesc{color:var(--muted)}.minp{background:var(--bg);color:var(--text);border-color:var(--border);min-height:48px}.modal-submit{width:100%;background:var(--text);color:var(--bg);border:0;padding:13px;border-radius:2px;font-size:14px;font-weight:700;font-family:'Inter',sans-serif;cursor:pointer;min-height:48px}.night{--bg:#1A1A1A;--card:#242424;--card2:#2D2D2D;--text:#F9F8F6;--muted:#C0BDB7;--border:rgba(249,248,246,.16)}.night .pinp{background:#202020}.night .bsync,.night .mbtn.active,.night .modal-submit{background:#F9F8F6;color:#1A1A1A}
.reveal{opacity:1;transform:none;filter:none}.js .reveal{opacity:0;transform:translateY(30px);filter:blur(3px);transition:opacity .7s cubic-bezier(.22,1,.36,1),transform .7s cubic-bezier(.22,1,.36,1),filter .7s cubic-bezier(.22,1,.36,1)}.js .reveal.is-visible{opacity:1;transform:none;filter:none}@media(max-width:600px){.container{padding:14px 14px 40px}.navbar{align-items:flex-start;gap:14px}.brand{font-size:20px}.nav-right{flex-wrap:wrap;justify-content:flex-end}.advisor{font-size:12px}.controls{align-items:stretch}.stakes,.sync-grp{width:100%}.sync-grp .pinp{flex:1;width:auto}.grid{gap:0}.card{padding:18px;margin-bottom:18px}.hero{padding:34px 16px}.digits-row{gap:7px}.dball{width:60px;height:60px}.numpad{gap:6px}.kbtn{min-height:62px;padding:8px 0}.dgrid{grid-template-columns:repeat(2,1fr);gap:14px}.dbot{gap:8px;flex-wrap:wrap}.dbot span{width:calc(50% - 4px)}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.js .reveal,.js .reveal.is-visible{opacity:1;transform:none;filter:none;transition:none}}
@media(max-width:700px){.navbar{flex-wrap:wrap}.navbar .brand{width:100%}.nav-right{width:100%;justify-content:space-between}.controls{width:100%}.stakes{gap:5px}.stakes>span{width:100%;margin-bottom:2px}.sync-grp{display:flex}.advisor{align-items:flex-start}.advisor span{max-width:100%}.tcard{gap:8px}.tcard>div:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
@media(max-width:360px){.nav-right{gap:5px}.nav-right .btn-pill,.nav-right .clock-pill{padding-left:9px;padding-right:9px;font-size:10px}.card{padding-left:14px;padding-right:14px}.dball{width:55px;height:55px}.kbtn{font-size:18px}}
</style>
</head>
<body>
<div class="container">
  <nav class="navbar">
    <div class="brand">✦ JAVIDH ALGO PRO</div>
    <div class="nav-right">
      <div class="mode-toggle">
        <button class="mbtn active" id="m30" onclick="setMode('30S')">⚡ 30S</button>
        <button class="mbtn" id="m1m" onclick="setMode('1M')">⏱ 1M</button>
      </div>
      <button class="btn-pill" onclick="openCap()">💰 <span id="navCap">₹2,000</span></button>
      <button class="btn-pill" id="themeToggle" onclick="toggleTheme()">☾ Night</button>
      <div class="clock-pill" id="clockPill">⏳ <span id="clockVal">30s</span></div>
    </div>
  </nav>

  <div class="advisor">
    <span>🎯 <strong id="advMode">30S:</strong> <span id="advWin">Best: 05:00–07:30 PM</span></span>
    <span class="gold" id="advStrat">Javidh Quantum Core v3</span>
  </div>

  <div class="controls">
    <div class="stakes">
      <span style="font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;margin-right:4px">BASE:</span>
      <button class="schip sel" onclick="setStake(50)">₹50</button>
      <button class="schip" onclick="setStake(75)">₹75</button>
      <button class="schip" onclick="setStake(100)">₹100</button>
      <button class="schip" onclick="setStake(125)">₹125</button>
      <button class="schip" onclick="setStake(150)">₹150</button>
      <button class="schip" onclick="addStake(25)" style="color:var(--gold)">+₹25</button>
    </div>
    <div class="sync-grp">
      <input type="text" id="periInp" class="pinp" value="52436" placeholder="Period">
      <button class="bsync" onclick="syncPeri()">⚡ SYNC</button>
    </div>
  </div>

  <div class="reset-banner" id="resetBanner">
    <span>⚠️ <strong>Drawdown detected!</strong> <span id="lossCnt">0</span> consecutive losses. Algorithm in recovery mode.</span>
    <button class="btn-pill" style="background:var(--red);color:#fff" onclick="resetAlgo()">🔄 RESET</button>
  </div>

  <div class="grid">
    <div>
      <section class="card hero reveal">
        <div class="peri-pill">🎯 TARGET: <span id="tgtPeri">52437</span></div>
        <div class="pred-main is-big" id="mainPred">BIG (5-9)</div>
        <div class="level-chip" id="lvlChip">LEVEL 1 • ₹50</div>
        <div class="stake-row">STAKE: <span class="stake-b" id="stkDisp">₹50</span> &bull; Edge: <strong style="color:var(--green)" id="confDisp">78%</strong></div>
        <div style="font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:700">Top Digits</div>
        <div class="digits-row" id="digGrid">
          <div class="dball g"><div class="dnum">7</div><div class="dpct">28%</div></div>
          <div class="dball r"><div class="dnum">8</div><div class="dpct">26%</div></div>
          <div class="dball g"><div class="dnum">9</div><div class="dpct">22%</div></div>
        </div>
        <div class="reasons" id="reasonBox">
          <strong>🧠 Analysis:</strong><br>• Dragon momentum detected<br>• Wavelet harmonic alignment confirmed
        </div>
      </section>

      <section class="card reveal">
        <div style="display:flex;justify-content:space-between;font-size:12px;font-weight:700;color:var(--muted);margin-bottom:8px">
          <span>⚡ RECORD RESULT</span><span style="color:var(--gold)">1-CLICK FEEDBACK</span>
        </div>
        <div class="numpad" id="numpad">
          <button class="kbtn v" onclick="submitAns(0)">0<span class="ksub">R+V</span></button>
          <button class="kbtn g" onclick="submitAns(1)">1<span class="ksub">Grn</span></button>
          <button class="kbtn r" onclick="submitAns(2)">2<span class="ksub">Red</span></button>
          <button class="kbtn g" onclick="submitAns(3)">3<span class="ksub">Grn</span></button>
          <button class="kbtn r" onclick="submitAns(4)">4<span class="ksub">Red</span></button>
          <button class="kbtn v" onclick="submitAns(5)">5<span class="ksub">G+V</span></button>
          <button class="kbtn r" onclick="submitAns(6)">6<span class="ksub">Red</span></button>
          <button class="kbtn g" onclick="submitAns(7)">7<span class="ksub">Grn</span></button>
          <button class="kbtn r" onclick="submitAns(8)">8<span class="ksub">Red</span></button>
          <button class="kbtn g" onclick="submitAns(9)">9<span class="ksub">Grn</span></button>
        </div>
        <div id="freezeMsg" style="text-align:center;margin-top:10px;font-size:13px;font-weight:700;color:var(--white);background:var(--red);padding:10px;border-radius:8px;display:none;cursor:pointer;animation:pulse 1s infinite" onclick="syncSilent()">
          🛑 STOP TRADING FOR THIS TREND — PRESS OK TO SYNC
        </div>
      </section>
    </div>

    <div>
      <section class="card reveal">
        <div style="font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-bottom:10px">💰 Capital</div>
        <div class="sgrid">
          <div class="sbox"><div class="stit">Bankroll</div><div class="sval tgrn" id="sBal">₹2,000</div></div>
          <div class="sbox"><div class="stit">PnL</div><div class="sval tgrn" id="sPnl">+₹0</div></div>
          <div class="sbox"><div class="stit">Win Rate</div><div class="sval tog" id="sWr">58%</div></div>
        </div>
        <div class="sgrid">
          <div class="sbox"><div class="stit">Trades</div><div class="sval" id="sTr">0</div></div>
          <div class="sbox"><div class="stit">W/L</div><div class="sval" id="sWl">0/0</div></div>
          <div class="sbox"><div class="stit">Streak</div><div class="sval tred" id="sSt">0</div></div>
        </div>
      </section>

      <section class="card reveal">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase">History</span>
          <a href="/api/export" style="color:var(--gold);text-decoration:none;font-size:11px;font-weight:700">📥 CSV</a>
        </div>
        <div class="tlog" id="tLog"></div>

        <div class="dsummary">
          <div class="dst">📊 Today's Summary</div>
          <div class="dgrid">
            <div class="dcell"><div class="dlbl">Trades</div><div class="dval" id="dTr">0</div></div>
            <div class="dcell"><div class="dlbl">Win Rate</div><div class="dval tgrn" id="dWr">0%</div></div>
            <div class="dcell"><div class="dlbl">PnL</div><div class="dval tgrn" id="dPnl">+₹0</div></div>
            <div class="dcell"><div class="dlbl">Balance</div><div class="dval tog" id="dBal">₹2,000</div></div>
          </div>
          <div class="dbot">
            <span>Wins: <strong id="dW">0</strong></span>
            <span>Losses: <strong id="dL">0</strong></span>
            <span>Staked: <strong id="dSt">₹0</strong></span>
            <span>Won: <strong id="dWbk">₹0</strong></span>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>

<div class="modal-bg" id="capModal">
  <div class="modal-box">
    <div class="mtitle">💰 Set Your Capital</div>
    <div class="mdesc">Enter your bankroll. Javidh Algo calculates your base stake and manages risk progression automatically.</div>
    <input type="number" id="capInp" class="minp" value="2000" step="500">
    <button class="modal-submit" onclick="submitCap()">START TRADING</button>
  </div>
</div>

<div class="modal-bg" id="periodModal">
  <div class="modal-box">
    <div class="mtitle">Set current period</div>
    <div class="mdesc">Enter the live period number to start syncing your dashboard.</div>
    <input type="text" id="periodModalInp" class="minp" value="52436" inputmode="numeric" autocomplete="off">
    <button class="modal-submit" onclick="submitInitialPeriod()">SYNC PERIOD</button>
  </div>
</div>

<script>
let curMode='30S';
document.documentElement.classList.add('js');
function toggleTheme(){const night=document.body.classList.toggle('night');localStorage.setItem('javidh_theme',night?'night':'day');document.getElementById('themeToggle').innerText=night?'☀ Day':'☾ Night'}
if(localStorage.getItem('javidh_theme')==='night'){document.body.classList.add('night');document.getElementById('themeToggle').innerText='☀ Day'}

// Freeze timer - visual warning + auto period increment
let lastPeriodSynced = null;

setInterval(async ()=>{
  const interval = curMode === '30S' ? 30 : 60;
  const rem = interval - (Math.floor(Date.now() / 1000) % interval);
  const el = document.getElementById('clockVal');
  const pill = document.getElementById('clockPill');
  el.innerText = (rem < 10 ? '0' : '') + rem + 's';

  if (rem <= 5) {
    pill.className = 'clock-pill clock-freeze';
    document.getElementById('freezeMsg').style.display = 'block';
  } else {
    pill.className = 'clock-pill';
    document.getElementById('freezeMsg').style.display = 'none';
  }

  // Auto-increment target period when a cycle completes (rem hits interval - 1)
  if (rem === interval - 1) {
    const currentTarget = document.getElementById('tgtPeri').innerText;
    if (currentTarget && currentTarget !== lastPeriodSynced) {
      lastPeriodSynced = currentTarget;
      // Auto-step target period on UI
      const nextTarget = (parseInt(currentTarget) + 1).toString();
      document.getElementById('tgtPeri').innerText = nextTarget;
      document.getElementById('periInp').value = currentTarget;
      // Fetch new prediction for this new period
      fetch('/api/calibrate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({period: currentTarget})
      }).then(() => refresh());
    }
  }
}, 1000);

// Check capital
if(!localStorage.getItem('javidh_cap'))document.getElementById('capModal').style.display='flex';

function openCap(){document.getElementById('capModal').style.display='flex'}
async function submitCap(){
  const v=parseFloat(document.getElementById('capInp').value);
  if(isNaN(v)||v<=0)return;
  await fetch('/api/set_cap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({capital:v})});
  localStorage.setItem('javidh_cap','1');
  document.getElementById('capModal').style.display='none';
  refresh();
}

async function setMode(m){
  curMode=m;
  document.getElementById('m30').className=m==='30S'?'mbtn active':'mbtn';
  document.getElementById('m1m').className=m==='1M'?'mbtn active':'mbtn';
  document.getElementById('advMode').innerText=m==='30S'?'30S:':'1M: ';
  document.getElementById('advWin').innerText=m==='30S'?'Best: 05:00–07:30 PM (Dragon Liquidity)':'Best: 08:30–11:00 PM (Macro Reversion)';
  await fetch('/api/set_mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:m})});
  refresh();
}

function setStake(v){
  document.querySelectorAll('.schip').forEach(c=>c.classList.remove('sel'));
  event.target.classList.add('sel');
  fetch('/api/set_stake',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stake:v})}).then(()=>refresh());
}
function addStake(d){fetch('/api/adj_stake',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta:d})}).then(()=>refresh());}

async function syncPeri(){
  const p=document.getElementById('periInp').value.trim();
  if(!p)return;
  await fetch('/api/calibrate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({period:p})});
  refresh();
}

async function syncSilent(){
  // Auto-sync next period silently
  const currentTarget = document.getElementById('tgtPeri').innerText;
  if(currentTarget){
    document.getElementById('periInp').value = currentTarget;
    await fetch('/api/calibrate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({period:currentTarget})});
  }
  document.getElementById('freezeMsg').style.display='none';
  refresh();
}

async function submitAns(num){
  await fetch('/api/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({number:num})});
  refresh();
}

async function resetAlgo(){
  await fetch('/api/reset',{method:'POST'});
  document.getElementById('resetBanner').style.display='none';
  refresh();
}

async function refresh(){
  try{
    const r1=await fetch('/api/predict');const d1=await r1.json();
    document.getElementById('tgtPeri').innerText=d1.target_period;
    const pe=document.getElementById('mainPred');
    pe.innerText=d1.prediction;
    pe.className='pred-main '+(d1.side==='BIG'?'is-big':'is-small');
    document.getElementById('lvlChip').innerText=d1.action;
    document.getElementById('stkDisp').innerText='₹'+d1.recommended_stake.toFixed(0);
    document.getElementById('confDisp').innerText=d1.confidence+'%';
    document.getElementById('advStrat').innerText=d1.strategy_name;

    const dg=document.getElementById('digGrid');dg.innerHTML='';
    d1.top_numbers.forEach(d=>{
      let c='g';if(d.num===0||d.num===5)c='v';else if([2,4,6,8].includes(d.num))c='r';
      dg.innerHTML+=`<div class="dball ${c}"><div class="dnum">${d.num}</div><div class="dpct">${d.prob}%</div></div>`;
    });
    document.getElementById('reasonBox').innerHTML='<strong>🧠 Analysis:</strong><br>'+d1.reasons.map(r=>'• '+r).join('<br>');

    const r2=await fetch('/api/history');const d2=await r2.json();
    document.getElementById('sBal').innerText='₹'+d2.bankroll.toFixed(0);
    document.getElementById('navCap').innerText='₹'+d2.bankroll.toFixed(0);
    const pnl=d2.bankroll-d2.initial_capital;
    const pe2=document.getElementById('sPnl');
    pe2.innerText=(pnl>=0?'+':'')+'₹'+Math.abs(pnl).toFixed(0);
    pe2.className='sval '+(pnl>=0?'tgrn':'tred');
    document.getElementById('sWr').innerText=d2.win_rate+'%';
    document.getElementById('sTr').innerText=d2.trades;
    document.getElementById('sWl').innerText=d2.wins+'/'+d2.losses;
    document.getElementById('sSt').innerText=d2.current_loss_streak;

    const tl=document.getElementById('tLog');tl.innerHTML='';
    d2.trade_log.slice(-6).reverse().forEach(x=>{
      tl.innerHTML+=`<div class="tcard"><div><strong>#${x.period}</strong> ${x.number} (${x.actual_side})</div><div class="${x.is_win?'tw':'tl'}">${x.is_win?'WIN +₹'+x.profit.toFixed(0):'LOSS -₹'+x.stake.toFixed(0)}</div></div>`;
    });

    // Daily summary is calculated server-side from the complete trade log.
    const ds=d2.daily_summary, tt=ds.trades, tw=ds.wins, tl2=ds.losses, tp=ds.pnl;
    document.getElementById('dTr').innerText=tt;
    document.getElementById('dWr').innerText=ds.win_rate+'%';
    document.getElementById('dPnl').innerText=(tp>=0?'+':'')+'₹'+tp.toFixed(0);
    document.getElementById('dPnl').style.color=tp>=0?'var(--green)':'var(--red)';
    document.getElementById('dBal').innerText='₹'+d2.bankroll.toFixed(0);
    document.getElementById('dW').innerText=tw;
    document.getElementById('dL').innerText=tl2;
    document.getElementById('dSt').innerText='₹'+ds.staked.toFixed(0);
    document.getElementById('dWbk').innerText='₹'+ds.won_back.toFixed(0);

    // Reset banner
    if(d2.current_loss_streak>=3){
      document.getElementById('resetBanner').style.display='flex';
      document.getElementById('lossCnt').innerText=d2.current_loss_streak;
    }else{
      document.getElementById('resetBanner').style.display='none';
    }
  }catch(e){console.error(e)}
}

async function submitInitialPeriod(){
  const p=document.getElementById('periodModalInp').value.trim();
  if(!p)return;
  document.getElementById('periInp').value=p;
  await syncPeri();
  localStorage.setItem('javidh_initial_sync_done','1');
  document.getElementById('periodModal').style.display='none';
}

// Initial check uses the website dialog, never a browser prompt.
window.addEventListener('load', ()=>{
  if(!localStorage.getItem('javidh_initial_sync_done')){
    setTimeout(()=>document.getElementById('periodModal').style.display='flex',250);
  }
});

const revealObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');revealObserver.unobserve(entry.target)}}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>revealObserver.observe(el));
refresh();
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass

    def do_GET(self):
        p=urllib.parse.urlparse(self.path).path
        if p in ['/','/index.html']:
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
            self.wfile.write(HTML.encode())
        elif p=='/api/predict':
            self.send_json(compute_pred())
        elif p=='/api/history':
            wr=round(state['wins']/max(1,state['trades'])*100,1)
            resp={k:state.get(k,0) for k in ['bankroll','initial_capital','base_stake','wins','losses','trades','current_loss_streak','max_loss_streak']}
            resp['win_rate']=wr
            resp['trade_log']=state['trade_log'][-15:]
            today=datetime.now().date()
            today_trades=[x for x in state['trade_log'] if str(x.get('timestamp','')).split('T')[0]==today.isoformat()]
            wins=sum(1 for x in today_trades if x.get('is_win'))
            losses=len(today_trades)-wins
            pnl=round(sum(float(x.get('profit',0)) for x in today_trades),2)
            resp['daily_summary']={'trades':len(today_trades),'wins':wins,'losses':losses,
                'win_rate':round(wins/max(1,len(today_trades))*100,1),'pnl':pnl,
                'staked':round(sum(float(x.get('stake',0)) for x in today_trades),2),
                'won_back':round(sum(float(x.get('stake',0)+x.get('profit',0)) for x in today_trades if x.get('is_win')),2)}
            self.send_json(resp)
        elif p=='/api/export':
            self.send_response(200)
            self.send_header('Content-Type','text/csv')
            self.send_header('Content-Disposition','attachment;filename="javidh_algo_pro.csv"')
            self.end_headers()
            lines=['Period,Number,Big_Small,Color,Result,Stake,Multiplier,Profit,Timestamp\n']
            for x in state['trade_log']:
                lines.append(f"{x['period']},{x['number']},{x['actual_side']},{x['color']},{'WIN' if x['is_win'] else 'LOSS'},{x['stake']},{x['multiplier']},{x['profit']},{x['timestamp']}\n")
            self.wfile.write(''.join(lines).encode())
        else:self.send_response(404);self.end_headers()

    def do_POST(self):
        p=urllib.parse.urlparse(self.path).path
        cl=int(self.headers.get('Content-Length',0))
        body=self.rfile.read(cl) if cl>0 else b'{}'
        try:data=json.loads(body.decode())
        except:data={}

        if p=='/api/record':
            num=int(data.get('number',-1))
            if 0<=num<=9:
                pred=compute_pred()
                tp=pred['target_period']
                stake=pred['recommended_stake']
                mult=pred['multiplier']
                side='BIG' if num>=5 else 'SMALL'
                won=(pred['side']==side)

                state['trades']+=1
                if won:
                    profit=(stake*1.96)-stake
                    state['bankroll']+=profit;state['wins']+=1;state['current_loss_streak']=0
                else:
                    profit=-stake;state['bankroll']-=stake;state['losses']+=1
                    state['current_loss_streak']+=1
                    state['max_loss_streak']=max(state['max_loss_streak'],state['current_loss_streak'])

                col=color_of(num);ts=datetime.now().isoformat(timespec='seconds')
                state['trade_log'].append({'period':tp,'number':num,'actual_side':side,'color':col,
                    'is_win':won,'stake':stake,'multiplier':mult,'profit':round(profit,2),'timestamp':ts})
                state['history'].append({'period':tp,'number':num,'is_big':1 if num>=5 else 0,'color':col,'timestamp':ts})
                state['current_period']=tp
                state['target_period']=str(int(tp)+1) if tp.isdigit() else str(int(tp)+1)

                # Write to CSV file (append with header if new)
                header_written = os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0
                with open(DATA_FILE,'a',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=['timestamp','game','period','number','is_big','big_small','color'])
                    if not header_written:
                        w.writeheader()
                    w.writerow({'timestamp':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'game':f'WinGo_{state["game_mode"]}','period':tp,'number':num,'is_big':1 if num>=5 else 0,'big_small':side,'color':col})

                self.send_json({'ok':True,'win':won,'bankroll':state['bankroll'],'period':tp})
        elif p=='/api/set_cap':
            cap=float(data.get('capital',2000));state['bankroll']=cap;state['initial_capital']=cap
            state['base_stake']=max(50,round(cap*0.025,0))
            state['wins']=state['losses']=state['trades']=state['current_loss_streak']=state['max_loss_streak']=0
            state['trade_log']=[]
            self.send_json({'ok':True})
        elif p=='/api/set_stake':
            state['base_stake']=max(10,float(data.get('stake',50)));self.send_json({'ok':True})
        elif p=='/api/adj_stake':
            state['base_stake']=max(10,state['base_stake']+float(data.get('delta',25)));self.send_json({'ok':True})
        elif p=='/api/set_mode':
            state['game_mode']=data.get('mode','30S');self.send_json({'ok':True})
        elif p=='/api/calibrate':
            ps=str(data.get('period','52436')).strip()
            if state['history']:
                ln=state['history'][-1]['number']
                state['history'].append({'period':ps,'number':ln,'is_big':1 if ln>=5 else 0,'color':color_of(ln),'timestamp':datetime.now().strftime('%H:%M:%S')})
            state['current_period']=ps
            state['target_period']=str(int(ps)+1) if ps.isdigit() else ps
            self.send_json({'ok':True})
        elif p=='/api/reset':
            state['current_loss_streak']=0
            init()
            self.send_json({'ok':True})
        else:self.send_response(404);self.end_headers()

    def send_json(self,d):
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps(d).encode())

def compute_pred():
    return predict()

if __name__=='__main__':
    print('\n'+'='*60)
    print(' ⚡ JAVIDH ALGO PRO v3 — http://localhost:5000')
    print('='*60+'\n')
    HTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
