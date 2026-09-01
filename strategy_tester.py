"""
Strategy Backtesting & PnL Simulation Engine for Win Go.
Pure Python Standard Library (No external dependencies needed).
"""

import csv
import sys
import os

class StrategyTester:
    def __init__(self, records: list, initial_capital: float = 1000.0, payout_multiplier: float = 1.96):
        # Sort by period ascending
        self.records = sorted(records, key=lambda x: str(x.get("period", "")))
        self.initial_capital = initial_capital
        self.payout_mult = payout_multiplier

    def run_strategy(self, strategy_name: str, bet_sizing: str = "flat", base_unit: float = 10.0, max_levels: int = 7) -> dict:
        balance = self.initial_capital
        history_balance = [balance]
        wins = 0
        losses = 0
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        current_loss_streak = 0
        bust = False

        is_big_arr = [r["is_big"] for r in self.records]
        num_arr = [r["number"] for r in self.records]
        period_arr = [r["period"] for r in self.records]
        n = len(self.records)

        for t in range(1, n):
            pred = self._get_prediction(strategy_name, is_big_arr[:t], num_arr[:t], period_arr[:t])
            if pred is None:
                continue

            if bet_sizing == "flat":
                bet_amount = base_unit
            elif bet_sizing == "martingale":
                bet_amount = base_unit * (2 ** min(current_loss_streak, max_levels - 1))
            elif bet_sizing == "dalembert":
                bet_amount = base_unit * max(1, 1 + current_loss_streak)
            else:
                bet_amount = base_unit

            if balance < bet_amount:
                bust = True
                bet_amount = balance
                if balance <= 0:
                    break

            actual = is_big_arr[t]
            is_win = (pred == actual)

            if is_win:
                profit = (bet_amount * self.payout_mult) - bet_amount
                balance += profit
                wins += 1
                current_loss_streak = 0
                current_streak = current_streak + 1 if current_streak > 0 else 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                balance -= bet_amount
                losses += 1
                current_loss_streak += 1
                current_streak = current_streak - 1 if current_streak < 0 else -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))

            history_balance.append(round(balance, 2))

        total_rounds = wins + losses
        win_rate = (wins / total_rounds * 100) if total_rounds > 0 else 0
        net_pnl = balance - self.initial_capital
        roi = (net_pnl / self.initial_capital) * 100

        peak = self.initial_capital
        max_dd = 0
        for b in history_balance:
            if b > peak:
                peak = b
            dd = (peak - b) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "strategy": strategy_name,
            "bet_sizing": bet_sizing,
            "total_rounds": total_rounds,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "final_balance": round(balance, 2),
            "net_pnl": round(net_pnl, 2),
            "roi_pct": round(roi, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "busted": bust and (balance <= 0)
        }

    def _get_prediction(self, name: str, past_bs: list, past_nums: list, past_periods: list):
        last_bs = past_bs[-1]
        last_num = past_nums[-1]

        if name == "Dragon_Follow":
            return last_bs
        elif name == "Anti_Dragon_Reversal":
            return 1 - last_bs
        elif name == "Reversal_After_Streak_3":
            if len(past_bs) >= 3 and past_bs[-1] == past_bs[-2] == past_bs[-3]:
                return 1 - last_bs
            return last_bs
        elif name == "Period_Formula_Sum_Mod2":
            period_str = str(past_periods[-1])
            digit_sum = sum(int(d) for d in period_str if d.isdigit()) + last_num
            return 1 if (digit_sum % 2 == 1) else 0
        elif name == "Parity_Mirror":
            return 1 if (last_num % 2 != 0) else 0
        else:
            return last_bs

def load_csv(csv_path: str):
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                num = int(r["number"])
                records.append({
                    "period": r.get("period", ""),
                    "number": num,
                    "is_big": 1 if num >= 5 else 0
                })
            except Exception:
                continue
    return records

def benchmark_file(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    records = load_csv(csv_path)
    if not records:
        print(f"No valid records found in {csv_path}")
        return

    tester = StrategyTester(records, initial_capital=1000.0, payout_multiplier=1.96)
    strategies = [
        "Dragon_Follow",
        "Anti_Dragon_Reversal",
        "Reversal_After_Streak_3",
        "Period_Formula_Sum_Mod2",
        "Parity_Mirror"
    ]

    print(f"\n==================== STRATEGY BENCHMARK ({csv_path} | N={len(records)}) ====================")
    print(f"{'Strategy':25s} | {'Sizing':10s} | {'Win Rate':9s} | {'Net PnL':12s} | {'Max Loss Streak':15s} | {'Max DD %':8s}")
    print("-" * 92)

    for strat in strategies:
        for sizing in ["flat", "martingale"]:
            res = tester.run_strategy(strat, bet_sizing=sizing, base_unit=10.0, max_levels=7)
            busted_str = " (BUSTED)" if res["busted"] else ""
            pnl_str = f"{res['net_pnl']:+.2f}{busted_str}"
            print(f"{strat:25s} | {sizing:10s} | {res['win_rate_pct']:6.2f}%   | {pnl_str:12s} | {res['max_loss_streak']:15d} | {res['max_drawdown_pct']:6.2f}%")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "live_wingo_collected.csv"
    benchmark_file(target)
