from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.markets import STOCK_GROUPS, ETF_MAP, VERIFIED_TICKERS  # noqa: E402
from core import db  # noqa: E402
from core.scanner import (  # noqa: E402
    compute_indicators, price_history_for_backtest, get_sp500_map, get_sp400_map, STRATEGIES,
)

st.set_page_config(page_title="XTB Screener", layout="wide")
st.title("📊 XTB Stock & ETF Screener")
st.caption(
    "Dane historyczne/fundamentalne: Yahoo Finance. Uniwersum tickerów oparte o "
    "składy głównych indeksów + popularne ETF-y UCITS — zweryfikuj dostępność "
    "konkretnego instrumentu w platformie XTB przed transakcją."
)


@st.cache_data(ttl=24 * 3600)
def _us_maps() -> tuple[dict, dict]:
    return get_sp500_map(), get_sp400_map()


sp500_map, sp400_map = _us_maps()
ALL_NAMES = {t: n for g in STOCK_GROUPS.values() for t, n in g.items()}
ALL_NAMES.update(ETF_MAP)
ALL_NAMES.update(sp500_map)
ALL_NAMES.update(sp400_map)

tab_screen, tab_strategie, tab_overview, tab_backtest = st.tabs(
    ["🔍 Screener", "🧭 Strategie", "🌍 Globalny przegląd", "⏪ Backtest spółki"]
)

# ---------------------------------------------------------------------------
# TAB 1 — Screener na bazie ostatniej zapisanej migawki
# ---------------------------------------------------------------------------
with tab_screen:
    dates = db.list_dates()
    if not dates:
        st.warning(
            "Brak zapisanych migawek w bazie jeszcze. Uruchom `python scripts/run_daily_scan.py` "
            "lokalnie albo poczekaj na pierwszy przebieg GitHub Actions."
        )
    else:
        chosen_date = st.selectbox("Data migawki", dates, index=0)
        df = db.load_snapshot(chosen_date)
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany (stara migawka sprzed dodania filtra rynków)"

        only_verified = st.checkbox("Pokaż tylko tickery ręcznie zweryfikowane na XTB", value=False)
        if only_verified and VERIFIED_TICKERS:
            df = df[df["Ticker"].isin(VERIFIED_TICKERS)]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            typ_options = ["Wszystkie"] + sorted(df["Typ"].dropna().unique().tolist())
            kind_choice = st.selectbox("Typ", typ_options, index=0)

        pool = df if kind_choice == "Wszystkie" else df[df["Typ"] == kind_choice]

        with col2:
            market_options = ["Wszystkie"] + sorted(pool["Rynek"].dropna().unique().tolist())
            market_choice = st.selectbox("Rynek / kraj", market_options, index=0)
        with col3:
            min_score = st.slider("Min. Buy Score", 0, 9, 0)
        with col4:
            max_ath = st.slider("Maks. % od ATH (np. -30 = co najmniej -30%)", -90, 0, 0)

        filtered = pool.copy()
        if market_choice != "Wszystkie":
            filtered = filtered[filtered["Rynek"] == market_choice]
        filtered = filtered[
            (filtered["Buy Score"] >= min_score) & (filtered["pct_from_ath"] <= max_ath)
        ].sort_values("Buy Score", ascending=False)

        st.dataframe(filtered, use_container_width=True, height=600)
        st.download_button(
            "⬇️ Pobierz CSV", filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"screener_{chosen_date}.csv",
        )

# ---------------------------------------------------------------------------
# TAB 2 — Strategie: wymienne "obiektywy" patrzenia na te same dane
# ---------------------------------------------------------------------------
STRATEGY_DESCRIPTIONS = {
    "Deep Value (spadki od ATH)": (
        "Premiuje duży dystans od ATH, ale tylko gdy fundamenty (ROE, marża "
        "operacyjna, wzrost EPS, zadłużenie) wciąż wyglądają zdrowo — ma to "
        "odsiewać 'spadające noże' od realnych okazji."
    ),
    "Momentum": (
        "Premiuje spółki w silnym, potwierdzonym trendzie wzrostowym: cena nad "
        "wszystkimi średnimi, byczy MACD, rosnący wolumen, blisko ATH, RSI w "
        "zdrowej strefie (50-70, nie wykupione)."
    ),
    "Dywidendowa": (
        "Premiuje solidną stopę dywidendy przy zdrowych fundamentach i "
        "historii nieprzerwanych wypłat przez ostatnie 3 lata."
    ),
}
STRATEGY_COLUMNS = {
    "Deep Value (spadki od ATH)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "pct_from_ath", "ROE (%)",
        "Marża Operac. (%)", "Wzrost EPS (%)", "Dług/Kapitał", "RSI",
    ],
    "Momentum": [
        "Ticker", "Nazwa", "Rynek", "Cena", "RSI", "volume_ratio",
        "SMA20", "SMA50", "pct_from_ath",
    ],
    "Dywidendowa": [
        "Ticker", "Nazwa", "Rynek", "Cena", "Stopa Dyw. (%)",
        "Lata z dywidendą (3Y)", "C/Z (P/E)", "ROE (%)", "Dług/Kapitał",
    ],
}

with tab_strategie:
    strategy_name = st.selectbox("Strategia", list(STRATEGIES.keys()))
    st.caption(STRATEGY_DESCRIPTIONS[strategy_name])
    score_col, _ = STRATEGIES[strategy_name]

    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        if score_col not in df.columns:
            st.warning(
                "Ta migawka powstała przed dodaniem tej strategii — uruchom skan "
                "ponownie (Actions → Run workflow), żeby ją policzyć."
            )
        else:
            ranked = df[df["Typ"] == "stock"].sort_values(score_col, ascending=False).head(30)
            display_cols = [c for c in STRATEGY_COLUMNS[strategy_name] + [score_col] if c in ranked.columns]
            st.dataframe(ranked[display_cols], use_container_width=True, height=600)

# ---------------------------------------------------------------------------
# TAB 3 — Globalny przegląd: kondycja całego rynku, niezależnie od strategii
# ---------------------------------------------------------------------------
with tab_overview:
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        stocks = df[df["Typ"] == "stock"].copy()

        st.subheader("Szerokość rynku (breadth)")
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

        c1.metric("% spółek > SMA200", f"{above200:.0f}%" if above200 is not None else "brak danych")
        c2.metric("% spółek > SMA50", f"{above50:.0f}%" if above50 is not None else "brak danych")
        c3.metric("Średnie RSI (cały rynek)", f"{avg_rsi:.1f}" if avg_rsi is not None else "brak danych")
        c4.metric("% z Buy Score ≥ 5", f"{buy5:.0f}%" if buy5 is not None else "brak danych")
        st.caption(
            "Wysoki % spółek nad SMA200 = szeroka hossa (ciągnie wiele spółek naraz). "
            "Niski % przy rosnących indeksach = wzrost napędzany tylko kilkoma dużymi spółkami."
        )

        st.subheader("Heatmapa rynków")
        agg_cols = {}
        if "Buy Score" in stocks.columns:
            agg_cols["Śr. Buy Score"] = ("Buy Score", "mean")
        if "pct_from_ath" in stocks.columns:
            agg_cols["Śr. % od ATH"] = ("pct_from_ath", "mean")
        agg_cols["Liczba spółek"] = ("Ticker", "count")
        agg = stocks.groupby("Rynek").agg(**agg_cols).round(2)
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

        st.subheader("Rozkład RSI (cały rynek)")
        if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty:
            counts, edges = np.histogram(stocks["RSI"].dropna(), bins=10, range=(0, 100))
            hist_df = pd.DataFrame(
                {"Liczba spółek": counts},
                index=[f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(counts))],
            )
            st.bar_chart(hist_df)
        else:
            st.info("Brak danych RSI do histogramu.")

        st.subheader("Top ruchy dnia")
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
                st.dataframe(
                    merged.sort_values("Zmiana %", ascending=False).head(10)[show_cols],
                    use_container_width=True,
                )
            with cold:
                st.write("📉 Największe spadki")
                st.dataframe(
                    merged.sort_values("Zmiana %", ascending=True).head(10)[show_cols],
                    use_container_width=True,
                )
        else:
            st.info("Top ruchy pojawią się po drugiej migawce (potrzebne porównanie dzień do dnia).")

# ---------------------------------------------------------------------------
# TAB 3 — Backtest: jak wyglądała spółka X dni/tygodni/miesięcy temu
# ---------------------------------------------------------------------------
with tab_backtest:
    ticker = st.selectbox("Spółka / ETF", sorted(ALL_NAMES.keys()),
                           format_func=lambda t: f"{t} — {ALL_NAMES[t]}")

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
        if df_price.empty:
            st.info("Brak danych cenowych.")
        else:
            back_days = st.slider("Cofnij się o (dni handlowych)", 0, min(500, len(df_price) - 30), 0)
            as_of = df_price.index[-1 - back_days]
            price_then = float(df_price.loc[:as_of, "Close"].iloc[-1])
            ind = compute_indicators(df_price, price_then, as_of=as_of)
            st.write(f"Stan na: **{as_of.date()}**, cena: **{price_then:.2f}**")
            st.json(ind)
            st.line_chart(df_price.loc[:as_of, "Close"])
