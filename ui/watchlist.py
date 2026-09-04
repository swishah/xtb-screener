"""
Modul Watchlist — obserwowane spolki z notatkami.
"""
from __future__ import annotations

import streamlit as st
from core import db
from core.scanner import compute_correlation_matrix
from ui.common import (
    ALL_NAMES,
    _column_config_for,
    _personalize_columns,
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 10 — Watchlist: oznaczone tickery z własnymi notatkami
# ---------------------------------------------------------------------------
def render_watchlist():
    st.write(
        "Oznacz spółki jako obserwowane, z własną notatką (np. 'czekam na wyniki Q3'). "
        "Zapisywane w bazie — przetrwa między sesjami i restartami appki."
    )

    st.subheader(
        "Dodaj do watchlisty",
        help="Wybierz spółkę, opcjonalnie dodaj notatkę (np. powód obserwacji), kliknij Dodaj.",
    )
    add_col1, add_col2, add_col3 = st.columns([2, 3, 1])
    with add_col1:
        new_ticker = st.selectbox(
            "Spółka / ETF", sorted(ALL_NAMES.keys()),
            format_func=lambda t: f"{t} — {ALL_NAMES[t]}", key="wl_add_ticker",
        )
    with add_col2:
        new_note = st.text_input("Notatka (opcjonalnie)", key="wl_add_note")
    with add_col3:
        st.write("")
        st.write("")
        if st.button("➕ Dodaj"):
            db.add_to_watchlist(new_ticker, new_note)
            st.success(f"Dodano {new_ticker} do watchlisty.")
            st.rerun()

    st.divider()
    st.subheader(
        "Twoja watchlist",
        help="Obserwowane spółki z aktualnymi danymi z najnowszej migawki. Notatki edytujesz "
             "bezpośrednio w tabeli.",
    )
    wl = db.load_watchlist()

    if wl.empty:
        st.info("Watchlist jest pusta — dodaj pierwszą spółkę powyżej.")
    else:
        dates = db.list_dates()
        if dates:
            latest = db.load_snapshot(dates[0])
            wl = wl.merge(latest, on="Ticker", how="left")
            wl = _with_tradingview_link(wl)
            if "Nazwa" in wl.columns and wl["Nazwa"].isna().any():
                st.caption(
                    "Niektóre spółki nie mają jeszcze danych z najnowszej migawki "
                    "(np. dodane po ostatnim skanie) — ceny/score pojawią się po kolejnym skanie."
                )

        default_watchlist_cols = ["Rynek", "Cena", "Buy Score", "Liczba flag", "pct_from_ath"]
        active_watchlist_cols = _personalize_columns(
            pref_key="watchlist_columns",
            available_columns=list(wl.columns),
            default_columns=[c for c in default_watchlist_cols if c in wl.columns],
            mandatory_columns=["Ticker", "Notatka", "TradingView"],
            label="Personalizuj dane widoczne obok notatek",
        )
        wl_display_cols = list(dict.fromkeys(
            [c for c in active_watchlist_cols if c in wl.columns] + ["Dodano"]
        ))
        wl_view = wl[wl_display_cols]

        edited = st.data_editor(
            wl_view,
            column_config={
                "Notatka": st.column_config.TextColumn("Notatka", width="large"),
                **_column_config_for([c for c in wl_display_cols if c not in ("Notatka",)]),
            },
            disabled=[c for c in wl_view.columns if c != "Notatka"],
            hide_index=True,
            use_container_width=True,
            key="wl_editor",
        )

        save_col, remove_col1, remove_col2 = st.columns([1, 2, 1])
        with save_col:
            if st.button("💾 Zapisz zmiany notatek"):
                for _, r in edited.iterrows():
                    db.update_watchlist_note(r["Ticker"], r["Notatka"] or "")
                st.success("Zapisano zmiany notatek.")
                st.rerun()
        with remove_col1:
            remove_ticker = st.selectbox("Usuń z watchlisty", wl["Ticker"].tolist(), key="wl_remove")
        with remove_col2:
            st.write("")
            if st.button("🗑️ Usuń"):
                db.remove_from_watchlist(remove_ticker)
                st.success(f"Usunięto {remove_ticker}.")
                st.rerun()

        st.divider()
        st.subheader(
            "🔗 Macierz korelacji",
            help="Wartości blisko 1.0 = spółki poruszają się razem (ryzyko koncentracji). "
                 "Blisko 0 = niezależne (dobra dywersyfikacja). Ujemne = poruszają się przeciwnie.",
        )
        st.caption(
            "Sprawdza, czy obserwowane spółki poruszają się razem (ryzyko koncentracji) "
            "czy niezależnie (dywersyfikacja) — liczone z dziennych zwrotów cen. "
            "Wartości blisko 1.0 = mocno skorelowane, blisko 0 = niezależne, ujemne = "
            "poruszają się przeciwnie do siebie."
        )
        if len(wl) < 2:
            st.info("Potrzeba co najmniej 2 spółek na watchliście, żeby policzyć korelację.")
        elif st.button("Oblicz macierz korelacji", key="wl_corr_btn"):
            with st.spinner("Pobieram historię cen i liczę korelacje..."):
                corr = compute_correlation_matrix(wl["Ticker"].tolist())
            if corr.empty:
                st.warning("Nie udało się pobrać wystarczających danych cenowych dla tych spółek.")
            else:
                _render_table(corr.reset_index().rename(columns={"index": "Ticker"}), height=min(400, 60 + 40 * len(corr)))
