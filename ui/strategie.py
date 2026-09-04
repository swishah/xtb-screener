"""
Modul Strategie — gotowe strategie inwestycyjne.
"""
from __future__ import annotations

import streamlit as st
from core import db
from core.scanner import STRATEGIES
from ui.common import (
    _personalize_columns,
    _render_table,
    _with_tradingview_link,
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
    "Dywidenda-okazja (sezon dywidendowy)": (
        "Szuka spółek, które regularnie płacą dywidendę i zapłaciły w POPRZEDNIM "
        "roku, ale JESZCZE NIE zapłaciły w bieżącym — wypłata jest więc dopiero "
        "przed nimi ('sezon dywidendowy' wciąż w toku). Plus sprawdzone payout "
        "ratio i wzrost przychodów, żeby odróżnić okazję od pułapki dywidendowej."
    ),
    "Jakość fundamentalna (F-Score uproszczony)": (
        "Inspirowane Piotroski F-Score, ale liczone WYŁĄCZNIE na bieżącym stanie "
        "(bez porównań rok-do-roku z pełnych sprawozdań — to spowolniłoby skan "
        "~1300+ spółek). Sprawdza 8 sygnałów jakości: ROA, przepływy operacyjne, "
        "ROE, marża netto, wzrost EPS/przychodów, zadłużenie, marża brutto."
    ),
}
STRATEGY_COLUMNS = {
    "Deep Value (spadki od ATH)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "pct_from_ath", "ROE (%)",
        "Marża Operac. (%)", "Wzrost EPS (%)", "Dług/Kapitał", "RSI", "Liczba flag",
    ],
    "Momentum": [
        "Ticker", "Nazwa", "Rynek", "Cena", "RSI", "volume_ratio",
        "SMA20", "SMA50", "pct_from_ath", "Liczba flag",
    ],
    "Dywidendowa": [
        "Ticker", "Nazwa", "Rynek", "Cena", "Stopa Dyw. (%)",
        "Lata z dywidendą (3Y)", "C/Z (P/E)", "ROE (%)", "Dług/Kapitał", "Liczba flag",
    ],
    "Dywidenda-okazja (sezon dywidendowy)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "Stopa Dyw. (%)",
        "Dyw. w poprzednim roku", "Dyw. w tym roku", "Przyszła dywidenda",
        "Zmiana ceny (1Y%)", "Payout ratio (%)", "Wzrost przychodów (%)",
        "Marża netto (%)", "Liczba flag",
    ],
    "Jakość fundamentalna (F-Score uproszczony)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "ROA (%)", "Przepływy operacyjne (mln)",
        "ROE (%)", "Marża netto (%)", "Wzrost EPS (%)", "Wzrost przychodów (%)",
        "Dług/Kapitał", "Marża brutto (%)", "Liczba flag",
    ],
}

def render_strategie():
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
            active_strategy_cols = _personalize_columns(
                pref_key=f"strategie_columns__{strategy_name}",
                available_columns=list(df.columns),
                default_columns=[c for c in STRATEGY_COLUMNS[strategy_name] if c not in ("Ticker", "Nazwa")],
                mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
                label=f"Personalizuj kolumny dla: {strategy_name}",
            )
            ranked = df[df["Typ"] == "stock"].sort_values(score_col, ascending=False).head(30)
            ranked = _with_tradingview_link(ranked)
            display_cols = [c for c in active_strategy_cols + [score_col] if c in ranked.columns]
            display_cols = list(dict.fromkeys(display_cols))  # usuń ewentualny duplikat score_col
            _render_table(ranked[display_cols], height=600)

        st.divider()
        st.subheader(
            "🔗 Zbieżność strategii",
            help="Spółki, które jednocześnie są w czołówce więcej niż jednej strategii — "
                 "silniejszy, wzajemnie potwierdzony sygnał niż wysoki wynik w tylko jednej.",
        )
        st.caption(
            "Spółki, które jednocześnie znajdują się w czołówce więcej niż jednej "
            "strategii naraz — silniejszy, wzajemnie potwierdzony sygnał niż wysoki "
            "wynik w tylko jednej z nich."
        )
        stocks_df = df[df["Typ"] == "stock"].copy()
        available = {name: col for name, (col, _) in STRATEGIES.items() if col in stocks_df.columns}

        if len(available) < 2:
            st.info(
                "Ta migawka ma policzoną tylko jedną strategię — uruchom skan ponownie, "
                "żeby zbieżność miała sens (potrzeba co najmniej dwóch strategii)."
            )
        else:
            conv_top_n = st.slider(
                "Próg: TOP N per strategia", 5, 50, 15, key="conv_top_n",
                help="Ile najlepszych spółek per strategia liczy się jako 'w czołówce' przy sprawdzaniu zbieżności.",
            )
            membership: dict[str, int] = {}
            for name, col in available.items():
                top_tickers = stocks_df.sort_values(col, ascending=False).head(conv_top_n)["Ticker"]
                for t in top_tickers:
                    membership[t] = membership.get(t, 0) + 1

            conv_tickers = [t for t, cnt in membership.items() if cnt >= 2]
            if not conv_tickers:
                st.info("Przy tym progu TOP N żadna spółka nie pojawia się w więcej niż jednej strategii.")
            else:
                conv_df = stocks_df[stocks_df["Ticker"].isin(conv_tickers)].copy()
                conv_df["Liczba strategii (w TOP N)"] = conv_df["Ticker"].map(membership)
                score_cols = list(available.values())
                show_cols = [c for c in ["Ticker", "Nazwa", "Rynek", "Cena"] + score_cols
                             + ["Liczba strategii (w TOP N)"] if c in conv_df.columns]
                conv_df = conv_df.sort_values(
                    ["Liczba strategii (w TOP N)"] + score_cols, ascending=False
                )
                _render_table(conv_df[show_cols], height=400)
