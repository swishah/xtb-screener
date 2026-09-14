#!/usr/bin/env python3
"""
Buduje dzienny snapshot uniwersum instrumentow do data/snapshots/.

Uzycie:
    python scripts/build_snapshot.py --out data/snapshots
    python scripts/build_snapshot.py --out data/snapshots --limit 20   # test

Uniwersum tickerow czytane jest z pierwszego znalezionego pliku:
    data/universe.csv   (kolumny: ticker, name, market  -- name i market opcjonalne)
    data/universe.txt   (jeden ticker na linie)
    data/tickers.txt

Jesli Twoj screener juz trzyma liste tickerow gdzie indziej, podmien
funkcje load_universe() -- reszta skryptu jest od niej niezalezna.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

# --------------------------------------------------------------------------
# Uniwersum
# --------------------------------------------------------------------------

UNIVERSE_CANDIDATES = [
    Path("data/universe.csv"),
    Path("data/universe.txt"),
    Path("data/tickers.txt"),
]

# Sufiks Yahoo -> nazwa rynku uzywana w raportach.
SUFFIX_TO_MARKET = {
    ".WA": "GPW",
    ".DE": "XETRA",
    ".F": "Frankfurt",
    ".PA": "Euronext Paris",
    ".AS": "Euronext Amsterdam",
    ".BR": "Euronext Brussels",
    ".LS": "Euronext Lisbon",
    ".L": "LSE",
    ".MC": "BME Madrid",
    ".MI": "Borsa Italiana",
    ".ST": "Nasdaq Stockholm",
    ".HE": "Nasdaq Helsinki",
    ".CO": "Nasdaq Copenhagen",
    ".OL": "Oslo Bors",
    ".SW": "SIX Swiss",
    ".VI": "Wiener Borse",
    ".IR": "Euronext Dublin",
}


def market_from_ticker(ticker: str) -> str:
    for suffix, market in SUFFIX_TO_MARKET.items():
        if ticker.upper().endswith(suffix):
            return market
    return "US"


def load_universe() -> list[dict]:
    """Zwraca liste dictow: {ticker, name, market}."""
    for path in UNIVERSE_CANDIDATES:
        if not path.exists():
            continue

        if path.suffix == ".csv":
            df = pd.read_csv(path)
            if "ticker" not in df.columns:
                sys.exit(f"{path}: brak kolumny 'ticker'")
            rows = []
            for _, r in df.iterrows():
                t = str(r["ticker"]).strip()
                if not t:
                    continue
                rows.append({
                    "ticker": t,
                    "name": str(r["name"]).strip() if "name" in df.columns and pd.notna(r.get("name")) else None,
                    "market": str(r["market"]).strip() if "market" in df.columns and pd.notna(r.get("market")) else market_from_ticker(t),
                })
            return rows

        tickers = [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
        return [{"ticker": t, "name": None, "market": market_from_ticker(t)} for t in tickers]

    sys.exit(
        "Nie znalazlem pliku z uniwersum. Utworz jeden z:\n  "
        + "\n  ".join(str(p) for p in UNIVERSE_CANDIDATES)
    )


# --------------------------------------------------------------------------
# Wskazniki
# --------------------------------------------------------------------------

def clean(value) -> float | None:
    """yfinance zwraca NaN, inf i numpy-typy. JSON tego nie lubi."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return clean(100 - (100 / (1 + rs)))


def macd_histogram(close: pd.Series) -> float | None:
    if len(close) < 35:
        return None
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return clean((macd_line - signal).iloc[-1])


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return clean(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def bollinger_position(close: pd.Series, period: int = 20, sigma: float = 2.0) -> float | None:
    """0.0 = dolna wstega, 1.0 = gorna. Poza zakresem gdy cena wybila."""
    if len(close) < period:
        return None
    mid = close.rolling(period).mean().iloc[-1]
    std = close.rolling(period).std().iloc[-1]
    if std == 0 or pd.isna(std):
        return None
    lower, upper = mid - sigma * std, mid + sigma * std
    return clean((close.iloc[-1] - lower) / (upper - lower))


def pct_change_over(close: pd.Series, days: int) -> float | None:
    """Zmiana procentowa wzgledem notowania sprzed `days` sesji."""
    if len(close) <= days:
        return None
    past = close.iloc[-(days + 1)]
    if past == 0 or pd.isna(past):
        return None
    return clean((close.iloc[-1] / past - 1) * 100)


# --------------------------------------------------------------------------
# Budowa rekordu
# --------------------------------------------------------------------------

def build_record(entry: dict, hist: pd.DataFrame, info: dict) -> dict:
    close = hist["Close"].dropna()
    if close.empty:
        return {}

    price = clean(close.iloc[-1])
    ath_price = clean(close.max())
    ath_date = close.idxmax()
    volume = hist["Volume"].dropna()

    drawdown = None
    if price and ath_price and ath_price > 0:
        drawdown = clean((price / ath_price - 1) * 100)

    return {
        "ticker": entry["ticker"],
        "name": entry.get("name") or info.get("longName") or info.get("shortName"),
        "market": entry.get("market"),
        "currency": info.get("currency"),

        "price": price,
        "change_1d_pct": pct_change_over(close, 1),
        "change_1m_pct": pct_change_over(close, 21),
        "change_1y_pct": pct_change_over(close, 252),
        "drawdown_from_ath_pct": drawdown,
        "ath_price": ath_price,
        "ath_date": ath_date.strftime("%Y-%m-%d") if hasattr(ath_date, "strftime") else None,

        "avg_volume_30d": clean(volume.tail(30).mean()) if not volume.empty else None,
        "atr_14": atr(hist["High"], hist["Low"], close),
        "rsi_14": rsi(close),
        "macd_hist": macd_histogram(close),
        "sma_50": clean(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None,
        "sma_200": clean(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None,
        "bb_position": bollinger_position(close),

        "market_cap": clean(info.get("marketCap")),
        "pe": clean(info.get("trailingPE")),
        "pb": clean(info.get("priceToBook")),
        "ev_ebitda": clean(info.get("enterpriseToEbitda")),
        "roe": clean(info.get("returnOnEquity") * 100) if info.get("returnOnEquity") is not None else None,
        "debt_to_equity": clean(info.get("debtToEquity")),
        "dividend_yield": clean(info.get("dividendYield")),

        # Autorskie scoringi ze screenera. Podepnij tu swoja funkcje liczaca,
        # jesli chcesz je miec w snapshocie -- null jest poprawna wartoscia.
        "score_technical": None,
        "score_fundamental": None,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/snapshots", help="katalog wyjsciowy")
    ap.add_argument("--limit", type=int, help="ogranicz liczbe tickerow (do testow)")
    ap.add_argument("--period", default="5y", help="okres historii dla ATH")
    ap.add_argument("--sleep", type=float, default=0.25, help="przerwa miedzy tickerami (s)")
    ap.add_argument("--keep-days", type=int, default=400, help="ile plikow dziennych zostawic")
    args = ap.parse_args()

    universe = load_universe()
    if args.limit:
        universe = universe[: args.limit]
    print(f"Uniwersum: {len(universe)} instrumentow", flush=True)

    instruments: list[dict] = []
    failed: list[str] = []

    for i, entry in enumerate(universe, 1):
        ticker = entry["ticker"]
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=args.period, auto_adjust=False)
            if hist.empty:
                failed.append(ticker)
            else:
                try:
                    info = tk.info or {}
                except Exception:
                    info = {}          # fundamenty potrafia sie wywalic same z siebie
                record = build_record(entry, hist, info)
                if record:
                    instruments.append(record)
                else:
                    failed.append(ticker)
        except Exception as exc:  # noqa: BLE001
            failed.append(ticker)
            print(f"  [blad] {ticker}: {exc}", flush=True)

        if i % 50 == 0:
            print(f"  {i}/{len(universe)}...", flush=True)
        time.sleep(args.sleep)

    if not instruments:
        print("Zero instrumentow pobranych -- nie nadpisuje latest.json.", file=sys.stderr)
        return 1

    snapshot = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe_size": len(universe),
        "fetched": len(instruments),
        "failed": failed,
        "source": "yfinance",
        "instruments": instruments,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    payload = json.dumps(snapshot, ensure_ascii=False, indent=1)
    (out_dir / f"{today}.json").write_text(payload, encoding="utf-8")
    (out_dir / "latest.json").write_text(payload, encoding="utf-8")

    # Rotacja plikow dziennych -- bez tego repo rosnie w nieskonczonosc.
    dailies = sorted(p for p in out_dir.glob("*.json") if p.stem[:1].isdigit())
    for old in dailies[: max(0, len(dailies) - args.keep_days)]:
        old.unlink()

    dates = sorted(p.stem for p in out_dir.glob("*.json") if p.stem[:1].isdigit())
    (out_dir / "index.json").write_text(
        json.dumps({"dates": dates, "latest": today}, indent=1), encoding="utf-8"
    )

    print(f"OK: {len(instruments)}/{len(universe)} pobranych, {len(failed)} nieudanych", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
