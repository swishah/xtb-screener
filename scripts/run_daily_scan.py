"""
Uruchamiane codziennie przez GitHub Actions (.github/workflows/daily_scan.yml).
Skanuje wszystkie grupy akcji + ETF-y, zapisuje migawkę do data/history.db.
Workflow commituje i pushuje zmieniony plik bazy z powrotem do repo.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.markets import STOCK_GROUPS, ETF_MAP  # noqa: E402
from core.scanner import analyze_group, get_sp500_map  # noqa: E402
from core.db import save_snapshot  # noqa: E402


def main() -> None:
    today = date.today().isoformat()
    all_rows: list[dict] = []

    groups = dict(STOCK_GROUPS)
    groups["USA (S&P 500)"] = get_sp500_map()

    for label, ticker_map in groups.items():
        print(f"🔄 {label} ({len(ticker_map)} tickerów)...")
        all_rows.extend(analyze_group(ticker_map, kind="stock", label=label, market_override=label))

    print(f"🔄 ETF-y ({len(ETF_MAP)})...")
    # bez market_override — ETF-y mają zróżnicowane giełdy notowania, więc
    # kraj/rynek jest rozpoznawany po sufiksie tickera (patrz infer_market)
    all_rows.extend(analyze_group(ETF_MAP, kind="etf", label="ETF"))

    print(f"💾 Zapisuję migawkę {today}: {len(all_rows)} instrumentów.")
    save_snapshot(today, all_rows)
    print("✅ Gotowe.")


if __name__ == "__main__":
    main()
