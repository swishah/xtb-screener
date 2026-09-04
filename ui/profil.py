"""
Modul Profil spolki — wszystkie dane jednej spolki + brief.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from core.scanner import STRATEGIES, STRATEGY_MAX_SCORES, compute_snowflake, compute_stockrank, generate_brief, get_insider_transactions
from ui.common import (
    ALL_NAMES,
    GROUP_ICONS,
    INDICATOR_GROUPS,
    INDICATOR_HELP,
    _fx_rates,
    _render_radar_chart,
    _render_table,
    _tradingview_url,
)

# ---------------------------------------------------------------------------
# TAB 3 — Profil spółki: wszystkie dane naraz + krótki brief inwestycyjny
# ---------------------------------------------------------------------------
def render_profile():
    st.write(
        "Wpisz spółkę, żeby zobaczyć **wszystkie** zebrane o niej dane naraz, plus "
        "krótki brief łączący wszystkie strategie i najważniejsze wskaźniki "
        "potrzebne do podjęcia decyzji."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
        return

    ticker = st.selectbox(
        "Spółka / ETF", sorted(ALL_NAMES.keys()),
        format_func=lambda t: f"{t} — {ALL_NAMES[t]}", key="profile_ticker",
    )
    df = db.load_snapshot(dates[0])
    row_df = df[df["Ticker"] == ticker]
    if row_df.empty:
        st.warning(
            "Ta spółka nie ma jeszcze danych z najnowszej migawki (np. dodana po "
            "ostatnim skanie) — uruchom skan ponownie albo wybierz inną spółkę."
        )
        return
    row = row_df.iloc[0].to_dict()

    st.subheader(f"{row.get('Nazwa', ticker)} ({ticker})")
    st.caption(f"{row.get('Rynek', '—')} · {row.get('Sektor', 'Nieznany')} / {row.get('Branża', 'Nieznana')}")
    st.link_button("📈 Otwórz wykres na TradingView", _tradingview_url(ticker))

    m1, m2, m3, m4 = st.columns(4)
    cena = row.get("Cena")
    waluta = row.get("Waluta", "")
    m1.metric("Cena", f"{cena} {waluta}" if cena is not None else "BRAK",
              help="Ostatnia cena zamknięcia w walucie notowania spółki.")
    if waluta and waluta != "PLN":
        try:
            rate = _fx_rates((waluta,)).get(waluta)
            if rate and isinstance(cena, (int, float)):
                m2.metric("Cena (PLN)", f"{round(cena * rate, 2)} PLN",
                      help="Cena przeliczona na złote wg bieżącego kursu wymiany (na żywo).")
        except Exception:  # noqa: BLE001
            pass
    m3.metric("Buy Score", row.get("Buy Score", "BRAK"),
              help="Suma podstawowych sygnałów technicznych kupna (RSI, MACD, trend, wolumen, "
                   "dystans od ATH). Wyżej = więcej sygnałów zgadza się naraz.")
    n_flags = row.get("Liczba flag", 0)
    m4.metric("Czerwone flagi", n_flags, delta=None,
              help="Liczba automatycznych ostrzeżeń wykrytych w danych spółki. 0 = brak wykrytych problemów.")

    st.divider()
    st.subheader(
        "📋 Brief inwestycyjny",
        help="Automatyczne, regułowe podsumowanie sytuacji spółki na bazie danych — "
             "nie porada inwestycyjna, tylko zestawienie faktów.",
    )
    for line in generate_brief(row):
        if line.startswith("## "):
            st.markdown(f"#### {line[3:]}")
        else:
            st.write(f"- {line}")
    if row.get("Czerwone flagi", "Brak") != "Brak":
        with st.expander("Zobacz treść czerwonych flag"):
            for f in str(row.get("Czerwone flagi", "")).split("; "):
                st.write(f)

    st.divider()
    st.subheader(
        "🧭 Wszystkie strategie na raz",
        help="Wynik i % maksimum dla każdej z 5 strategii naraz — wyżej % = spółka lepiej "
             "pasuje do danej strategii.",
    )
    strategy_rows = []
    for name, (score_col, _) in STRATEGIES.items():
        score = row.get(score_col)
        max_score = STRATEGY_MAX_SCORES.get(score_col)
        pct = round(score / max_score * 100) if isinstance(score, (int, float)) and max_score else None
        strategy_rows.append({
            "Strategia": name, "Wynik": score, "Maks. możliwy": max_score,
            "% maksimum": pct,
        })
    _render_table(pd.DataFrame(strategy_rows), height=200)

    stocks_universe = df[df["Typ"] == "stock"].copy()
    is_stock = row.get("Typ") == "stock" and ticker in stocks_universe["Ticker"].values

    if is_stock:
        st.divider()
        st.subheader(
            "🎯 StockRank: Quality / Value / Momentum",
            help="Quality = jakość biznesu (ROE, marże, dług). Value = atrakcyjność wyceny "
                 "(niskie C/Z i C/WK, wysoka dywidenda). Momentum = siła trendu (RSI, wolumen, "
                 "dystans od ATH). Każdy 0-100, percentyl na tle rynku — wyżej zawsze lepiej.",
        )
        st.caption(
            "Percentyl (0-100) na tle CAŁEGO zeskanowanego uniwersum akcji w tej migawce "
            "— inspirowane Stockopedia StockRanks."
        )
        ranked = compute_stockrank(stocks_universe)
        rr = ranked[ranked["Ticker"] == ticker].iloc[0]
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Quality", f"{rr['Quality']:.0f}" if pd.notna(rr.get("Quality")) else "BRAK",
                  help="Percentyl jakości biznesu (ROE, marże, dług) na tle rynku. Wyżej = lepiej.")
        rc2.metric("Value", f"{rr['Value']:.0f}" if pd.notna(rr.get("Value")) else "BRAK",
                  help="Percentyl atrakcyjności wyceny (niskie C/Z i C/WK, wysoka dywidenda). Wyżej = taniej.")
        rc3.metric("Momentum", f"{rr['Momentum']:.0f}" if pd.notna(rr.get("Momentum")) else "BRAK",
                  help="Percentyl siły trendu (RSI, wolumen, dystans od ATH). Wyżej = silniejszy trend wzrostowy.")

        st.divider()
        st.subheader(
            "🌸 Profil Snowflake",
            help="5 osi po 0-100 (percentyl na tle rynku): Wycena, Wzrost, Wyniki, Zdrowie, "
                 "Dywidendy. Duży, wypełniony kształt = mocna spółka na wielu frontach naraz.",
        )
        st.caption(
            "5-osiowy profil (inspirowany Simply Wall St) — każda oś to percentyl na tle "
            "reszty uniwersum. Duży, wypełniony obszar = mocna spółka na wielu frontach naraz."
        )
        snow = compute_snowflake(stocks_universe)
        sr = snow[snow["Ticker"] == ticker].iloc[0]
        axis_labels = ["Wycena", "Wzrost", "Wyniki", "Zdrowie", "Dywidendy"]
        axis_values = [
            sr.get("Snowflake: Wycena"), sr.get("Snowflake: Wzrost"), sr.get("Snowflake: Wyniki"),
            sr.get("Snowflake: Zdrowie"), sr.get("Snowflake: Dywidendy"),
        ]
        _render_radar_chart(axis_labels, axis_values)

        st.divider()
        st.subheader(
            "👔 Transakcje insiderów",
            help="Zakupy/sprzedaże akcji przez zarząd i dużych akcjonariuszy. Insiderzy kupujący "
                 "własne akcje bywają uznawani za pozytywny sygnał zaufania do przyszłości spółki.",
        )
        st.caption(
            "Na żądanie, z Yahoo Finance. Pokrycie tych danych bywa znacznie lepsze dla "
            "spółek notowanych w USA niż europejskich — pusty wynik może po prostu "
            "oznaczać brak danych źródłowych, nie błąd."
        )
        if st.button("Sprawdź transakcje insiderów", key="profile_insider_btn"):
            with st.spinner("Pobieram dane z Yahoo Finance..."):
                transactions = get_insider_transactions(ticker)
            if not transactions:
                st.info("Brak dostępnych danych o transakcjach insiderów dla tej spółki.")
            else:
                _render_table(pd.DataFrame(transactions), height=300)

    st.divider()
    st.subheader(
        "📚 Wszystkie dane, wg kategorii",
        help="Kompletna lista wszystkich zebranych wskaźników dla tej spółki, pogrupowana "
             "tematycznie — rozwiń kategorię, żeby zobaczyć szczegóły z wyjaśnieniami.",
    )
    st.caption("Kliknij kategorię, żeby rozwinąć pełną listę wskaźników dla tej spółki.")
    for group_name, group_cols in INDICATOR_GROUPS.items():
        available = [c for c in group_cols if c in row]
        if not available:
            continue
        icon = GROUP_ICONS.get(group_name, "📁")
        with st.expander(f"{icon} {group_name} ({len(available)})", expanded=False):
            for col in available:
                val = row.get(col, "BRAK")
                help_text = INDICATOR_HELP.get(col, "")
                st.write(f"**{col}:** {val}")
                if help_text:
                    st.caption(help_text)
