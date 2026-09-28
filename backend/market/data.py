"""Shared market data: universe, batched daily bars, live quotes and betas (Yahoo Finance).

Every agent that needs prices goes through here so Yahoo is hit with one batched download per
refresh instead of one request per agent per ticker.
"""
import datetime
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

logger = logging.getLogger("alphaforge.market")

NY = ZoneInfo("America/New_York")

# Liquid US large caps (S&P 100 members). A fixed list: the fund trades it forward in time,
# so there is no backtest survivorship issue, only a universe choice.
LARGE_CAPS: List[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "AVGO", "TSLA", "LLY",
    "JPM", "V", "UNH", "XOM", "MA", "JNJ", "PG", "HD", "COST", "ABBV",
    "WMT", "NFLX", "BAC", "CRM", "KO", "CVX", "MRK", "ORCL", "AMD", "PEP",
    "TMO", "ADBE", "LIN", "ACN", "MCD", "CSCO", "ABT", "WFC", "IBM", "GE",
    "DHR", "QCOM", "TXN", "INTU", "CAT", "AMGN", "PM", "VZ", "NOW", "ISRG",
    "CMCSA", "DIS", "GS", "NEE", "RTX", "SPGI", "PFE", "UNP", "T", "LOW",
    "AXP", "HON", "BKNG", "UBER", "BLK", "SYK", "MS", "C", "PLD", "COP",
    "LMT", "SCHW", "DE", "ELV", "TMUS", "MDT", "ADP", "AMT", "GILD", "SBUX",
    "BMY", "MO", "CB", "MMC", "UPS", "CVS", "SO", "DUK", "CL", "MDLZ",
    "INTC", "BA", "GD", "USB", "COF", "NKE", "TGT", "MU", "PYPL", "F",
]
SECTOR_ETFS: Dict[str, str] = {
    "XLK": "Technology", "XLF": "Financial Services", "XLV": "Healthcare", "XLE": "Energy",
    "XLI": "Industrials", "XLY": "Consumer Cyclical", "XLP": "Consumer Defensive", "XLU": "Utilities",
    "XLB": "Basic Materials", "XLRE": "Real Estate", "XLC": "Communication Services",
}
BENCHMARK = "SPY"
INVERSE_HEDGE = "SH"  # ProShares Short S&P 500: -1x daily, buyable in fractional size
MACRO = ["^VIX", "^VIX3M", "^IRX"]

# Regulatory fees on sells (what Alpaca and most US brokers pass through). Commission is $0.
SEC_FEE_RATE = 27.80 / 1_000_000       # $ per $ of sale proceeds
FINRA_TAF_PER_SHARE = 0.000166
FINRA_TAF_MAX = 8.30


def is_market_open(now: datetime.datetime = None) -> bool:
    """Regular NYSE session, Mon-Fri 9:30-16:00 New York time (exchange holidays not modelled)."""
    now = (now or datetime.datetime.now(datetime.UTC)).astimezone(NY)
    if now.weekday() >= 5:
        return False
    return datetime.time(9, 30) <= now.time() < datetime.time(16, 0)


def ny_today() -> datetime.date:
    return datetime.datetime.now(NY).date()


# ---------------------------------------------------------------------------
# Daily bars
# ---------------------------------------------------------------------------

_bars_lock = threading.Lock()
_bars_cache: Dict[str, pd.DataFrame] = {}
_bars_fetched_at: Dict[str, float] = {}
BARS_TTL_SEC = 15 * 60


def daily_closes(tickers: List[str], period: str = "2y") -> pd.DataFrame:
    """Adjusted daily closes (columns = tickers). During the session the last row is today's live bar.
    Tickers Yahoo can't price are simply absent from the frame."""
    tickers = sorted(set(tickers))
    now = time.time()
    with _bars_lock:
        stale = [t for t in tickers if now - _bars_fetched_at.get(t, 0) > BARS_TTL_SEC]
    if stale:
        df = yf.download(stale, period=period, interval="1d", auto_adjust=True,
                         group_by="ticker", threads=True, progress=False)
        with _bars_lock:
            for t in stale:
                try:
                    col = df[t]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
                except KeyError:
                    continue
                col = col.dropna()
                if len(col):
                    _bars_cache[t] = col
                    _bars_fetched_at[t] = now
    with _bars_lock:
        present = {t: _bars_cache[t] for t in tickers if t in _bars_cache}
    return pd.DataFrame(present).sort_index()


def beta(returns: pd.DataFrame, symbol: str, window: int = 120) -> Optional[float]:
    """OLS beta of ``symbol`` daily returns vs SPY over the last ``window`` days."""
    if symbol not in returns or BENCHMARK not in returns:
        return None
    pair = returns[[symbol, BENCHMARK]].dropna().tail(window)
    if len(pair) < 40:
        return None
    var = pair[BENCHMARK].var()
    return float(pair[symbol].cov(pair[BENCHMARK]) / var) if var > 0 else None


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    source: str                 # LIVE_QUOTE (real NBBO from Yahoo) or MODELED_SPREAD
    adv_dollars: Optional[float]
    exchange: Optional[str]
    quote_type: Optional[str]   # EQUITY, ETF, ...
    sector: Optional[str]
    short_pct_float: Optional[float]

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> float:
        return (self.ask - self.bid) / self.mid * 10_000 if self.mid > 0 else 0.0


_info_cache: Dict[str, tuple] = {}
INFO_TTL_SEC = 60


def _info(symbol: str) -> dict:
    hit = _info_cache.get(symbol)
    if hit and time.time() - hit[0] < INFO_TTL_SEC:
        return hit[1]
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as e:
        logger.warning(f"Yahoo info failed for {symbol}: {e}")
        info = {}
    _info_cache[symbol] = (time.time(), info)
    return info


def modeled_half_spread_bps(adv_dollars: Optional[float]) -> float:
    """Fallback when no live quote: half-spread shrinks with liquidity.
    ~1 bp for mega caps ($10B/day), ~6 bps at $100M/day, capped at 50 bps for illiquid names."""
    if not adv_dollars or adv_dollars <= 0:
        return 50.0
    return float(min(50.0, max(1.0, 2.0 * math.sqrt(1e9 / adv_dollars))))


def get_quote(symbol: str) -> Optional[Quote]:
    """Best available executable quote, or None if the symbol has no price at all."""
    info = _info(symbol)
    last = info.get("regularMarketPrice") or info.get("currentPrice")
    if not last:
        try:
            last = yf.Ticker(symbol).fast_info.get("last_price")
        except Exception:
            last = None
    if not last or last <= 0:
        return None
    last = float(last)

    avg_vol = info.get("averageDailyVolume10Day") or info.get("averageVolume")
    adv = float(avg_vol) * last if avg_vol else None
    bid, ask = info.get("bid"), info.get("ask")

    # Use the real quote only if it is sane: two-sided, not crossed, near the last trade, and not
    # wildly wider than this name normally trades (Yahoo sometimes shows stale or odd-lot quotes)
    max_spread_bps = max(25.0, 10 * 2 * modeled_half_spread_bps(adv))
    live = (bid and ask and bid > 0 and ask >= bid
            and (ask - bid) / ((ask + bid) / 2) * 10_000 <= max_spread_bps
            and abs((bid + ask) / 2 - last) / last < 0.02 and is_market_open())
    if live:
        source = "LIVE_QUOTE"
        bid, ask = float(bid), float(ask)
    else:
        half = modeled_half_spread_bps(adv) / 10_000
        bid, ask, source = last * (1 - half), last * (1 + half), "MODELED_SPREAD"

    spf = info.get("shortPercentOfFloat")
    return Quote(symbol=symbol, bid=bid, ask=ask, last=last, source=source, adv_dollars=adv,
                 exchange=info.get("exchange"), quote_type=info.get("quoteType"),
                 sector=info.get("sector") or SECTOR_ETFS.get(symbol),
                 short_pct_float=float(spf) if spf else None)


def sell_fees(notional: float, shares: float) -> float:
    """SEC Section 31 fee + FINRA TAF on a sale (both apply to long sells and short sales)."""
    sec = notional * SEC_FEE_RATE
    taf = min(FINRA_TAF_MAX, shares * FINRA_TAF_PER_SHARE)
    # Brokers round each fee up to the next cent
    return math.ceil(sec * 100) / 100 + math.ceil(taf * 100) / 100


def borrow_rate(q: Quote) -> float:
    """Annual stock-loan fee. General collateral is cheap; crowded shorts are 'hard to borrow'."""
    spf = q.short_pct_float or 0.0
    if spf > 0.30:
        return 0.20
    if spf > 0.15:
        return 0.05
    return 0.0025
