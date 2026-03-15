"""
🗡️ 刀神指標 — Calculator Engine
9 sub-indicators, all via yfinance (free, no API key required).
Compatible with yfinance >= 0.2.60 (MultiIndex columns).
"""

import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Weights (must sum to 1.0) ────────────────────────────────────────────────
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

# ── Helpers ──────────────────────────────────────────────────────────────────

def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def norm(val: float, low: float, high: float, invert: bool = False) -> float:
    """Linearly map val in [low, high] -> [0, 100]; clamp outside range."""
    if high == low:
        return 50.0
    s = (val - low) / (high - low) * 100.0
    s = clamp(s)
    return round(100.0 - s if invert else s, 1)


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns to simple strings."""
    if isinstance(df.columns, pd.MultiIndex):
        # For single ticker: ('Close', 'SPY') → 'Close'
        # For multi ticker: ('Close', 'SPY') → 'SPY', but we need context
        df = df.copy()
        df.columns = ['_'.join(str(c) for c in col).strip('_') for col in df.columns]
    return df


def _dl_single(symbol: str, days: int = 400) -> pd.Series:
    """Download close prices for a single ticker, return as Series."""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    raw = yf.download(symbol, start=start, auto_adjust=True,
                      progress=False, threads=False)
    if raw.empty:
        return pd.Series(dtype=float)
    flat = _flatten_cols(raw)
    # Find the Close column
    close_col = [c for c in flat.columns if c.startswith("Close")]
    if not close_col:
        return pd.Series(dtype=float)
    return flat[close_col[0]].dropna().rename(symbol)


def _dl_multi(symbols: list, days: int = 400) -> pd.DataFrame:
    """Download close prices for multiple tickers, return DataFrame with ticker columns."""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    raw = yf.download(symbols, start=start, auto_adjust=True,
                      progress=False, threads=True)
    if raw.empty:
        return pd.DataFrame()
    # With MultiIndex: level 0 = Price type, level 1 = Ticker
    if isinstance(raw.columns, pd.MultiIndex):
        # Extract Close prices only
        try:
            close_df = raw["Close"]
        except KeyError:
            close_df = raw.xs("Close", axis=1, level=0)
        return close_df.dropna(how="all")
    # Fallback: single ticker wrapped in list
    flat = _flatten_cols(raw)
    close_col = [c for c in flat.columns if c.startswith("Close")]
    if close_col:
        return flat[close_col].dropna(how="all")
    return pd.DataFrame()


# ── 1. Stock Market Momentum ────────────────────────────────────────────────

def calc_momentum():
    spy = _dl_single("SPY", 300)
    if len(spy) < 130:
        return 50.0, "SPY 資料不足"
    ma125 = float(spy.rolling(125).mean().iloc[-1])
    cur = float(spy.iloc[-1])
    pct = (cur - ma125) / ma125 * 100
    score = norm(pct, -15, 15)
    return score, f"SPY {cur:.2f} vs MA125 {ma125:.2f} ({pct:+.1f}%)"


# ── 2. Volatility — VIX ────────────────────────────────────────────────────

def calc_vix():
    vix = _dl_single("^VIX", 200)
    if len(vix) < 55:
        return 50.0, "VIX 資料不足"
    cur = float(vix.iloc[-1])
    ma50_val = float(vix.rolling(50).mean().iloc[-1])
    # Low VIX → greed (high score); high VIX → fear (low score)
    score = norm(cur, 40, 10)
    return score, f"VIX {cur:.2f}（50日均 {ma50_val:.2f}）"


# ── 3. Put / Call Ratio ──────────────────────────────────────────────────────

def calc_putcall():
    """VIX/Realized-Vol ratio with percentile rank over 252 days."""
    try:
        spy = _dl_single("SPY", 500)
        vix_s = _dl_single("^VIX", 500)
        if len(spy) < 60 or len(vix_s) < 60:
            return 50.0, "P/C 替代指標資料不足"

        # Compute daily IV/RV ratio series
        log_ret = np.log(spy / spy.shift(1)).dropna()
        rv20 = log_ret.rolling(20).std() * np.sqrt(252) * 100  # annualised %
        vix_aligned = vix_s.reindex(rv20.index, method="ffill")
        ratio_series = (vix_aligned / rv20).replace([np.inf, -np.inf], np.nan).dropna()

        if len(ratio_series) < 60:
            return 50.0, "波動比歷史不足"

        cur_ratio = float(ratio_series.iloc[-1])

        # Percentile rank over available history (inverted: high ratio = fear = low score)
        window = min(252, len(ratio_series) - 1)
        vals = ratio_series.tail(window + 1).values
        pct_rank = float(np.sum(vals[:-1] <= vals[-1]) / len(vals[:-1]))
        score = round((1 - pct_rank) * 100, 1)

        iv_val = float(vix_aligned.iloc[-1])
        rv_val = float(rv20.iloc[-1])
        return score, f"隱含/實現波動比 {cur_ratio:.2f} (VIX {iv_val:.1f} / RV {rv_val:.1f})"
    except Exception as exc:
        return 50.0, f"P/C 資料暫時不可用（{exc}）"


# ── 4. Junk Bond Demand ──────────────────────────────────────────────────────

def calc_junk():
    df = _dl_multi(["HYG", "LQD"], 90)
    if df.shape[0] < 35 or "HYG" not in df.columns or "LQD" not in df.columns:
        return 50.0, "HYG/LQD 資料不足"
    r30 = df.pct_change(30).iloc[-1]
    hyg_r = float(r30["HYG"])
    lqd_r = float(r30["LQD"])
    diff = (hyg_r - lqd_r) * 100
    score = norm(diff, -5, 5)
    return score, f"HYG-LQD 30日報酬差：{diff:+.2f}%"


# ── 5. Safe Haven Demand ─────────────────────────────────────────────────────

def calc_safehaven():
    df = _dl_multi(["SPY", "TLT"], 60)
    if df.shape[0] < 25 or "SPY" not in df.columns or "TLT" not in df.columns:
        return 50.0, "SPY/TLT 資料不足"
    r20 = df.pct_change(20).iloc[-1]
    spy_r = float(r20["SPY"])
    tlt_r = float(r20["TLT"])
    diff = (spy_r - tlt_r) * 100
    score = norm(diff, -10, 10)
    return score, f"SPY-TLT 20日報酬差：{diff:+.2f}%"


# ── 6. Market Breadth (sector ETFs above 50-day MA) ──────────────────────────

SECTOR_ETFS = ["XLK", "XLV", "XLF", "XLI", "XLY",
               "XLP", "XLE", "XLU", "XLRE", "XLB", "XLC"]

def calc_breadth():
    df = _dl_multi(SECTOR_ETFS, 120)
    if df.shape[0] < 55:
        return 50.0, "行業 ETF 資料不足"
    latest = df.iloc[-1]
    ma50 = df.rolling(50).mean().iloc[-1]
    above = int((latest > ma50).sum())
    total = len([c for c in df.columns if c in SECTOR_ETFS])
    if total == 0:
        return 50.0, "行業 ETF 資料不足"
    score = round(above / total * 100, 1)
    return score, f"{above}/{total} 行業 ETF 高於 MA50"


# ── 7. Leverage proxy (RSP vs SPY equal-weight spread) ───────────────────────

def calc_margin():
    df = _dl_multi(["RSP", "SPY"], 130)
    if df.shape[0] < 65 or "RSP" not in df.columns or "SPY" not in df.columns:
        return 50.0, "RSP/SPY 資料不足"
    ratio = (df["RSP"] / df["SPY"]).dropna()
    ma60 = ratio.rolling(60).mean()
    cur = float(ratio.iloc[-1])
    avg = float(ma60.iloc[-1])
    pct = (cur - avg) / avg * 100
    score = norm(pct, -5, 5)
    return score, f"RSP/SPY 離均差：{pct:+.2f}%"


# ── 8. Smart Money / COT proxy (SPY vs GLD) ─────────────────────────────────

def calc_cot():
    df = _dl_multi(["GLD", "SPY"], 90)
    if df.shape[0] < 25 or "GLD" not in df.columns or "SPY" not in df.columns:
        return 50.0, "GLD/SPY 資料不足"
    r20 = df.pct_change(20).iloc[-1]
    spy_r = float(r20["SPY"])
    gld_r = float(r20["GLD"])
    diff = (spy_r - gld_r) * 100
    score = norm(diff, -10, 10)
    return score, f"SPY-GLD 20日報酬差：{diff:+.2f}%"


# ── 9. Crypto Contagion (BTC 30-day z-score) ────────────────────────────────

def calc_crypto():
    btc = _dl_single("BTC-USD", 450)
    if len(btc) < 100:
        return 50.0, "BTC 資料不足"
    ret30 = btc.pct_change(30).dropna()
    if len(ret30) < 60:
        return 50.0, "BTC 歷史不足"
    window = min(252, len(ret30) - 1)
    mu = float(ret30.rolling(window).mean().iloc[-1])
    sigma = float(ret30.rolling(window).std().iloc[-1])
    r = float(ret30.iloc[-1])
    z = (r - mu) / sigma if sigma > 0 else 0.0
    score = norm(z, -2.5, 2.5)
    return score, f"BTC 30日 z-score：{z:+.2f}σ"


# ── Indicator registry ───────────────────────────────────────────────────────

INDICATORS = [
    ("momentum",  calc_momentum,  "📊", "股市動能",       "Market Momentum",   "15%"),
    ("vix",       calc_vix,       "⚡", "VIX 恐慌指數",   "Volatility (VIX)",  "15%"),
    ("putcall",   calc_putcall,   "🎲", "Put/Call 比率",  "Options Sentiment", "15%"),
    ("junk",      calc_junk,      "💸", "垃圾債需求",     "Junk Bond Demand",  "10%"),
    ("safehaven", calc_safehaven, "🏦", "安全資產需求",   "Safe Haven Demand", "10%"),
    ("breadth",   calc_breadth,   "📐", "市場廣度",       "Market Breadth",    "10%"),
    ("margin",    calc_margin,    "⚖️", "融資槓桿",       "Leverage Proxy",    "10%"),
    ("cot",       calc_cot,       "🏛️", "機構籌碼 (COT)", "Smart Money / COT", "10%"),
    ("crypto",    calc_crypto,    "₿",  "加密溢出",       "Crypto Contagion",  "5%"),
]


# Source labels for dashboard display
SOURCES = {
    "momentum":  "Yahoo Finance (SPY)",
    "vix":       "Yahoo Finance (^VIX)",
    "putcall":   "CBOE / Yahoo Finance",
    "junk":      "Yahoo Finance (HYG/LQD)",
    "safehaven": "Yahoo Finance (SPY/TLT)",
    "breadth":   "Yahoo Finance (行業 ETF)",
    "margin":    "Yahoo Finance (RSP/SPY)",
    "cot":       "Yahoo Finance (GLD/SPY)",
    "crypto":    "Yahoo Finance (BTC-USD)",
}


# ── Main compute function ────────────────────────────────────────────────────

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
            "source":   SOURCES.get(key, "Yahoo Finance"),
        })
        weighted_sum += score * weight

    total = round(weighted_sum, 1)
    return {
        "score":      total,
        "indicators": results,
        "updatedAt":  datetime.now(timezone.utc).isoformat(),
    }


# ── Fast history (simplified 3-factor for speed) ─────────────────────────────

def compute_history(days: int = 252) -> list[dict]:
    """
    Daily Blade Index scores for the past N trading days.
    Uses simplified 3-factor proxy (40% momentum, 40% VIX, 20% junk spread)
    to avoid 9 separate downloads per day.
    """
    spy = _dl_single("SPY", days + 200)
    vix = _dl_single("^VIX", days + 100)
    hj = _dl_multi(["HYG", "LQD"], days + 60)

    # Align on common trading dates
    base = spy.index.intersection(vix.index)
    has_junk = "HYG" in hj.columns and "LQD" in hj.columns
    if has_junk:
        base = base.intersection(hj.index)
    base = base.sort_values()[-days:]

    spy = spy.reindex(base)
    vix = vix.reindex(base)

    history = []
    for dt in base:
        try:
            # Momentum score
            spy_window = spy[:dt].tail(150)
            if len(spy_window) >= 125:
                ma125 = float(spy_window.rolling(125).mean().iloc[-1])
            else:
                ma125 = float(spy_window.mean())
            cur = float(spy_window.iloc[-1])
            m_pct = (cur - ma125) / ma125 * 100
            m_score = clamp(norm(m_pct, -15, 15))

            # VIX score (inverted)
            v = float(vix.loc[dt]) if dt in vix.index else 20.0
            v_score = clamp(norm(v, 40, 10))

            # Junk bond score
            if has_junk:
                hj_window = hj.loc[:dt].tail(35)
                if len(hj_window) >= 31:
                    r30_h = float(hj_window["HYG"].pct_change(30).iloc[-1]) * 100
                    r30_l = float(hj_window["LQD"].pct_change(30).iloc[-1]) * 100
                    diff = r30_h - r30_l
                    j_score = clamp(norm(diff, -5, 5))
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
