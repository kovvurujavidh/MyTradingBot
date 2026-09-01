"""
Live Data Collector for Win Go (30S and 1M) - Self-Contained & Resilient.
Pre-populates with HAR records and continuously collects live draws.
"""

import base64
import csv
import json
import os
import time
import urllib.request
from datetime import datetime

ENDPOINTS = {
    "WinGo_30S": "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json",
    "WinGo_1M": "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json",
}

CSV_FILE = "live_wingo_collected.csv"
CSV_FIELDS = ["timestamp", "game", "period", "number", "is_big", "big_small", "color"]

def fetch_json(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://damansuperstar1.com/",
        "Origin": "https://damansuperstar1.com"
    }
    ts = int(time.time() * 1000)
    full_url = f"{url}?ts={ts}"
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
            # Try decoding as utf-8 string
            try:
                text = raw.decode("utf-8")
            except Exception:
                text = str(raw)

            # Try direct JSON parsing
            try:
                return json.loads(text)
            except Exception:
                pass

            # Try base64 decode if response is encoded
            try:
                decoded = base64.b64decode(raw).decode("utf-8")
                return json.loads(decoded)
            except Exception:
                pass

            return None
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Network fetch notice ({url.split('/')[-2]}): {e}")
        return None

def parse_records(data, game_code: str):
    records = []
    if not data or not isinstance(data, dict):
        return records

    data_payload = data.get("data", {})
    if isinstance(data_payload, dict):
        items = data_payload.get("list", [])
    elif isinstance(data_payload, list):
        items = data_payload
    else:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue
        issue = str(item.get("issueNumber", item.get("issue", "")))
        num_raw = item.get("number", item.get("winningNumber", None))
        if issue and num_raw is not None:
            try:
                num = int(str(num_raw).strip().split(",")[-1])
                color = item.get("color", "")
                records.append({
                    "timestamp": datetime.now().isoformat(),
                    "game": game_code,
                    "period": issue,
                    "number": num,
                    "is_big": 1 if num >= 5 else 0,
                    "big_small": "Big" if num >= 5 else "Small",
                    "color": color
                })
            except ValueError:
                continue
    return records

def load_seen_periods():
    seen = set()
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "period" in row and row["period"]:
                        seen.add(row["period"])
        except Exception:
            pass
    return seen

def append_records(records):
    file_exists = os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0
    with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        for r in records:
            writer.writerow(r)

def import_har_data():
    """Extracts all historical records from HAR files if CSV is empty/missing."""
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 100:
        return

    print("Extracting historical rounds from HAR files to initialize dataset...")
    extracted = []
    har_files = [("damansuperstar1.com.har", "WinGo_30S"), ("damansuperstar2.com.har", "WinGo_1M")]

    for har_name, game in har_files:
        if not os.path.exists(har_name):
            continue
        try:
            with open(har_name, "r", encoding="utf-8", errors="ignore") as f:
                har = json.load(f)
            entries = har.get("log", {}).get("entries", [])
            for e in entries:
                text = e.get("response", {}).get("content", {}).get("text", "")
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except Exception:
                    try:
                        obj = json.loads(base64.b64decode(text).decode("utf-8"))
                    except Exception:
                        continue
                recs = parse_records(obj, game)
                extracted.extend(recs)
        except Exception as e:
            print(f"HAR import note for {har_name}: {e}")

    if extracted:
        # Deduplicate
        unique_recs = []
        seen = set()
        for r in extracted:
            if r["period"] not in seen:
                seen.add(r["period"])
                unique_recs.append(r)
        # Sort by period
        unique_recs.sort(key=lambda x: str(x["period"]))
        append_records(unique_recs)
        print(f"Initialized {CSV_FILE} with {len(unique_recs)} historical rounds from HAR files.")

def run_tracker(interval_sec: int = 5):
    print("==================================================")
    print("       LIVE WIN GO DATA COLLECTOR RUNNING         ")
    print("==================================================")
    print(f"Data file: {CSV_FILE}")
    print("Press Ctrl+C to stop at any time.\n")

    import_har_data()
    seen_periods = load_seen_periods()
    print(f"Total periods currently in database: {len(seen_periods)}\n")

    while True:
        new_records = []
        for game_code, endpoint in ENDPOINTS.items():
            data = fetch_json(endpoint)
            recs = parse_records(data, game_code)
            for r in recs:
                if r["period"] not in seen_periods:
                    seen_periods.add(r["period"])
                    new_records.append(r)
                    color_tag = f"[{r['color']}]" if r['color'] else ""
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] NEW: {r['game']} | Period: {r['period']} | Result: {r['number']} ({r['big_small']}) {color_tag}")

        if new_records:
            append_records(new_records)
            print(f"--> Saved {len(new_records)} new rounds to {CSV_FILE} (Total: {len(seen_periods)})\n")

        time.sleep(interval_sec)

if __name__ == "__main__":
    try:
        run_tracker(interval_sec=5)
    except KeyboardInterrupt:
        print("\nTracker stopped by user.")
