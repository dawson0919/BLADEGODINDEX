"""
🗡️ 刀神指標 — Flask Backend
Serves the dashboard and provides SPX K-line data via yfinance.
"""
import os
import json
from datetime import datetime, timezone

from flask import Flask, jsonify, send_from_directory, request
import yfinance as yf
import pandas as pd

app = Flask(__name__, static_folder="dashboard")
PORT = int(os.environ.get("PORT", 7788))

# ── In-memory cache (expires every 30 min) ──────────────────────────────────
_cache: dict = {"data": None, "ts": 0}
CACHE_TTL = 1800  # seconds


def _fetch_spx(period: str = "max") -> list[dict]:
    """Download SPX OHLCV data using yfinance and return as list of dicts."""
    ticker = yf.Ticker("^GSPC")
    hist: pd.DataFrame = ticker.history(period=period, interval="1d", auto_adjust=True)

    candles = []
    for dt, row in hist.iterrows():
        if pd.isna(row["Open"]):
            continue
        # yfinance returns timezone-aware DatetimeIndex; convert to date string
        if hasattr(dt, "date"):
            date_str = dt.date().strftime("%Y-%m-%d")
        else:
            date_str = str(dt)[:10]

        candles.append({
            "time":   date_str,
            "open":   round(float(row["Open"]),   2),
            "high":   round(float(row["High"]),   2),
            "low":    round(float(row["Low"]),    2),
            "close":  round(float(row["Close"]),  2),
            "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
        })

    # Deduplicate and sort by date (yfinance occasionally returns duplicates)
    seen = set()
    unique = []
    for c in candles:
        if c["time"] not in seen:
            seen.add(c["time"])
            unique.append(c)
    unique.sort(key=lambda x: x["time"])
    return unique


# ── API: SPX K-lines ─────────────────────────────────────────────────────────

@app.route("/api/spx-klines")
def spx_klines():
    now = datetime.now(timezone.utc).timestamp()
    period = request.args.get("period", "max")

    # Serve from cache if fresh
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        candles = _cache["data"]
    else:
        try:
            candles = _fetch_spx(period)
            _cache["data"] = candles
            _cache["ts"]   = now
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({
        "candles": candles,
        "total":   len(candles),
        "from":    candles[0]["time"]  if candles else None,
        "to":      candles[-1]["time"] if candles else None,
    })


# ── API: Blade God Index (real-time score) ─────────────────────────────────────

from calculator import compute, compute_history

_blade_cache:   dict = {"data": None, "ts": 0}
_history_cache: dict = {"data": None, "ts": 0}
BLADE_TTL   = 1800   # 30 min
HISTORY_TTL = 3600   # 1 hour


@app.route("/api/blade-index")
def blade_index():
    now = datetime.now(timezone.utc).timestamp()
    if _blade_cache["data"] and (now - _blade_cache["ts"]) < BLADE_TTL:
        return jsonify(_blade_cache["data"])
    try:
        result = compute()
        _blade_cache["data"] = result
        _blade_cache["ts"]   = now
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/blade-history")
def blade_history():
    now  = datetime.now(timezone.utc).timestamp()
    days = int(request.args.get("days", 252))
    if _history_cache["data"] and (now - _history_cache["ts"]) < HISTORY_TTL:
        return jsonify({"history": _history_cache["data"]})
    try:
        hist = compute_history(days)
        _history_cache["data"] = hist
        _history_cache["ts"]   = now
        return jsonify({"history": hist})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


@app.route("/<path:path>")
def static_files(path):
    full = os.path.join("dashboard", path)
    if os.path.isfile(full):
        return send_from_directory("dashboard", path)
    return send_from_directory("dashboard", "index.html")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🗡️  刀神指標 running at http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
