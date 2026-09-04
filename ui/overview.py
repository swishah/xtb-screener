"""
Modul Globalny przeglad — kondycja calego rynku.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from core import db
from ui.common import (
    _render_table,
)

# ---------------------------------------------------------------------------
# TAB 4 — Globalny przegląd: kondycja całego rynku, niezależnie od strategii
# ---------------------------------------------------------------------------
def render_overview():
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        stocks = df[df["Typ"] == "stock"].copy()

        st.subheader(
            "Szerokość rynku (breadth)",
            help="Wysoki % spółek nad SMA200 = szeroka hossa (ciągnie wiele spółek naraz). "
                 "Niski % przy rosnących indeksach = wzrost napędzany tylko kilkoma dużymi spółkami.",
        )
        c1, c2, c3, c4 = st.columns(4)

        def _pct_above(col: str) -> float | None:
            if col not in stocks.columns:
                return None
            valid = stocks.dropna(subset=[col, "Cena"])
            if valid.empty:
                return None
            return float((valid["Cena"] > valid[col]).mean() * 100)

        above200, above50 = _pct_above("SMA200"), _pct_above("SMA50")
        avg_rsi = float(stocks["RSI"].mean()) if "RSI" in stocks.columns and not stocks["RSI"].isna().all() else None
        buy5 = float((stocks["Buy Score"] >= 5).mean() * 100) if "Buy Score" in stocks.columns else None

        c1.metric("% spółek > SMA200", f"{above200:.0f}%" if above200 is not None else "brak danych",
                  help="Ile % zeskanowanych spółek ma cenę powyżej 200-dniowej średniej — "
                       "klasyczny wyznacznik długoterminowej hossy/bessy.")
        c2.metric("% spółek > SMA50", f"{above50:.0f}%" if above50 is not None else "brak danych",
                  help="Jak wyżej, ale dla średniej 50-dniowej (trend średnioterminowy).")
        c3.metric("Średnie RSI (cały rynek)", f"{avg_rsi:.1f}" if avg_rsi is not None else "brak danych",
                  help="Średnie RSI całego rynku. >50 = generalnie trend wzrostowy, <50 = spadkowy.")
        c4.metric("% z Buy Score ≥ 5", f"{buy5:.0f}%" if buy5 is not None else "brak danych",
                  help="Ile % spółek ma wysoki Buy Score — więcej = więcej okazji technicznych naraz na rynku.")
        st.caption(
            "Wysoki % spółek nad SMA200 = szeroka hossa (ciągnie wiele spółek naraz). "
            "Niski % przy rosnących indeksach = wzrost napędzany tylko kilkoma dużymi spółkami."
        )

        def _show_heatmap(group_col: str, title: str, help_text: str) -> None:
            st.subheader(title, help=help_text)
            if group_col not in stocks.columns:
                st.info(f"Brak kolumny '{group_col}' w tej migawce.")
                return
            valid = stocks[stocks[group_col].notna() & (stocks[group_col] != "Nieznany")]
            if valid.empty:
                st.info("Brak danych do pokazania.")
                return
            agg_cols = {}
            if "Buy Score" in valid.columns:
                agg_cols["Śr. Buy Score"] = ("Buy Score", "mean")
            if "pct_from_ath" in valid.columns:
                agg_cols["Śr. % od ATH"] = ("pct_from_ath", "mean")
            agg_cols["Liczba spółek"] = ("Ticker", "count")
            agg = valid.groupby(group_col).agg(**agg_cols).round(2)
            if "Śr. Buy Score" in agg.columns:
                agg = agg.sort_values("Śr. Buy Score", ascending=False)
            try:
                styled = agg.style
                if "Śr. Buy Score" in agg.columns:
                    styled = styled.background_gradient(cmap="RdYlGn", subset=["Śr. Buy Score"])
                if "Śr. % od ATH" in agg.columns:
                    styled = styled.background_gradient(cmap="RdYlGn", subset=["Śr. % od ATH"])
                st.dataframe(styled, use_container_width=True)
            except ImportError:
                # background_gradient wymaga matplotlib — jeśli go nie ma, pokaż zwykłą tabelę
                st.dataframe(agg, use_container_width=True)

        hm_col1, hm_col2 = st.columns(2)
        with hm_col1:
            _show_heatmap(
                "Rynek", "Heatmapa rynków",
                "Który kraj/giełda ma teraz najwyższy średni Buy Score i największy spadek "
                "od ATH — szybki obraz, który rynek jest 'przeceniony', a który 'drogi'.",
            )
        with hm_col2:
            _show_heatmap(
                "Sektor", "Heatmapa sektorów",
                "Jak wyżej, ale w podziale na sektor gospodarki zamiast kraju notowania.",
            )

        st.subheader(
            "Rozkład RSI (cały rynek)",
            help="Histogram RSI całego zeskanowanego rynku. Dużo spółek po lewej (RSI<30) = "
                 "rynek generalnie wyprzedany, dużo po prawej (RSI>70) = wykupiony.",
        )
        if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty:
            counts, edges = np.histogram(stocks["RSI"].dropna(), bins=10, range=(0, 100))
            hist_df = pd.DataFrame(
                {"Liczba spółek": counts},
                index=[f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(counts))],
            )
            st.bar_chart(hist_df)
        else:
            st.info("Brak danych RSI do histogramu.")

        st.subheader(
            "Top ruchy dnia",
            help="Największe wzrosty/spadki ceny od poprzedniej migawki (dzień do dnia).",
        )
        if len(dates) >= 2:
            prev = db.load_snapshot(dates[1])
            merged = df.merge(
                prev[["Ticker", "Cena"]], on="Ticker", suffixes=("", " (poprzednio)"),
            )
            merged["Zmiana %"] = round(
                ((merged["Cena"] - merged["Cena (poprzednio)"]) / merged["Cena (poprzednio)"]) * 100, 2
            )
            show_cols = [c for c in ["Ticker", "Nazwa", "Rynek", "Cena", "Zmiana %"] if c in merged.columns]
            colu, cold = st.columns(2)
            with colu:
                st.write("📈 Największe wzrosty")
                _render_table(merged.sort_values("Zmiana %", ascending=False).head(10)[show_cols], height=350)
            with cold:
                st.write("📉 Największe spadki")
                _render_table(merged.sort_values("Zmiana %", ascending=True).head(10)[show_cols], height=350)
        else:
            st.info("Top ruchy pojawią się po drugiej migawce (potrzebne porównanie dzień do dnia).")
