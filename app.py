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
    compute_indicators, price_history_for_backtest, get_sp500_map, get_sp400_map,
    STRATEGIES, backtest_strategy, get_fx_rates, get_next_earnings_date,
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


@st.cache_data(ttl=6 * 3600)
def _fx_rates(currencies: tuple[str, ...]) -> dict[str, float]:
    return get_fx_rates(set(currencies), target="PLN")


@st.cache_data(ttl=6 * 3600)
def _earnings_date(ticker: str) -> str | None:
    return get_next_earnings_date(ticker)


sp500_map, sp400_map = _us_maps()
ALL_NAMES = {t: n for g in STOCK_GROUPS.values() for t, n in g.items()}
ALL_NAMES.update(ETF_MAP)
ALL_NAMES.update(sp500_map)
ALL_NAMES.update(sp400_map)

tab_screen, tab_strategie, tab_overview, tab_dividends, tab_bt_strategy, tab_backtest = st.tabs(
    ["🔍 Screener", "🧭 Strategie", "🌍 Globalny przegląd", "💰 Dywidendy",
     "📈 Backtest strategii", "⏪ Backtest spółki"]
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

        row1_col1, row1_col2, row1_col3 = st.columns(3)
        with row1_col1:
            typ_options = ["Wszystkie"] + sorted(df["Typ"].dropna().unique().tolist())
            kind_choice = st.selectbox("Typ", typ_options, index=0)

        pool = df if kind_choice == "Wszystkie" else df[df["Typ"] == kind_choice]

        with row1_col2:
            market_options = ["Wszystkie"] + sorted(pool["Rynek"].dropna().unique().tolist())
            market_choice = st.selectbox("Rynek / kraj", market_options, index=0)

        pool2 = pool if market_choice == "Wszystkie" else pool[pool["Rynek"] == market_choice]

        with row1_col3:
            if "Sektor" in pool2.columns:
                sector_options = ["Wszystkie"] + sorted(
                    s for s in pool2["Sektor"].dropna().unique().tolist() if s != "Nieznany"
                )
                sector_choice = st.selectbox("Sektor", sector_options, index=0)
            else:
                sector_choice = "Wszystkie"

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            min_score = st.slider("Min. Buy Score", 0, 9, 0)
        with row2_col2:
            max_ath = st.slider("Maks. % od ATH (np. -30 = co najmniej -30%)", -90, 0, 0)
        with row2_col3:
            max_flags = st.slider(
                "Maks. liczba czerwonych flag", 0, 10, 10,
                help="0 = pokaż tylko spółki bez żadnych automatycznych ostrzeżeń.",
            )

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

        st.dataframe(filtered, use_container_width=True, height=600)
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
        st.subheader("📅 Najbliższe wyniki finansowe (earnings)")
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
                st.dataframe(edf, use_container_width=True)
                soon = edf[edf["Za ile dni"] <= 7]
                if not soon.empty:
                    st.warning(
                        f"⚠️ {len(soon)} spółka/spółki mają wyniki w ciągu 7 dni — "
                        "wyższa zmienność, inny kontekst decyzyjny."
                    )
            else:
                st.info("Brak danych o najbliższych wynikach dla widocznych spółek (albo Yahoo ich nie udostępnia).")

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
    "Dywidenda-okazja (cena jeszcze nie wzrosła)": (
        "Wysoka stopa dywidendy przy cenie, która w ostatnim roku prawie się "
        "nie ruszyła (albo spadła) — plus sprawdzone payout ratio i wzrost "
        "przychodów, żeby odróżnić okazję od pułapki dywidendowej."
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
    "Dywidenda-okazja (cena jeszcze nie wzrosła)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "Stopa Dyw. (%)", "Zmiana ceny (1Y%)",
        "Payout ratio (%)", "Wzrost przychodów (%)", "Marża netto (%)", "Liczba flag",
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

        st.divider()
        st.subheader("🔗 Zbieżność strategii")
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
            conv_top_n = st.slider("Próg: TOP N per strategia", 5, 50, 15, key="conv_top_n")
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
                st.dataframe(conv_df[show_cols], use_container_width=True, height=400)

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

        def _show_heatmap(group_col: str, title: str) -> None:
            st.subheader(title)
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
            _show_heatmap("Rynek", "Heatmapa rynków")
        with hm_col2:
            _show_heatmap("Sektor", "Heatmapa sektorów")

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
# TAB 4 — Dywidendy: wysoka stopa dywidendy, cena jeszcze nie wzrosła
# ---------------------------------------------------------------------------
with tab_dividends:
    st.write(
        "Szuka spółek z wysoką stopą dywidendy (z ostatniego roku) względem ceny, "
        "które **jeszcze nie zdrożały** — plus wskaźniki sprawdzające, czy sytuacja "
        "biznesu się nie pogorszyła (przychody, marże, payout ratio), żeby odróżnić "
        "realną okazję od 'pułapki dywidendowej' (wysoka stopa, bo cena spadła "
        "z powodu problemów w firmie)."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        if "Rynek" not in df.columns:
            df["Rynek"] = "Nieznany"
        stocks = df[df["Typ"] == "stock"].copy()

        c1, c2, c3 = st.columns(3)
        with c1:
            min_yield = st.slider("Min. stopa dywidendy (%)", 0.0, 15.0, 4.0, 0.5)
        with c2:
            max_price_change = st.slider(
                "Maks. zmiana ceny w ostatnim roku (%)", -50, 100, 15,
                help="Niżej = szukasz spółek, których cena jeszcze się nie ruszyła (albo spadła) mimo wysokiej dywidendy.",
            )
        with c3:
            max_payout = st.slider(
                "Maks. payout ratio (%)", 0, 200, 80,
                help="Ile % zysku firma wypłaca jako dywidendę. Powyżej 100% oznacza, że wypłaca więcej niż zarabia — sygnał ostrzegawczy.",
            )

        candidates = stocks.copy()
        if "Stopa Dyw. (%)" in candidates.columns:
            candidates = candidates[pd.to_numeric(candidates["Stopa Dyw. (%)"], errors="coerce") >= min_yield]
        if "Zmiana ceny (1Y%)" in candidates.columns:
            candidates = candidates[
                pd.to_numeric(candidates["Zmiana ceny (1Y%)"], errors="coerce") <= max_price_change
            ]
        if "Payout ratio (%)" in candidates.columns:
            payout_num = pd.to_numeric(candidates["Payout ratio (%)"], errors="coerce")
            candidates = candidates[(payout_num <= max_payout) | payout_num.isna()]

        score_col = "Score: Dywidenda-Okazja"
        sort_col = score_col if score_col in candidates.columns else "Stopa Dyw. (%)"
        candidates = candidates.sort_values(sort_col, ascending=False)

        st.caption(f"Znaleziono **{len(candidates)}** spółek spełniających kryteria.")

        display_cols = [c for c in [
            "Ticker", "Nazwa", "Rynek", "Cena", "Stopa Dyw. (%)", "Zmiana ceny (1Y%)",
            "Lata z dywidendą (3Y)", "Payout ratio (%)", "C/Z (P/E)", "ROE (%)",
            "Marża Operac. (%)", "Marża netto (%)", "Wzrost przychodów (%)",
            "Wzrost EPS (%)", "Dług/Kapitał", "Liczba flag", score_col,
        ] if c in candidates.columns]
        st.dataframe(candidates[display_cols], use_container_width=True, height=600)
        st.download_button(
            "⬇️ Pobierz CSV", candidates[display_cols].to_csv(index=False).encode("utf-8"),
            file_name=f"dywidendy_{dates[0]}.csv",
        )
        st.caption(
            "Payout ratio i wzrost przychodów/marż pokazują, czy dywidenda jest bezpieczna. "
            "'Zmiana ceny (1Y%)' blisko zera lub ujemna = rynek jeszcze nie 'przecenił w górę' tej spółki."
        )

# ---------------------------------------------------------------------------
# TAB 5 — Backtest strategii: czy TOP N wg danego score'a faktycznie zarabia?
# ---------------------------------------------------------------------------
with tab_bt_strategy:
    st.write(
        "Sprawdza, co by było, gdyby co skan kupić TOP N spółek wg wybranej strategii "
        "i sprzedać je po K kolejnych skanach. Liczone na bazie **zapisanych migawek** "
        "(nie pełnej historii cen) — bo tylko migawki mają realny, historyczny scoring "
        "fundamentalny. Im dłużej appka zbiera codzienne skany, tym wiarygodniejszy wynik."
    )
    dates_all = db.list_dates()
    n_snapshots = len(dates_all)

    if n_snapshots < 2:
        st.info(
            f"Masz na razie {n_snapshots} migawkę/migawki w bazie. Potrzeba co najmniej "
            "kilku(nastu), żeby backtest miał sens — appka zbierze je automatycznie "
            "wraz z kolejnymi uruchomieniami codziennego skanu."
        )
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            bt_strategy_name = st.selectbox("Strategia", list(STRATEGIES.keys()), key="bt_strategy")
        with c2:
            bt_top_n = st.slider("TOP N spółek", 1, 20, 5)
        with c3:
            max_hold = max(1, n_snapshots - 1)
            if max_hold < 2:
                bt_hold = 1
                st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
            else:
                bt_hold = st.slider("Trzymaj przez (liczba skanów)", 1, max_hold, min(5, max_hold))

        score_col, _ = STRATEGIES[bt_strategy_name]
        df_all = db.load_all_snapshots()
        bt_result = backtest_strategy(df_all, score_col, top_n=bt_top_n, hold_snapshots=bt_hold)

        if bt_result.empty:
            st.warning(
                "Za mało danych dla tej kombinacji parametrów — spróbuj mniejszej liczby "
                "skanów do przetrzymania, albo poczekaj na kolejne migawki."
            )
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Śr. zwrot na okno", f"{bt_result['Śr. zwrot %'].mean():.2f}%")
            m2.metric("Win rate (średni)", f"{bt_result['Win rate %'].mean():.1f}%")
            m3.metric("Liczba przetestowanych okien", len(bt_result))
            best, worst = bt_result["Śr. zwrot %"].max(), bt_result["Śr. zwrot %"].min()
            m4.metric("Najlepsze / najgorsze okno", f"{best:.1f}% / {worst:.1f}%")

            st.caption(
                "Krzywa kapitału zakłada mechaniczne reinwestowanie zwrotu z każdego okna "
                "z rzędu — to uproszczenie (okna się nakładają w czasie), traktuj jako "
                "orientacyjny obraz, nie realną symulację portfela."
            )
            equity = (1 + bt_result["Śr. zwrot %"] / 100).cumprod() - 1
            equity_df = pd.DataFrame(
                {"Skumulowany zwrot %": (equity * 100).round(2)}, index=bt_result["Data wyjścia"]
            )
            st.line_chart(equity_df)

            st.dataframe(bt_result, use_container_width=True, height=400)

# ---------------------------------------------------------------------------
# TAB 6 — Backtest: jak wyglądała spółka X dni/tygodni/miesięcy temu
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
        max_back = min(500, len(df_price) - 30)
        if df_price.empty or max_back < 1:
            st.info("Za krótka historia cen dla tej spółki, żeby cofać się w czasie (potrzeba co najmniej ~30 dni notowań).")
        else:
            back_days = st.slider("Cofnij się o (dni handlowych)", 0, max_back, 0)
            as_of = df_price.index[-1 - back_days]
            price_then = float(df_price.loc[:as_of, "Close"].iloc[-1])
            ind = compute_indicators(df_price, price_then, as_of=as_of)
            st.write(f"Stan na: **{as_of.date()}**, cena: **{price_then:.2f}**")
            st.json(ind)
            st.line_chart(df_price.loc[:as_of, "Close"])
