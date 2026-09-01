import os
import csv
import math

def load_data(csv_path):
    if not os.path.exists(csv_path): return []
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                num = int(r["number"])
                records.append({
                    "period": str(r["period"]).strip(),
                    "number": num,
                    "is_big": 1 if num >= 5 else 0,
                    "spin": 1 if num >= 5 else -1,
                })
            except Exception:
                continue
    return sorted(records, key=lambda x: str(x["period"]))

def calculate_kelly_stake(prob):
    """Fractional Kelly Sizing (1/4th Kelly) based on CLAUDE.md"""
    if prob >= 0.65: return 35.0, "ULTRA_35"
    elif prob >= 0.60: return 25.0, "HIGH_25"
    elif prob >= 0.57: return 15.0, "MED_15"
    return 0.0, "SKIP"


# =====================================================================
# VARIANT 1: Multi-Scale Wavelet (Spectral) Cycle Detection
# =====================================================================
class SpectralWaveletEngine:
    @staticmethod
    def calculate_spectral_power(history, window, period_length):
        if len(history) < window: return 0.0
        spins = [r["spin"] for r in history[-window:]]
        N = len(spins)
        cos_sum = sum(spins[n] * math.cos(2 * math.pi * n / period_length) for n in range(N))
        sin_sum = sum(spins[n] * math.sin(2 * math.pi * n / period_length) for n in range(N))
        return (cos_sum**2 + sin_sum**2) / N

    @staticmethod
    def evaluate(history):
        if len(history) < 20: return None, False, 0.0, 0.5, "WARMUP"
        
        last_bs = history[-1]["is_big"]
        
        # Powers for 2 (alternating), 4 (short cycle), 8 (long trend)
        pow_2 = SpectralWaveletEngine.calculate_spectral_power(history, 16, 2)
        pow_4 = SpectralWaveletEngine.calculate_spectral_power(history, 16, 4)
        pow_8 = SpectralWaveletEngine.calculate_spectral_power(history, 16, 8)
        
        tot_power = pow_2 + pow_4 + pow_8 + 1e-5
        
        # If 2-period dominates (chop)
        if pow_2 / tot_power > 0.5:
            pred = 1 - last_bs
            prob = 0.5 + 0.15 * (pow_2 / tot_power)
        # If 8-period dominates (trend)
        elif pow_8 / tot_power > 0.5:
            pred = last_bs
            prob = 0.5 + 0.15 * (pow_8 / tot_power)
        else:
            # Noise
            return None, False, 0.0, 0.5, "NOISE"
            
        stake, tier = calculate_kelly_stake(prob)
        take_trade = stake > 0
        return (pred, take_trade, stake, prob, tier)


# =====================================================================
# VARIANT 2: Lempel-Ziv (LZ77) Kolmogorov Complexity
# =====================================================================
class LempelZivEngine:
    @staticmethod
    def lz_complexity(s):
        i, k, l = 0, 1, 1
        k_max = 1
        n = len(s)
        complexity = 1
        while True:
            if i + k >= n:
                break
            if s[i + k] == s[l + k - 1]:
                k += 1
                if l + k > k_max:
                    k_max = l + k
            else:
                if l == i + 1:
                    i += k_max
                    k = 1
                    l = 1
                    k_max = 1
                    complexity += 1
                else:
                    l += 1
        return complexity

    @staticmethod
    def evaluate(history):
        if len(history) < 25: return None, False, 0.0, 0.5, "WARMUP"
        
        window = 20
        spins = [str(r["is_big"]) for r in history[-window:]]
        seq = "".join(spins)
        
        c = LempelZivEngine.lz_complexity(seq)
        
        # Normalized complexity roughly
        norm_c = c / window
        
        # Low complexity -> highly predictable (trending or strict alternating)
        if norm_c < 0.35:
            # Compressible. Let's see if it's a trend or alternating
            s1, s2 = history[-2]["is_big"], history[-1]["is_big"]
            if s1 == s2: 
                pred = s2 # follow trend
                prob = 0.65
            else:
                pred = 1 - s2 # follow alternating
                prob = 0.65
        else:
            prob = 0.5
            pred = 0
            
        stake, tier = calculate_kelly_stake(prob)
        take_trade = stake > 0
        return (pred, take_trade, stake, prob, tier)


# =====================================================================
# VARIANT 3: Rolling Logistic Regression on Entropy & Ising Features
# =====================================================================
class RollingLogisticEngine:
    @staticmethod
    def get_features(history, idx):
        # We need a sub-history up to idx
        if idx < 15: return [0, 0, 0]
        sub = history[:idx]
        spins = [r["spin"] for r in sub[-10:]]
        
        # J_t (Ising coupling)
        J_t = sum(spins[i]*spins[i-1] for i in range(1, len(spins))) / (len(spins)-1)
        
        # Entropy H
        p_big = sum(1 for s in spins if s == 1) / len(spins)
        p_small = 1.0 - p_big
        H = 0.0
        if 0 < p_big < 1:
            H = -(p_big * math.log2(p_big) + p_small * math.log2(p_small))
            
        # Streak length
        streak = 1
        for i in range(len(spins)-2, -1, -1):
            if spins[i] == spins[-1]: streak += 1
            else: break
            
        return [J_t, H, streak]

    @staticmethod
    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(max(min(-x, 100), -100)))

    @staticmethod
    def evaluate(history):
        train_window = 30
        if len(history) < train_window + 15:
            return None, False, 0.0, 0.5, "WARMUP"
            
        # Prepare training data (last 30 rounds)
        X = []
        y = []
        for i in range(len(history) - train_window, len(history)):
            X.append(RollingLogisticEngine.get_features(history, i))
            y.append(history[i]["is_big"])
            
        # Train simple logistic regression with gradient descent
        w = [0.0, 0.0, 0.0]
        b = 0.0
        lr = 0.1
        epochs = 20
        
        for _ in range(epochs):
            for i in range(len(X)):
                z = w[0]*X[i][0] + w[1]*X[i][1] + w[2]*X[i][2] + b
                pred_y = RollingLogisticEngine.sigmoid(z)
                err = pred_y - y[i]
                w[0] -= lr * err * X[i][0]
                w[1] -= lr * err * X[i][1]
                w[2] -= lr * err * X[i][2]
                b -= lr * err

        # Predict next
        curr_feat = RollingLogisticEngine.get_features(history, len(history))
        z_next = w[0]*curr_feat[0] + w[1]*curr_feat[1] + w[2]*curr_feat[2] + b
        prob_big = RollingLogisticEngine.sigmoid(z_next)
        
        if prob_big >= 0.575:
            pred = 1
            prob = prob_big
        elif prob_big <= 0.425:
            pred = 0
            prob = 1.0 - prob_big
        else:
            return None, False, 0.0, prob_big, "BELOW_SNR"
            
        stake, tier = calculate_kelly_stake(prob)
        take_trade = stake > 0
        return (pred, take_trade, stake, prob, tier)


# =====================================================================
# VARIANT 4: Bayesian Dirichlet Markov Engine (Sniper Threshold)
# =====================================================================
class BayesianDirichletEngine:
    @staticmethod
    def evaluate(history):
        if len(history) < 20:
            return None, False, 0.0, 0.5, "WARMUP"
            
        # Prior pseudocounts for transitions (0->0, 0->1, 1->0, 1->1)
        # We use a slight momentum prior
        counts = {
            (0, 0): 2.0, (0, 1): 1.0, 
            (1, 0): 1.0, (1, 1): 2.0
        }
        
        # Look back 50 rounds for local adaptation
        window = history[-50:]
        
        for i in range(1, len(window)):
            prev = window[i-1]["is_big"]
            curr = window[i]["is_big"]
            counts[(prev, curr)] += 1.0
            
        last_state = window[-1]["is_big"]
        
        # Posterior predictive probability
        alpha_0 = counts[(last_state, 0)]
        alpha_1 = counts[(last_state, 1)]
        total = alpha_0 + alpha_1
        
        prob_big = alpha_1 / total
        
        if prob_big >= 0.65:
            pred = 1
            prob = prob_big
        elif prob_big <= 0.35:
            pred = 0
            prob = 1.0 - prob_big
        else:
            return None, False, 0.0, prob_big, "BELOW_SNIPER_THRESHOLD"
            
        stake, tier = calculate_kelly_stake(prob)
        # Force ultra conviction stake
        stake = 35.0
        return (pred, True, stake, prob, "SNIPER_TIER")


# =====================================================================
# VARIANT 5: Non-Linear Attractor / Chaos Phase Space (KNN Trajectory)
# =====================================================================
class ChaosAttractorEngine:
    @staticmethod
    def evaluate(history):
        d = 4 # Embedding dimension
        tau = 1 # Time delay
        k_neighbors = 7 # K-nearest neighbors for probability density
        
        # Need enough history for embedding and finding neighbors
        if len(history) < d * tau + k_neighbors + 20:
            return None, False, 0.0, 0.5, "WARMUP"
            
        # We use the raw numbers (0-9) to form the phase space, rather than just binary
        nums = [r["number"] for r in history]
        
        # Current trajectory state vector
        v_current = nums[-d:]
        
        # Build library of past state vectors and their next outcomes
        distances = []
        for i in range(len(nums) - d - 1):
            v_past = nums[i : i+d]
            next_num = nums[i+d]
            
            # Euclidean distance
            dist = math.sqrt(sum((v_current[j] - v_past[j])**2 for j in range(d)))
            distances.append((dist, 1 if next_num >= 5 else 0))
            
        # Sort by closest trajectories
        distances.sort(key=lambda x: x[0])
        
        # Take K nearest neighbors
        nearest = distances[:k_neighbors]
        
        # Calculate probability of Big among the closest past trajectories
        big_count = sum(1 for _, outcome in nearest if outcome == 1)
        prob_big = big_count / k_neighbors
        
        if prob_big >= 0.70:
            pred = 1
            prob = prob_big
        elif prob_big <= 0.30:
            pred = 0
            prob = 1.0 - prob_big
        else:
            return None, False, 0.0, prob_big, "LOW_PREDICTABILITY_ATTRACTOR"
            
        stake, tier = calculate_kelly_stake(prob)
        # Dynamic sizing for chaos model
        if prob >= 0.85: stake = 40.0
        elif prob >= 0.70: stake = 25.0
        else: stake = 15.0
        
        return (pred, True, stake, prob, "ATTRACTOR_RESONANCE")


# =====================================================================
# SIMULATION ENGINE
# =====================================================================
def run_sim(records, engine_class, initial_capital=2000.0, payout_mult=1.96):
    balance = initial_capital
    peak = initial_capital
    max_dd = 0.0
    wins, losses, trades = 0, 0, 0
    cur_loss_streak, max_loss_streak = 0, 0
    cooldown = 0
    
    trade_log = []
    
    for t in range(25, len(records)):
        history = records[:t]
        actual_bs = records[t]["is_big"]
        actual_num = records[t]["number"]
        period = records[t]["period"]
        
        if cooldown > 0:
            cooldown -= 1
            continue
            
        pred, take_trade, stake, conf, tier = engine_class.evaluate(history)
        if not take_trade or pred is None: continue
        
        trades += 1
        is_win = (pred == actual_bs)
        
        if is_win:
            profit = (stake * payout_mult) - stake
            balance += profit
            wins += 1
            cur_loss_streak = 0
        else:
            balance -= stake
            losses += 1
            cur_loss_streak += 1
            max_loss_streak = max(max_loss_streak, cur_loss_streak)
            if cur_loss_streak >= 2:
                cooldown = 1
                
        peak = max(peak, balance)
        dd = (peak - balance) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        
        trade_log.append({
            "trade_no": trades,
            "period": period,
            "pred": "Big" if pred == 1 else "Small",
            "actual": "Big" if actual_bs == 1 else "Small",
            "result": "WIN" if is_win else "LOSS",
            "stake": stake,
            "pnl": profit if is_win else -stake,
            "balance": balance
        })
        
    success_rate = (wins / trades * 100) if trades > 0 else 0.0
    net_pnl = balance - initial_capital
    
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "success_rate": success_rate,
        "net_pnl": net_pnl,
        "final_bankroll": balance,
        "max_loss_streak": max_loss_streak,
        "max_dd_pct": max_dd * 100,
        "trade_log": trade_log
    }

def main():
    recs_30s = load_data("wingo_30s_data.csv")
    recs_1m = load_data("wingo_1m_data.csv")
    recs_all = sorted(recs_30s + recs_1m, key=lambda x: str(x["period"]))

    variants = [
        ("Variant 1: Spectral Wavelet Engine", SpectralWaveletEngine),
        ("Variant 2: Lempel-Ziv LZ77 Engine", LempelZivEngine),
        ("Variant 3: Rolling Logistic Regression", RollingLogisticEngine),
        ("Variant 4: Bayesian Dirichlet Sniper", BayesianDirichletEngine),
        ("Variant 5: Chaos Phase Space Trajectory", ChaosAttractorEngine)
    ]
    
    results_dict = {}
    
    print(f"{'Strategy Name':38s} | {'Trades':6s} | {'Wins':5s} | {'Loss':5s} | {'Success Rate':12s} | {'Net PnL (Rs)':11s} | {'Bankroll (Rs)':12s} | {'Max Loss':8s} | {'Max DD%':7s}")
    print("-" * 125)
    
    for name, engine in variants:
        res = run_sim(recs_all, engine)
        results_dict[name] = res
        pnl_s = f"+{res['net_pnl']:.2f}" if res['net_pnl'] >= 0 else f"{res['net_pnl']:.2f}"
        print(f"{name:38s} | {res['trades']:6d} | {res['wins']:5d} | {res['losses']:5d} | {res['success_rate']:6.2f}%      | {pnl_s:11s} | {res['final_bankroll']:12.2f} | {res['max_loss_streak']:8d} | {res['max_dd_pct']:.2f}%")

    top_res = results_dict["Variant 1: Spectral Wavelet Engine"]
    print("\n" + "=" * 120)
    print("          TRADE-BY-TRADE PROCESS LOG (TOP STRATEGY: Variant 1) - LAST 15 TRADES")
    print("=" * 120)
    print(f"{'Trade #':7s} | {'Period':17s} | {'Prediction':10s} | {'Actual Side':11s} | {'Result':7s} | {'Stake (Rs)':10s} | {'PnL (Rs)':10s} | {'Bankroll (Rs)':13s}")
    print("-" * 120)
    for t in top_res["trade_log"][-15:]:
        pnl_s = f"+{t['pnl']:.2f}" if t['pnl'] >= 0 else f"{t['pnl']:.2f}"
        print(f"{t['trade_no']:<7d} | {t['period']:17s} | {t['pred']:10s} | {t['actual']:11s} | {t['result']:7s} | {t['stake']:<10.2f} | {pnl_s:10s} | {t['balance']:<13.2f}")
    print("=" * 120)

if __name__ == "__main__":
    main()
