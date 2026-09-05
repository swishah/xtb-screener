"""
Moduł Własne instrumenty — ręczne dopisywanie tickerów do uniwersum.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import db
from core.scanner import sprawdz_instrument, xtb_to_yahoo
from ui.common import ALL_NAMES, _render_table

ETYKIETY_TYPOW = {"stock": "Akcja", "etf": "ETF", "index": "Indeks"}


def render_wlasne():
    st.write(
        "Dopisz instrument, którego nie ma w uniwersum. Trafi do skanu razem "
        "z resztą przy najbliższym uruchomieniu i od tego momentu będzie "
        "widoczny we wszystkich modułach."
    )

    # --- dodawanie ----------------------------------------------------------
    st.subheader(
        "Dodaj instrument",
        help="Ticker w formacie Yahoo Finance. Jeśli wkleisz ticker z XTB "
             "(np. ALE.PL), appka sama zaproponuje poprawną wersję.",
    )

    kol_ticker, kol_przycisk = st.columns([3, 1], vertical_alignment="bottom")
    with kol_ticker:
        wpisany = st.text_input(
            "Ticker", key="wlasne_ticker", placeholder="np. ALE.WA, AAPL, SXR8.DE"
        ).strip().upper()
    with kol_przycisk:
        sprawdz = st.button(
            "🔍 Sprawdź", key="wlasne_sprawdz", use_container_width=True, type="primary"
        )

    # Wynik sprawdzenia trzymamy w session_state, bo przycisk „Dodaj" pojawia
    # się dopiero po weryfikacji, czyli w KOLEJNYM przebiegu skryptu.
    if sprawdz and wpisany:
        st.session_state["wlasne_wynik"] = _zweryfikuj(wpisany)

    wynik = st.session_state.get("wlasne_wynik")
    if wynik:
        _pokaz_wynik(wynik)

    st.divider()

    # --- lista --------------------------------------------------------------
    lista = db.wlasne_instrumenty()
    st.subheader(
        f"Dopisane instrumenty ({len(lista)})",
        help="Te instrumenty są skanowane codziennie razem z uniwersum "
             "wbudowanym. Usunięcie wpisu nie kasuje zebranych już migawek.",
    )

    if not lista:
        st.caption(
            "Jeszcze nic nie dopisałeś. Uniwersum wbudowane to składy głównych "
            "indeksów plus 69 ETF-ów — XTB oferuje ich około 1900, więc "
            "zawsze będzie czego dokładać."
        )
        return

    df = pd.DataFrame(lista)
    df["typ"] = df["typ"].map(ETYKIETY_TYPOW).fillna(df["typ"])
    df.columns = ["Ticker", "Nazwa", "Typ", "Dodano"]
    _render_table(df, height=min(400, 60 + 36 * len(df)))

    do_usuniecia = st.selectbox(
        "Usuń instrument", ["— wybierz —"] + [i["ticker"] for i in lista],
        key="wlasne_usun_wybor",
    )
    if do_usuniecia != "— wybierz —":
        if st.button(f"🗑️ Usuń {do_usuniecia}", key="wlasne_usun"):
            db.usun_wlasny(do_usuniecia)
            st.success(
                f"Usunięto {do_usuniecia}. Od następnego skanu nie będzie "
                f"pobierany; dotychczasowe migawki zostają nietknięte."
            )
            st.rerun()


def _zweryfikuj(wpisany: str) -> dict:
    """
    Trzy kontrole, każda z innego powodu:

    1. Czy nie jest już dopisany — baza i tak odrzuci duplikat (ticker jest
       kluczem głównym), ale komunikat „już go masz" jest użyteczniejszy niż
       cichy brak efektu.
    2. Czy nie ma go w uniwersum wbudowanym — dopisywanie spółki z WIG20 nie
       ma sensu i tylko zdublowałoby ją w skanie.
    3. Czy Yahoo faktycznie zwraca notowania. To najważniejsze: bez tego
       literówka wchodzi na listę i cicho wypada przy każdym nocnym skanie.
    """
    juz_wlasny = {i["ticker"] for i in db.wlasne_instrumenty()}
    if wpisany in juz_wlasny:
        return {"status": "duplikat", "ticker": wpisany}

    if wpisany in ALL_NAMES:
        return {"status": "wbudowany", "ticker": wpisany, "nazwa": ALL_NAMES[wpisany]}

    # Sprawdzamy też, czy wersja po tłumaczeniu z XTB nie jest już znana —
    # inaczej wklejenie „ALE.PL" dodałoby duplikat Allegro pod innym tickerem.
    przetlumaczony = xtb_to_yahoo(wpisany)
    if przetlumaczony != wpisany:
        if przetlumaczony in juz_wlasny:
            return {"status": "duplikat", "ticker": przetlumaczony}
        if przetlumaczony in ALL_NAMES:
            return {
                "status": "wbudowany",
                "ticker": przetlumaczony,
                "nazwa": ALL_NAMES[przetlumaczony],
                "poprawiony_z": wpisany,
            }

    odp = sprawdz_instrument(wpisany)
    return {"status": "ok" if odp.get("ok") else "brak", **odp}


def _pokaz_wynik(wynik: dict) -> None:
    status = wynik.get("status")

    if status == "duplikat":
        st.warning(
            f"**{wynik['ticker']} jest już na Twojej liście.** Nie dodaję drugi raz.",
            icon="⚠️",
        )
        return

    if status == "wbudowany":
        poprawka = (
            f" (rozpoznane z „{wynik['poprawiony_z']}”)" if wynik.get("poprawiony_z") else ""
        )
        st.info(
            f"**{wynik['ticker']} — {wynik.get('nazwa', '')} — jest już w uniwersum "
            f"wbudowanym**{poprawka}, więc jest skanowany codziennie. "
            f"Dopisywanie go nic nie zmieni.",
            icon="ℹ️",
        )
        return

    if status != "ok":
        st.error(wynik.get("powod", "Nie udało się sprawdzić instrumentu."), icon="⚠️")
        return

    # --- znaleziony ---------------------------------------------------------
    if wynik.get("poprawiony_z"):
        st.info(
            f"Ticker **{wynik['poprawiony_z']}** wygląda na format XTB — "
            f"poprawiłem go na **{wynik['ticker']}**, bo tego oczekuje Yahoo Finance.",
            icon="🔁",
        )

    st.success(
        f"**{wynik['ticker']} — {wynik['nazwa']}**  \n"
        f"Ostatnia cena: {wynik['cena']} {wynik['waluta']} · "
        f"rozpoznany typ: {ETYKIETY_TYPOW.get(wynik['typ'], wynik['typ'])}"
        + (f" · giełda: {wynik['gielda']}" if wynik.get("gielda") else ""),
        icon="✅",
    )

    if wynik["typ"] == "index":
        st.warning(
            "To indeks, nie spółka — nie ma bilansu ani zysków, więc wskaźniki "
            "fundamentalne (C/Z, ROE, marże) zostaną puste. Techniczne (RSI, "
            "średnie, dystans od szczytu) będą liczone normalnie.",
            icon="ℹ️",
        )

    kol_typ, kol_dodaj = st.columns([2, 1], vertical_alignment="bottom")
    with kol_typ:
        typ = st.selectbox(
            "Typ w uniwersum",
            list(ETYKIETY_TYPOW.keys()),
            index=list(ETYKIETY_TYPOW).index(wynik["typ"]),
            format_func=lambda t: ETYKIETY_TYPOW[t],
            key="wlasne_typ",
            help="Rozpoznany automatycznie z danych Yahoo — popraw, jeśli się myli.",
        )
    with kol_dodaj:
        if st.button("➕ Dodaj do uniwersum", key="wlasne_dodaj",
                     use_container_width=True, type="primary"):
            if db.dodaj_wlasny(wynik["ticker"], wynik["nazwa"], typ):
                st.session_state.pop("wlasne_wynik", None)
                st.success(
                    f"Dodano **{wynik['ticker']}**. Pojawi się w tabelach po "
                    f"najbliższym nocnym skanie — wcześniej nie ma dla niego "
                    f"żadnych danych."
                )
                st.rerun()
            else:
                st.error("Nie udało się dodać — instrument już istnieje.", icon="⚠️")
