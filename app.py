from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.markets import STOCK_GROUPS, ETF_MAP, VERIFIED_TICKERS  # noqa: E402
from core import db  # noqa: E402
from core.scanner import (  # noqa: E402
    analyze_ticker, compute_indicators, score_row, deep_value_score,
    price_history_for_backtest, get_current_price, get_sp500_map, get_sp400_map,
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

tab_screen, tab_deep, tab_backtest = st.tabs(
    ["🔍 Screener", "💎 Deep Value (spadki od ATH)", "⏪ Backtest spółki"]
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
            kind_filter = st.multiselect("Typ", ["stock", "etf"], default=["stock", "etf"])
        with col2:
            market_options = sorted(df["Rynek"].dropna().unique().tolist())
            market_filter = st.multiselect("Rynek / kraj", market_options, default=market_options)
        with col3:
            min_score = st.slider("Min. Buy Score", 0, 9, 0)
        with col4:
            max_ath = st.slider("Maks. % od ATH (np. -30 = co najmniej -30%)", -90, 0, 0)

        filtered = df[
            df["Typ"].isin(kind_filter)
            & df["Rynek"].isin(market_filter)
            & (df["Buy Score"] >= min_score)
            & (df["pct_from_ath"] <= max_ath)
        ].sort_values("Buy Score", ascending=False)

        st.dataframe(filtered, use_container_width=True, height=600)
        st.download_button(
            "⬇️ Pobierz CSV", filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"screener_{chosen_date}.csv",
        )

# ---------------------------------------------------------------------------
# TAB 2 — Deep Value: duży spadek od ATH + wciąż zdrowy biznes
# ---------------------------------------------------------------------------
with tab_deep:
    st.write(
        "Ranking wg **Deep Value Score** — premiuje duży dystans od ATH, ale tylko "
        "gdy fundamenty (ROE, marża operacyjna, wzrost EPS, zadłużenie) wciąż wyglądają zdrowo. "
        "To ma odsiewać 'spadające noże' od realnych okazji."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        deep = df[df["Typ"] == "stock"].sort_values("Deep Value Score", ascending=False).head(30)
        st.dataframe(
            deep[["Ticker", "Nazwa", "Rynek", "Cena", "pct_from_ath", "ROE (%)", "Marża Operac. (%)",
                  "Wzrost EPS (%)", "Dług/Kapitał", "RSI", "Deep Value Score", "Buy Score"]],
            use_container_width=True, height=600,
        )

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
