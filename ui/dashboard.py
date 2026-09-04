"""
Modul Dashboard (eksperymentalny) — widok kafelkowy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from core import db
from core.scanner import compute_sentiment_index
from ui.common import (
    _earnings_date,
    _vix_level,
)

# ---------------------------------------------------------------------------
# TAB 5 — Dashboard (eksperymentalny): gęsty widok kafelkowy w stylu terminala
# ---------------------------------------------------------------------------
def _tile_header(title: str, note: str = "") -> None:
    st.markdown(f"**{title}**")
    if note:
        st.caption(note)


def render_dashboard():
    st.warning(
        "🧪 **Tryb eksperymentalny.** Układ inspirowany terminalami tradingowymi. "
        "VIX pochodzi z prawdziwego tickera giełdowego (^VIX) przez Yahoo Finance. "
        "**Wskaźnik nastrojów poniżej to własna metodologia appki** (VIX + szerokość "
        "rynku + RSI) — NIE jest to oficjalny CNN Fear & Greed Index, który nie ma "
        "publicznego API. Dane makro (Fed Funds Rate), pozycjonowanie futures/COT "
        "i towary wciąż wymagałyby dodatkowych, zewnętrznych źródeł — daj znać, "
        "jeśli chcesz je dodać."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
        return

    df = db.load_snapshot(dates[0])
    stocks = df[df["Typ"] == "stock"].copy()
    if "Rynek" not in stocks.columns:
        stocks["Rynek"] = "Nieznany"
    if "Sektor" not in stocks.columns:
        stocks["Sektor"] = "Nieznany"

    def _pct_above(col: str):
        if col not in stocks.columns:
            return None
        valid_rows = stocks.dropna(subset=[col, "Cena"])
        return float((valid_rows["Cena"] > valid_rows[col]).mean() * 100) if not valid_rows.empty else None

    pct_sma20 = _pct_above("SMA20")
    pct_sma50 = _pct_above("SMA50")
    pct_sma200 = _pct_above("SMA200")
    avg_rsi = float(stocks["RSI"].mean()) if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty else None
    vix = _vix_level()
    sentiment = compute_sentiment_index(vix["value"] if vix else None, pct_sma50, pct_sma200, avg_rsi)

    vc1, vc2 = st.columns(2)
    with vc1:
        with st.container(border=True):
            _tile_header("😨 VIX (indeks zmienności)", "Yahoo Finance, ticker ^VIX — dane realne")
            if vix:
                st.metric("VIX", vix["value"], delta=f"{vix['change_pct']}%" if vix["change_pct"] is not None else None,
                          delta_color="inverse",
                          help="Indeks zmienności S&P500. <20 = spokojny rynek, 20-30 = podwyższona "
                               "zmienność, >30 = wysoki niepokój/panika.")
                if vix["value"] > 30:
                    st.caption("🔴 Wysoka zmienność — podwyższony niepokój rynku.")
                elif vix["value"] > 20:
                    st.caption("🟡 Podwyższona zmienność.")
                else:
                    st.caption("🟢 Spokojny rynek.")
            else:
                st.caption("Nie udało się pobrać VIX (brak sieci albo Yahoo tymczasowo niedostępne).")
    with vc2:
        with st.container(border=True):
            _tile_header("🎭 Wskaźnik nastrojów (własna metodologia)", "VIX + szerokość rynku + śr. RSI — nie CNN Fear & Greed")
            if sentiment:
                st.metric(
                    "Wynik (0-100)", sentiment["score"],
                    help="Własny wskaźnik z VIX + szerokości rynku + RSI. <25 ekstremalny strach, "
                         "25-45 strach, 45-55 neutralnie, 55-75 chciwość, >75 ekstremalna chciwość.",
                )
                st.caption(f"**{sentiment['label']}**")
            else:
                st.caption("Za mało danych, żeby policzyć wskaźnik.")

    row1 = st.columns(3)
    row2 = st.columns(3)
    row3 = st.columns(3)

    with row1[0]:
        with st.container(border=True):
            _tile_header("🌍 RYNKI DZIŚ", "Śr. zmiana ceny per rynek")
            if len(dates) >= 2 and "Buy Score" in stocks.columns:
                prev = db.load_snapshot(dates[1])
                merged = stocks.merge(prev[["Ticker", "Cena"]], on="Ticker", suffixes=("", "_poprzednio"))
                merged = merged.dropna(subset=["Cena", "Cena_poprzednio"])
                merged = merged[merged["Cena_poprzednio"] != 0]
                if not merged.empty:
                    merged["Zmiana %"] = (merged["Cena"] - merged["Cena_poprzednio"]) / merged["Cena_poprzednio"] * 100
                    agg = merged.groupby("Rynek")["Zmiana %"].mean().round(2).sort_values(ascending=False)
                    for rynek, chg in agg.head(6).items():
                        arrow = "🟢▲" if chg > 0 else ("🔴▼" if chg < 0 else "⚪")
                        st.write(f"{arrow} **{rynek}** — {chg:+.2f}%")
                else:
                    st.caption("Brak wspólnych tickerów między migawkami.")
            else:
                st.caption("Potrzeba co najmniej 2 migawek, żeby pokazać zmianę dzień do dnia.")

    with row1[1]:
        with st.container(border=True):
            _tile_header("🔥 MAPA CIEPLNA SEKTORA", "Śr. Buy Score per sektor")
            valid = stocks[stocks["Sektor"] != "Nieznany"]
            if not valid.empty and "Buy Score" in valid.columns:
                agg = valid.groupby("Sektor")["Buy Score"].mean().round(2).sort_values(ascending=False)
                tile_cols = st.columns(3)
                for i, (sektor, score) in enumerate(agg.head(6).items()):
                    color = "#1b5e20" if score >= 5 else ("#7f0000" if score <= 2 else "#5c4d00")
                    with tile_cols[i % 3]:
                        st.markdown(
                            f"<div style='background-color:{color};border-radius:8px;padding:8px;"
                            f"text-align:center;margin-bottom:6px;'>"
                            f"<div style='font-size:0.7em;color:#ddd;overflow:hidden;text-overflow:ellipsis;"
                            f"white-space:nowrap;'>{sektor[:14]}</div>"
                            f"<div style='font-size:1.1em;font-weight:bold;color:white'>{score}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
            else:
                st.caption("Brak danych sektorowych w tej migawce.")

    with row1[2]:
        with st.container(border=True):
            _tile_header("📏 SZEROKOŚĆ RYNKU")

            any_data = False
            for label, pct in [("% > SMA20", pct_sma20), ("% > SMA50", pct_sma50), ("% > SMA200", pct_sma200)]:
                if pct is not None:
                    any_data = True
                    st.write(f"{label}: **{pct:.1f}%**")
                    st.progress(min(max(int(pct), 0), 100) / 100)
            if not any_data:
                st.caption("Brak danych technicznych w tej migawce.")

    with row2[0]:
        with st.container(border=True):
            _tile_header("🗺️ MAPA CIEPLNA RYNKÓW", "Śr. Buy Score per giełda")
            if "Buy Score" in stocks.columns and not stocks.empty:
                agg = stocks.groupby("Rynek")["Buy Score"].mean().round(2).sort_values(ascending=False)
                for rynek, score in agg.head(8).items():
                    st.write(f"**{rynek}**: {score}")
                    st.progress(min(max(score / 9, 0), 1))

    with row2[1]:
        with st.container(border=True):
            _tile_header("🎯 TOP SYGNAŁY KUPNA", "Najwyższy Buy Score dzisiaj")
            if "Buy Score" in stocks.columns and not stocks.empty:
                top = stocks.sort_values("Buy Score", ascending=False).head(6)
                for _, r in top.iterrows():
                    st.write(f"🟢 **{r['Ticker']}** — {r.get('Nazwa', '')} (score {r['Buy Score']})")

    with row2[2]:
        with st.container(border=True):
            _tile_header("🚩 NAJWIĘCEJ OSTRZEŻEŃ", "Spółki z największą liczbą czerwonych flag")
            if "Liczba flag" in stocks.columns and not stocks.empty:
                top_flags = stocks[stocks["Liczba flag"] > 0].sort_values("Liczba flag", ascending=False).head(6)
                if top_flags.empty:
                    st.caption("Brak spółek z ostrzeżeniami w tej migawce.")
                else:
                    for _, r in top_flags.iterrows():
                        st.write(f"🔴 **{r['Ticker']}** — {int(r['Liczba flag'])} flag(a/i)")

    with row3[0]:
        with st.container(border=True):
            _tile_header("📅 WYNIKI — WATCHLIST", "Sprawdzane na żądanie (max 10 spółek)")
            wl = db.load_watchlist()
            if wl.empty:
                st.caption("Watchlist jest pusta.")
            elif st.button("Sprawdź daty wyników", key="dash_earnings"):
                any_found = False
                for t in wl["Ticker"].head(10):
                    ed = _earnings_date(t)
                    if ed:
                        any_found = True
                        st.write(f"**{t}**: {ed}")
                if not any_found:
                    st.caption("Brak potwierdzonych dat dla obserwowanych spółek.")

    with row3[1]:
        with st.container(border=True):
            _tile_header("📊 ROZKŁAD RSI")
            if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty:
                counts, edges = np.histogram(stocks["RSI"].dropna(), bins=10, range=(0, 100))
                hist_df = pd.DataFrame(
                    {"Liczba": counts},
                    index=[f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(counts))],
                )
                st.bar_chart(hist_df, height=180)
            else:
                st.caption("Brak danych RSI.")

    with row3[2]:
        with st.container(border=True):
            _tile_header("⭐ WATCHLIST")
            wl = db.load_watchlist()
            if wl.empty:
                st.caption("Pusta.")
            else:
                merge_cols = [c for c in ["Ticker", "Cena", "Buy Score"] if c in stocks.columns]
                merged_wl = wl.merge(stocks[merge_cols], on="Ticker", how="left") if merge_cols else wl
                for _, r in merged_wl.head(8).iterrows():
                    st.write(f"**{r['Ticker']}** — {r.get('Cena', '—')} (score {r.get('Buy Score', '—')})")
