"""
Silnik analityczny — oparty na oryginalnym skrypcie użytkownika, przerobiony
na funkcje wielokrotnego użytku (zamiast liniowego skryptu) tak, żeby mogły
z niego korzystać: cronowy scan dzienny (scripts/run_daily_scan.py) i appka
Streamlit (do przeliczeń "na żywo" / backtestu z historii cen).
"""
from __future__ import annotations

import io
import random
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

HISTORICAL_PERIOD = "10y"
DELAY_MIN, DELAY_MAX = 0.4, 0.9

if hasattr(yf, "config"):
    yf.config.network.retries = 3
    yf.config.debug.hide_exceptions = True


def get_sp500_map() -> dict[str, str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        table = pd.read_html(io.StringIO(response.text))[0]
        table["Symbol"] = table["Symbol"].str.replace(".", "-", regex=False)
        return dict(zip(table["Symbol"], table["Security"]))
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nie udało się pobrać S&P 500 z Wikipedii ({e}), używam skróconej listy.")
        return {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corp."}


def get_sp400_map() -> dict[str, str]:
    """S&P 400 MidCap — szerszy rynek USA poza samym S&P 500 (spółki średniej wielkości)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        table = pd.read_html(io.StringIO(response.text))[0]
        symbol_col = "Symbol" if "Symbol" in table.columns else "Ticker symbol"
        name_col = "Security" if "Security" in table.columns else "Company"
        table[symbol_col] = table[symbol_col].astype(str).str.replace(".", "-", regex=False)
        return dict(zip(table[symbol_col], table[name_col]))
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nie udało się pobrać S&P 400 z Wikipedii ({e}), pomijam tę grupę.")
        return {}


def run_monte_carlo(data: pd.DataFrame) -> tuple[float, float]:
    returns = data["Close"].pct_change().dropna()
    if len(returns) < 30:
        return 0, 0
    mu, sigma = returns.mean(), returns.std()
    last = float(data["Close"].iloc[-1])
    sims = [last * (1 + np.random.normal(mu, sigma, 30)).prod() for _ in range(30)]
    med = np.median(sims)
    return round(med, 2), round(((med - last) / last) * 100, 1)


def get_current_price(tk: "yf.Ticker", df: pd.DataFrame) -> float | None:
    try:
        fi = tk.fast_info
        p = fi.get("lastPrice") or fi.get("last_price")
        if p and not pd.isna(p):
            return float(p)
    except Exception:  # noqa: BLE001
        pass
    try:
        info = tk.info or {}
        for key in ("currentPrice", "regularMarketPrice", "previousClose"):
            p = info.get(key)
            if p and not pd.isna(p):
                return float(p)
    except Exception:  # noqa: BLE001
        pass
    try:
        closes = df["Close"].dropna()
        if not closes.empty:
            return float(closes.iloc[-1])
    except Exception:  # noqa: BLE001
        pass
    return None


def _safe_get(info: dict, key: str, is_pct: bool = False):
    val = info.get(key)
    if val is None or pd.isna(val):
        return None
    return round(val * 100, 2) if is_pct else round(val, 2)


def compute_indicators(df: pd.DataFrame, price: float, as_of: pd.Timestamp | None = None) -> dict:
    """
    Liczy wskaźniki techniczne z historii OHLC do momentu `as_of` (włącznie).
    Gdy as_of=None -> ostatni dostępny dzień. To jest podstawa "szybkiego"
    backtestu: wystarczy obciąć df do danej daty i przeliczyć od nowa.
    """
    d = df if as_of is None else df.loc[:as_of]
    if len(d) < 30:
        return {}

    ath = float(d["High"].max())
    atl = float(d["Low"].min())
    pct_from_ath = round(((price - ath) / ath) * 100, 1)

    delta = d["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi = float((100 - (100 / (1 + gain / loss))).iloc[-1])

    macd_line = d["Close"].ewm(span=12).mean() - d["Close"].ewm(span=26).mean()
    macd_signal = macd_line.ewm(span=9).mean()

    sma20 = float(d["Close"].rolling(20).mean().iloc[-1])
    sma50 = float(d["Close"].rolling(50).mean().iloc[-1]) if len(d) >= 50 else None
    sma100 = float(d["Close"].rolling(100).mean().iloc[-1]) if len(d) >= 100 else None
    sma200 = float(d["Close"].rolling(200).mean().iloc[-1]) if len(d) >= 200 else None

    std20 = d["Close"].rolling(20).std().iloc[-1]
    b_low, b_up = sma20 - (std20 * 2), sma20 + (std20 * 2)
    b_pct = float((price - b_low) / (b_up - b_low)) if (b_up - b_low) != 0 else 0.5

    v_rat = float(d["Volume"].iloc[-1] / d["Volume"].rolling(20).mean().iloc[-1])
    p_low = d["Low"].shift(1).rolling(20).min().iloc[-1]
    smc = "💎 SMC BUY" if (d["Low"].iloc[-1] < p_low and price > p_low and v_rat > 1.2) else "Neutralny"
    mc_target, mc_pct = run_monte_carlo(d)

    return dict(
        ATH=round(ath, 2), ATL=round(atl, 2), pct_from_ath=pct_from_ath,
        RSI=round(rsi, 1), MACD=round(float(macd_line.iloc[-1]), 2),
        macd_bullish=bool(macd_line.iloc[-1] > macd_signal.iloc[-1]),
        SMA20=round(sma20, 2) if sma20 else None,
        SMA50=round(sma50, 2) if sma50 else None,
        SMA100=round(sma100, 2) if sma100 else None,
        SMA200=round(sma200, 2) if sma200 else None,
        bollinger_pct=round(b_pct, 2), volume_ratio=round(v_rat, 2),
        smc=smc, mc_target=mc_target, mc_pct=mc_pct,
    )


def score_row(price: float, ind: dict, fund: dict) -> int:
    """Suma sygnałów kupna — sama technika + potwierdzenie fundamentalne."""
    sma200 = ind.get("SMA200")
    signals = [
        ind.get("RSI") is not None and ind["RSI"] < 35,
        ind.get("macd_bullish"),
        ind.get("SMA20") and price > ind["SMA20"],
        ind.get("SMA50") and price > ind["SMA50"],
        ind.get("bollinger_pct") is not None and ind["bollinger_pct"] < 0.15,
        ind.get("volume_ratio") is not None and ind["volume_ratio"] > 1.3,
        ind.get("smc") == "💎 SMC BUY",
        ind.get("mc_pct") is not None and ind["mc_pct"] > 3,
        ind.get("pct_from_ath") is not None and ind["pct_from_ath"] < -15,
    ]
    return int(sum(1 for s in signals if s))


def deep_value_score(row: dict) -> int:
    """
    Strategia "Deep Value": duży spadek od ATH, ale biznes wciąż zdrowy.
    Karze spadek od ATH mocniej, ale wymaga potwierdzenia jakości biznesu
    (ROE, marża, wzrost EPS, dług), żeby odsiać "spadające noże".
    """
    pts = 0
    ath = row.get("pct_from_ath")
    if ath is not None:
        if ath < -50:
            pts += 3
        elif ath < -30:
            pts += 2
        elif ath < -15:
            pts += 1
    roe = row.get("ROE (%)")
    if isinstance(roe, (int, float)) and roe > 12:
        pts += 2
    op_margin = row.get("Marża Operac. (%)")
    if isinstance(op_margin, (int, float)) and op_margin > 10:
        pts += 1
    eps_growth = row.get("Wzrost EPS (%)")
    if isinstance(eps_growth, (int, float)) and eps_growth > 0:
        pts += 2
    debt_eq = row.get("Dług/Kapitał")
    if isinstance(debt_eq, (int, float)) and debt_eq < 100:
        pts += 1
    rsi = row.get("RSI")
    if rsi is not None and rsi < 40:
        pts += 1
    return pts


def momentum_score(row: dict) -> int:
    """
    Strategia "Momentum": spółka w silnym, potwierdzonym trendzie wzrostowym
    (cena nad wszystkimi średnimi, MACD byczy, rosnący wolumen, blisko ATH,
    RSI w zdrowej strefie wzrostu — nie wykupiona powyżej 70).
    """
    pts = 0
    price = row.get("Cena")
    if isinstance(price, (int, float)):
        for key in ("SMA20", "SMA50", "SMA100", "SMA200"):
            sma = row.get(key)
            if isinstance(sma, (int, float)) and price > sma:
                pts += 1
    if row.get("macd_bullish"):
        pts += 1
    rsi = row.get("RSI")
    if isinstance(rsi, (int, float)) and 50 <= rsi <= 70:
        pts += 1
    v_rat = row.get("volume_ratio")
    if isinstance(v_rat, (int, float)) and v_rat > 1.2:
        pts += 1
    ath = row.get("pct_from_ath")
    if isinstance(ath, (int, float)) and ath > -10:
        pts += 1
    return pts


def dividend_score(row: dict) -> int:
    """
    Strategia "Dywidendowa": solidna, rosnąca stopa dywidendy przy zdrowych
    fundamentach i historii nieprzerwanych wypłat (3 lata z rzędu).
    """
    pts = 0
    yld = row.get("Stopa Dyw. (%)")
    if isinstance(yld, (int, float)):
        if yld > 3:
            pts += 1
        if yld > 5:
            pts += 1
    pe = row.get("C/Z (P/E)")
    if isinstance(pe, (int, float)) and 0 < pe < 20:
        pts += 1
    roe = row.get("ROE (%)")
    if isinstance(roe, (int, float)) and roe > 10:
        pts += 1
    debt_eq = row.get("Dług/Kapitał")
    if isinstance(debt_eq, (int, float)) and debt_eq < 100:
        pts += 1
    if row.get("Lata z dywidendą (3Y)", 0) >= 3:
        pts += 2
    return pts


def dividend_opportunity_score(row: dict) -> int:
    """
    Strategia "Dywidenda-okazja (sezon dywidendowy)": szuka spółek, które
    regularnie płacą dywidendę, ZAPŁACIŁY w poprzednim roku, ale JESZCZE NIE
    zapłaciły w bieżącym — czyli wypłata dopiero przed nimi. Przy niskiej
    dotychczasowej zmianie ceny (rynek jeszcze "nie podbił" kursu przed
    sezonem) i zdrowych fundamentach to typowa "tania spółka przed sezonem
    dywidendowym". Wymaga potwierdzenia bezpieczeństwa (payout ratio,
    przychody, marża), żeby odróżnić okazję od pułapki dywidendowej.
    """
    pts = 0
    yld = row.get("Stopa Dyw. (%)")
    if isinstance(yld, (int, float)):
        if yld > 4:
            pts += 1
        if yld > 6:
            pts += 1
    chg = row.get("Zmiana ceny (1Y%)")
    if isinstance(chg, (int, float)):
        if chg < 10:
            pts += 1
        if chg < 0:
            pts += 1
    payout = row.get("Payout ratio (%)")
    if isinstance(payout, (int, float)) and 0 < payout < 80:
        pts += 2
    rev_growth = row.get("Wzrost przychodów (%)")
    if isinstance(rev_growth, (int, float)) and rev_growth > 0:
        pts += 1
    profit_margin = row.get("Marża netto (%)")
    if isinstance(profit_margin, (int, float)) and profit_margin > 5:
        pts += 1
    if row.get("Lata z dywidendą (3Y)", 0) >= 3:
        pts += 1

    # Sezon dywidendowy: kluczowa część tej strategii.
    if row.get("Dyw. w poprzednim roku") == "Tak":
        pts += 1
    if row.get("Dyw. w tym roku") == "Nie":
        pts += 2  # wypłata jeszcze przed nami w tym roku — sedno strategii
    if row.get("Przyszła dywidenda", "BRAK") != "BRAK":
        pts += 1  # wiemy dokładnie, kiedy nastąpi wypłata
    return pts


STRATEGIES = {
    "Deep Value (spadki od ATH)": ("Score: Deep Value", deep_value_score),
    "Momentum": ("Score: Momentum", momentum_score),
    "Dywidendowa": ("Score: Dywidendowa", dividend_score),
    "Dywidenda-okazja (sezon dywidendowy)": ("Score: Dywidenda-Okazja", dividend_opportunity_score),
}


_SUFFIX_MARKET = {
    ".WA": "Polska", ".DE": "Niemcy", ".PA": "Francja", ".AS": "Holandia (Euronext)",
    ".L": "UK", ".MC": "Hiszpania", ".ST": "Szwecja", ".OL": "Norwegia", ".SW": "Szwajcaria",
    ".MI": "Włochy", ".VI": "Austria", ".LS": "Portugalia",
}


def infer_market(ticker: str) -> str:
    """Rozpoznaje rynek/kraj po sufiksie tickera (fallback, gdy nie podano jawnie)."""
    for suffix, market in _SUFFIX_MARKET.items():
        if ticker.endswith(suffix):
            return market
    return "USA"


_SUFFIX_CURRENCY = {
    ".WA": "PLN", ".DE": "EUR", ".PA": "EUR", ".AS": "EUR", ".MC": "EUR",
    ".LS": "EUR", ".MI": "EUR", ".VI": "EUR", ".L": "GBP", ".ST": "SEK",
    ".OL": "NOK", ".SW": "CHF",
}


def infer_currency(ticker: str) -> str:
    """Rozpoznaje walutę notowania po sufiksie tickera (fallback, gdy Yahoo nie poda jej w `info`)."""
    for suffix, currency in _SUFFIX_CURRENCY.items():
        if ticker.endswith(suffix):
            return currency
    return "USD"


def get_fx_rates(currencies: set[str], target: str = "PLN") -> dict[str, float]:
    """
    Kursy walut do wspólnej waluty docelowej (domyślnie PLN), pobierane na
    żywo z Yahoo Finance (pary XXXTARGET=X). Nie jest zapisywane w migawkach —
    liczone na bieżąco w appce, żeby nie zwalniać codziennego skanu.
    """
    rates = {target: 1.0}
    for cur in currencies:
        if not cur or cur in (target, "BRAK"):
            continue
        try:
            tk = yf.Ticker(f"{cur}{target}=X")
            hist = tk.history(period="5d")
            if not hist.empty:
                rates[cur] = float(hist["Close"].dropna().iloc[-1])
        except Exception:  # noqa: BLE001
            continue
    return rates


def get_next_earnings_date(ticker: str) -> str | None:
    """
    Data najbliższej publikacji wyników finansowych. Próbuje dwóch metod
    (yfinance zmieniał to API między wersjami) — zwraca None, gdy się nie uda,
    zamiast wywalać cały widok.
    """
    tk = yf.Ticker(ticker)
    try:
        cal = tk.calendar
        dates = None
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
        elif cal is not None and hasattr(cal, "loc") and "Earnings Date" in getattr(cal, "index", []):
            dates = cal.loc["Earnings Date"].tolist()
        if dates:
            today = pd.Timestamp.now().normalize()
            future = [pd.Timestamp(d) for d in dates if d and pd.Timestamp(d) >= today]
            if future:
                return min(future).date().isoformat()
    except Exception:  # noqa: BLE001
        pass
    try:
        edf = tk.get_earnings_dates(limit=8)
        if edf is not None and not edf.empty:
            now = pd.Timestamp.now(tz=edf.index.tz)
            future = edf[edf.index >= now]
            if not future.empty:
                return future.index.min().date().isoformat()
    except Exception:  # noqa: BLE001
        pass
    return None


def red_flags(row: dict) -> list[str]:
    """
    Automatyczne ostrzeżenia liczone na już zebranych danych spółki — szybka
    kontrola jakości bez ręcznego przeglądania każdej kolumny osobno.
    🔴 = poważne ostrzeżenie, 🟡 = warto sprawdzić dokładniej.
    """
    flags: list[str] = []

    pm = row.get("Marża netto (%)")
    if isinstance(pm, (int, float)) and pm < 0:
        flags.append("🔴 Ujemna marża netto (spółka traci pieniądze)")

    pe = row.get("C/Z (P/E)")
    if isinstance(pe, (int, float)) and pe < 0:
        flags.append("🔴 Ujemne C/Z (strata na akcję)")

    debt = row.get("Dług/Kapitał")
    if isinstance(debt, (int, float)) and debt > 150:
        flags.append("🔴 Bardzo wysoki dług/kapitał (>150%)")

    payout = row.get("Payout ratio (%)")
    if isinstance(payout, (int, float)) and payout > 100:
        flags.append("🔴 Payout ratio >100% (wypłaca więcej niż zarabia)")

    price, sma200, sma50 = row.get("Cena"), row.get("SMA200"), row.get("SMA50")
    if all(isinstance(v, (int, float)) for v in (price, sma200, sma50)) and price < sma200 and price < sma50:
        flags.append("🔴 Cena poniżej SMA50 i SMA200 (silny trend spadkowy)")

    rev_growth = row.get("Wzrost przychodów (%)")
    if isinstance(rev_growth, (int, float)) and rev_growth < -5:
        flags.append("🟡 Malejące przychody")

    eps_growth = row.get("Wzrost EPS (%)")
    if isinstance(eps_growth, (int, float)) and eps_growth < -10:
        flags.append("🟡 Malejący zysk na akcję")

    op_margin = row.get("Marża Operac. (%)")
    if isinstance(op_margin, (int, float)) and op_margin < 5:
        flags.append("🟡 Niska marża operacyjna (<5%)")

    ath = row.get("pct_from_ath")
    if isinstance(ath, (int, float)) and ath < -70:
        flags.append("🟡 Ekstremalny spadek od ATH (>-70%) — sprawdź, czy to nie dystres")

    rsi = row.get("RSI")
    if isinstance(rsi, (int, float)) and rsi > 75:
        flags.append("🟡 RSI mocno wykupiony (>75)")

    return flags


def _to_timestamp(val) -> pd.Timestamp | None:
    """Bezpiecznie zamienia epoch (sekundy) albo string/datetime na pd.Timestamp."""
    if val is None:
        return None
    try:
        return pd.Timestamp(val, unit="s")
    except Exception:  # noqa: BLE001
        try:
            return pd.Timestamp(val)
        except Exception:  # noqa: BLE001
            return None


def analyze_ticker(ticker: str, full_name: str, kind: str = "stock") -> dict | None:
    """Analizuje jeden ticker "na żywo" (dzisiejsze dane). Zwraca None, gdy brak danych."""
    tk = yf.Ticker(ticker)
    df = tk.history(period=HISTORICAL_PERIOD, interval="1d", auto_adjust=True, actions=True)
    if df.empty or len(df) < 200:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    price = get_current_price(tk, df)
    if price is None:
        return None

    try:
        info = tk.info or {}
    except Exception:  # noqa: BLE001
        info = {}

    currency = info.get("currency") or infer_currency(ticker)
    sector = info.get("sector") or "Nieznany"
    industry = info.get("industry") or "Nieznana"

    fund = {
        "C/Z (P/E)": _safe_get(info, "trailingPE") or "BRAK",
        "Forward C/Z": _safe_get(info, "forwardPE") or "BRAK",
        "C/WK (P/B)": _safe_get(info, "priceToBook") or "BRAK",
        "ROE (%)": _safe_get(info, "returnOnEquity", is_pct=True) or "BRAK",
        "Marża Operac. (%)": _safe_get(info, "operatingMargins", is_pct=True) or "BRAK",
        "Marża netto (%)": _safe_get(info, "profitMargins", is_pct=True) or "BRAK",
        "Marża brutto (%)": _safe_get(info, "grossMargins", is_pct=True) or "BRAK",
        "Dług/Kapitał": _safe_get(info, "debtToEquity") or "BRAK",
        "Wzrost EPS (%)": _safe_get(info, "earningsGrowth", is_pct=True) or "BRAK",
        "Wzrost przychodów (%)": _safe_get(info, "revenueGrowth", is_pct=True) or "BRAK",
        "Payout ratio (%)": _safe_get(info, "payoutRatio", is_pct=True) or "BRAK",
    }

    # Dodatkowe dane rynkowe — wszystkie za darmo z już pobranego `info`,
    # bez dodatkowych zapytań do API.
    market_cap = info.get("marketCap")
    market_cap_b = round(market_cap / 1e9, 2) if isinstance(market_cap, (int, float)) else "BRAK"

    _REC_MAP = {
        "strong_buy": "Silne kupuj", "buy": "Kupuj", "hold": "Trzymaj",
        "sell": "Sprzedaj", "strong_sell": "Silne sprzedaj", "none": "Brak",
    }
    rec_raw = info.get("recommendationKey")
    recommendation = _REC_MAP.get(rec_raw, "BRAK")

    analyst_count = info.get("numberOfAnalystOpinions")
    analyst_count = int(analyst_count) if isinstance(analyst_count, (int, float)) else "BRAK"

    extra_market_data = {
        "Kapitalizacja (mld)": market_cap_b,
        "Beta": _safe_get(info, "beta") or "BRAK",
        "52-tyg. maksimum": _safe_get(info, "fiftyTwoWeekHigh") or "BRAK",
        "52-tyg. minimum": _safe_get(info, "fiftyTwoWeekLow") or "BRAK",
        "Cena docelowa (analitycy)": _safe_get(info, "targetMeanPrice") or "BRAK",
        "Rekomendacja analityków": recommendation,
        "Liczba analityków": analyst_count,
        "% udziałów instytucji": _safe_get(info, "heldPercentInstitutions", is_pct=True) or "BRAK",
    }

    # Zmiana ceny w ostatnim roku — kluczowe dla strategii "wysoka dywidenda,
    # cena jeszcze nie wzrosła": łapie spółki, których rynek jeszcze nie
    # "przecenił w górę" mimo atrakcyjnej stopy dywidendy.
    price_change_1y = None
    if len(df) > 5:
        idx_1y = -252 if len(df) > 252 else 0
        price_1y_ago = float(df["Close"].iloc[idx_1y])
        if price_1y_ago > 0:
            price_change_1y = round(((price - price_1y_ago) / price_1y_ago) * 100, 1)

    curr_y = datetime.now().year
    div_yield = "BRAK"
    div_years_paid = 0
    last_div_date = "BRAK"
    div_paid_prev_year = "Nie"
    div_paid_this_year = "Nie"
    if "Dividends" in df.columns:
        divs = df["Dividends"]
        nonzero_divs = divs[divs > 0]
        if not nonzero_divs.empty:
            last_div_date = nonzero_divs.index.max().date().isoformat()
        if not divs.empty and divs.sum() > 0:
            by_year = divs.groupby(divs.index.year).sum()
            last_div = round(float(by_year.get(curr_y - 1, 0)), 2)
            if last_div > 0 and price > 0:
                div_yield = round((last_div / price) * 100, 2)
            div_years_paid = sum(
                1 for y in (curr_y - 1, curr_y - 2, curr_y - 3) if by_year.get(y, 0) > 0
            )
            div_paid_prev_year = "Tak" if by_year.get(curr_y - 1, 0) > 0 else "Nie"
            div_paid_this_year = "Tak" if by_year.get(curr_y, 0) > 0 else "Nie"

    # Najbliższa (przyszła) dywidenda — Yahoo bywa niekonsekwentne: pola te
    # czasem opisują OSTATNIĄ ex-dividend date, nie przyszłą, więc uznajemy
    # datę za "przyszłą" tylko gdy faktycznie wypada od dziś wzwyż.
    today = pd.Timestamp.now().normalize()
    next_div_date = "BRAK"
    for key in ("dividendDate", "exDividendDate"):
        resolved = _to_timestamp(info.get(key))
        if resolved is not None and resolved.normalize() >= today:
            next_div_date = resolved.date().isoformat()
            break

    ind = compute_indicators(df, price)
    if not ind:
        return None

    row = {
        "Ticker": ticker, "Nazwa": full_name, "Typ": kind, "Cena": round(price, 2),
        "Waluta": currency, "Zmiana ceny (1Y%)": price_change_1y,
        "Sektor": sector, "Branża": industry,
        "Stopa Dyw. (%)": div_yield, "Lata z dywidendą (3Y)": div_years_paid,
        "Poprzednia dywidenda": last_div_date, "Przyszła dywidenda": next_div_date,
        "Dyw. w poprzednim roku": div_paid_prev_year, "Dyw. w tym roku": div_paid_this_year,
        **fund, **extra_market_data, **ind,
        "Buy Score": score_row(price, ind, fund),
    }
    for _, (score_col, score_fn) in STRATEGIES.items():
        row[score_col] = score_fn(row)

    flags = red_flags(row)
    row["Liczba flag"] = len(flags)
    row["Czerwone flagi"] = "; ".join(flags) if flags else "Brak"
    return row


def analyze_group(
    ticker_map: dict[str, str], kind: str = "stock", label: str = "",
    market_override: str | None = None,
) -> list[dict]:
    results, skipped = [], []
    for t, name in ticker_map.items():
        try:
            row = analyze_ticker(t, name, kind=kind)
            if row is None:
                skipped.append(t)
            else:
                row["Rynek"] = market_override or infer_market(t)
                results.append(row)
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{t} ({type(e).__name__})")
        finally:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    if skipped:
        print(f"⚠️ {label}: pominięto {len(skipped)}/{len(ticker_map)}: {skipped[:10]}")
    return results


def price_history_for_backtest(ticker: str) -> pd.DataFrame:
    """Pobiera historię cen jednej spółki — do przeliczania wskaźników wstecz."""
    tk = yf.Ticker(ticker)
    df = tk.history(period=HISTORICAL_PERIOD, interval="1d", auto_adjust=True, actions=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def get_ticker_news(ticker: str, limit: int = 6) -> list[dict]:
    """
    Najświeższe nagłówki dla spółki z Yahoo Finance. Format odpowiedzi yfinance
    zmieniał się między wersjami (płaskie pola vs zagnieżdżone pod "content"),
    więc próbujemy obu wariantów. Zwraca listę słowników title/publisher/link/date
    (posortowaną od najnowszych), albo pustą listę, gdy się nie uda.
    """
    try:
        tk = yf.Ticker(ticker)
        raw_news = tk.news or []
    except Exception:  # noqa: BLE001
        return []

    results: list[dict] = []
    for item in raw_news[:limit]:
        content = item.get("content") if isinstance(item.get("content"), dict) else None
        source = content or item

        title = source.get("title")
        if not title:
            continue

        publisher = None
        provider = source.get("provider")
        if isinstance(provider, dict):
            publisher = provider.get("displayName")
        publisher = publisher or item.get("publisher") or "Nieznane źródło"

        link = None
        canonical = source.get("canonicalUrl")
        if isinstance(canonical, dict):
            link = canonical.get("url")
        link = link or item.get("link")

        ts = source.get("pubDate") or item.get("providerPublishTime")
        date_str = None
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    date_str = pd.Timestamp(ts, unit="s").strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M")
            except Exception:  # noqa: BLE001
                date_str = None

        results.append({"title": title, "publisher": publisher, "link": link, "date": date_str})
    return results


def backtest_strategy(df_all: pd.DataFrame, score_col: str, top_n: int, hold_snapshots: int) -> pd.DataFrame:
    """
    Backtest na bazie zapisanych migawek: dla każdego dnia skanu bierze TOP N
    spółek wg score_col, sprawdza ich cenę `hold_snapshots` migawek później
    (czyli "co by było, gdyby kupić dziś i sprzedać po K skanach") i liczy
    średni zwrot oraz win rate dla tego okna. Zwraca jeden wiersz na okno.
    """
    if df_all.empty or score_col not in df_all.columns:
        return pd.DataFrame()

    stocks = df_all[df_all["Typ"] == "stock"]
    dates = sorted(stocks["scan_date"].unique())
    if len(dates) <= hold_snapshots:
        return pd.DataFrame()

    results = []
    for i in range(len(dates) - hold_snapshots):
        entry_date, exit_date = dates[i], dates[i + hold_snapshots]
        entry_df = stocks[stocks["scan_date"] == entry_date].dropna(subset=[score_col])
        if entry_df.empty:
            continue
        picks = entry_df.sort_values(score_col, ascending=False).head(top_n)
        exit_prices = stocks[stocks["scan_date"] == exit_date][["Ticker", "Cena"]]
        merged = picks.merge(exit_prices, on="Ticker", how="inner", suffixes=("", "_exit"))
        if merged.empty:
            continue
        merged["Zwrot %"] = ((merged["Cena_exit"] - merged["Cena"]) / merged["Cena"]) * 100
        results.append({
            "Data wejścia": entry_date, "Data wyjścia": exit_date,
            "Śr. zwrot %": round(float(merged["Zwrot %"].mean()), 2),
            "Win rate %": round(float((merged["Zwrot %"] > 0).mean() * 100), 1),
            "Liczba spółek": len(merged),
        })
    return pd.DataFrame(results)
