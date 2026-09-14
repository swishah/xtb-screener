#!/usr/bin/env python3
"""
Porównanie poziomów: Python (`core/poziomy.py`) kontra publiczne API frontendu.

PO CO TO ISTNIEJE. `frontend/lib/poziomy.ts` jest LUSTREM `core/poziomy.py` —
tą samą matematyką napisaną drugi raz, w innym języku, po to, żeby maszyna
researchowa w Claude mogła policzyć poziomy dla dowolnej spółki bez udziału
komputera użytkownika. Dwie implementacje tego samego rozjeżdżają się po cichu:
kompilator tego nie złapie, testy jednostkowe po jednej stronie też nie.
Objawem byłby stop-loss postawiony na poziomie, którego nie ma na wykresie.

To ta sama zasada, która w tym projekcie wyłapała błąd z NaN, sprawę remisów
w rankingach i rozjazd zaokrągleń w statystyce planów: liczba policzona po obu
stronach musi wyjść identyczna, a „wygląda dobrze" nie wystarcza.

Użycie:

    py scripts/porownaj_poziomy.py --adres http://localhost:3000
    py scripts/porownaj_poziomy.py --adres https://xtb-screener.vercel.app MMM KO ALE.WA

UWAGA O GODZINIE. Przy otwartej giełdzie ostatnia świeca jest niepełna i rośnie
w trakcie sesji, więc obie strony pobierają ją w nieco innym momencie. Rozjazd
WYŁĄCZNIE na ostatniej świecy (kurs, ATR, wolumen) jest wtedy normalny i skrypt
zgłasza go jako ostrzeżenie, nie jako błąd. Rozjazd na średnich, swingach czy
zakresie 52 tygodni normalny nie jest nigdy.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests  # noqa: E402
import yfinance as yf  # noqa: E402

from core import poziomy  # noqa: E402

# Domyślna próbka: pięć rynków i dwa rodzaje pułapek — spółka dywidendowa
# (korekta o dywidendy), Londyn (notowanie w pensach), GPW (sufiks .WA).
TICKERY = ["MMM", "KO", "ALE.WA", "BAS.DE", "SHEL.L"]

# Tolerancja porównania liczb — WZGLĘDNA, nie bezwzględna.
#
# Ceny w tym uniwersum idą od 2 zł do 5000 pensów, więc jedna stała w groszach
# znaczy co innego przy każdej spółce. Jedna dziesięciotysięczna przy kursie
# 2732 to zupełnie inna precyzja niż przy kursie 12.
#
# Skąd w ogóle bierze się różnica: obie strony korygują notowania o dywidendy
# i splity, ale yfinance nakłada skumulowany współczynnik, a my liczymy go
# z pary (zamknięcie, zamknięcie skorygowane) dla każdej sesji osobno. Na
# świecach sprzed dziesięciu lat, gdzie korekta jest największa, daje to
# rozjazd rzędu 0,00001% — mierzalny, ale bez wpływu na cokolwiek: poziomy,
# ATR, trendy i zakres 52 tygodni zgadzają się co do czwartego miejsca.
TOLERANCJA_WZGL = 1e-6
# Podłoga dla wartości bliskich zeru, gdzie względna miara traci sens.
TOLERANCJA_MIN = 0.0001

# Pola, których rozjazd przy otwartej sesji jest normalny, bo zależą od
# ostatniej, niepełnej świecy.
ZALEZNE_OD_OSTATNIEJ = {"kurs", "atr", "atr_pct", "wolumen", "zakres_52t.pozycja_pct"}


class Wynik:
    def __init__(self) -> None:
        self.ok = 0
        self.bledy: list[str] = []
        self.ostrzezenia: list[str] = []

    def sprawdz(self, nazwa: str, a, b) -> None:
        if _rowne(a, b):
            self.ok += 1
            return
        opis = f"{nazwa}: python={a!r} api={b!r}"
        if nazwa in ZALEZNE_OD_OSTATNIEJ or nazwa.startswith("swiece.1d[-1]"):
            self.ostrzezenia.append(opis)
        else:
            self.bledy.append(opis)


def _rowne(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        granica = max(TOLERANCJA_MIN, abs(float(a)) * TOLERANCJA_WZGL)
        return abs(float(a) - float(b)) <= granica
    return a == b


def pobierz_python(ticker: str) -> dict | None:
    df = yf.Ticker(ticker).history(
        period="10y", interval="1d", auto_adjust=True, actions=False
    )
    if df is None or df.empty:
        return None
    return poziomy.zbuduj(df)


def pobierz_api(adres: str, ticker: str) -> dict | None:
    odp = requests.get(f"{adres}/api/dane/notowania/{ticker}", timeout=60)
    if odp.status_code != 200:
        print(f"   API odpowiedziało {odp.status_code}: {odp.text[:200]}")
        return None
    return odp.json()


def porownaj(ticker: str, py_dane: dict, api: dict, w: Wynik) -> None:
    w.sprawdz("kurs", py_dane["kurs"], api.get("kurs"))
    w.sprawdz("atr", py_dane["atr"], api.get("atr"))
    w.sprawdz("atr_pct", py_dane["atr_pct"], api.get("atr_pct"))
    w.sprawdz("sesji_w_historii", py_dane["sesji_w_historii"], api.get("sesji_w_historii"))

    for okres in ("1d", "1w", "1m"):
        w.sprawdz(f"trend.{okres}", py_dane["trend"][okres], (api.get("trend") or {}).get(okres))

    for pole in ("min", "maks", "pozycja_pct"):
        w.sprawdz(
            f"zakres_52t.{pole}",
            py_dane["zakres_52t"][pole],
            (api.get("zakres_52t") or {}).get(pole),
        )

    # Poziomy: ten sam zestaw identyfikatorów i te same wartości. To jest
    # najważniejsza część porównania — z tych liczb powstaje plan wejścia.
    py_poziomy = {p["id"]: p for p in py_dane["poziomy"]}
    api_poziomy = {p["id"]: p for p in (api.get("poziomy") or [])}
    w.sprawdz("poziomy: zestaw id", sorted(py_poziomy), sorted(api_poziomy))
    for ident in sorted(set(py_poziomy) & set(api_poziomy)):
        w.sprawdz(
            f"poziom {ident}.wartosc",
            py_poziomy[ident]["wartosc"],
            api_poziomy[ident]["wartosc"],
        )
        w.sprawdz(
            f"poziom {ident}.opis", py_poziomy[ident]["opis"], api_poziomy[ident]["opis"]
        )

    w.sprawdz("luki: liczba", len(py_dane["luki"]), len(api.get("luki") or []))
    for nr, (a, b) in enumerate(zip(py_dane["luki"], api.get("luki") or [])):
        w.sprawdz(f"luka[{nr}].od", a["od"], b.get("od"))
        w.sprawdz(f"luka[{nr}].do", a["do"], b.get("do"))
        w.sprawdz(f"luka[{nr}].data", a["data"], b.get("data"))

    for interwal in ("1d", "1w", "1m"):
        py_sw = py_dane["swiece"][interwal]
        api_sw = (api.get("swiece") or {}).get(interwal) or []
        w.sprawdz(f"swiece.{interwal}: liczba", len(py_sw), len(api_sw))
        if py_sw and api_sw:
            w.sprawdz(f"swiece.{interwal}[-1].d", py_sw[-1]["d"], api_sw[-1].get("d"))
            w.sprawdz(f"swiece.{interwal}[-1].c", py_sw[-1]["c"], api_sw[-1].get("c"))
            # Pierwsza świeca sprawdza, czy obie strony wzięły ten sam zakres dat.
            w.sprawdz(f"swiece.{interwal}[0].d", py_sw[0]["d"], api_sw[0].get("d"))
            w.sprawdz(f"swiece.{interwal}[0].c", py_sw[0]["c"], api_sw[0].get("c"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickery", nargs="*", default=None)
    parser.add_argument("--adres", default="http://localhost:3000")
    args = parser.parse_args()
    tickery = args.tickery or TICKERY

    w = Wynik()
    for ticker in tickery:
        print(f"\n=== {ticker} ===")
        py_dane = pobierz_python(ticker)
        if py_dane is None:
            w.bledy.append(f"{ticker}: Python nie policzył poziomów")
            print("   Python: brak danych")
            continue
        api = pobierz_api(args.adres, ticker)
        if api is None:
            w.bledy.append(f"{ticker}: API nie oddało poziomów")
            continue
        przed = w.ok
        porownaj(ticker, py_dane, api, w)
        print(f"   zgodnych porównań: {w.ok - przed}")

    print(f"\n{'=' * 60}")
    print(f"Zgodnych: {w.ok}")
    if w.ostrzezenia:
        print(f"\nOstrzeżenia ({len(w.ostrzezenia)}) — zależne od niepełnej świecy:")
        for o in w.ostrzezenia:
            print(f"   ~ {o}")
    if w.bledy:
        print(f"\nROZJAZDY ({len(w.bledy)}):")
        for b in w.bledy:
            print(f"   ! {b}")
        return 1
    print("\nBez rozjazdów — lustro zgadza się z Pythonem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
