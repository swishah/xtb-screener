"""
Modul Screener — filtrowanie i przeglad calej migawki.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from config.markets import VERIFIED_TICKERS
from core import db
from ui.common import (
    DEFAULT_SCREENER_COLUMNS,
    _earnings_date,
    _fx_rates,
    _personalize_columns,
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 1 — Screener na bazie ostatniej zapisanej migawki
# ---------------------------------------------------------------------------
GURU_SCREENS = {
    "💎 Głębokie przeceny, zero ostrzeżeń": {"typ": "stock", "min_score": 3, "max_ath": -30, "max_flags": 0},
    "🚀 Mocny sygnał techniczny": {"typ": "stock", "min_score": 6, "max_ath": 0, "max_flags": 3},
    "🛡️ Najbezpieczniejsze (0 flag)": {"typ": "stock", "min_score": 0, "max_ath": 0, "max_flags": 0},
    "🌍 Tylko ETF-y": {"typ": "etf", "min_score": 0, "max_ath": 0, "max_flags": 10},
}


def render_screener():
    if "pending_screen_load" in st.session_state:
        _cfg = st.session_state.pop("pending_screen_load")
        st.session_state["scr_typ"] = _cfg["typ"]
        st.session_state["scr_min_score"] = _cfg["min_score"]
        st.session_state["scr_max_ath"] = _cfg["max_ath"]
        st.session_state["scr_max_flags"] = _cfg["max_flags"]

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

        picker_available_cols = list(df.columns)
        if "Waluta" in df.columns and "Cena (PLN)" not in picker_available_cols:
            picker_available_cols.append("Cena (PLN)")  # doliczane dopiero niżej, ale ma być wybieralne już tutaj

        active_columns = _personalize_columns(
            pref_key="screener_columns",
            available_columns=picker_available_cols,
            default_columns=DEFAULT_SCREENER_COLUMNS,
            mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
        )

        only_verified = st.checkbox("Pokaż tylko tickery ręcznie zweryfikowane na XTB", value=False)
        if only_verified and VERIFIED_TICKERS:
            df = df[df["Ticker"].isin(VERIFIED_TICKERS)]

        row1_col1, row1_col2, row1_col3 = st.columns(3)
        with row1_col1:
            typ_options = ["Wszystkie"] + sorted(df["Typ"].dropna().unique().tolist())
            kind_choice = st.selectbox(
                "Typ", typ_options, index=0, key="scr_typ",
                help="Czy przeglądasz akcje, ETF-y, czy oba typy naraz.",
            )

        pool = df if kind_choice == "Wszystkie" else df[df["Typ"] == kind_choice]

        with row1_col2:
            market_options = ["Wszystkie"] + sorted(pool["Rynek"].dropna().unique().tolist())
            market_choice = st.selectbox(
                "Rynek / kraj", market_options, index=0,
                help="Zawęża do jednej giełdy/kraju notowania.",
            )

        pool2 = pool if market_choice == "Wszystkie" else pool[pool["Rynek"] == market_choice]

        with row1_col3:
            if "Sektor" in pool2.columns:
                sector_options = ["Wszystkie"] + sorted(
                    s for s in pool2["Sektor"].dropna().unique().tolist() if s != "Nieznany"
                )
                sector_choice = st.selectbox(
                    "Sektor", sector_options, index=0,
                    help="Zawęża do jednego sektora gospodarki (klasyfikacja Yahoo Finance).",
                )
            else:
                sector_choice = "Wszystkie"

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            min_score = st.slider(
                "Min. Buy Score", 0, 9, 0, key="scr_min_score",
                help="Buy Score to suma podstawowych sygnałów technicznych (RSI, MACD, trend, "
                     "wolumen, dystans od ATH). Wyżej = więcej sygnałów kupna zgadza się naraz. "
                     "0 = bez filtra.",
            )
        with row2_col2:
            max_ath = st.slider(
                "Maks. % od ATH (np. -30 = co najmniej -30%)", -90, 0, 0, key="scr_max_ath",
                help="Ile maksymalnie spółka może być poniżej swojego historycznego szczytu. "
                     "Np. -30 pokaże tylko spółki co najmniej 30% poniżej ATH.",
            )
        with row2_col3:
            max_flags = st.slider(
                "Maks. liczba czerwonych flag", 0, 10, 10, key="scr_max_flags",
                help="0 = pokaż tylko spółki bez żadnych automatycznych ostrzeżeń.",
            )

        with st.expander("📚 Gotowe przesiewy (Guru Screens) i zapisane własne", expanded=False):
            st.caption(
                "Gotowe kombinacje inspirowane popularnymi strategiami (Finviz/GuruFocus). "
                "Bardziej złożone strategie (np. Magic Formula, Net-Net Graham) lepiej "
                "sprawdzisz w zakładkach 'Własny scoring' i 'vs Sektor'."
            )
            saved_screens = db.get_preference("saved_screens", {})
            all_screens = {**GURU_SCREENS, **saved_screens}
            load_pick = st.selectbox(
                "Wczytaj przesiew", ["— wybierz —"] + list(all_screens.keys()), key="scr_load_screen",
            )
            if load_pick != "— wybierz —" and st.button("📥 Wczytaj", key="scr_load_btn"):
                st.session_state["pending_screen_load"] = all_screens[load_pick]
                st.rerun()

            sc1, sc2 = st.columns([3, 1])
            with sc1:
                save_name = st.text_input("Nazwa dla obecnych ustawień filtrów", key="scr_save_name")
            with sc2:
                st.write("")
                if st.button("💾 Zapisz", key="scr_save_btn") and save_name:
                    saved_screens[save_name] = {
                        "typ": kind_choice, "min_score": min_score,
                        "max_ath": max_ath, "max_flags": max_flags,
                    }
                    db.set_preference("saved_screens", saved_screens)
                    st.success(f"Zapisano przesiew „{save_name}”.")

        filtered = pool2.copy()
        if sector_choice != "Wszystkie" and "Sektor" in filtered.columns:
            filtered = filtered[filtered["Sektor"] == sector_choice]
        filtered = filtered[
            (filtered["Buy Score"] >= min_score) & (filtered["pct_from_ath"] <= max_ath)
        ]
        if "Liczba flag" in filtered.columns:
            filtered = filtered[filtered["Liczba flag"] <= max_flags]
        filtered = filtered.sort_values("Buy Score", ascending=False)

        if "Waluta" in filtered.columns:
            currencies = tuple(sorted(filtered["Waluta"].dropna().unique().tolist()))
            rates = _fx_rates(currencies)
            filtered = filtered.copy()
            filtered["Cena (PLN)"] = filtered.apply(
                lambda r: round(r["Cena"] * rates[r["Waluta"]], 2)
                if r.get("Waluta") in rates else None,
                axis=1,
            )
            # przenieś "Cena (PLN)" zaraz obok "Cena", żeby łatwo je zestawić
            cols = list(filtered.columns)
            cols.remove("Cena (PLN)")
            cols.insert(cols.index("Cena") + 1, "Cena (PLN)")
            filtered = filtered[cols]
            st.caption(
                "Kursy walut pobierane na żywo (nie zapisywane w migawce) — 'Cena (PLN)' "
                "ułatwia porównanie spółek notowanych w różnych walutach."
            )

        filtered = _with_tradingview_link(filtered)
        display_cols = [c for c in active_columns if c in filtered.columns]
        display_df = filtered[display_cols]
        _render_table(display_df, height=600)
        st.download_button(
            "⬇️ Pobierz CSV", filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"screener_{chosen_date}.csv",
        )

        if "Czerwone flagi" in filtered.columns and not filtered.empty:
            with st.expander("🚩 Zobacz treść czerwonych flag dla konkretnej spółki"):
                flag_ticker = st.selectbox(
                    "Spółka", filtered["Ticker"].tolist(),
                    format_func=lambda t: f"{t} — {filtered.set_index('Ticker').loc[t, 'Nazwa']}",
                )
                flags_text = filtered.set_index("Ticker").loc[flag_ticker, "Czerwone flagi"]
                if flags_text == "Brak":
                    st.success("Brak automatycznych ostrzeżeń dla tej spółki.")
                else:
                    for f in flags_text.split("; "):
                        st.write(f)

        st.divider()
        st.subheader(
            "📅 Najbliższe wyniki finansowe (earnings)",
            help="Data najbliższej publikacji wyników kwartalnych/rocznych. Wyniki blisko dziś "
                 "= wyższa zmienność, inny kontekst decyzyjny na kupno/sprzedaż.",
        )
        st.caption(
            "Sprawdzane na żądanie (nie podczas codziennego skanu, żeby go nie spowalniać) "
            "— dla maks. 30 spółek z aktualnie przefiltrowanej tabeli powyżej."
        )
        if st.button("Sprawdź daty najbliższych wyników"):
            sample = filtered[filtered["Typ"] == "stock"].head(30)
            earnings_rows = []
            with st.spinner("Pobieram kalendarz wyników z Yahoo Finance..."):
                for _, r in sample.iterrows():
                    ed = _earnings_date(r["Ticker"])
                    if ed:
                        days = (pd.Timestamp(ed) - pd.Timestamp.now().normalize()).days
                        earnings_rows.append({
                            "Ticker": r["Ticker"], "Nazwa": r["Nazwa"], "Rynek": r.get("Rynek"),
                            "Najbliższe wyniki": ed, "Za ile dni": days,
                        })
            if earnings_rows:
                edf = pd.DataFrame(earnings_rows).sort_values("Za ile dni")
                _render_table(edf, height=300)
                soon = edf[edf["Za ile dni"] <= 7]
                if not soon.empty:
                    st.warning(
                        f"⚠️ {len(soon)} spółka/spółki mają wyniki w ciągu 7 dni — "
                        "wyższa zmienność, inny kontekst decyzyjny."
                    )
            else:
                st.info("Brak danych o najbliższych wynikach dla widocznych spółek (albo Yahoo ich nie udostępnia).")
