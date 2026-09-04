"""
Modul Backtest strategii.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from core.scanner import STRATEGIES, backtest_strategy
from ui.common import (
    _render_table,
)

# ---------------------------------------------------------------------------
# TAB 12 — Backtest strategii: czy TOP N wg danego score'a faktycznie zarabia?
# ---------------------------------------------------------------------------
def render_bt_strategy():
    st.write(
        "Sprawdza, co by było, gdyby co skan kupić TOP N spółek wg wybranej strategii "
        "i sprzedać je po K kolejnych skanach. Liczone na bazie **zapisanych migawek** "
        "(nie pełnej historii cen) — bo tylko migawki mają realny, historyczny scoring "
        "fundamentalny. Im dłużej appka zbiera codzienne skany, tym wiarygodniejszy wynik."
    )
    dates_all = db.list_dates()
    n_snapshots = len(dates_all)

    if n_snapshots < 2:
        st.info(
            f"Masz na razie {n_snapshots} migawkę/migawki w bazie. Potrzeba co najmniej "
            "kilku(nastu), żeby backtest miał sens — appka zbierze je automatycznie "
            "wraz z kolejnymi uruchomieniami codziennego skanu."
        )
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            bt_strategy_name = st.selectbox("Strategia", list(STRATEGIES.keys()), key="bt_strategy")
        with c2:
            bt_top_n = st.slider(
                "TOP N spółek", 1, 20, 5,
                help="Ile najlepszych spółek wg wybranej strategii 'kupujesz' w każdym oknie testowym.",
            )
        with c3:
            max_hold = max(1, n_snapshots - 1)
            if max_hold < 2:
                bt_hold = 1
                st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
            else:
                bt_hold = st.slider(
                    "Trzymaj przez (liczba skanów)", 1, max_hold, min(5, max_hold),
                    help="Ile kolejnych skanów 'trzymasz' pozycję przed symulowaną sprzedażą.",
                )

        score_col, _ = STRATEGIES[bt_strategy_name]
        df_all = db.load_all_snapshots()
        bt_result = backtest_strategy(df_all, score_col, top_n=bt_top_n, hold_snapshots=bt_hold)

        if bt_result.empty:
            st.warning(
                "Za mało danych dla tej kombinacji parametrów — spróbuj mniejszej liczby "
                "skanów do przetrzymania, albo poczekaj na kolejne migawki."
            )
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Śr. zwrot na okno", f"{bt_result['Śr. zwrot %'].mean():.2f}%",
                      help="Średni zwrot % z każdego przetestowanego okna (kupno TOP N, "
                           "trzymanie K skanów, sprzedaż).")
            m2.metric("Win rate (średni)", f"{bt_result['Win rate %'].mean():.1f}%",
                      help="Jaki % przetestowanych okien zakończył się zyskiem.")
            m3.metric("Liczba przetestowanych okien", len(bt_result),
                      help="Ile historycznych okien czasowych zostało przetestowanych — "
                           "więcej = bardziej wiarygodny wynik.")
            best, worst = bt_result["Śr. zwrot %"].max(), bt_result["Śr. zwrot %"].min()
            m4.metric("Najlepsze / najgorsze okno", f"{best:.1f}% / {worst:.1f}%",
                      help="Zwrot % najlepszego i najgorszego pojedynczego okna w teście.")

            st.caption(
                "Krzywa kapitału zakłada mechaniczne reinwestowanie zwrotu z każdego okna "
                "z rzędu — to uproszczenie (okna się nakładają w czasie), traktuj jako "
                "orientacyjny obraz, nie realną symulację portfela."
            )
            equity = (1 + bt_result["Śr. zwrot %"] / 100).cumprod() - 1
            equity_df = pd.DataFrame(
                {"Skumulowany zwrot %": (equity * 100).round(2)}, index=bt_result["Data wyjścia"]
            )
            st.line_chart(equity_df)

            _render_table(bt_result, height=400)
