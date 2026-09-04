"""
Modul vs Sektor — porownanie z mediana sektora.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from ui.common import (
    SECTOR_METRICS,
    _personalize_columns,
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 6 — vs Sektor: dynamiczne porównanie spółki z medianą jej sektora
# ---------------------------------------------------------------------------
def render_sector():
    st.write(
        "Sprawdza, jak konkretna spółka wypada na tle **mediany swojego sektora** "
        "w bieżącej migawce — to jest porównanie liczone na żywo na aktualnych "
        "danych (w przeciwieństwie do ogólnych progów w dymkach w Screenerze, "
        "które są statyczne)."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        stocks = df[df["Typ"] == "stock"].copy()

        if "Sektor" not in stocks.columns:
            st.info("Ta migawka nie ma jeszcze danych sektorowych — uruchom skan ponownie po aktualizacji kodu.")
        else:
            stocks = stocks[stocks["Sektor"].notna() & (stocks["Sektor"] != "Nieznany")]
            if stocks.empty:
                st.info("Brak spółek z rozpoznanym sektorem w tej migawce.")
            else:
                ticker_choice = st.selectbox(
                    "Spółka", sorted(stocks["Ticker"].unique().tolist()),
                    format_func=lambda t: f"{t} — {stocks.set_index('Ticker').loc[t, 'Nazwa']}",
                    key="sector_ticker",
                )
                row = stocks[stocks["Ticker"] == ticker_choice].iloc[0]
                sector = row["Sektor"]
                peers = stocks[stocks["Sektor"] == sector]
                st.caption(f"Sektor: **{sector}** — {len(peers)} spółek w tej migawce (w tym {ticker_choice})")

                if len(peers) < 3:
                    st.warning(
                        "Za mało spółek w tym sektorze w bieżącej migawce, żeby mediana była "
                        "wiarygodna (potrzeba co najmniej 3 — zwiększ uniwersum albo poczekaj "
                        "na kolejne skany)."
                    )

                comp_rows = []
                for col, direction in SECTOR_METRICS:
                    if col not in peers.columns:
                        continue
                    numeric_peers = pd.to_numeric(peers[col], errors="coerce")
                    median_val = numeric_peers.median()
                    own_val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]

                    if pd.isna(own_val) or pd.isna(median_val):
                        ocena, diff_txt = "brak danych", "—"
                    else:
                        diff_pct = ((own_val - median_val) / abs(median_val) * 100) if median_val != 0 else None
                        better = (own_val > median_val) if direction == "higher" else (own_val < median_val)
                        if diff_pct is not None and abs(diff_pct) < 5:
                            ocena = "⚪ Podobnie do sektora"
                        elif better:
                            ocena = "🟢 Lepiej niż mediana"
                        else:
                            ocena = "🔴 Gorzej niż mediana"
                        diff_txt = f"{diff_pct:+.1f}%" if diff_pct is not None else "—"

                    comp_rows.append({
                        "Wskaźnik": col,
                        "Kierunek": "wyżej = lepiej" if direction == "higher" else "niżej = lepiej",
                        ticker_choice: None if pd.isna(own_val) else round(float(own_val), 2),
                        "Mediana sektora": None if pd.isna(median_val) else round(float(median_val), 2),
                        "Różnica": diff_txt,
                        "Ocena": ocena,
                    })

                st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, height=480, hide_index=True)

                st.divider()
                st.subheader(
                    f"Wszystkie spółki w sektorze „{sector}”",
                    help="Pełna lista spółek z tego samego sektora w bieżącej migawce, do "
                         "bezpośredniego porównania obok siebie.",
                )
                default_sector_cols = ["Rynek", "Buy Score"] + [m for m, _ in SECTOR_METRICS]
                active_sector_cols = _personalize_columns(
                    pref_key="sector_columns",
                    available_columns=list(peers.columns),
                    default_columns=default_sector_cols,
                    mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
                    label="Personalizuj kolumny tej tabeli",
                )
                peers = _with_tradingview_link(peers)
                sector_cols = [c for c in active_sector_cols if c in peers.columns]
                sort_col = "Buy Score" if "Buy Score" in sector_cols else "Cena"
                _render_table(peers[sector_cols].sort_values(sort_col, ascending=False), height=400)
                st.download_button(
                    "⬇️ Pobierz CSV (wszystkie dane sektora)", peers.to_csv(index=False).encode("utf-8"),
                    file_name=f"sektor_{sector}_{dates[0]}.csv",
                )
