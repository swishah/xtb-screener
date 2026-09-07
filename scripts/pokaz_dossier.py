"""
Wyświetlanie dossier w formie do czytania — wejście dla skilla `/plan-dnia`.

PO CO OSOBNY SKRYPT. Dossier siedzi w bazie jako JSON i nadaje się do
przetwarzania, nie do czytania. Warstwa oceniająca dostaje stąd ten sam
komplet liczb, tylko rozpisany: poziomy z nazwami, trendy, zakres roku,
świece. Nic tu nie jest interpretowane — skrypt niczego nie ocenia i nie
wybiera, przekłada wyłącznie format.

DWA TRYBY, BO KONTEKST NIE JEST Z GUMY. Bez argumentów dostajesz PRZEGLĄD
wszystkich spółek: poziomy i kontekst, bez świec. Dopiero `--ticker` dokłada
świece 1D/1W/1M dla jednej spółki — a to jest gruby kawałek tekstu, więc
ciągnie się go świadomie i po kolei, a nie hurtem dla dwudziestu spółek.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db  # noqa: E402

# Ile kolumn migawki wypisujemy w przeglądzie. Reszta i tak jest w dossier
# i wychodzi przy `--ticker`.
WAZNE_Z_MIGAWKI = (
    "C/Z (P/E)", "C/WK (P/B)", "ROE (%)", "Marża netto (%)", "Dług/Kapitał",
    "Stopa Dyw. (%)", "Zmiana ceny (1Y%)", "pct_from_ath", "RSI",
    "Buy Score", "Liczba flag", "Cena docelowa (analitycy)",
    "Rekomendacja analityków", "Krótkie pozycje (%)",
)


def _lb(w, cyfry: int = 4) -> str:
    if w is None:
        return "—"
    if isinstance(w, (int, float)):
        return f"{w:.{cyfry}f}".rstrip("0").rstrip(".")
    return str(w)


def naglowek(wpis: dict) -> list[str]:
    zrodla = ", ".join(
        f"{z['ranking']} ({z['miejsce']})" for z in wpis.get("zrodla", [])
    )
    zakres = wpis.get("zakres_52t") or {}
    trend = wpis.get("trend") or {}
    wol = wpis.get("wolumen") or {}

    linie = [
        f"## {wpis['ticker']} — {wpis.get('nazwa', '')}"
        f" ({wpis.get('rynek', '?')}, {wpis.get('sektor', '?')})"
        f" | {wpis.get('waluta', '?')}",
    ]
    if wpis.get("waluta_w_podjednostkach"):
        linie.append(
            "!! UWAGA: notowanie w PODJEDNOSTKACH (np. pensach). Wszystkie "
            "liczby poniżej są w tej samej skali co kurs — nie przeliczaj ich."
        )
    linie += [
        f"Wskazana przez {wpis.get('liczba_zrodel', 0)} rankingów: {zrodla}",
        f"Kurs {_lb(wpis.get('kurs'))} | ATR(14) {_lb(wpis.get('atr'))} "
        f"({_lb(wpis.get('atr_pct'), 2)}% kursu) | trend 1D "
        f"{trend.get('1d', '?')} / 1W {trend.get('1w', '?')} / 1M "
        f"{trend.get('1m', '?')}",
        f"52 tygodnie: {_lb(zakres.get('min'))} – {_lb(zakres.get('maks'))} "
        f"(kurs na {_lb(zakres.get('pozycja_pct'), 1)}% zakresu)"
        + (f" | wolumen {wol.get('krotnosc')}× średniej z 20 sesji" if wol else ""),
    ]
    return linie


def poziomy_tekst(wpis: dict) -> list[str]:
    linie = ["", "POZIOMY — plan wolno oprzeć WYŁĄCZNIE na tych wartościach:",
             "  id                  wartość      dystans   rodzaj      opis"]
    for p in wpis.get("poziomy", []):
        linie.append(
            f"  {p['id']:<18}  {_lb(p['wartosc']):>10}  "
            f"{p['dystans_pct']:>+7.2f}%  {p['rodzaj']:<10}  {p['opis']}"
        )
    return linie


def reszta_tekst(wpis: dict) -> list[str]:
    linie: list[str] = []
    luki = wpis.get("luki") or []
    if luki:
        linie.append("")
        linie.append("LUKI NIEDOMKNIĘTE")
        for l in luki:
            linie.append(
                f"  {l['data']} {l['kierunek']}: {_lb(l['od'])} – {_lb(l['do'])}"
            )

    migawka = wpis.get("migawka") or {}
    dane = [f"{k}: {migawka[k]}" for k in WAZNE_Z_MIGAWKI if k in migawka]
    if dane:
        linie.append("")
        linie.append("Z MIGAWKI: " + " | ".join(dane))

    flagi = migawka.get("Czerwone flagi")
    if flagi:
        linie.append(f"CZERWONE FLAGI: {flagi}")
    return linie


def swiece_tekst(wpis: dict) -> list[str]:
    linie = ["", "ŚWIECE (data, otwarcie, maksimum, minimum, zamknięcie)"]
    for okres, etykieta in (("1d", "dzienne"), ("1w", "tygodniowe"),
                            ("1m", "miesięczne")):
        swiece = (wpis.get("swiece") or {}).get(okres) or []
        linie.append(f"-- {etykieta} ({len(swiece)}) --")
        for s in swiece:
            linie.append(
                f"  {s['d']}  {_lb(s['o'])}  {_lb(s['h'])}  {_lb(s['l'])}  {_lb(s['c'])}"
            )
    return linie


def main() -> None:
    parser = argparse.ArgumentParser(description="Dossier w formie do czytania.")
    parser.add_argument("--dzien", default=None,
                        help="Dzień dossier (domyślnie najnowszy).")
    parser.add_argument("--ticker", default=None,
                        help="Jedna spółka, ze świecami 1D/1W/1M.")
    parser.add_argument("--json", action="store_true",
                        help="Surowy JSON zamiast tekstu.")
    parser.add_argument("--dni", action="store_true",
                        help="Wypisz tylko dni, na które istnieje dossier.")
    args = parser.parse_args()

    if args.dni:
        for d in db.dni_dossier():
            print(d)
        return

    dni = db.dni_dossier()
    if not dni:
        print("Brak dossier w bazie. Uruchom scripts/przygotuj_dossier.py.")
        sys.exit(1)
    dzien = args.dzien or dni[0]

    wpisy = db.wczytaj_dossier(dzien)
    if not wpisy:
        print(f"Brak dossier na {dzien}. Dostępne dni: {', '.join(dni[:10])}")
        sys.exit(1)

    if args.ticker:
        szukany = args.ticker.upper()
        wpisy = [w for w in wpisy if w["ticker"].upper() == szukany]
        if not wpisy:
            print(f"{szukany} nie ma w dossier na {dzien}.")
            sys.exit(1)

    if args.json:
        print(json.dumps(wpisy, ensure_ascii=False, indent=2))
        return

    # Kolejność jak przy zbiórce: najpierw wskazane przez najwięcej rankingów.
    wpisy.sort(key=lambda w: (-w.get("liczba_zrodel", 0),
                              w.get("srednie_miejsce", 99), w["ticker"]))

    print(f"DOSSIER NA {dzien} — {len(wpisy)} "
          f"{'spółka' if len(wpisy) == 1 else 'spółek'}")
    print("Wszystkie liczby policzone z notowań, nic tu nie jest oceną.")
    for wpis in wpisy:
        print()
        print("\n".join(naglowek(wpis)))
        print("\n".join(poziomy_tekst(wpis)))
        print("\n".join(reszta_tekst(wpis)))
        if args.ticker:
            print("\n".join(swiece_tekst(wpis)))
    if not args.ticker:
        print()
        print("Świece 1D/1W/1M dla pojedynczej spółki: "
              "python scripts/pokaz_dossier.py --ticker <TICKER>")


if __name__ == "__main__":
    main()
