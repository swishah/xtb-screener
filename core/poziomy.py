"""
Poziomy techniczne liczone z surowych notowań — podstawa planów wejścia.

DLACZEGO TO W OGÓLE ISTNIEJE. Plany wejścia i stop-lossy stoją na KONKRETNYCH
liczbach. Model językowy poproszony o „wsparcie z wykresu" poda liczbę, która
brzmi wiarygodnie i której nikt nie jest w stanie zweryfikować. Dlatego poziomy
liczy tutaj Python, deterministycznie, a warstwa oceniająca może już tylko
WYBRAĆ jeden z policzonych — nie wymyślić własny. Bramka (`core/bramka.py`)
odrzuca każdy plan, którego poziomu nie ma na tej liście.

LICZYMY Z SUROWEGO OHLC, NIE Z MIGAWKI. To nie jest powielanie pracy skanu:
w migawkach kolumny `SMA200` i `SMA50` bywają puste dla większości spółek
(zmierzone: 1274 z 1281 w migawce 2026-09-04), a plan wejścia bez średnich
byłby ślepy. Licząc tu od zera, omijamy ten problem w całości i przy okazji
dostajemy niezależny punkt odniesienia, gdyby trzeba było go kiedyś
zdiagnozować.

KAŻDY POZIOM MA IDENTYFIKATOR I OPIS. To nie ozdoba — identyfikator jest
jedynym sposobem, w jaki plan może się powołać na poziom, a bramka to
sprawdzić.
"""
from __future__ import annotations

import pandas as pd

# Okno do wykrywania lokalnych ekstremów: punkt jest szczytem swingu, gdy jest
# najwyższy w promieniu tylu sesji. Pięć to kompromis — przy trzech łapiemy
# szum, przy dziesięciu gubimy poziomy z ostatnich dwóch tygodni.
OKNO_SWINGU = 5

# Ile ostatnich swingów każdego rodzaju zatrzymujemy. Więcej niż cztery to już
# poziomy sprzed miesięcy, których nikt nie bierze pod uwagę przy wejściu.
ILE_SWINGOW = 4

# Ile świec oddajemy do oceny. Dzienne obejmują kwartał, tygodniowe rok,
# miesięczne pięć lat — tyle wystarcza, żeby zobaczyć kontekst bez zalewania
# odbiorcy tysiącem liczb.
SWIEC_1D = 60
SWIEC_1W = 52
SWIEC_1M = 60


def _liczba(w) -> float | None:
    try:
        x = float(w)
    except (TypeError, ValueError):
        return None
    return x if pd.notna(x) else None


def atr(df: pd.DataFrame, okres: int = 14) -> float | None:
    """
    Średni rzeczywisty zakres — miara zmienności w jednostkach ceny.

    Potrzebna, bo stop-loss ma sens wyłącznie w odniesieniu do zmienności
    danego papieru. Trzy złote od kursu to przepaść przy spółce, która rusza
    się o 50 groszy dziennie, i szum przy takiej, która rusza się o pięć.
    """
    if len(df) < okres + 1:
        return None
    wysoki, niski, zamkniecie = df["High"], df["Low"], df["Close"]
    poprzednie = zamkniecie.shift(1)
    zakres = pd.concat(
        [wysoki - niski, (wysoki - poprzednie).abs(), (niski - poprzednie).abs()],
        axis=1,
    ).max(axis=1)
    wynik = _liczba(zakres.rolling(okres).mean().iloc[-1])
    return round(wynik, 4) if wynik else None


def swingi(df: pd.DataFrame, okno: int = OKNO_SWINGU) -> tuple[list, list]:
    """
    Lokalne szczyty i dołki. Zwraca listy (data, cena), od najnowszych.

    Szczyt swingu to sesja, której maksimum jest najwyższe w promieniu `okno`
    sesji w obie strony. Ostatnie `okno` sesji jest z definicji niepełne —
    nie wiemy jeszcze, czy nie padnie tam wyższy szczyt — więc ich nie
    zgłaszamy. To celowe: poziom, który może się jeszcze zmienić, nie nadaje
    się na stop-loss.
    """
    if len(df) < okno * 2 + 1:
        return [], []

    gory: list[tuple[str, float]] = []
    doly: list[tuple[str, float]] = []
    wysoki = df["High"].to_numpy()
    niski = df["Low"].to_numpy()

    for i in range(okno, len(df) - okno):
        okolica_g = wysoki[i - okno : i + okno + 1]
        okolica_d = niski[i - okno : i + okno + 1]
        dzien = df.index[i]
        etykieta = pd.Timestamp(dzien).date().isoformat()
        if wysoki[i] == okolica_g.max():
            gory.append((etykieta, round(float(wysoki[i]), 4)))
        if niski[i] == okolica_d.min():
            doly.append((etykieta, round(float(niski[i]), 4)))

    return gory[::-1], doly[::-1]


def _srednia(df: pd.DataFrame, okres: int) -> float | None:
    if len(df) < okres:
        return None
    # dropna PRZED liczeniem: pojedyncza dziura w notowaniach nie może
    # wyzerować całego okna kroczącego.
    czyste = df["Close"].dropna()
    if len(czyste) < okres:
        return None
    return round(float(czyste.rolling(okres).mean().iloc[-1]), 4)


def _trend(df: pd.DataFrame, okres: int, wstecz: int) -> str:
    """
    Kierunek trendu: cena wobec średniej PLUS nachylenie samej średniej.

    Sama relacja ceny do średniej nie wystarcza — cena bywa nad opadającą
    średnią w trakcie odbicia w trendzie spadkowym. Dopiero oba warunki naraz
    pozwalają nazwać rzecz trendem, a nie chwilowym wychyleniem.
    """
    czyste = df["Close"].dropna()
    if len(czyste) < okres + wstecz:
        return "nieokreślony"
    srednia = czyste.rolling(okres).mean()
    teraz = _liczba(srednia.iloc[-1])
    kiedys = _liczba(srednia.iloc[-1 - wstecz])
    cena = _liczba(czyste.iloc[-1])
    if teraz is None or kiedys is None or cena is None:
        return "nieokreślony"
    rosnie = teraz > kiedys
    nad = cena > teraz
    if nad and rosnie:
        return "wzrostowy"
    if not nad and not rosnie:
        return "spadkowy"
    return "boczny"


def luki(df: pd.DataFrame, ile: int = 3) -> list[dict]:
    """
    Niedomknięte luki cenowe z ostatnich sesji.

    Luka to poziom, do którego rynek często wraca, więc bywa naturalnym celem
    albo miejscem odbicia. Za domkniętą uznajemy taką, przez którą cena już
    przeszła — te pomijamy, bo nie są już żadnym poziomem.
    """
    if len(df) < 2:
        return []
    wynik: list[dict] = []
    wysoki = df["High"].to_numpy()
    niski = df["Low"].to_numpy()
    ostatnia = float(df["Close"].dropna().iloc[-1])

    for i in range(len(df) - 1, max(0, len(df) - 120), -1):
        gora_w_gore = niski[i] > wysoki[i - 1]
        gora_w_dol = wysoki[i] < niski[i - 1]
        if not (gora_w_gore or gora_w_dol):
            continue
        od = float(wysoki[i - 1]) if gora_w_gore else float(wysoki[i])
        do = float(niski[i]) if gora_w_gore else float(niski[i - 1])
        # Domknięta, gdy kurs zdążył wejść w jej zakres.
        if min(od, do) <= ostatnia <= max(od, do):
            continue
        wynik.append({
            "data": pd.Timestamp(df.index[i]).date().isoformat(),
            "od": round(min(od, do), 4),
            "do": round(max(od, do), 4),
            "kierunek": "w górę" if gora_w_gore else "w dół",
        })
        if len(wynik) >= ile:
            break
    return wynik


def _swiece(df: pd.DataFrame, ile: int) -> list[dict]:
    """Ostatnie świece w zwięzłej formie — do oceny kontekstu, nie do liczenia."""
    ogon = df.tail(ile)
    return [
        {
            "d": pd.Timestamp(i).date().isoformat(),
            "o": round(float(r["Open"]), 4),
            "h": round(float(r["High"]), 4),
            "l": round(float(r["Low"]), 4),
            "c": round(float(r["Close"]), 4),
        }
        for i, r in ogon.iterrows()
        if pd.notna(r["Close"])
    ]


def _przelicz(df: pd.DataFrame, reguła: str) -> pd.DataFrame:
    """Przeliczenie świec dziennych na tygodniowe albo miesięczne."""
    return (
        df.resample(reguła)
        .agg({"Open": "first", "High": "max", "Low": "min",
              "Close": "last", "Volume": "sum"})
        .dropna(subset=["Close"])
    )


def zbuduj(df: pd.DataFrame, kurs: float | None = None) -> dict | None:
    """
    Komplet poziomów i kontekstu dla jednej spółki.

    `df` to dzienne OHLC (indeks czasowy). Tygodniowe i miesięczne
    przeliczamy sami, zamiast pobierać osobno — mniej zapytań i pewność, że
    wszystkie trzy interwały opisują dokładnie ten sam zakres dat.
    """
    if df is None or df.empty or len(df) < 60:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    if getattr(df.index, "tz", None) is not None:
        df = df.tz_localize(None)

    zamkniecia = df["Close"].dropna()
    if zamkniecia.empty:
        return None
    cena = _liczba(kurs) or float(zamkniecia.iloc[-1])
    if cena <= 0:
        return None

    tyg = _przelicz(df, "W")
    mies = _przelicz(df, "ME")

    gory, doly = swingi(df)
    a = atr(df)
    rok = df.tail(252)
    szczyt52 = _liczba(rok["High"].max())
    dolek52 = _liczba(rok["Low"].min())

    poziomy: list[dict] = []

    def dodaj(ident: str, wartosc, opis: str, rodzaj: str) -> None:
        w = _liczba(wartosc)
        if w is None or w <= 0:
            return
        poziomy.append({
            "id": ident,
            "wartosc": round(w, 4),
            "opis": opis,
            "rodzaj": rodzaj,
            "dystans_pct": round((w - cena) / cena * 100, 2),
        })

    for nr, (dzien, w) in enumerate(doly[:ILE_SWINGOW], start=1):
        dodaj(f"swing_low_{nr}", w, f"dołek swingu 1D z {dzien}", "wsparcie")
    for nr, (dzien, w) in enumerate(gory[:ILE_SWINGOW], start=1):
        dodaj(f"swing_high_{nr}", w, f"szczyt swingu 1D z {dzien}", "opór")

    for okres in (20, 50, 200):
        dodaj(f"sma{okres}", _srednia(df, okres), f"średnia {okres}-sesyjna",
              "średnia")
    dodaj("sma_tyg_10", _srednia(tyg, 10), "średnia 10-tygodniowa", "średnia")

    dodaj("szczyt_52t", szczyt52, "szczyt 52 tygodni", "opór")
    dodaj("dolek_52t", dolek52, "dołek 52 tygodni", "wsparcie")

    for nr, l in enumerate(luki(df), start=1):
        dodaj(f"luka_{nr}_od", l["od"], f"luka {l['kierunek']} z {l['data']} (brzeg)",
              "luka")
        dodaj(f"luka_{nr}_do", l["do"], f"luka {l['kierunek']} z {l['data']} (brzeg)",
              "luka")

    wolumen = None
    if "Volume" in df.columns and len(df) >= 20:
        ostatni = _liczba(df["Volume"].iloc[-1])
        srednia20 = _liczba(df["Volume"].tail(20).mean())
        if ostatni is not None and srednia20:
            wolumen = {
                "ostatni": int(ostatni),
                "srednia_20": int(srednia20),
                "krotnosc": round(ostatni / srednia20, 2),
            }

    pozycja = None
    if szczyt52 and dolek52 and szczyt52 > dolek52:
        pozycja = round((cena - dolek52) / (szczyt52 - dolek52) * 100, 1)

    return {
        "kurs": round(cena, 4),
        "atr": a,
        "atr_pct": round(a / cena * 100, 2) if a else None,
        "trend": {
            "1d": _trend(df, 20, 10),
            "1w": _trend(tyg, 10, 4),
            "1m": _trend(mies, 12, 3),
        },
        "zakres_52t": {
            "min": szczyt52 and dolek52 and round(dolek52, 4),
            "maks": szczyt52 and round(szczyt52, 4),
            "pozycja_pct": pozycja,
        },
        "wolumen": wolumen,
        "luki": luki(df),
        "poziomy": sorted(poziomy, key=lambda p: p["wartosc"]),
        "swiece": {
            "1d": _swiece(df, SWIEC_1D),
            "1w": _swiece(tyg, SWIEC_1W),
            "1m": _swiece(mies, SWIEC_1M),
        },
        "sesji_w_historii": len(df),
    }
