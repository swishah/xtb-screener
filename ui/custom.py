"""
Modul Wlasny scoring — ranking na bazie wlasnych wag.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from core.scanner import backtest_strategy
from ui.common import (
    INDICATOR_HELP,
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 9 — Własny scoring: kreator wag zamiast sztywnych strategii
# ---------------------------------------------------------------------------
# (label, kolumna, kierunek "higher"/"lower" = co jest lepsze, domyślna waga)
CUSTOM_COMPONENTS = [
    ("Spadek od ATH (duży = lepiej)", "pct_from_ath", "lower", 2),
    ("ROE", "ROE (%)", "higher", 1),
    ("Marża operacyjna", "Marża Operac. (%)", "higher", 1),
    ("Marża netto", "Marża netto (%)", "higher", 1),
    ("Wzrost przychodów", "Wzrost przychodów (%)", "higher", 1),
    ("Wzrost EPS", "Wzrost EPS (%)", "higher", 1),
    ("Dług/Kapitał (niższy = lepiej)", "Dług/Kapitał", "lower", 1),
    ("C/Z – P/E (niższe = taniej)", "C/Z (P/E)", "lower", 1),
    ("Stopa dywidendy", "Stopa Dyw. (%)", "higher", 1),
    ("RSI (niższe = wyprzedanie)", "RSI", "lower", 1),
    ("Wolumen rosnący", "volume_ratio", "higher", 0),
    ("Payout ratio (niższy = bezpieczniej)", "Payout ratio (%)", "lower", 0),
    ("Zmiana ceny 1Y (niższa = jeszcze niezauważona)", "Zmiana ceny (1Y%)", "lower", 0),
]


def _component_score(series: pd.Series, direction: str) -> pd.Series:
    """Percentylowa pozycja spółki na tle reszty (0-1) — działa niezależnie od
    jednostek/skali danej kolumny. 'higher' = wyższa wartość = wyższy wynik,
    'lower' = niższa wartość = wyższy wynik."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(pct=True, ascending=(direction == "higher"))


def _compute_custom_score(pool: pd.DataFrame, weights: dict[str, int]) -> pd.Series | None:
    total_weight = sum(weights.values())
    if total_weight == 0:
        return None
    score = pd.Series(0.0, index=pool.index)
    for _, col, direction, _ in CUSTOM_COMPONENTS:
        w = weights.get(col, 0)
        if w == 0 or col not in pool.columns:
            continue
        score = score + w * _component_score(pool[col], direction).fillna(0.5)
    return (score / total_weight * 100).round(1)


def render_custom():
    st.write(
        "Zamiast sztywnych strategii — ustaw własne wagi dla wskaźników, które są dla "
        "Ciebie ważne. 0 = pomiń wskaźnik całkowicie. Wynik liczony jest jako pozycja "
        "percentylowa na tle reszty rynku (0-100), więc suwaki działają niezależnie od "
        "jednostek poszczególnych kolumn."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        stocks = df[df["Typ"] == "stock"].copy()

        weights: dict[str, int] = {}
        cw_cols = st.columns(3)
        for i, (label, col, direction, default) in enumerate(CUSTOM_COMPONENTS):
            with cw_cols[i % 3]:
                weights[col] = st.slider(
                    label, 0, 5, default, key=f"cw_{col}",
                    help=INDICATOR_HELP.get(col, "0 = pomiń ten wskaźnik całkowicie w Twojej formule."),
                )

        custom_score = _compute_custom_score(stocks, weights)
        if custom_score is None:
            st.warning("Ustaw przynajmniej jedną wagę większą od 0.")
        else:
            stocks["Własny wynik"] = custom_score
            ranked = stocks.sort_values("Własny wynik", ascending=False).head(30)
            ranked = _with_tradingview_link(ranked)
            active_cols = [col for _, col, _, _ in CUSTOM_COMPONENTS if weights.get(col, 0) > 0]
            show_cols = ["Ticker", "Nazwa", "Rynek", "Cena", "TradingView", "Własny wynik"] + active_cols + ["Liczba flag"]
            show_cols = [c for c in dict.fromkeys(show_cols) if c in ranked.columns]
            _render_table(ranked[show_cols], height=600)

            st.divider()
            st.subheader(
                "Backtest własnych wag",
                help="Sprawdza historyczną skuteczność DOKŁADNIE tej kombinacji wag na zapisanych "
                     "migawkach — wyższy średni zwrot i win rate = lepiej sprawdzająca się "
                     "formuła w przeszłości.",
            )
            st.caption(
                "Sprawdza historyczną skuteczność DOKŁADNIE tej kombinacji wag na "
                "bazie zapisanych migawek — tak samo jak w zakładce Backtest strategii."
            )
            n_snapshots = len(dates)
            if n_snapshots < 3:
                st.info(f"Masz {n_snapshots} migawkę/migawki — potrzeba co najmniej kilku do backtestu.")
            else:
                bc1, bc2 = st.columns(2)
                with bc1:
                    cw_top_n = st.slider(
                    "TOP N spółek", 1, 20, 5, key="cw_top_n",
                    help="Ile najlepszych spółek wg Twojej formuły 'kupujesz' w każdym oknie testowym.",
                )
                with bc2:
                    cw_max_hold = max(1, n_snapshots - 1)
                    if cw_max_hold < 2:
                        cw_hold = 1
                        st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
                    else:
                        cw_hold = st.slider(
                            "Trzymaj przez (liczba skanów)", 1, cw_max_hold, min(5, cw_max_hold), key="cw_hold",
                            help="Ile kolejnych skanów 'trzymasz' pozycję przed symulowaną sprzedażą.",
                        )

                if st.button("Uruchom backtest tych wag"):
                    with st.spinner("Liczę scoring dla każdej historycznej migawki..."):
                        df_all = db.load_all_snapshots()
                        stocks_all = df_all[df_all["Typ"] == "stock"].copy()
                        stocks_all["Własny wynik"] = stocks_all.groupby("scan_date", group_keys=False).apply(
                            lambda g: _compute_custom_score(g, weights)
                        )
                        cw_bt = backtest_strategy(stocks_all, "Własny wynik", top_n=cw_top_n, hold_snapshots=cw_hold)
                    if cw_bt.empty:
                        st.warning("Za mało danych dla tej kombinacji parametrów.")
                    else:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Śr. zwrot na okno", f"{cw_bt['Śr. zwrot %'].mean():.2f}%",
                                  help="Średni zwrot % z każdego przetestowanego okna (kupno TOP N, "
                                       "trzymanie K skanów, sprzedaż).")
                        m2.metric("Win rate (średni)", f"{cw_bt['Win rate %'].mean():.1f}%",
                                  help="Jaki % przetestowanych okien zakończył się zyskiem.")
                        m3.metric("Liczba przetestowanych okien", len(cw_bt),
                                  help="Ile historycznych okien czasowych zostało przetestowanych — "
                                       "więcej = bardziej wiarygodny wynik.")
                        equity = (1 + cw_bt["Śr. zwrot %"] / 100).cumprod() - 1
                        st.line_chart(pd.DataFrame(
                            {"Skumulowany zwrot %": (equity * 100).round(2)}, index=cw_bt["Data wyjścia"]
                        ))
                        _render_table(cw_bt, height=300)
