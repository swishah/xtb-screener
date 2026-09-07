"""
Przygotowanie dossier kandydatów do planu dnia.

CO ROBI. Bierze najnowszą migawkę, wyciąga po pięć spółek z czoła każdego
rankingu (`core/kandydaci.py`), a dla tych, które zostaną po deduplikacji
i obcięciu, pobiera dziesięć lat notowań i liczy z nich poziomy techniczne
(`core/poziomy.py`). Wynik ląduje w tabeli `dossier` — jedna paczka na spółkę
na dzień.

CZEGO NIE ROBI: NIE OCENIA. Tu nie ma ani jednej decyzji uznaniowej i nie ma
żadnego modelu językowego. Ten skrypt tylko PRZYGOTOWUJE materiał — komplet
liczb, z których wolno potem wybierać. Dzięki temu chodzi w GitHub Actions
za darmo i codziennie, a jego wynik da się sprawdzić liczbami.

DLACZEGO OSOBNY KROK, A NIE CZĘŚĆ SKANU. Skan przerabia ~1300 instrumentów
i trwa kilkadziesiąt minut; dossier dotyczy dwudziestu i trwa minutę. Sklejenie
ich znaczyłoby, że przy każdej poprawce w dossier trzeba przepuścić cały skan.
Osobno da się też uruchomić dossier ręcznie na wczorajszej migawce.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import bramka, db, kandydaci, poziomy  # noqa: E402

# WYJŚCIE WYMUSZAMY NA UTF-8 I TO NIE JEST OZDOBA.
# Na Windowsie `sys.stdout` dziedziczy kodowanie konsoli (zmierzone: cp1250),
# w którym emoji z naszych komunikatów po prostu nie istnieją — pierwszy
# `print` z ikoną wywala skrypt wyjątkiem UnicodeEncodeError, zanim zdąży
# cokolwiek zrobić. Złapane na zadaniu cyklicznym: uruchomione z powłoki bez
# PYTHONIOENCODING padało w pierwszej linii, a w kodzie nie było widać nic
# podejrzanego.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Odstęp między zapytaniami do Yahoo. Dwadzieścia spółek to nie jest obciążenie,
# ale seria żądań bez przerwy bywa traktowana jak ruch automatyczny.
PRZERWA_S = 0.4

# Ile historii pobieramy. Dziesięć lat, tak jak skan — miesięczne świece
# potrzebują lat, żeby w ogóle powiedzieć cokolwiek o trendzie.
OKRES = "10y"

# Kolumny z migawki, które wędrują do dossier. Świadomie WYBRANE, a nie
# wszystkie: paczka idzie potem do oceny, a sto kolumn na spółkę to sto okazji,
# żeby uwaga poszła nie tam, gdzie trzeba. Bierzemy to, co opisuje spółkę
# (wycena, jakość, ryzyko), i pomijamy to, co i tak przeliczamy z notowań.
KOLUMNY_MIGAWKI = (
    "Nazwa", "Rynek", "Sektor", "Branża", "Waluta", "Cena",
    "C/Z (P/E)", "Forward C/Z", "C/WK (P/B)", "ROE (%)", "ROA (%)",
    "Marża Operac. (%)", "Marża netto (%)", "Marża brutto (%)",
    "Dług/Kapitał", "Wzrost EPS (%)", "Wzrost przychodów (%)",
    "Kapitalizacja (mld)", "Beta", "Zmiana ceny (1Y%)", "pct_from_ath",
    "Stopa Dyw. (%)", "Payout ratio (%)", "Dywidenda nieregularna",
    "Przyszła dywidenda",
    "Cena docelowa (analitycy)", "Rekomendacja analityków", "Liczba analityków",
    "Źródło rekomendacji", "Zmiana ceny docelowej (%)", "Zmiana rekomendacji",
    "Krótkie pozycje (%)", "Źródło krótkich pozycji",
    "Buy Score", "Liczba flag", "Czerwone flagi",
    "RSI", "MACD", "volume_ratio",
)

# Waluty notowane w setnych częściach jednostki. Ta sama pułapka co przy
# alarmach cenowych: Londyn notuje w PENSACH, więc kurs „122,30" to 1,22 funta.
# Flaga jedzie w dossier, żeby przy ocenie było to widać wprost.
PODJEDNOSTKI = {"GBP": "GBp", "ZAC": "ZAc", "ILA": "ILA", "GBX": "GBX"}


def _liczba(w) -> float | None:
    try:
        x = float(w)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # odsiewa NaN


def _podjednostka(waluta: str) -> bool:
    """Czy waluta notowania jest setną częścią jednostki (pensy, agory…)."""
    w = str(waluta or "").strip()
    if not w:
        return False
    # Rozpoznajemy po MAŁEJ literze w kodzie waluty ("GBp" kontra "GBP") —
    # to konwencja Yahoo, a nie nasza. Dopisane kody na wszelki wypadek.
    return w != w.upper() or w.upper() in {"GBX", "ILA", "ZAC"}


def pobierz_notowania(ticker: str) -> pd.DataFrame | None:
    """Dzienne OHLC z Yahoo. Każdy błąd kończy się None, nie wyjątkiem."""
    try:
        df = yf.Ticker(ticker).history(
            period=OKRES, interval="1d", auto_adjust=True, actions=False
        )
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ {ticker}: pobieranie nie powiodło się ({e}).")
        return None
    if df is None or df.empty:
        return None
    return df


def zbuduj_wpis(kandydat: dict, wiersz: dict) -> tuple[dict | None, str]:
    """
    Dossier jednej spółki. Zwraca (wpis, powód odrzucenia).

    Odrzucenie NIE jest błędem — spółka bez miejsca na stop po prostu nie
    nadaje się do planu i lepiej powiedzieć to tutaj niż oddać ją do oceny.
    """
    ticker = kandydat["ticker"]
    df = pobierz_notowania(ticker)
    if df is None:
        return None, "brak notowań"
    if len(df) < 60:
        return None, f"za krótka historia ({len(df)} sesji)"

    # KURS BIERZEMY Z OSTATNIEJ POBRANEJ ŚWIECY, NIE Z MIGAWKI.
    #
    # Pierwsza wersja przekazywała tu cenę z migawki, żeby dossier zgadzało się
    # z resztą aplikacji. Przy codziennym skanie to jedno i to samo — ale gdy
    # migawka jest starsza (weekend, nieudany skan, ręczne uruchomienie),
    # dostawaliśmy poziomy policzone do DZIŚ zestawione z ceną SPRZED KILKU DNI.
    # Bramka mierzy od tej ceny, czy wejście mieści się w 5%, więc plany
    # wychodziłyby oparte na kursie, którego już nie ma. Poziomy i kurs muszą
    # pochodzić z tego samego dnia — a najświeższy wspólny dzień to ostatnia
    # świeca z Yahoo.
    dane = poziomy.zbuduj(df)
    if dane is None:
        return None, "nie dało się policzyć poziomów"

    # Rozjazd wobec migawki NIE jest błędem, ale musi być widoczny: mówi wprost,
    # jak nieaktualne są dane fundamentalne dołożone niżej.
    kurs_migawki = _liczba(wiersz.get("Cena"))
    rozjazd = None
    if kurs_migawki and dane.get("kurs"):
        rozjazd = round((dane["kurs"] - kurs_migawki) / kurs_migawki * 100, 2)

    mozliwy, powod = bramka.mozliwy_plan(dane)
    if not mozliwy:
        return None, powod

    migawka = {
        k: wiersz[k] for k in KOLUMNY_MIGAWKI
        if k in wiersz and wiersz[k] is not None and str(wiersz[k]) != ""
    }
    waluta = str(wiersz.get("Waluta") or "")

    wpis = {
        "ticker": ticker,
        "nazwa": kandydat.get("nazwa") or str(wiersz.get("Nazwa", "")),
        "rynek": kandydat.get("rynek", ""),
        "sektor": kandydat.get("sektor", ""),
        "waluta": waluta,
        "waluta_w_podjednostkach": _podjednostka(waluta),
        "zrodla": kandydat["zrodla"],
        "liczba_zrodel": kandydat["liczba_zrodel"],
        "srednie_miejsce": kandydat["srednie_miejsce"],
        "kurs_migawki": kurs_migawki,
        "rozjazd_wobec_migawki_pct": rozjazd,
        "migawka": migawka,
    }
    wpis.update(dane)
    return wpis, ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Dossier kandydatów do planu dnia.")
    parser.add_argument("--dzien", default=date.today().isoformat(),
                        help="Dzień, pod którym zapisać dossier (domyślnie dziś).")
    parser.add_argument("--ile", type=int, default=kandydaci.MAKS_KANDYDATOW,
                        help="Ilu kandydatów maksymalnie przetworzyć.")
    parser.add_argument("--sucho", action="store_true",
                        help="Policz i wypisz, ale NIE zapisuj do bazy.")
    args = parser.parse_args()

    print(f"📚 Dossier na {args.dzien} (baza: {db.tryb()}).")

    migawka = db.load_latest()
    if migawka is None or migawka.empty:
        print("❌ Brak migawki w bazie — nie ma z czego wybierać kandydatów.")
        sys.exit(1)

    lista = kandydaci.zbierz(migawka)[: args.ile]
    if not lista:
        print("❌ Żaden ranking nie zwrócił kandydatów.")
        sys.exit(1)
    print(f"🎯 {len(lista)} kandydatów z rankingów.")

    wiersze = {str(r["Ticker"]): r for r in migawka.to_dict("records")}

    wpisy: list[dict] = []
    odrzucone: list[tuple[str, str]] = []
    for nr, kandydat in enumerate(lista, start=1):
        ticker = kandydat["ticker"]
        zrodla = ", ".join(z["ranking"] for z in kandydat["zrodla"])
        print(f"[{nr}/{len(lista)}] {ticker} — {zrodla}")
        wpis, powod = zbuduj_wpis(kandydat, wiersze.get(ticker, {}))
        if wpis is None:
            print(f"   ⏭️ pomijam: {powod}")
            odrzucone.append((ticker, powod))
        else:
            r = wpis["rozjazd_wobec_migawki_pct"]
            nota = ""
            if r is not None and abs(r) >= 1:
                nota = f", kurs {r:+.2f}% wobec migawki"
            print(f"   ✔️ {len(wpis['poziomy'])} poziomów, ATR "
                  f"{wpis['atr']} ({wpis['atr_pct']}%), trend "
                  f"{wpis['trend']['1d']}/{wpis['trend']['1w']}/{wpis['trend']['1m']}"
                  f"{nota}")
            wpisy.append(wpis)
        time.sleep(PRZERWA_S)

    print(f"\n📦 Gotowych dossier: {len(wpisy)}, odrzuconych: {len(odrzucone)}.")
    for ticker, powod in odrzucone:
        print(f"   • {ticker}: {powod}")

    if not wpisy:
        print("❌ Nic do zapisania.")
        sys.exit(1)

    if args.sucho:
        print("🧪 Tryb suchy — nic nie zapisuję.")
        return

    zapisane = db.zapisz_dossier(args.dzien, wpisy)
    print(f"💾 Zapisano {zapisane} wpisów do tabeli `dossier`.")


if __name__ == "__main__":
    main()
