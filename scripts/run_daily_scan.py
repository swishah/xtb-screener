"""
Uruchamiane codziennie przez GitHub Actions (.github/workflows/daily_scan.yml).
Skanuje wszystkie grupy akcji + ETF-y, zapisuje migawkę do data/history.db.
Workflow commituje i pushuje zmieniony plik bazy z powrotem do repo. Na końcu
sprawdza, czy jakaś spółka wskoczyła dziś do TOP 10 którejś strategii, i jeśli
tak — wysyła powiadomienie (Discord/Telegram/e-mail, o ile skonfigurowane).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.markets import STOCK_GROUPS, ETF_MAP  # noqa: E402
from core.scanner import analyze_group, get_sp500_map, get_sp400_map, STRATEGIES  # noqa: E402
from core.db import (  # noqa: E402
    save_snapshot, list_dates, load_snapshot, wlasne_wg_typu,
)
from core.alerts import check_top10_newcomers  # noqa: E402
from core.rekomendacje import rekomendacje_gpw  # noqa: E402
from core.rekomendacje_swiat import uzupelnij as rekomendacje_swiat  # noqa: E402



def _uzupelnij_rekomendacje(rows: list[dict]) -> None:
    """
    Uzupełnia rekomendacje analityków z dwóch dodatkowych źródeł.

    KOLEJNOŚĆ ŹRÓDEŁ JEST CELOWA i wynika z metodologii, nie z wygody:

    1. **Yahoo** — konsensus wielu analityków. Zostaje wszędzie tam, gdzie
       jest; niczego nie nadpisujemy.
    2. **stockanalysis.com** — też konsensus wielu analityków, więc wartości
       są PORÓWNYWALNE z Yahoo. Stąd drugie miejsce. Pokrywa Londyn,
       Frankfurt, Mediolan, Wiedeń, Lizbonę, Warszawę i kilka innych giełd,
       na których Yahoo ma dziury (Londyn: 35% pokrycia).
    3. **biznesradar.pl** — pojedyncze rekomendacje polskich domów
       maklerskich. INNA metodologia (kilka rekomendacji zamiast konsensusu
       kilkunastu analityków), więc dopiero na końcu — dla mniejszych spółek
       z GPW, których nie zna żadne z poprzednich źródeł.

    Przy każdej wartości zapisujemy źródło w osobnej kolumnie. Bez tego
    użytkownik widziałby jedną liczbę „rekomendacja” pochodzącą z trzech
    różnych metod liczenia i nie miałby jak tego odróżnić.
    """
    _uzupelnij_ze_swiata(rows)
    _uzupelnij_rekomendacje_gpw(rows)


def _uzupelnij_ze_swiata(rows: list[dict]) -> None:
    """
    Konsensus ze stockanalysis.com dla spółek, których Yahoo nie pokrywa.

    Odpytujemy WYŁĄCZNIE spółki z faktyczną luką — to jedno zapytanie na
    spółkę, więc lista bez filtrowania oznaczałaby 1300 zapytań zamiast ~150.
    """
    braki: list[tuple[str, float | None]] = []
    for r in rows:
        if _ma_rekomendacje(r):
            continue
        try:
            kurs = float(r.get("Cena"))
        except (TypeError, ValueError):
            kurs = None
        braki.append((str(r.get("Ticker", "")), kurs))

    if not braki:
        return

    dane = rekomendacje_swiat(braki)
    if not dane:
        print("ℹ️ Rekomendacje świat: brak danych ze źródła — pomijam.")
        return

    for r in rows:
        d = dane.get(str(r.get("Ticker", "")))
        if not d or _ma_rekomendacje(r):
            continue
        r["Rekomendacja analityków"] = d["rekomendacja"]
        r["Liczba analityków"] = d["liczba"]
        if d["cena_docelowa"] is not None:
            r["Cena docelowa (analitycy)"] = d["cena_docelowa"]
        r["Źródło rekomendacji"] = "stockanalysis"
        r["Rekomendacja z dnia"] = "BRAK"

    print(f"🌍 Rekomendacje świat: uzupełniono {len(dane)} spółek "
          f"(sprawdzono {len(braki)}).")


def _uzupelnij_rekomendacje_gpw(rows: list[dict]) -> None:
    """
    Dokłada rekomendacje domów maklerskich tam, gdzie nadal nic nie ma.

    Yahoo pokrywa 90% spółek z S&P 500, ale tylko 15% ze sWIG80 — bez
    rekomendacji zostają nawet mBank, Orange Polska czy Inter Cars. Jedno
    zapytanie do biznesradar.pl uzupełnia całą polską giełdę naraz.

    NADPISUJEMY WYŁĄCZNIE PUSTE POLA. Gdzie Yahoo ma konsensus, tam zostaje —
    to dwie różne metodologie (konsensus wielu analityków kontra pojedyncze
    rekomendacje domów maklerskich) i mieszanie ich dałoby liczbę, której nie
    da się zinterpretować. Źródło zapisujemy w osobnej kolumnie, żeby przy
    każdej wartości było wiadomo, skąd pochodzi.
    """
    dane = rekomendacje_gpw()
    if not dane:
        print("ℹ️ Rekomendacje GPW: brak danych ze źródła — pomijam uzupełnianie.")
        for r in rows:
            r.setdefault("Źródło rekomendacji", "Yahoo" if _ma_rekomendacje(r) else "BRAK")
            r.setdefault("Rekomendacja z dnia", "BRAK")
        return

    uzupelnione = 0
    for r in rows:
        if _ma_rekomendacje(r):
            # Puste źródło znaczy, że wartość przyszła z Yahoo — poprzednia
            # warstwa podpisuje swoje wpisy sama.
            r.setdefault("Źródło rekomendacji", "Yahoo")
            r.setdefault("Rekomendacja z dnia", "BRAK")
            continue

        d = dane.get(str(r.get("Ticker", "")))
        if not d:
            r["Źródło rekomendacji"] = "BRAK"
            r["Rekomendacja z dnia"] = "BRAK"
            continue

        r["Rekomendacja analityków"] = d["rekomendacja"]
        r["Liczba analityków"] = d["liczba"]
        if d["cena_docelowa"] is not None:
            r["Cena docelowa (analitycy)"] = d["cena_docelowa"]
        r["Źródło rekomendacji"] = f"biznesradar ({d['domy']})"
        r["Rekomendacja z dnia"] = d["ostatnia"]
        uzupelnione += 1

    print(f"📊 Rekomendacje GPW: uzupełniono {uzupelnione} spółek "
          f"(źródło zna {len(dane)}).")


def _ma_rekomendacje(r: dict) -> bool:
    """Czy Yahoo podał cokolwiek sensownego."""
    w = str(r.get("Rekomendacja analityków", "")).strip().lower()
    return w not in ("", "brak", "nan", "none")


def main() -> None:
    today = date.today().isoformat()
    all_rows: list[dict] = []

    groups = dict(STOCK_GROUPS)
    groups["USA (S&P 500)"] = get_sp500_map()
    groups["USA (S&P 400 MidCap)"] = get_sp400_map()

    for label, ticker_map in groups.items():
        print(f"🔄 {label} ({len(ticker_map)} tickerów)...")
        all_rows.extend(analyze_group(ticker_map, kind="stock", label=label, market_override=label))

    # Instrumenty dopisane ręcznie przez użytkownika. Bez market_override —
    # rynek rozpoznaje się po sufiksie tickera, bo mogą pochodzić z dowolnej
    # giełdy.
    wlasne_akcje = wlasne_wg_typu("stock")
    if wlasne_akcje:
        print(f"🔄 Własne akcje ({len(wlasne_akcje)})...")
        all_rows.extend(analyze_group(wlasne_akcje, kind="stock", label="Własne"))

    etfy = dict(ETF_MAP)
    etfy.update(wlasne_wg_typu("etf"))
    print(f"🔄 ETF-y ({len(etfy)})...")
    # bez market_override — ETF-y mają zróżnicowane giełdy notowania, więc
    # kraj/rynek jest rozpoznawany po sufiksie tickera (patrz infer_market)
    all_rows.extend(analyze_group(etfy, kind="etf", label="ETF"))

    wlasne_indeksy = wlasne_wg_typu("index")
    if wlasne_indeksy:
        print(f"🔄 Własne indeksy ({len(wlasne_indeksy)})...")
        all_rows.extend(analyze_group(wlasne_indeksy, kind="index", label="Indeksy"))

    _uzupelnij_rekomendacje(all_rows)

    # Migawka sprzed dzisiejszego zapisu — to jest nasze "wczoraj" do porównania.
    prior_dates = list_dates()
    prev_df = load_snapshot(prior_dates[0]) if prior_dates else None

    print(f"💾 Zapisuję migawkę {today}: {len(all_rows)} instrumentów.")
    save_snapshot(today, all_rows)

    today_df = pd.DataFrame(all_rows)
    check_top10_newcomers(STRATEGIES, today_df, prev_df)

    print("✅ Gotowe.")


if __name__ == "__main__":
    main()
