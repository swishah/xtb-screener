"""
Modul Analiza transakcji — import historii z XTB.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core.scanner import analyze_trade
from ui.common import (
    _render_table,
    _with_tradingview_link,
)

# ---------------------------------------------------------------------------
# TAB 11 — Analiza transakcji: ile taniej dało się kupić / za wcześnie sprzedać
# ---------------------------------------------------------------------------
def render_trade_review():
    st.write(
        "Wgraj historię swoich transakcji (CSV/XLSX, np. eksport z XTB), a appka sprawdzi "
        "dla każdego zakupu: **ile taniej dało się kupić**, gdybyś poczekał, oraz jakie "
        "wskaźniki techniczne panowały w dniu zakupu. Jeśli podasz też sprzedaże — sprawdzi, "
        "czy nie sprzedałeś zbyt wcześnie."
    )
    st.caption(
        "Twój plik nie jest nigdzie wysyłany ani zapisywany — jest przetwarzany w pamięci "
        "tylko na czas tej analizy. Do wyliczeń appka pobiera z Yahoo Finance wyłącznie "
        "historię cen podanych tickerów."
    )

    uploaded = st.file_uploader("Plik z transakcjami (CSV lub XLSX)", type=["csv", "xlsx"], key="tr_upload")
    if uploaded is None:
        with st.expander("ℹ️ Jak przygotować plik?"):
            st.markdown(
                "Plik musi zawierać co najmniej: **ticker**, **datę zakupu** i **cenę zakupu**. "
                "Opcjonalnie: datę i cenę sprzedaży. Nazwy kolumn nie mają znaczenia — "
                "po wgraniu sam wskażesz, która kolumna jest która.\n\n"
                "**Ważne:** tickery muszą być w formacie Yahoo Finance (z sufiksem giełdy), "
                "np. `ALE.WA` dla Allegro, `SAP.DE` dla SAP, `AAPL` dla Apple. Jeśli Twój "
                "eksport z XTB używa innych oznaczeń (np. `ALE.PL`), trzeba je najpierw poprawić "
                "w pliku — inaczej appka nie pobierze historii cen."
            )
        return

    try:
        if uploaded.name.lower().endswith(".csv"):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)
    except Exception as e:  # noqa: BLE001
        st.error(f"Nie udało się wczytać pliku: {e}")
        return

    if raw.empty:
        st.warning("Wgrany plik nie zawiera żadnych wierszy.")
        return

    st.subheader("Podgląd wgranego pliku", help="Pierwsze wiersze Twojego pliku — sprawdź, czy wczytał się poprawnie.")
    st.dataframe(raw.head(10), use_container_width=True)

    st.subheader(
        "Wskaż kolumny",
        help="Appka nie zgaduje nazw kolumn — wskaż ręcznie, która jest która, "
             "żeby działało niezależnie od formatu eksportu z Twojego brokera.",
    )
    cols = ["— brak —"] + list(raw.columns)
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        col_ticker = st.selectbox("Kolumna: Ticker", cols, key="tr_col_ticker")
    with mc2:
        col_buy_date = st.selectbox("Kolumna: Data zakupu", cols, key="tr_col_buy_date")
    with mc3:
        col_buy_price = st.selectbox("Kolumna: Cena zakupu", cols, key="tr_col_buy_price")
    mc4, mc5, mc6 = st.columns(3)
    with mc4:
        col_sell_date = st.selectbox("Kolumna: Data sprzedaży (opcjonalnie)", cols, key="tr_col_sell_date")
    with mc5:
        col_sell_price = st.selectbox("Kolumna: Cena sprzedaży (opcjonalnie)", cols, key="tr_col_sell_price")
    with mc6:
        lookback = st.slider(
            "Okno analizy po zakupie (dni)", 7, 365, 90, key="tr_lookback",
            help="W jakim okresie po zakupie szukać najniższej ceny — np. 90 dni sprawdza, "
                 "czy w ciągu kwartału po zakupie dało się kupić taniej.",
        )

    required = [col_ticker, col_buy_date, col_buy_price]
    if any(c == "— brak —" for c in required):
        st.info("Wskaż co najmniej kolumny: Ticker, Data zakupu i Cena zakupu.")
        return

    if st.button("🔍 Przeanalizuj transakcje", key="tr_analyze", type="primary"):
        results = []
        failed = []
        rows = raw.to_dict("records")
        progress = st.progress(0.0)
        with st.spinner("Pobieram historię cen i analizuję transakcje..."):
            for i, r in enumerate(rows):
                ticker = str(r.get(col_ticker, "")).strip()
                if not ticker:
                    continue
                try:
                    buy_price = float(r.get(col_buy_price))
                    buy_date = pd.Timestamp(r.get(col_buy_date))
                except Exception:  # noqa: BLE001
                    failed.append(f"{ticker} (nieczytelna data lub cena zakupu)")
                    progress.progress((i + 1) / len(rows))
                    continue

                sell_date = sell_price = None
                if col_sell_date != "— brak —" and col_sell_price != "— brak —":
                    try:
                        raw_sd, raw_sp = r.get(col_sell_date), r.get(col_sell_price)
                        if pd.notna(raw_sd) and pd.notna(raw_sp):
                            sell_date, sell_price = pd.Timestamp(raw_sd), float(raw_sp)
                    except Exception:  # noqa: BLE001
                        pass  # sprzedaż jest opcjonalna — brak/błąd nie przerywa analizy zakupu

                res = analyze_trade(ticker, buy_date, buy_price, sell_date, sell_price, lookback_days=lookback)
                if res is None:
                    failed.append(f"{ticker} (brak danych cenowych — sprawdź format tickera)")
                else:
                    results.append(res)
                progress.progress((i + 1) / len(rows))
        progress.empty()

        if failed:
            with st.expander(f"⚠️ Nie udało się przeanalizować {len(failed)} pozycji"):
                for f in failed:
                    st.write(f"- {f}")

        if not results:
            st.warning(
                "Nie udało się przeanalizować żadnej transakcji. Najczęstsza przyczyna: "
                "tickery nie są w formacie Yahoo Finance (patrz instrukcja powyżej)."
            )
            return

        res_df = pd.DataFrame(results)

        st.divider()
        st.subheader("📊 Podsumowanie", help="Zbiorcze wnioski ze wszystkich przeanalizowanych transakcji.")
        savings = pd.to_numeric(res_df["Ile taniej mogłeś kupić (%)"], errors="coerce").dropna()
        s1, s2, s3 = st.columns(3)
        s1.metric(
            "Przeanalizowanych transakcji", len(res_df),
            help="Ile pozycji z pliku udało się poprawnie przeanalizować.",
        )
        if not savings.empty:
            s2.metric(
                "Śr. potencjalna oszczędność", f"{savings.mean():.2f}%",
                help="Średnio o tyle % taniej dało się kupić, czekając na dołek w wybranym oknie. "
                     "Im bardziej ujemna wartość, tym częściej kupujesz przed dalszymi spadkami.",
            )
            n_worse = int((savings < -2).sum())
            s3.metric(
                "Zakupy >2% przed dołkiem", f"{n_worse}/{len(savings)}",
                help="Ile zakupów miało w oknie analizy cenę o ponad 2% niższą — sygnał, "
                     "czy warto rozważyć zlecenia z limitem zamiast kupna po cenie rynkowej.",
            )

        rsi_at_buy = pd.to_numeric(res_df["RSI w dniu zakupu"], errors="coerce").dropna()
        if not rsi_at_buy.empty:
            high_rsi = int((rsi_at_buy > 50).sum())
            st.write(
                f"**RSI w dniu zakupu:** średnio {rsi_at_buy.mean():.1f}. "
                f"W {high_rsi}/{len(rsi_at_buy)} transakcjach RSI przekraczało 50 — "
                + (
                    "kupujesz częściej w trakcie odbicia/wzrostu niż w dołku wyprzedania."
                    if high_rsi > len(rsi_at_buy) / 2
                    else "kupujesz przeważnie przy niskim RSI, czyli blisko stref wyprzedania."
                )
            )

        if "Niewykorzystany wzrost po sprzedaży (%)" in res_df.columns:
            upside = pd.to_numeric(res_df["Niewykorzystany wzrost po sprzedaży (%)"], errors="coerce").dropna()
            if not upside.empty:
                st.write(
                    f"**Sprzedaże:** po sprzedaży cena rosła średnio jeszcze o {upside.mean():.1f}% "
                    "(maks. w dostępnej historii) — wysoka wartość sugeruje, że sprzedajesz zbyt wcześnie."
                )

        st.caption(
            "To analiza historyczna „po fakcie”, nie porada inwestycyjna — pokazuje wzorce w Twoich "
            "dotychczasowych decyzjach. Trafienie w dokładny dołek jest z definicji niemożliwe; "
            "celem jest wychwycenie systematycznych tendencji, nie ocena pojedynczych transakcji."
        )

        st.divider()
        st.subheader("Szczegóły transakcji", help="Pełne wyniki dla każdej przeanalizowanej pozycji.")
        res_df = _with_tradingview_link(res_df)
        _render_table(res_df, height=500)
        st.download_button(
            "⬇️ Pobierz CSV z analizą", res_df.to_csv(index=False).encode("utf-8"),
            file_name="analiza_transakcji.csv",
        )
