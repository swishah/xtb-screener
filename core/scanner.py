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
from urllib.parse import quote

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


def piotroski_lite_score(row: dict) -> int:
    """
    Uproszczony, zaadaptowany F-Score Piotroskiego. UWAGA: prawdziwy Piotroski
    F-Score (9 pkt) porównuje wskaźniki ROK DO ROKU (np. czy dźwignia spadła,
    czy płynność wzrosła) na bazie pełnych sprawozdań finansowych. Pobieranie
    tego dla ~1300+ tickerów podczas codziennego skanu wymagałoby 3 dodatkowych
    zapytań API na spółkę i znacząco wydłużyłoby skan, więc świadomie
    rezygnujemy z tego na rzecz wersji opartej WYŁĄCZNIE na danych z bieżącego
    stanu (już pobieranych) — sprawdza jakość i rentowność biznesu punktowo,
    nie trend. Traktuj jako 'jakość fundamentalna', nie dosłowny F-Score.
    """
    pts = 0
    roa = row.get("ROA (%)")
    if isinstance(roa, (int, float)) and roa > 0:
        pts += 1
    cfo = row.get("Przepływy operacyjne (mln)")
    if isinstance(cfo, (int, float)) and cfo > 0:
        pts += 1
    roe = row.get("ROE (%)")
    if isinstance(roe, (int, float)) and roe > 0:
        pts += 1
    net_margin = row.get("Marża netto (%)")
    if isinstance(net_margin, (int, float)) and net_margin > 0:
        pts += 1
    eps_growth = row.get("Wzrost EPS (%)")
    if isinstance(eps_growth, (int, float)) and eps_growth > 0:
        pts += 1
    rev_growth = row.get("Wzrost przychodów (%)")
    if isinstance(rev_growth, (int, float)) and rev_growth > 0:
        pts += 1
    debt = row.get("Dług/Kapitał")
    if isinstance(debt, (int, float)) and debt < 100:
        pts += 1
    gross_margin = row.get("Marża brutto (%)")
    if isinstance(gross_margin, (int, float)) and gross_margin > 20:
        pts += 1
    return pts


STRATEGIES = {
    "Deep Value (spadki od ATH)": ("Score: Deep Value", deep_value_score),
    "Momentum": ("Score: Momentum", momentum_score),
    "Dywidendowa": ("Score: Dywidendowa", dividend_score),
    "Dywidenda-okazja (sezon dywidendowy)": ("Score: Dywidenda-Okazja", dividend_opportunity_score),
    "Jakość fundamentalna (F-Score uproszczony)": ("Score: F-Score Lite", piotroski_lite_score),
}

# Maksymalne teoretyczne wartości każdego score'a — zweryfikowane empirycznie
# (wywołaniem funkcji na "idealnych" danych), nie liczone ręcznie, żeby uniknąć
# pomyłki. Używane do pokazania % maksimum w briefie spółki.
STRATEGY_MAX_SCORES = {
    "Buy Score": 9,
    "Score: Deep Value": 10,
    "Score: Momentum": 8,
    "Score: Dywidendowa": 7,
    "Score: Dywidenda-Okazja": 13,
    "Score: F-Score Lite": 8,
}


def generate_brief(row: dict) -> list[str]:
    """
    Rozbudowane, czytelne dla człowieka podsumowanie sytuacji spółki na bazie
    już policzonych danych — reguły, nie AI (w pełni deterministyczne i
    wyjaśnialne). Zwraca listę linii: te zaczynające się od '## ' to nagłówki
    sekcji, reszta to punkty do wypunktowania pod danym nagłówkiem.
    """
    lines: list[str] = []

    def _num(key):
        v = row.get(key)
        return v if isinstance(v, (int, float)) else None

    # --- Wycena ------------------------------------------------------------
    lines.append("## 💵 Wycena")
    pe, fpe, pb, mcap = _num("C/Z (P/E)"), _num("Forward C/Z"), _num("C/WK (P/B)"), _num("Kapitalizacja (mld)")
    if pe is not None:
        if pe < 0:
            lines.append(f"Ujemne C/Z ({pe}) — spółka odnotowuje stratę, standardowe mnożniki wyceny tracą tu sens.")
        elif pe < 15:
            lines.append(f"C/Z {pe} — relatywnie tanio (porównaj z medianą sektora w zakładce „vs Sektor”).")
        elif pe > 25:
            lines.append(f"C/Z {pe} — relatywnie drogo, rynek zakłada spory wzrost zysków.")
        else:
            lines.append(f"C/Z {pe} — w okolicach przeciętnej.")
    if fpe is not None and pe is not None:
        if fpe < pe:
            lines.append(f"Forward C/Z ({fpe}) niższe niż bieżące — rynek oczekuje wzrostu zysków w kolejnym roku.")
        elif fpe > pe:
            lines.append(f"Forward C/Z ({fpe}) wyższe niż bieżące — rynek oczekuje spadku zysków.")
    if pb is not None:
        if pb < 1:
            lines.append(f"C/WK {pb} — poniżej wartości księgowej (albo okazja, albo rynek widzi problem — sprawdź fundamenty).")
        else:
            lines.append(f"C/WK {pb}.")
    if mcap is not None:
        size = "duża (>10 mld)" if mcap > 10 else ("średnia (2-10 mld)" if mcap >= 2 else "mała (<2 mld)")
        lines.append(f"Kapitalizacja {mcap} mld — spółka {size}, {'zwykle stabilniejsza' if mcap > 10 else 'większy potencjał wzrostu, ale i ryzyka'}.")

    # --- Trend i technika ----------------------------------------------------
    lines.append("## 📈 Trend i technika")
    price = _num("Cena")
    sma20, sma50, sma200 = _num("SMA20"), _num("SMA50"), _num("SMA200")
    if price is not None and sma200 is not None:
        trend = "długoterminowa hossa (cena nad SMA200)" if price > sma200 else "długoterminowa bessa (cena pod SMA200)"
        lines.append(f"Trend długoterminowy: {trend}.")
    if price is not None and sma20 is not None and sma50 is not None:
        short_trend = "wzrostowy" if price > sma20 and price > sma50 else ("spadkowy" if price < sma20 and price < sma50 else "mieszany/boczny")
        lines.append(f"Trend krótkoterminowy (SMA20/50): {short_trend}.")
    rsi = _num("RSI")
    if rsi is not None:
        if rsi < 30:
            lines.append(f"RSI {rsi} — wyprzedanie, możliwe odbicie.")
        elif rsi > 70:
            lines.append(f"RSI {rsi} — wykupienie, podwyższone ryzyko korekty.")
        else:
            lines.append(f"RSI {rsi} — neutralna strefa.")
    if row.get("macd_bullish") is not None:
        lines.append("MACD byczy (sygnał wzrostowy)." if row.get("macd_bullish") else "MACD niedźwiedzi (sygnał spadkowy).")
    v_rat = _num("volume_ratio")
    if v_rat is not None and v_rat > 1.3:
        lines.append(f"Wolumen {v_rat}x średniej z 20 dni — wyraźnie podwyższone zainteresowanie rynku.")
    ath = _num("pct_from_ath")
    if ath is not None and ath < -15:
        lines.append(f"Dystans od ATH: {ath}% — sprawdź w Deep Value, czy to okazja, czy sygnał realnych problemów biznesu.")
    w52h, w52l = _num("52-tyg. maksimum"), _num("52-tyg. minimum")
    if price is not None and w52h is not None and w52l is not None and w52h > w52l:
        pos = round((price - w52l) / (w52h - w52l) * 100)
        lines.append(f"Cena jest na {pos}% zakresu z ostatnich 52 tygodni (0% = roczne minimum, 100% = roczne maksimum).")

    # --- Jakość biznesu ------------------------------------------------------
    lines.append("## 🏢 Jakość biznesu")
    roe, op_m, net_m = _num("ROE (%)"), _num("Marża Operac. (%)"), _num("Marża netto (%)")
    if roe is not None:
        lines.append(f"ROE {roe}% — {'wysokie' if roe > 20 else ('dobre' if roe > 15 else ('przeciętne' if roe > 5 else 'niskie'))}.")
    if op_m is not None:
        lines.append(f"Marża operacyjna {op_m}%.")
    if net_m is not None:
        lines.append(f"Marża netto {net_m}%{' — spółka jest na stracie' if net_m < 0 else ''}.")
    rev_g, eps_g = _num("Wzrost przychodów (%)"), _num("Wzrost EPS (%)")
    if rev_g is not None:
        lines.append(f"Przychody {'rosną' if rev_g > 0 else 'maleją'} o {abs(rev_g)}% rdr.")
    if eps_g is not None:
        lines.append(f"Zysk na akcję {'rośnie' if eps_g > 0 else 'maleje'} o {abs(eps_g)}% rdr.")
    debt = _num("Dług/Kapitał")
    if debt is not None:
        lines.append(f"Dług/kapitał {debt}% — {'bezpiecznie' if debt < 50 else ('umiarkowanie' if debt < 150 else 'wysokie ryzyko finansowe')}.")

    # --- Dywidenda -------------------------------------------------------------
    lines.append("## 💰 Dywidenda")
    yld = _num("Stopa Dyw. (%)")
    if yld is not None:
        season_bit = ""
        if row.get("Dyw. w poprzednim roku") == "Tak" and row.get("Dyw. w tym roku") == "Nie":
            season_bit = " Płaciła w zeszłym roku, jeszcze nie w tym — wypłata może być dopiero przed nią."
        lines.append(f"Stopa dywidendy {yld}%.{season_bit}")
        payout = _num("Payout ratio (%)")
        if payout is not None:
            lines.append(f"Payout ratio {payout}% — {'bezpieczny poziom' if payout < 80 else 'wypłaca więcej niż bezpiecznie, sprawdź trwałość'}.")
        years = row.get("Lata z dywidendą (3Y)")
        if isinstance(years, (int, float)):
            lines.append(f"Wypłacała dywidendę w {int(years)}/3 ostatnich lat.")
        next_div = row.get("Przyszła dywidenda", "BRAK")
        if next_div and next_div != "BRAK":
            lines.append(f"Najbliższa wypłata: {next_div}.")
    else:
        lines.append("Spółka nie wypłaca dywidendy (albo brak danych).")

    # --- Analitycy i ryzyko ------------------------------------------------------
    lines.append("## 🔮 Analitycy i ryzyko")
    rec = row.get("Rekomendacja analityków", "BRAK")
    n_analysts = row.get("Liczba analityków", "BRAK")
    if rec and rec != "BRAK":
        extra = f" (na bazie {n_analysts} analityków)" if isinstance(n_analysts, (int, float)) else ""
        lines.append(f"Konsensus analityków: {rec}{extra}.")
    target = _num("Cena docelowa (analitycy)")
    if target is not None and price is not None and price > 0:
        upside = round((target - price) / price * 100, 1)
        kierunek = "powyżej" if upside > 0 else "poniżej"
        lines.append(f"Średnia cena docelowa {target} — {abs(upside)}% {kierunek} obecnej ceny.")
    beta = _num("Beta")
    if beta is not None:
        charakter = "bardziej zmienna niż rynek" if beta > 1.2 else ("mniej zmienna/defensywna" if beta < 0.8 else "podobna zmienność do rynku")
        lines.append(f"Beta {beta} — {charakter}.")
    n_flags = row.get("Liczba flag", 0)
    if isinstance(n_flags, (int, float)) and n_flags > 0:
        lines.append(f"⚠️ Wykryto {int(n_flags)} czerwoną/e flagę/i — sprawdź szczegóły niżej.")
    else:
        lines.append("✅ Brak wykrytych automatycznych ostrzeżeń (czerwonych flag).")

    # --- Podsumowanie strategii --------------------------------------------------
    lines.append("## 🎯 Podsumowanie strategii")
    scored = []
    for name, (score_col, _) in STRATEGIES.items():
        score = row.get(score_col)
        max_score = STRATEGY_MAX_SCORES.get(score_col)
        if isinstance(score, (int, float)) and max_score:
            scored.append((name, score, max_score, round(score / max_score * 100)))
    if scored:
        scored.sort(key=lambda x: x[3], reverse=True)
        best_name, best_score, best_max, best_pct = scored[0]
        lines.append(f"Najmocniejszy sygnał: **{best_name}** ({best_score}/{best_max} = {best_pct}% maksimum).")
        for name, score, max_score, pct in scored[1:]:
            lines.append(f"{name}: {score}/{max_score} ({pct}%).")

    # Usuwa nagłówki sekcji, pod którymi finalnie nie znalazło się nic
    # (np. spółka bez żadnych danych technicznych) — zamiast pustego nagłówka
    # wiszącego bez treści.
    cleaned: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            has_content = i + 1 < len(lines) and not lines[i + 1].startswith("## ")
            if has_content:
                cleaned.append(line)
        else:
            cleaned.append(line)
    return cleaned


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


# ---------------------------------------------------------------------------
# Konwersja tickerów z formatu XTB na format Yahoo Finance
#
# XTB oznacza instrumenty sufiksem KRAJU (ALE.PL), Yahoo — sufiksem GIEŁDY
# (ALE.WA). Bez tłumaczenia eksport z XTB jest w module Analizy transakcji
# bezużyteczny, bo Yahoo nie rozpozna praktycznie żadnego symbolu.
#
# Mapowanie sprawdzone EMPIRYCZNIE na prawdziwym eksporcie z xStation 5
# (45 instrumentów, wrzesień 2026) — każdy symbol został realnie pobrany
# z Yahoo. Wynik: 43/45. Dwa braki to instrumenty, których Yahoo po prostu
# nie prowadzi (Credit Suisse po wchłonięciu przez UBS, Kombinat Konopny),
# a nie błąd tłumaczenia.
# ---------------------------------------------------------------------------
_XTB_SUFFIX_YAHOO = {
    # --- zweryfikowane na prawdziwych danych ---
    "PL": "WA",   # GPW Warszawa
    "US": "",     # giełdy USA — Yahoo nie używa sufiksu
    "DE": "DE",   # Xetra (akurat zgodne)
    "FR": "PA",   # Euronext Paryż
    "CH": "SW",   # SIX Zurych
    "UK": "L",    # LSE Londyn
    "IT": "MI",   # Borsa Italiana
    # --- z konwencji Yahoo, NIEsprawdzone (brak w eksporcie testowym) ---
    # Jeśli któryś okaże się błędny, popraw tutaj — reszta kodu bez zmian.
    "ES": "MC", "NL": "AS", "PT": "LS", "BE": "BR", "AT": "VI",
    "SE": "ST", "NO": "OL", "DK": "CO", "FI": "HE", "CZ": "PR",
    "IE": "IR", "HU": "BD",
}

# Przypadki, w których sam sufiks nie wystarcza — spółka zmieniła nazwę albo
# Yahoo prowadzi ją pod innym symbolem bazowym. Oba sprawdzone pobraniem.
_XTB_TICKER_OVERRIDES = {
    "CCC.PL": "MDV.WA",    # CCC przemianowane na Modivo, wraz ze zmianą tickera
    "TUI.DE": "TUI1.DE",   # Yahoo prowadzi TUI na Xetrze jako TUI1
}


# Ile razy pomnożyć cenę z brokera, żeby zgadzała się z notowaniem Yahoo.
# Część giełd (przede wszystkim LSE) Yahoo podaje w SUBJEDNOSTKACH waluty —
# pensach zamiast funtów, co sygnalizuje małą literą w kodzie waluty ("GBp"
# zamiast "GBP"). Broker podaje cenę w funtach, więc bez korekty porównanie
# wychodzi zawyżone 100-krotnie (realny przypadek: Wizz Air kupiony po 10,75
# GBP vs notowanie 1074 pensy dawało "mogłeś kupić taniej o 9795%").
_SKALA_CACHE: dict[str, float] = {}


def yahoo_price_scale(ticker: str) -> float:
    """
    Zwraca 100.0, gdy Yahoo notuje instrument w subjednostkach waluty
    (np. pensach), a 1.0 w każdym innym przypadku — również wtedy, gdy nie
    udało się ustalić waluty, bo lepiej nie ruszać ceny niż zepsuć dobrą.
    """
    t = str(ticker or "").strip().upper()
    if not t:
        return 1.0
    if t in _SKALA_CACHE:
        return _SKALA_CACHE[t]
    skala = 1.0
    try:
        currency = (yf.Ticker(t).info or {}).get("currency")
        # "GBp" ma małą literę na końcu, "GBP"/"USD"/"PLN" nie mają.
        if currency and str(currency) != str(currency).upper():
            skala = 100.0
    except Exception:  # noqa: BLE001
        pass
    _SKALA_CACHE[t] = skala
    return skala


def xtb_to_yahoo(ticker: str) -> str:
    """
    Tłumaczy symbol z eksportu XTB na symbol Yahoo Finance (ALE.PL -> ALE.WA).

    Przy nieznanym sufiksie zwraca wejście bez zmian — lepiej spróbować i nie
    znaleźć danych, niż z góry odrzucić symbol, który może być zgodny.
    """
    t = str(ticker or "").strip().upper()
    if not t:
        return ""
    if t in _XTB_TICKER_OVERRIDES:
        return _XTB_TICKER_OVERRIDES[t]
    if "." not in t:
        return t
    base, suffix = t.rsplit(".", 1)
    yahoo_suffix = _XTB_SUFFIX_YAHOO.get(suffix)
    if yahoo_suffix is None:
        return t
    return base if yahoo_suffix == "" else f"{base}.{yahoo_suffix}"


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


# Kody giełd używane przez TradingView (potwierdzone oficjalną listą giełd
# TradingView) — inne niż sufiksy Yahoo Finance, stąd osobne mapowanie.
# Austria (.VI) i Portugalia (.LS) nie są jednoznacznie potwierdzone w
# oficjalnym źródle — najlepszy dostępny szacunek (VIE, EURONEXT).
_SUFFIX_TRADINGVIEW = {
    ".WA": "GPW", ".DE": "XETR", ".PA": "EURONEXT", ".AS": "EURONEXT",
    ".MC": "BME", ".ST": "OMXSTO", ".OL": "OSL", ".MI": "MIL",
    ".VI": "VIE", ".LS": "EURONEXT", ".L": "LSE", ".SW": "SIX",
}


def get_tradingview_url(ticker: str, layout_id: str | None = None) -> str:
    """
    Link do wykresu na TradingView. Jeśli podano `layout_id` (identyfikator
    własnego, zapisanego layoutu użytkownika na TradingView — z URL-a jego
    wykresu, część po /chart/ a przed /?symbol=), link otwiera DOKŁADNIE ten
    layout z podmienionym tylko symbolem — to jedyny sposób, żeby ominąć
    przekierowanie TradingView dla niezalogowanych użytkowników na stronę
    przeglądową spółki zamiast wprost na wykres. Bez layout_id używa
    ogólnego linku do wykresu (może przekierować niezalogowanych).
    """
    base, exchange = ticker, None
    for suffix, tv_exchange in _SUFFIX_TRADINGVIEW.items():
        if ticker.endswith(suffix):
            base, exchange = ticker[: -len(suffix)], tv_exchange
            break
    symbol = f"{exchange}:{base}" if exchange else base  # USA i inne bez sufiksu — TradingView sam rozpozna giełdę
    if layout_id:
        return f"https://www.tradingview.com/chart/{layout_id}/?symbol={quote(symbol)}"
    return f"https://www.tradingview.com/chart/?symbol={quote(symbol)}"


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


def green_flags(row: dict) -> list[str]:
    """
    Pozytywne sygnały jakości/bezpieczeństwa spółki — dopełnienie red_flags().
    Pomaga odróżnić realną okazję (niskie C/Z, ale zdrowy biznes) od pułapki
    wartościowej (niskie C/Z, bo rynek słusznie wycenia problemy).
    """
    flags: list[str] = []

    roe = row.get("ROE (%)")
    if isinstance(roe, (int, float)) and roe > 15:
        flags.append(f"🟢 Wysokie ROE ({roe}%)")

    op_margin = row.get("Marża Operac. (%)")
    if isinstance(op_margin, (int, float)) and op_margin > 15:
        flags.append(f"🟢 Solidna marża operacyjna ({op_margin}%)")

    debt = row.get("Dług/Kapitał")
    if isinstance(debt, (int, float)) and debt < 50:
        flags.append(f"🟢 Niskie zadłużenie (dług/kapitał {debt}%)")

    rev_growth = row.get("Wzrost przychodów (%)")
    if isinstance(rev_growth, (int, float)) and rev_growth > 5:
        flags.append(f"🟢 Rosnące przychody (+{rev_growth}%)")

    eps_growth = row.get("Wzrost EPS (%)")
    if isinstance(eps_growth, (int, float)) and eps_growth > 5:
        flags.append(f"🟢 Rosnący zysk na akcję (+{eps_growth}%)")

    years = row.get("Lata z dywidendą (3Y)")
    if isinstance(years, (int, float)) and years >= 3:
        flags.append("🟢 Nieprzerwana dywidenda przez ostatnie 3 lata")

    if row.get("Liczba flag", 1) == 0:
        flags.append("🟢 Zero czerwonych flag ostrzegawczych")

    return flags


def get_vix_level() -> dict | None:
    """
    Bieżący poziom VIX (indeks zmienności) — prawdziwy ticker giełdowy (^VIX)
    dostępny przez Yahoo Finance dokładnie tak samo, jak każda inna spółka
    w tym projekcie. Zwraca None, gdy się nie uda (np. brak sieci).
    """
    try:
        tk = yf.Ticker("^VIX")
        hist = tk.history(period="5d")
        closes = hist["Close"].dropna()
        if closes.empty:
            return None
        current = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else current
        change_pct = round(((current - prev) / prev) * 100, 2) if prev else None
        return {"value": round(current, 2), "change_pct": change_pct}
    except Exception:  # noqa: BLE001
        return None


def compute_sentiment_index(
    vix_value: float | None, pct_above_sma50: float | None,
    pct_above_sma200: float | None, avg_rsi: float | None,
) -> dict | None:
    """
    Własny wskaźnik nastrojów rynkowych (0-100), inspirowany logiką znanego
    Fear & Greed Index, ale liczony WYŁĄCZNIE z danych, które appka faktycznie
    ma: VIX z Yahoo Finance + szerokość rynku (SMA50/200) + średnie RSI
    z bieżącej migawki. To NIE jest oficjalny wskaźnik CNN Fear & Greed —
    ten nie ma publicznego, oficjalnego API, więc świadomie nie próbujemy go
    naśladować pod tą samą nazwą.
    """
    components: list[float] = []
    if vix_value is not None:
        # niski VIX (~10) = spokój/chciwość, wysoki (~40) = strach — skala odwrotna
        vix_score = max(0.0, min(100.0, 100 - (vix_value - 10) * (100 / 30)))
        components.append(vix_score)
    if pct_above_sma50 is not None:
        components.append(pct_above_sma50)
    if pct_above_sma200 is not None:
        components.append(pct_above_sma200)
    if avg_rsi is not None:
        components.append(avg_rsi)

    if not components:
        return None

    score = round(sum(components) / len(components))
    if score < 25:
        label = "Ekstremalny strach"
    elif score < 45:
        label = "Strach"
    elif score < 55:
        label = "Neutralnie"
    elif score < 75:
        label = "Chciwość"
    else:
        label = "Ekstremalna chciwość"
    return {"score": score, "label": label}


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
        "ROA (%)": _safe_get(info, "returnOnAssets", is_pct=True) or "BRAK",
        "Przepływy operacyjne (mln)": (
            round(info.get("operatingCashflow") / 1e6, 1)
            if isinstance(info.get("operatingCashflow"), (int, float)) else "BRAK"
        ),
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


def analyze_trade(
    ticker: str, buy_date, buy_price: float,
    sell_date=None, sell_price: float | None = None, lookback_days: int = 90,
) -> dict | None:
    """
    Analiza pojedynczej transakcji "po fakcie": ile taniej dało się kupić w
    oknie po zakupie, jakie wskaźniki techniczne były w dniu zakupu (żeby
    sprawdzić, czy kupno wypadło podczas odbicia czy w realnym dołku), i —
    jeśli podano sprzedaż — czy sprzedaż nie była zbyt wczesna.
    Zwraca None, gdy nie da się pobrać/dopasować danych (np. zły ticker).
    """
    try:
        hist = price_history_for_backtest(ticker)
        if hist.empty:
            return None
        if getattr(hist.index, "tz", None) is not None:
            hist.index = hist.index.tz_localize(None)

        buy_ts = pd.Timestamp(buy_date)
        hist_upto_buy = hist.loc[:buy_ts]
        ind_at_buy = compute_indicators(hist, buy_price, as_of=buy_ts) if len(hist_upto_buy) >= 30 else {}

        end_ts = min(buy_ts + pd.Timedelta(days=lookback_days), hist.index.max())
        if sell_date is not None:
            end_ts = max(end_ts, pd.Timestamp(sell_date))
        window = hist.loc[buy_ts:end_ts]
        if window.empty:
            return None

        min_after = float(window["Low"].min())
        min_after_date = window["Low"].idxmin()
        pct_could_save = round(((min_after - buy_price) / buy_price) * 100, 2)

        result = {
            "Ticker": ticker,
            "Data zakupu": buy_ts.date().isoformat(),
            "Cena zakupu": round(float(buy_price), 2),
            "Min. cena po zakupie": round(min_after, 2),
            "Data minimum": pd.Timestamp(min_after_date).date().isoformat(),
            "Ile taniej mogłeś kupić (%)": pct_could_save,
            "RSI w dniu zakupu": ind_at_buy.get("RSI"),
            "% od ATH w dniu zakupu": ind_at_buy.get("pct_from_ath"),
        }

        if sell_date is not None and sell_price is not None:
            sell_ts = pd.Timestamp(sell_date)
            after_sell = hist.loc[sell_ts:]
            if not after_sell.empty:
                max_after_sell = float(after_sell["High"].max())
                pct_missed_upside = round(((max_after_sell - sell_price) / sell_price) * 100, 2)
                result["Cena sprzedaży"] = round(float(sell_price), 2)
                result["Maks. cena po sprzedaży"] = round(max_after_sell, 2)
                result["Niewykorzystany wzrost po sprzedaży (%)"] = pct_missed_upside

        return result
    except Exception:  # noqa: BLE001
        return None


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


def get_insider_transactions(ticker: str, limit: int = 8) -> list[dict]:
    """
    Ostatnie transakcje insiderów (zarząd/rada/duzi akcjonariusze) z Yahoo
    Finance — na żądanie, nie podczas skanu. UWAGA: pokrycie tych danych przez
    Yahoo jest zwykle znacznie lepsze dla spółek notowanych w USA niż
    europejskich — dla wielu tickerów z tego projektu może zwrócić pustą listę,
    co nie jest błędem, tylko brakiem danych źródłowych.
    """
    try:
        tk = yf.Ticker(ticker)
        raw = tk.get_insider_transactions()
    except Exception:  # noqa: BLE001
        return []
    if raw is None or raw.empty:
        return []

    results: list[dict] = []
    for _, row in raw.head(limit).iterrows():
        d = row.to_dict()
        date_val = d.get("Start Date") or d.get("Date")
        date_str = None
        if date_val is not None:
            try:
                date_str = pd.Timestamp(date_val).strftime("%Y-%m-%d")
            except Exception:  # noqa: BLE001
                date_str = str(date_val)
        results.append({
            "date": date_str,
            "insider": d.get("Insider") or d.get("Filer Name") or "Nieznany",
            "relation": d.get("Position") or d.get("Filer Relation") or "",
            "transaction": d.get("Transaction") or d.get("Transaction Description") or "",
            "shares": d.get("Shares"),
            "value": d.get("Value"),
        })
    return results


def compute_stockrank(stocks: pd.DataFrame) -> pd.DataFrame:
    """
    Dodaje trzy kolumny percentylowe (0-100, względem przekazanego zbioru
    spółek) inspirowane Stockopedia StockRanks: Quality, Value, Momentum.
    Liczone NA ŻYWO na dostarczonym zbiorze (nie zapisywane w migawce) —
    percentyle są więc zawsze względne do tego, co akurat porównujesz
    (np. cały rynek vs tylko jeden sektor dadzą różne wyniki).
    """
    df = stocks.copy()

    def _rank(col: str, higher_better: bool = True) -> pd.Series | None:
        if col not in df.columns:
            return None
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.dropna().empty:
            return None
        return numeric.rank(pct=True, ascending=higher_better) * 100

    def _combine(components: list[tuple[str, bool]]) -> pd.Series | None:
        ranks = [r for r in (_rank(col, higher) for col, higher in components) if r is not None]
        if not ranks:
            return None
        return pd.concat(ranks, axis=1).mean(axis=1).round(0)

    df["Quality"] = _combine([
        ("ROE (%)", True), ("Marża Operac. (%)", True), ("Marża netto (%)", True),
        ("Dług/Kapitał", False), ("ROA (%)", True),
    ])
    df["Value"] = _combine([
        ("C/Z (P/E)", False), ("C/WK (P/B)", False), ("Forward C/Z", False), ("Stopa Dyw. (%)", True),
    ])
    df["Momentum"] = _combine([
        ("RSI", True), ("volume_ratio", True), ("pct_from_ath", True), ("Zmiana ceny (1Y%)", True),
    ])
    return df


def compute_snowflake(stocks: pd.DataFrame) -> pd.DataFrame:
    """
    5-osiowy profil spółki (inspirowany 'Snowflake' z Simply Wall St): Wycena,
    Wzrost, Wyniki historyczne, Zdrowie finansowe, Dywidendy — każda oś 0-100,
    percentylowo względem przekazanego zbioru spółek (ta sama metodologia co
    compute_stockrank, tylko więcej, węższych osi pod wykres radarowy).
    """
    df = stocks.copy()

    def _rank(col: str, higher_better: bool = True) -> pd.Series | None:
        if col not in df.columns:
            return None
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.dropna().empty:
            return None
        return numeric.rank(pct=True, ascending=higher_better) * 100

    def _combine(components: list[tuple[str, bool]]) -> pd.Series | None:
        ranks = [r for r in (_rank(col, higher) for col, higher in components) if r is not None]
        if not ranks:
            return None
        return pd.concat(ranks, axis=1).mean(axis=1).round(0)

    df["Snowflake: Wycena"] = _combine([("C/Z (P/E)", False), ("C/WK (P/B)", False), ("Forward C/Z", False)])
    df["Snowflake: Wzrost"] = _combine([("Wzrost przychodów (%)", True), ("Wzrost EPS (%)", True)])
    df["Snowflake: Wyniki"] = _combine([("Zmiana ceny (1Y%)", True), ("pct_from_ath", True)])
    df["Snowflake: Zdrowie"] = _combine([
        ("Dług/Kapitał", False), ("ROA (%)", True), ("Score: F-Score Lite", True),
    ])
    df["Snowflake: Dywidendy"] = _combine([
        ("Stopa Dyw. (%)", True), ("Lata z dywidendą (3Y)", True), ("Payout ratio (%)", False),
    ])
    return df


def compute_correlation_matrix(tickers: list[str]) -> pd.DataFrame:
    """
    Macierz korelacji dziennych zwrotów dla podanych tickerów (np. z
    Watchlisty) — liczona z historii cen, którą i tak już pobieramy do
    backtestu pojedynczej spółki. Ticker, dla którego nie uda się pobrać
    danych, jest pomijany bez wywalania reszty.
    """
    returns: dict[str, pd.Series] = {}
    for ticker in tickers:
        try:
            hist = price_history_for_backtest(ticker)
            if hist.empty or "Close" not in hist.columns:
                continue
            returns[ticker] = hist["Close"].pct_change().dropna()
        except Exception:  # noqa: BLE001
            continue
    if len(returns) < 2:
        return pd.DataFrame()
    combined = pd.DataFrame(returns)
    return combined.corr().round(2)


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
