"""
Modul Dywidendy — tanie spolki przed sezonem dywidendowym.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from ui.common import (
    _personalize_columns,
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 8 — Dywidendy: wysoka stopa dywidendy, cena jeszcze nie wzrosła
# ---------------------------------------------------------------------------
def render_dividends():
    st.write(
        "Szuka spółek z wysoką stopą dywidendy (z ostatniego roku) względem ceny, "
        "które **jeszcze nie zdrożały** — plus wskaźniki sprawdzające, czy sytuacja "
        "biznesu się nie pogorszyła (przychody, marże, payout ratio), żeby odróżnić "
        "realną okazję od 'pułapki dywidendowej' (wysoka stopa, bo cena spadła "
        "z powodu problemów w firmie)."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        stocks = df[df["Typ"] == "stock"].copy()

        c1, c2, c3 = st.columns(3)
        with c1:
            min_yield = st.slider(
                "Min. stopa dywidendy (%)", 0.0, 15.0, 4.0, 0.5,
                help="Minimalna stopa dywidendy z ostatniego roku względem obecnej ceny.",
            )
        with c2:
            max_price_change = st.slider(
                "Maks. zmiana ceny w ostatnim roku (%)", -50, 100, 15,
                help="Niżej = szukasz spółek, których cena jeszcze się nie ruszyła (albo spadła) mimo wysokiej dywidendy.",
            )
        with c3:
            max_payout = st.slider(
                "Maks. payout ratio (%)", 0, 200, 80,
                help="Ile % zysku firma wypłaca jako dywidendę. Powyżej 100% oznacza, że wypłaca więcej niż zarabia — sygnał ostrzegawczy.",
            )

        only_before_season = st.checkbox(
            "🗓️ Pokaż tylko spółki PRZED sezonem dywidendowym "
            "(płaciły w zeszłym roku, jeszcze nie zapłaciły w tym)",
            value=False,
        )

        candidates = stocks.copy()
        if "Stopa Dyw. (%)" in candidates.columns:
            candidates = candidates[pd.to_numeric(candidates["Stopa Dyw. (%)"], errors="coerce") >= min_yield]
        if "Zmiana ceny (1Y%)" in candidates.columns:
            candidates = candidates[
                pd.to_numeric(candidates["Zmiana ceny (1Y%)"], errors="coerce") <= max_price_change
            ]
        if "Payout ratio (%)" in candidates.columns:
            payout_num = pd.to_numeric(candidates["Payout ratio (%)"], errors="coerce")
            candidates = candidates[(payout_num <= max_payout) | payout_num.isna()]
        if only_before_season and "Dyw. w poprzednim roku" in candidates.columns and "Dyw. w tym roku" in candidates.columns:
            candidates = candidates[
                (candidates["Dyw. w poprzednim roku"] == "Tak") & (candidates["Dyw. w tym roku"] == "Nie")
            ]

        score_col = "Score: Dywidenda-Okazja"
        sort_col = score_col if score_col in candidates.columns else "Stopa Dyw. (%)"
        candidates = candidates.sort_values(sort_col, ascending=False)

        st.caption(f"Znaleziono **{len(candidates)}** spółek spełniających kryteria.")

        default_dividend_cols = [
            "Rynek", "Stopa Dyw. (%)", "Dyw. w poprzednim roku", "Dyw. w tym roku",
            "Poprzednia dywidenda", "Przyszła dywidenda", "Zmiana ceny (1Y%)",
            "Lata z dywidendą (3Y)", "Payout ratio (%)", "C/Z (P/E)", "ROE (%)",
            "Marża Operac. (%)", "Marża netto (%)", "Wzrost przychodów (%)",
            "Wzrost EPS (%)", "Dług/Kapitał", "Liczba flag",
        ]
        candidates = _with_tradingview_link(candidates)
        active_dividend_cols = _personalize_columns(
            pref_key="dividends_columns",
            available_columns=list(candidates.columns),
            default_columns=default_dividend_cols,
            mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
        )
        display_cols = list(dict.fromkeys(
            [c for c in active_dividend_cols if c in candidates.columns] + [score_col]
        ))
        _render_table(candidates[display_cols], height=600)
        st.download_button(
            "⬇️ Pobierz CSV (wszystkie dane)", candidates.to_csv(index=False).encode("utf-8"),
            file_name=f"dywidendy_{dates[0]}.csv",
        )
        st.caption(
            "'Dyw. w poprzednim roku' / 'Dyw. w tym roku' pokazują, czy spółka jest jeszcze "
            "PRZED tegoroczną wypłatą (sedno tej strategii) czy już PO. Payout ratio i wzrost "
            "przychodów/marż pokazują, czy dywidenda jest bezpieczna. 'Przyszła dywidenda' "
            "pokazuje BRAK, jeśli Yahoo nie udostępnia potwierdzonej przyszłej daty (częste poza USA)."
        )
