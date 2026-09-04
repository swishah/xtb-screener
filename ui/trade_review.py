"""
Modul Analiza transakcji — import historii z XTB.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core.scanner import analyze_trade, xtb_to_yahoo, yahoo_price_scale
from ui.common import (
    _render_table,
    _with_tradingview_link,
)


# ---------------------------------------------------------------------------
# Wczytywanie natywnego eksportu z xStation 5
#
# Eksport XTB nie jest zwykłą tabelą: ma trzy arkusze, a nad właściwymi danymi
# kilka wierszy metadanych (numer rachunku, zakres dat). Wczytany domyślnie
# przez pandas wygląda na uszkodzony — nagłówkiem zostaje "Account number".
# Stąd sztywne numery wierszy nagłówka, ustalone na prawdziwym pliku.
#
# Nazwy kolumn różnią się wielkością liter między arkuszami ("Open Price" vs
# "Open price"), więc szukamy ich bez rozróżniania wielkości liter.
# ---------------------------------------------------------------------------
_XTB_ARKUSZ_ZAMKNIETE = "Closed Positions"
_XTB_ARKUSZ_OTWARTE = "Open Positions"
_XTB_WIERSZ_NAGLOWKA = {_XTB_ARKUSZ_ZAMKNIETE: 4, _XTB_ARKUSZ_OTWARTE: 10}


def _kolumna(df: pd.DataFrame, *nazwy: str):
    """Znajduje kolumnę po nazwie, ignorując wielkość liter i białe znaki."""
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for n in nazwy:
        if n.strip().lower() in mapa:
            return mapa[n.strip().lower()]
    return None


def _wczytaj_eksport_xtb(plik):
    """
    Rozpoznaje i normalizuje eksport z XTB. Zwraca (DataFrame, mapa_tickerów)
    albo None, jeśli to nie jest plik z XTB — wtedy działa ścieżka ręczna.

    Bierze pozycje zamknięte (z ceną sprzedaży) ORAZ wciąż otwarte (sam
    zakup) — te drugie też warto ocenić, bo pytanie "czy dobrze wszedłem"
    nie wymaga zamkniętej pozycji.
    """
    if not str(getattr(plik, "name", "")).lower().endswith(".xlsx"):
        return None
    try:
        plik.seek(0)
        arkusze = pd.ExcelFile(plik).sheet_names
    except Exception:  # noqa: BLE001
        return None
    if _XTB_ARKUSZ_ZAMKNIETE not in arkusze:
        return None  # to nie jest eksport z XTB

    wiersze: list[dict] = []
    for arkusz, status in ((_XTB_ARKUSZ_ZAMKNIETE, "zamknięta"), (_XTB_ARKUSZ_OTWARTE, "otwarta")):
        if arkusz not in arkusze:
            continue
        try:
            plik.seek(0)
            df = pd.read_excel(plik, sheet_name=arkusz, header=_XTB_WIERSZ_NAGLOWKA[arkusz])
        except Exception:  # noqa: BLE001
            continue

        c_tic = _kolumna(df, "Ticker")
        c_od = _kolumna(df, "Open Time (UTC)", "Open time (UTC)")
        c_oc = _kolumna(df, "Open Price", "Open price")
        c_typ = _kolumna(df, "Type")
        c_nazwa = _kolumna(df, "Instrument", "Instrument/Position")
        c_zd = _kolumna(df, "Close Time (UTC)", "Close time (UTC)")
        c_zc = _kolumna(df, "Close Price", "Close price")
        if c_tic is None or c_od is None or c_oc is None:
            continue

        for _, r in df.iterrows():
            tic = str(r.get(c_tic, "")).strip()
            if not tic or tic.lower() == "nan":
                continue
            # Arkusz pozycji otwartych zawiera też wiersze zbiorcze (suma po
            # instrumencie) — poznajemy je po braku daty otwarcia.
            if pd.isna(r.get(c_od)):
                continue
            # Krótkie pozycje (SELL) rządzą się odwrotną logiką niż pytanie
            # "ile taniej dało się kupić", więc ich nie analizujemy.
            if c_typ is not None:
                typ = str(r.get(c_typ, "")).strip().upper()
                if typ not in ("BUY", "", "NAN"):
                    continue
            nazwa = str(r.get(c_nazwa, "")).strip() if c_nazwa else ""
            if nazwa.isdigit() or nazwa.lower() == "nan":
                nazwa = ""
            wiersze.append({
                "Instrument": nazwa,
                "Ticker XTB": tic,
                "Ticker": xtb_to_yahoo(tic),
                "Data zakupu": r.get(c_od),
                "Cena zakupu": r.get(c_oc),
                "Data sprzedaży": r.get(c_zd) if c_zd else None,
                "Cena sprzedaży": r.get(c_zc) if c_zc else None,
                "Status": status,
            })

    if not wiersze:
        return None
    out = pd.DataFrame(wiersze)

    # W arkuszu pozycji otwartych kolumna "Instrument/Position" trzyma numer
    # pozycji zamiast nazwy spółki — uzupełniamy ją po tickerze z tych wierszy,
    # które nazwę mają (arkusz pozycji zamkniętych albo wiersz zbiorczy).
    nazwy = (
        out[out["Instrument"] != ""]
        .drop_duplicates(subset=["Ticker XTB"])
        .set_index("Ticker XTB")["Instrument"]
        .to_dict()
    )
    out["Instrument"] = out.apply(
        lambda r: r["Instrument"] or nazwy.get(r["Ticker XTB"], ""), axis=1
    )
    mapa = (
        out[["Ticker XTB", "Ticker", "Instrument"]]
        .drop_duplicates(subset=["Ticker XTB"])
        .sort_values("Ticker XTB")
        .reset_index(drop=True)
    )
    return out, mapa


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
                "**Eksport z XTB działa od ręki — nic nie trzeba poprawiać.** W xStation 5 "
                "wejdź w zakładkę *Historia* (dolny panel), ustaw zakres dat, kliknij prawym "
                "przyciskiem na dowolną transakcję i wybierz *Eksportuj do Excel (XLSX)*. "
                "Wgraj plik tutaj — appka sama rozpozna format, pominie wiersze metadanych, "
                "weźmie pozycje zamknięte i otwarte oraz przetłumaczy tickery z oznaczeń XTB "
                "(`ALE.PL`) na format Yahoo Finance (`ALE.WA`).\n\n"
                "**Inny broker albo własny plik?** Musi zawierać co najmniej: **ticker**, "
                "**datę zakupu** i **cenę zakupu**; opcjonalnie datę i cenę sprzedaży. Nazwy "
                "kolumn nie mają znaczenia — po wgraniu sam wskażesz, która jest która. "
                "Tickery powinny być w formacie Yahoo Finance; jeśli używają oznaczeń XTB, "
                "zaznacz po wgraniu opcję tłumaczenia."
            )
        return

    wykryty_xtb = _wczytaj_eksport_xtb(uploaded)
    if wykryty_xtb is not None:
        raw, mapa_tickerow = wykryty_xtb
    else:
        mapa_tickerow = None
        try:
            uploaded.seek(0)
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

    if mapa_tickerow is not None:
        # --- ścieżka automatyczna: rozpoznany eksport z XTB ------------------
        zamkniete = int((raw["Status"] == "zamknięta").sum())
        otwarte = int((raw["Status"] == "otwarta").sum())
        st.success(
            f"Rozpoznano eksport z XTB — wczytano {len(raw)} zakupów "
            f"({zamkniete} z pozycji zamkniętych, {otwarte} z wciąż otwartych). "
            "Tickery przetłumaczone automatycznie, kolumn nie musisz wskazywać."
        )
        with st.expander(f"🔤 Jak przetłumaczyłem tickery ({len(mapa_tickerow)} instrumentów)"):
            st.caption(
                "XTB oznacza instrumenty sufiksem KRAJU (`ALE.PL`), a Yahoo Finance — "
                "sufiksem GIEŁDY (`ALE.WA`), więc bez tłumaczenia nie dałoby się pobrać "
                "żadnych cen. Gdyby któryś symbol przetłumaczył się źle, zobaczysz go po "
                "analizie na liście pozycji bez danych cenowych."
            )
            st.dataframe(mapa_tickerow, use_container_width=True, hide_index=True)

        st.subheader(
            "Podgląd wczytanych transakcji",
            help="Tak appka zrozumiała Twój eksport — sprawdź, czy daty i ceny wyglądają sensownie.",
        )
        st.dataframe(raw.head(10), use_container_width=True)

        col_ticker, col_buy_date, col_buy_price = "Ticker", "Data zakupu", "Cena zakupu"
        col_sell_date, col_sell_price = "Data sprzedaży", "Cena sprzedaży"
        tlumacz_xtb = False  # tickery przetłumaczono już przy wczytywaniu
        lookback = st.slider(
            "Okno analizy po zakupie (dni)", 7, 365, 90, key="tr_lookback",
            help="W jakim okresie po zakupie szukać najniższej ceny — np. 90 dni sprawdza, "
                 "czy w ciągu kwartału po zakupie dało się kupić taniej.",
        )
    else:
        # --- ścieżka ręczna: dowolny inny plik ------------------------------
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

        tlumacz_xtb = st.checkbox(
            "Tickery są w formacie XTB — przetłumacz je (np. `ALE.PL` → `ALE.WA`)",
            value=False, key="tr_tlumacz_xtb",
            help="Zaznacz, jeśli Twój plik używa oznaczeń XTB z sufiksem kraju. "
                 "Natywny eksport XLSX z xStation rozpoznaje się sam — ta opcja jest "
                 "dla plików przerabianych ręcznie albo z innych źródeł.",
        )

        required = [col_ticker, col_buy_date, col_buy_price]
        if any(c == "— brak —" for c in required):
            st.info("Wskaż co najmniej kolumny: Ticker, Data zakupu i Cena zakupu.")
            return

    # Ceny z XTB są w walucie głównej (funty), a Yahoo notuje LSE w pensach —
    # patrz yahoo_price_scale(). Skalujemy tylko dane pochodzące z XTB, bo dla
    # pliku z innego źródła nie wiemy, w jakich jednostkach są ceny.
    zrodlo_xtb = mapa_tickerow is not None or tlumacz_xtb

    if st.button("🔍 Przeanalizuj transakcje", key="tr_analyze", type="primary"):
        results = []
        failed = []
        przeskalowane: set[str] = set()
        rows = raw.to_dict("records")
        progress = st.progress(0.0)
        with st.spinner("Pobieram historię cen i analizuję transakcje..."):
            for i, r in enumerate(rows):
                ticker = str(r.get(col_ticker, "")).strip()
                if not ticker:
                    continue
                if tlumacz_xtb:
                    ticker = xtb_to_yahoo(ticker)
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

                if zrodlo_xtb:
                    skala = yahoo_price_scale(ticker)
                    if skala != 1.0:
                        buy_price *= skala
                        if sell_price is not None:
                            sell_price *= skala
                        przeskalowane.add(ticker)

                res = analyze_trade(ticker, buy_date, buy_price, sell_date, sell_price, lookback_days=lookback)
                if res is None:
                    failed.append(f"{ticker} (brak danych cenowych — sprawdź format tickera)")
                else:
                    results.append(res)
                progress.progress((i + 1) / len(rows))
        progress.empty()

        if przeskalowane:
            st.info(
                "💱 Ceny przeliczone z waluty głównej na subjednostkę dla: "
                + ", ".join(sorted(przeskalowane))
                + ". Yahoo notuje te instrumenty w pensach, a broker podaje je w funtach — "
                "bez tej korekty wyniki byłyby zawyżone 100-krotnie."
            )

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
