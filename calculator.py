"""
刀神指標 — 計算引擎
9 sub-indicators, all via yfinance (no API key required).
"""

import io
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Weights (must sum to 1.0) ─────────────────────────────────────────────────
WEIGHTS = {
    "momentum":  0.15,
    "vix":       0.15,
    "putcall":   0.15,
    "junk":      0.10,
    "safehaven": 0.10,
    "breadth":   0.10,
    "margin":    0.10,
    "cot":       0.10,
    "crypto":    0.05,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def norm(val: float, low: float, high: float, invert: bool = False) -> float:
    """Linearly map val ∈ [low, high] → [0, 100]; clamp outside range."""
    if high == low:
        return 50.0
    s = (val - low) / (high - low) * 100.0
    s = clamp(s)
    return round(100.0 - s if invert else s, 1)


def _dl(symbols, days: int = 400) -> pd.DataFrame:
    """Download adjusted close prices for symbol(s)."""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    raw = yf.download(symbols, start=start, auto_adjust=True,
                      progress=False, threads=True)
    if isinstance(symbols, str):
        col = "Close"
        return raw[[col]].rename(columns={col: symbols}).dropna()
    return raw["Close"].dropna(how="all")


# ── 1. Stock Market Momentum ───────────────────────────────────────────────────

def calc_momentum():
    spy = _dl("SPY", 300)["SPY"]
    if len(spy) < 130:
        return 50.0, "SPY 資料不足"
    ma125 = spy.rolling(125).mean().iloc[-1]
    cur   = float(spy.iloc[-1])
    pct   = (cur - float(ma125)) / float(ma125) * 100
    score = norm(pct, -15, 15)
    return score, f"SPY {cur:.2f} vs MA125 {ma125:.2f} ({pct:+.1f}%)"


# ── 2. Volatility — VIX ───────────────────────────────────────────────────────

def calc_vix():
    vix = _dl("^VIX", 200)["^VIX"]
    if len(vix) < 55:
        return 50.0, "VIX 資料不足"
    cur  = float(vix.iloc[-1])
    ma50 = float(vix.rolling(50).mean().iloc[-1])
    # Low VIX → greed (score high); high VIX → fear (score low)
    score = norm(cur, 40, 10)
    return score, f"VIX {cur:.2f}（50日均 {ma50:.2f}）"


# ── 3. Put / Call Ratio ────────────────────────────────────────────────────────

def calc_putcall():
    try:
        url = "https://www.cboe.com/data/volatility-indexes/total-pc-ratio.csv"
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        # Expect columns: date, pc ratio (or similar)
        pc_col = [c for c in df.columns if "ratio" in c or "put" in c]
        if not pc_col:
            pc_col = [df.columns[1]]
        df = df.rename(columns={pc_col[0]: "pc"})
        df["pc"] = pd.to_numeric(df["pc"], errors="coerce")
        df = df.dropna(subset=["pc"]).tail(10)
        ma5 = float(df["pc"].mean())
        # Low P/C (0.5) → greed; high P/C (1.5) → fear
        score = norm(ma5, 1.5, 0.5)
        return score, f"P/C Ratio {ma5:.2f}（5日均）"
    except Exception:
        return 50.0, "P/C 資料暫時不可用（中性）"


# ── 4. Junk Bond Demand ────────────────────────────────────────────────────────

def calc_junk():
    df = _dl(["HYG", "LQD"], 90)
    if df.shape[0] < 35 or "HYG" not in df or "LQD" not in df:
        return 50.0, "HYG/LQD 資料不足"
    r30 = df.pct_change(30).iloc[-1]
    diff = float(r30["HYG"] - r30["LQD"]) * 100
    score = norm(diff, -5, 5)
    return score, f"HYG-LQD 30日報酬差：{diff:+.2f}%"


# ── 5. Safe Haven Demand ───────────────────────────────────────────────────────

def calc_safehaven():
    df = _dl(["SPY", "TLT"], 60)
    if df.shape[0] < 25 or "SPY" not in df or "TLT" not in df:
        return 50.0, "SPY/TLT 資料不足"
    r20 = df.pct_change(20).iloc[-1]
    diff = float(r20["SPY"] - r20["TLT"]) * 100
    score = norm(diff, -10, 10)
    return score, f"SPY-TLT 20日報酬差：{diff:+.2f}%"


# ── 6. Market Breadth (sector ETFs above 50-day MA) ───────────────────────────

SECTOR_ETFS = ["XLK", "XLV", "XLF", "XLI", "XLY",
               "XLP", "XLE", "XLU", "XLRE", "XLB", "XLC"]


def calc_breadth():
    df = _dl(SECTOR_ETFS, 120)
    if df.shape[0] < 55:
        return 50.0, "行業 ETF 資料不足"
    latest = df.iloc[-1]
    ma50   = df.rolling(50).mean().iloc[-1]
    above  = int((latest > ma50).sum())
    total  = len(SECTOR_ETFS)
    score  = round(above / total * 100, 1)
    return score, f"{above}/{total} 行業 ETF 高於 MA50"


# ── 7. Margin / Leverage (RSP vs SPY equal-weight spread) ─────────────────────

def calc_margin():
    df = _dl(["RSP", "SPY"], 130)
    if df.shape[0] < 65 or "RSP" not in df or "SPY" not in df:
        return 50.0, "RSP/SPY 資料不足"
    ratio = (df["RSP"] / df["SPY"]).dropna()
    ma60  = ratio.rolling(60).mean()
    cur   = float(ratio.iloc[-1])
    avg   = float(ma60.iloc[-1])
    pct   = (cur - avg) / avg * 100
    score = norm(pct, -5, 5)
    return score, f"RSP/SPY 離均差：{pct:+.2f}%"


# ── 8. Smart Money / COT proxy (SPY vs GLD risk-on) ───────────────────────────

def calc_cot():
    df = _dl(["GLD", "SPY"], 90)
    if df.shape[0] < 25 or "GLD" not in df or "SPY" not in df:
        return 50.0, "GLD/SPY 資料不足"
    r20  = df.pct_change(20).iloc[-1]
    diff = float(r20["SPY"] - r20["GLD"]) * 100
    score = norm(diff, -10, 10)
    return score, f"SPY-GLD 20日報酬差：{diff:+.2f}%"


# ── 9. Crypto Contagion (BTC 30-day z-score) ──────────────────────────────────

def calc_crypto():
    btc = _dl("BTC-USD", 450)["BTC-USD"]
    if len(btc) < 100:
        return 50.0, "BTC 資料不足"
    ret30 = btc.pct_change(30).dropna()
    mu    = float(ret30.rolling(252).mean().iloc[-1])
    sigma = float(ret30.rolling(252).std().iloc[-1])
    r     = float(ret30.iloc[-1])
    z     = (r - mu) / sigma if sigma > 0 else 0.0
    score = norm(z, -2.5, 2.5)
    return score, f"BTC 30日 z-score：{z:+.2f}σ"


# ── Indicator registry ─────────────────────────────────────────────────────────

INDICATORS = [
    ("momentum",  calc_momentum,  "📊", "股市動能",       "Market Momentum",   "15%"),
    ("vix",       calc_vix,       "⚡", "VIX 恐慌指數",   "Volatility (VIX)",  "15%"),
    ("putcall",   calc_putcall,   "🎲", "Put/Call 比率",  "Options Sentiment", "15%"),
    ("junk",      calc_junk,      "💸", "垃圾債需求",     "Junk Bond Demand",  "10%"),
    ("safehaven", calc_safehaven, "🏦", "安全資產需求",   "Safe Haven Demand", "10%"),
    ("breadth",   calc_breadth,   "📐", "市場廣度",       "Market Breadth",    "10%"),
    ("margin",    calc_margin,    "⚖️", "融資槓桿",       "Margin Debt",       "10%"),
    ("cot",       calc_cot,       "🏛️", "機構籌碼 (COT)", "Smart Money / COT", "10%"),
    ("crypto",    calc_crypto,    "₿",  "加密溢出",       "Crypto Contagion",  "5%"),
]


# ── Source labels for display ──────────────────────────────────────────────────

SOURCES = {
    "momentum":  "Yahoo Finance (SPY)",
    "vix":       "Yahoo Finance (^VIX)",
    "putcall":   "CBOE 官方 CSV",
    "junk":      "Yahoo Finance (HYG/LQD)",
    "safehaven": "Yahoo Finance (SPY/TLT)",
    "breadth":   "Yahoo Finance (行業 ETF)",
    "margin":    "Yahoo Finance (RSP/SPY)",
    "cot":       "Yahoo Finance (GLD/SPY proxy)",
    "crypto":    "Yahoo Finance (BTC-USD)",
}


# ── Main compute function ──────────────────────────────────────────────────────

def compute() -> dict:
    """Calculate all 9 indicators and return composite Blade God Index score."""
    results = []
    weighted_sum = 0.0

    for key, fn, icon, name, name_en, weight_str in INDICATORS:
        weight = WEIGHTS[key]
        try:
            score, raw = fn()
        except Exception as exc:
            score, raw = 50.0, f"計算失敗: {exc}"

        results.append({
            "id":       key,
            "icon":     icon,
            "name":     name,
            "nameEn":   name_en,
            "weight":   weight_str,
            "score":    round(score, 1),
            "rawValue": raw,
            "source":   SOURCES[key],
        })
        weighted_sum += score * weight

    total = round(weighted_sum, 1)
    return {
        "score":      total,
        "indicators": results,
        "updatedAt":  datetime.now(timezone.utc).isoformat(),
    }


# ── Fast history (uses only SPY + VIX + HYG + LQD for speed) ─────────────────

def compute_history(days: int = 252) -> list[dict]:
    """
    Return a list of daily Blade Index scores for the past `days` trading days.
    Uses a simplified 4-factor proxy to stay fast:
      40% SPY momentum, 40% VIX (inverted), 20% HYG/LQD junk spread
    """
    spy = _dl("SPY",  days + 200)["SPY"]
    vix = _dl("^VIX", days + 100)["^VIX"]
    hj  = _dl(["HYG", "LQD"], days + 60)

    # Align all series on common trading dates
    base = spy.index.intersection(vix.index)
    if "HYG" in hj.columns and "LQD" in hj.columns:
        base = base.intersection(hj.index)
    base = base[-days:]

    spy = spy.reindex(base)
    vix = vix.reindex(base)

    history = []
    for dt in base:
        try:
            # Momentum score up to dt
            spy_window = spy[:dt].tail(150)
            ma125 = float(spy_window.rolling(125).mean().iloc[-1]) if len(spy_window) >= 125 else float(spy_window.mean())
            cur   = float(spy_window.iloc[-1])
            m_score = clamp((cur - ma125) / ma125 * 100 / 30.0 * 100 + 50)

            # VIX score
            v = float(vix.reindex([dt]).iloc[0])
            v_score = clamp((40 - v) / 30 * 100)

            # Junk bond score
            if "HYG" in hj.columns and "LQD" in hj.columns:
                hj_window = hj.loc[:dt].tail(35)
                if len(hj_window) >= 31:
                    r30_h = float(hj_window["HYG"].pct_change(30).iloc[-1]) * 100
                    r30_l = float(hj_window["LQD"].pct_change(30).iloc[-1]) * 100
                    diff  = r30_h - r30_l
                    j_score = clamp(diff / 10.0 * 100 + 50)
                else:
                    j_score = 50.0
            else:
                j_score = 50.0

            daily = round(m_score * 0.40 + v_score * 0.40 + j_score * 0.20, 1)
        except Exception:
            daily = 50.0

        history.append({
            "date":  dt.strftime("%Y-%m-%d"),
            "score": daily,
        })

    return history
