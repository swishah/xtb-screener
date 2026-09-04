"""
Modul Backtest spolki.
"""
from __future__ import annotations

import streamlit as st
from core import db
from core.scanner import compute_indicators, price_history_for_backtest
from ui.common import (
    ALL_NAMES,
    _ticker_news,
)

# ---------------------------------------------------------------------------
# TAB 13 — Backtest: jak wyglądała spółka X dni/tygodni/miesięcy temu
# ---------------------------------------------------------------------------
def render_backtest():
    ticker = st.selectbox("Spółka / ETF", sorted(ALL_NAMES.keys()),
                           format_func=lambda t: f"{t} — {ALL_NAMES[t]}")

    with st.expander("📰 Najnowsze newsy dla tej spółki"):
        if st.button("Pobierz najnowsze nagłówki", key="news_btn"):
            with st.spinner("Pobieram newsy z Yahoo Finance..."):
                news_items = _ticker_news(ticker)
            if not news_items:
                st.info("Brak dostępnych newsów dla tej spółki (albo Yahoo ich nie udostępnia dla tego rynku).")
            else:
                for item in news_items:
                    date_part = f" — {item['date']}" if item.get("date") else ""
                    if item.get("link"):
                        st.markdown(f"**[{item['title']}]({item['link']})**{date_part}")
                    else:
                        st.markdown(f"**{item['title']}**{date_part}")
                    st.caption(item.get("publisher", "Nieznane źródło"))
                    st.divider()

    mode = st.radio(
        "Źródło backtestu",
        ["Migawki zapisane w bazie (dokładne dane z tamtego dnia)",
         "Przeliczenie na żywo z historii cen (szybkie, tylko technika)"],
        horizontal=False,
    )

    if mode.startswith("Migawki"):
        hist = db.load_ticker_history(ticker)
        if hist.empty:
            st.info("Brak zapisanych migawek dla tego tickera jeszcze.")
        else:
            st.line_chart(hist.set_index("scan_date")[["Cena", "Buy Score"]])
            pick_date = st.select_slider("Dzień migawki", options=list(hist["scan_date"]))
            st.dataframe(hist[hist["scan_date"] == pick_date].T, use_container_width=True)
    else:
        df_price = price_history_for_backtest(ticker)
        max_back = min(500, len(df_price) - 30)
        if df_price.empty or max_back < 1:
            st.info("Za krótka historia cen dla tej spółki, żeby cofać się w czasie (potrzeba co najmniej ~30 dni notowań).")
        else:
            back_days = st.slider(
                "Cofnij się o (dni handlowych)", 0, max_back, 0,
                help="Przesuwa punkt odniesienia wstecz w historii cen, żeby zobaczyć jak wyglądały "
                     "wskaźniki techniczne X dni handlowych temu.",
            )
            as_of = df_price.index[-1 - back_days]
            price_then = float(df_price.loc[:as_of, "Close"].iloc[-1])
            ind = compute_indicators(df_price, price_then, as_of=as_of)
            st.write(f"Stan na: **{as_of.date()}**, cena: **{price_then:.2f}**")
            st.json(ind)
            st.line_chart(df_price.loc[:as_of, "Close"])
