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
from core.db import save_snapshot, list_dates, load_snapshot  # noqa: E402
from core.alerts import check_top10_newcomers  # noqa: E402


def main() -> None:
    today = date.today().isoformat()
    all_rows: list[dict] = []

    groups = dict(STOCK_GROUPS)
    groups["USA (S&P 500)"] = get_sp500_map()
    groups["USA (S&P 400 MidCap)"] = get_sp400_map()

    for label, ticker_map in groups.items():
        print(f"🔄 {label} ({len(ticker_map)} tickerów)...")
        all_rows.extend(analyze_group(ticker_map, kind="stock", label=label, market_override=label))

    print(f"🔄 ETF-y ({len(ETF_MAP)})...")
    # bez market_override — ETF-y mają zróżnicowane giełdy notowania, więc
    # kraj/rynek jest rozpoznawany po sufiksie tickera (patrz infer_market)
    all_rows.extend(analyze_group(ETF_MAP, kind="etf", label="ETF"))

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
