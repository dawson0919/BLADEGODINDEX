"""
🗡️ 刀神指標 — Calculator Engine
9 sub-indicators, all via yfinance (free, no API key required).
Compatible with yfinance >= 0.2.60 (MultiIndex columns).

v2: Percentile-rank normalization for all indicators.
    Scores now reach 0-20 (extreme fear) and 80-100 (extreme greed)
    in genuine extreme market conditions.
"""

import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Weights (must sum to 1.0) ────────────────────────────────────────────────
# Direct fear gauges (VIX, momentum, breadth, options) get higher weight.
# Proxy indicators (junk, safehaven, margin, cot, crypto) get lower weight.
WEIGHTS = {
    "momentum":  0.20,
    "vix":       0.20,
    "putcall":   0.15,
    "breadth":   0.15,
    "junk":      0.08,
    "safehaven": 0.08,
    "margin":    0.05,
    "cot":       0.05,
    "crypto":    0.04,
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


def _pct_rank_single(cur: float, history: np.ndarray) -> float:
    """Percentile rank of cur within history array → 0..100."""
    if len(history) < 20:
        return 50.0
    return float(np.sum(history <= cur) / len(history)) * 100.0


def _stretch(score: float, k: float = 0.10) -> float:
    """Sigmoid stretch that pushes scores away from 50 toward 0/100.
    k controls steepness: higher = more extreme spread."""
    z = (score - 50.0) * k
    return 100.0 / (1.0 + np.exp(-z))


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
    spy = _dl_single("SPY", 500)
    if len(spy) < 130:
        return 50.0, "SPY 資料不足"
    ma125 = spy.rolling(125).mean()
    pct_diff = ((spy - ma125) / ma125 * 100).dropna()
    cur_pct = float(pct_diff.iloc[-1])
    # Percentile rank over 1yr history
    hist = pct_diff.values[:-1]
    score = _pct_rank_single(cur_pct, hist[-252:])
    score = _stretch(score)
    cur = float(spy.iloc[-1])
    ma125_val = float(ma125.iloc[-1])
    return round(score, 1), f"SPY {cur:.2f} vs MA125 {ma125_val:.2f} ({cur_pct:+.1f}%)"


# ── 2. Volatility — VIX ────────────────────────────────────────────────────

def calc_vix():
    vix = _dl_single("^VIX", 500)
    if len(vix) < 55:
        return 50.0, "VIX 資料不足"
    cur = float(vix.iloc[-1])
    ma50_val = float(vix.rolling(50).mean().iloc[-1])
    # Inverted percentile: high VIX → high percentile → low score (fear)
    hist = vix.values[:-1]
    pct = _pct_rank_single(cur, hist[-252:])
    score = 100.0 - pct  # invert: high VIX = low score
    score = _stretch(score)
    return round(score, 1), f"VIX {cur:.2f}（50日均 {ma50_val:.2f}）"


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

        # Percentile rank (inverted: high ratio = fear = low score)
        hist = ratio_series.values[:-1]
        pct = _pct_rank_single(cur_ratio, hist[-252:])
        score = 100.0 - pct
        score = _stretch(score)

        iv_val = float(vix_aligned.iloc[-1])
        rv_val = float(rv20.iloc[-1])
        return round(score, 1), f"隱含/實現波動比 {cur_ratio:.2f} (VIX {iv_val:.1f} / RV {rv_val:.1f})"
    except Exception as exc:
        return 50.0, f"P/C 資料暫時不可用（{exc}）"


# ── 4. Junk Bond Demand ──────────────────────────────────────────────────────

def calc_junk():
    df = _dl_multi(["HYG", "LQD"], 500)
    if df.shape[0] < 35 or "HYG" not in df.columns or "LQD" not in df.columns:
        return 50.0, "HYG/LQD 資料不足"
    spread = (df["HYG"].pct_change(30) - df["LQD"].pct_change(30)).dropna() * 100
    if len(spread) < 30:
        return 50.0, "HYG/LQD 歷史不足"
    cur = float(spread.iloc[-1])
    hist = spread.values[:-1]
    score = _pct_rank_single(cur, hist[-252:])
    score = _stretch(score)
    return round(score, 1), f"HYG-LQD 30日報酬差：{cur:+.2f}%"


# ── 5. Safe Haven Demand ─────────────────────────────────────────────────────

def calc_safehaven():
    df = _dl_multi(["SPY", "TLT"], 500)
    if df.shape[0] < 25 or "SPY" not in df.columns or "TLT" not in df.columns:
        return 50.0, "SPY/TLT 資料不足"
    spread = (df["SPY"].pct_change(20) - df["TLT"].pct_change(20)).dropna() * 100
    if len(spread) < 30:
        return 50.0, "SPY/TLT 歷史不足"
    cur = float(spread.iloc[-1])
    hist = spread.values[:-1]
    score = _pct_rank_single(cur, hist[-252:])
    score = _stretch(score)
    return round(score, 1), f"SPY-TLT 20日報酬差：{cur:+.2f}%"


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
    # Breadth is already 0-100, apply stretch to push extremes
    raw_score = above / total * 100
    score = _stretch(raw_score)
    return round(score, 1), f"{above}/{total} 行業 ETF 高於 MA50"


# ── 7. Leverage proxy (RSP vs SPY equal-weight spread) ───────────────────────

def calc_margin():
    df = _dl_multi(["RSP", "SPY"], 500)
    if df.shape[0] < 65 or "RSP" not in df.columns or "SPY" not in df.columns:
        return 50.0, "RSP/SPY 資料不足"
    ratio = (df["RSP"] / df["SPY"]).dropna()
    ma60 = ratio.rolling(60).mean()
    deviation = ((ratio - ma60) / ma60 * 100).dropna()
    if len(deviation) < 30:
        return 50.0, "RSP/SPY 歷史不足"
    cur = float(deviation.iloc[-1])
    hist = deviation.values[:-1]
    score = _pct_rank_single(cur, hist[-252:])
    score = _stretch(score)
    return round(score, 1), f"RSP/SPY 離均差：{cur:+.2f}%"


# ── 8. Smart Money / COT proxy (SPY vs GLD) ─────────────────────────────────

def calc_cot():
    df = _dl_multi(["GLD", "SPY"], 500)
    if df.shape[0] < 25 or "GLD" not in df.columns or "SPY" not in df.columns:
        return 50.0, "GLD/SPY 資料不足"
    spread = (df["SPY"].pct_change(20) - df["GLD"].pct_change(20)).dropna() * 100
    if len(spread) < 30:
        return 50.0, "GLD/SPY 歷史不足"
    cur = float(spread.iloc[-1])
    hist = spread.values[:-1]
    score = _pct_rank_single(cur, hist[-252:])
    score = _stretch(score)
    return round(score, 1), f"SPY-GLD 20日報酬差：{cur:+.2f}%"


# ── 9. Crypto Contagion (BTC 30-day z-score) ────────────────────────────────

def calc_crypto():
    btc = _dl_single("BTC-USD", 500)
    if len(btc) < 100:
        return 50.0, "BTC 資料不足"
    ret30 = btc.pct_change(30).dropna()
    if len(ret30) < 60:
        return 50.0, "BTC 歷史不足"
    cur = float(ret30.iloc[-1])
    hist = ret30.values[:-1]
    score = _pct_rank_single(cur, hist[-252:])
    score = _stretch(score)
    z_window = min(252, len(ret30) - 1)
    mu = float(ret30.rolling(z_window).mean().iloc[-1])
    sigma = float(ret30.rolling(z_window).std().iloc[-1])
    z = (cur - mu) / sigma if sigma > 0 else 0.0
    return round(score, 1), f"BTC 30日 z-score：{z:+.2f}σ"


# ── Indicator registry ───────────────────────────────────────────────────────

INDICATORS = [
    ("momentum",  calc_momentum,  "📊", "股市動能",       "Market Momentum",   "20%"),
    ("vix",       calc_vix,       "⚡", "VIX 恐慌指數",   "Volatility (VIX)",  "20%"),
    ("putcall",   calc_putcall,   "🎲", "Put/Call 比率",  "Options Sentiment", "15%"),
    ("breadth",   calc_breadth,   "📐", "市場廣度",       "Market Breadth",    "15%"),
    ("junk",      calc_junk,      "💸", "垃圾債需求",     "Junk Bond Demand",  "8%"),
    ("safehaven", calc_safehaven, "🏦", "安全資產需求",   "Safe Haven Demand", "8%"),
    ("margin",    calc_margin,    "⚖️", "融資槓桿",       "Leverage Proxy",    "5%"),
    ("cot",       calc_cot,       "🏛️", "機構籌碼 (COT)", "Smart Money / COT", "5%"),
    ("crypto",    calc_crypto,    "₿",  "加密溢出",       "Crypto Contagion",  "4%"),
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
    """Calculate all 9 indicators and return composite Blade God Index score.

    Uses consensus adjustment: when 5+ indicators agree on extreme fear (<25)
    or extreme greed (>75), the composite is pulled further in that direction.
    This prevents a few noisy outliers from masking a clear market regime.
    """
    results = []
    weighted_sum = 0.0
    all_scores = []

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
        all_scores.append(score)

    raw_total = weighted_sum

    # ── Consensus adjustment ──────────────────────────────────────────────
    # When majority of indicators agree on fear/greed, adjust composite
    fear_count = sum(1 for s in all_scores if s < 25)
    greed_count = sum(1 for s in all_scores if s > 75)
    median_score = float(np.median(all_scores))

    if fear_count >= 5:
        # Strong fear consensus: blend toward median (which will be low)
        blend = 0.3 * (fear_count - 4) / 5  # 0.06 per extra fearful indicator
        blend = min(blend, 0.5)
        raw_total = raw_total * (1 - blend) + median_score * blend
    elif greed_count >= 5:
        blend = 0.3 * (greed_count - 4) / 5
        blend = min(blend, 0.5)
        raw_total = raw_total * (1 - blend) + median_score * blend

    total = round(clamp(raw_total), 1)
    return {
        "score":      total,
        "indicators": results,
        "updatedAt":  datetime.now(timezone.utc).isoformat(),
    }


# ── Percentile rank helper ────────────────────────────────────────────────────

def _pct_rank(series: pd.Series, lookback: int = 252) -> pd.Series:
    """Rolling percentile rank: 0 = worst in window, 100 = best in window."""
    def _rank_at(window):
        if len(window) < 20:
            return 50.0
        cur = window.iloc[-1]
        past = window.iloc[:-1]
        return float(np.sum(past <= cur) / len(past)) * 100.0
    return series.rolling(lookback, min_periods=20).apply(_rank_at, raw=False)


def _sigmoid_stretch(x: float, midpoint: float = 50.0, steepness: float = 0.08) -> float:
    """Sigmoid that stretches scores away from midpoint toward 0/100 extremes."""
    z = (x - midpoint) * steepness
    return 100.0 / (1.0 + np.exp(-z))


# ── Enhanced history (6-factor, percentile-ranked) ────────────────────────────

def compute_history(days: int = 252) -> list[dict]:
    """
    Daily Blade Index scores for the past N trading days.
    Uses 6 factors with percentile-rank normalization so that
    extreme market events (crashes, euphoria) map to 0-20 / 80-100.
    Downloads extra lookback for a stable 252-day ranking window.
    """
    lookback = days + 400  # extra data for rolling percentile window

    # Download all needed data in bulk
    spy = _dl_single("SPY", lookback)
    vix = _dl_single("^VIX", lookback)
    multi = _dl_multi(["HYG", "LQD", "TLT", "BTC-USD", "RSP"], lookback)

    # ── Build raw signal Series ──────────────────────────────────────────

    # 1. Momentum: SPY % above/below 125-day MA
    spy_ma125 = spy.rolling(125, min_periods=80).mean()
    momentum_raw = ((spy - spy_ma125) / spy_ma125 * 100).dropna()

    # 2. VIX level (inverted: high VIX = fear)
    vix_raw = vix.dropna()

    # 3. Junk bond demand: HYG - LQD 30-day return spread
    has_junk = "HYG" in multi.columns and "LQD" in multi.columns
    if has_junk:
        hyg_r30 = multi["HYG"].pct_change(30)
        lqd_r30 = multi["LQD"].pct_change(30)
        junk_raw = ((hyg_r30 - lqd_r30) * 100).dropna()
    else:
        junk_raw = pd.Series(dtype=float)

    # 4. Safe haven: SPY - TLT 20-day return spread
    has_tlt = "TLT" in multi.columns
    if has_tlt:
        spy_r20 = spy.pct_change(20)
        tlt_r20 = multi["TLT"].pct_change(20)
        safe_raw = ((spy_r20 - tlt_r20) * 100).dropna()
    else:
        safe_raw = pd.Series(dtype=float)

    # 5. Leverage proxy: RSP/SPY ratio deviation from 60-day mean
    has_rsp = "RSP" in multi.columns
    if has_rsp:
        ratio = (multi["RSP"] / spy).dropna()
        ratio_ma60 = ratio.rolling(60, min_periods=30).mean()
        leverage_raw = ((ratio - ratio_ma60) / ratio_ma60 * 100).dropna()
    else:
        leverage_raw = pd.Series(dtype=float)

    # 6. Crypto sentiment: BTC 30-day return z-score
    has_btc = "BTC-USD" in multi.columns
    if has_btc:
        btc = multi["BTC-USD"].dropna()
        btc_r30 = btc.pct_change(30).dropna()
        btc_mu = btc_r30.rolling(252, min_periods=60).mean()
        btc_sigma = btc_r30.rolling(252, min_periods=60).std()
        crypto_raw = ((btc_r30 - btc_mu) / btc_sigma.replace(0, np.nan)).dropna()
    else:
        crypto_raw = pd.Series(dtype=float)

    # ── Percentile-rank each signal over rolling 252-day window ──────────

    pct_window = 252

    momentum_pct = _pct_rank(momentum_raw, pct_window)
    # VIX inverted: high VIX → low rank → fear
    vix_pct = 100.0 - _pct_rank(vix_raw, pct_window)

    junk_pct = _pct_rank(junk_raw, pct_window) if len(junk_raw) > 30 else None
    safe_pct = _pct_rank(safe_raw, pct_window) if len(safe_raw) > 30 else None
    leverage_pct = _pct_rank(leverage_raw, pct_window) if len(leverage_raw) > 30 else None
    crypto_pct = _pct_rank(crypto_raw, pct_window) if len(crypto_raw) > 30 else None

    # ── Composite: weighted average of available percentile scores ───────
    # Weights: momentum 25%, VIX 25%, junk 15%, safe haven 15%, leverage 10%, crypto 10%

    base_dates = momentum_pct.dropna().index.intersection(vix_pct.dropna().index)
    base_dates = base_dates.sort_values()[-days:]

    history = []
    for dt in base_dates:
        try:
            scores = []
            weights = []

            m = float(momentum_pct.loc[dt]) if dt in momentum_pct.index else np.nan
            v = float(vix_pct.loc[dt]) if dt in vix_pct.index else np.nan

            if not np.isnan(m):
                scores.append(m); weights.append(0.25)
            if not np.isnan(v):
                scores.append(v); weights.append(0.25)

            if junk_pct is not None and dt in junk_pct.index:
                j = float(junk_pct.loc[dt])
                if not np.isnan(j):
                    scores.append(j); weights.append(0.15)

            if safe_pct is not None and dt in safe_pct.index:
                s = float(safe_pct.loc[dt])
                if not np.isnan(s):
                    scores.append(s); weights.append(0.15)

            if leverage_pct is not None and dt in leverage_pct.index:
                lv = float(leverage_pct.loc[dt])
                if not np.isnan(lv):
                    scores.append(lv); weights.append(0.10)

            if crypto_pct is not None and dt in crypto_pct.index:
                cr = float(crypto_pct.loc[dt])
                if not np.isnan(cr):
                    scores.append(cr); weights.append(0.10)

            if not scores:
                daily = 50.0
            else:
                # Normalize weights to sum to 1
                w_sum = sum(weights)
                daily = sum(s * w / w_sum for s, w in zip(scores, weights))
                # Apply sigmoid stretch to amplify extremes
                daily = _sigmoid_stretch(daily, midpoint=50.0, steepness=0.08)
                daily = round(clamp(daily), 1)

        except Exception:
            daily = 50.0

        history.append({
            "date":  dt.strftime("%Y-%m-%d"),
            "score": daily,
        })

    return history
