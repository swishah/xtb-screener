"""
Zbiórka kandydatów do planu dnia — po pięć najlepszych z każdego rankingu.

CO TU JEST „MODUŁEM". Aplikacja ma czternaście zakładek, ale tylko dwanaście
z nich SZEREGUJE spółki. Watchlist, alarmy, analiza transakcji i własne
instrumenty pokazują to, co sam wprowadziłeś; globalny przegląd, dashboard
i vs Sektor opisują rynek, a nie wybierają z niego. Zbieramy więc z tych
rankingów, które faktycznie mają czołówkę — dziewięciu strategii, Buy Score,
„Tanie vs sektor" i „Dywidend".

DUPLIKATY SĄ TU SYGNAŁEM, NIE PROBLEMEM. Ta sama spółka wychodzi zwykle
z kilku rankingów naraz i to mówi więcej niż pojedyncze trafienie: „wskazana
przez cztery z dwunastu" znaczy, że widać ją i od strony wyceny, i od strony
techniki. Dlatego po deduplikacji ZAPAMIĘTUJEMY, skąd przyszła, a liczba
źródeł decyduje o kolejności.

DLACZEGO OBCINAMY LISTĘ. Dossier wymaga pobrania dziesięciu lat notowań na
spółkę. Przy sześćdziesięciu kandydatach to sześćdziesiąt zapytań i kilka
minut, a i tak dziesięć planów na wyjściu znaczy, że reszta poszłaby do kosza.
Obcinamy więc do `MAKS_KANDYDATOW` — po deduplikacji, żeby ciąć najsłabsze,
a nie przypadkowe.
"""
from __future__ import annotations

import pandas as pd

from core.scanner import STRATEGIES

# Ile spółek bierzemy z czoła każdego rankingu.
ILE_Z_RANKINGU = 5

# Górny limit kandydatów, dla których liczymy dossier.
MAKS_KANDYDATOW = 20

# Minimalna liczba spółek w sektorze, żeby mediana C/Z coś znaczyła —
# ta sama granica co w module „Tanie vs sektor" i w heatmapach.
MIN_SPOLEK_W_SEKTORZE = 5

# O ile procent poniżej mediany sektora musi być C/Z, żeby uznać to za okazję.
PROG_TANIOSCI = -20.0


def _num(seria: pd.Series) -> pd.Series:
    return pd.to_numeric(seria, errors="coerce")


def _uszereguj(df: pd.DataFrame, kolumna: str) -> pd.DataFrame:
    """
    Sortowanie z regułą remisów obowiązującą w całym projekcie:
    mniej flag → wyższy Buy Score → ticker alfabetycznie.

    Bez niej czołówka zmienia się między uruchomieniami, bo wyniki strategii
    są całkowite i niskie, więc remisuje po kilkanaście spółek naraz.
    """
    pom = df.copy()
    pom["_wynik"] = _num(pom[kolumna])
    pom["_flagi"] = _num(pom.get("Liczba flag")).fillna(0)
    pom["_buy"] = _num(pom.get("Buy Score")).fillna(0)
    return pom.dropna(subset=["_wynik"]).sort_values(
        ["_wynik", "_flagi", "_buy", "Ticker"],
        ascending=[False, True, False, True],
    )


def _tanie_vs_sektor(spolki: pd.DataFrame) -> pd.DataFrame:
    """Spółki z C/Z wyraźnie niższym niż mediana ich własnego sektora."""
    if "Sektor" not in spolki.columns or "C/Z (P/E)" not in spolki.columns:
        return spolki.iloc[0:0]
    pom = spolki.copy()
    pom["_pe"] = _num(pom["C/Z (P/E)"])
    pom = pom[(pom["_pe"] > 0) & pom["Sektor"].notna()]
    pom = pom[~pom["Sektor"].isin(["Nieznany", "BRAK"])]
    if pom.empty:
        return pom

    licznosc = pom.groupby("Sektor")["_pe"].transform("count")
    mediana = pom.groupby("Sektor")["_pe"].transform("median")
    pom = pom[licznosc >= MIN_SPOLEK_W_SEKTORZE]
    if pom.empty:
        return pom
    pom["_roznica"] = (pom["_pe"] - mediana) / mediana * 100
    pom = pom[pom["_roznica"] <= PROG_TANIOSCI]
    # Im taniej względem sektora, tym wyżej — stąd sortowanie rosnąco po
    # różnicy, a nie malejąco jak przy score'ach.
    return pom.sort_values(["_roznica", "Ticker"], ascending=[True, True])


def _dywidendy(spolki: pd.DataFrame) -> pd.DataFrame:
    """
    Spółki dywidendowe po tych samych filtrach co moduł Dywidendy.

    Wypłaty jednorazowe wykluczamy — nie tworzą sezonu, na który da się
    czekać, a ich „stopa" bierze się z jednego zdarzenia sprzed roku.
    """
    kol = "Score: Dywidenda-Okazja"
    if kol not in spolki.columns:
        return spolki.iloc[0:0]
    pom = spolki.copy()
    if "Dywidenda nieregularna" in pom.columns:
        pom = pom[pom["Dywidenda nieregularna"] != "Tak"]
    stopa = _num(pom.get("Stopa Dyw. (%)"))
    pom = pom[stopa >= 4]
    if pom.empty:
        return pom
    return _uszereguj(pom, kol)


def zbierz(migawka: pd.DataFrame, ile: int = ILE_Z_RANKINGU) -> list[dict]:
    """
    Kandydaci z wszystkich rankingów, zdeduplikowani i uszeregowani.

    Zwraca listę słowników: ticker, nazwa, rynek, kurs oraz `zrodla` — lista
    rankingów, które daną spółkę wskazały, wraz z zajmowanym miejscem.
    """
    if migawka is None or migawka.empty:
        return []

    spolki = migawka[migawka.get("Typ") == "stock"].copy()
    if spolki.empty:
        return []

    rankingi: dict[str, pd.DataFrame] = {}
    for nazwa, (kolumna, _) in STRATEGIES.items():
        if kolumna in spolki.columns:
            rankingi[nazwa] = _uszereguj(spolki, kolumna)
    if "Buy Score" in spolki.columns:
        rankingi["Buy Score"] = _uszereguj(spolki, "Buy Score")
    rankingi["Tanie vs sektor"] = _tanie_vs_sektor(spolki)
    rankingi["Dywidendy"] = _dywidendy(spolki)

    zebrane: dict[str, dict] = {}
    for nazwa, df in rankingi.items():
        if df is None or df.empty:
            continue
        for miejsce, (_, wiersz) in enumerate(df.head(ile).iterrows(), start=1):
            ticker = str(wiersz["Ticker"])
            wpis = zebrane.setdefault(ticker, {
                "ticker": ticker,
                "nazwa": str(wiersz.get("Nazwa", "")),
                "rynek": str(wiersz.get("Rynek", "")),
                "sektor": str(wiersz.get("Sektor", "")),
                "kurs": _num(pd.Series([wiersz.get("Cena")])).iloc[0],
                "zrodla": [],
            })
            wpis["zrodla"].append({"ranking": nazwa, "miejsce": miejsce})

    kandydaci = list(zebrane.values())
    for k in kandydaci:
        k["liczba_zrodel"] = len(k["zrodla"])
        # Średnie miejsce zajmowane w rankingach: rozstrzyga między spółkami
        # wskazanymi tyle samo razy. Piąte miejsce w trzech rankingach to
        # słabszy sygnał niż pierwsze w trzech.
        k["srednie_miejsce"] = round(
            sum(z["miejsce"] for z in k["zrodla"]) / len(k["zrodla"]), 2
        )

    kandydaci.sort(
        key=lambda k: (-k["liczba_zrodel"], k["srednie_miejsce"], k["ticker"])
    )
    return kandydaci[:MAKS_KANDYDATOW]
