"""
Appka Streamlit — szkielet. Sama zawartość zakładek siedzi w pakiecie ui/,
po jednym pliku na moduł (patrz ui/common.py po wspólne pomocniki).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _zastosuj_sekrety_streamlit() -> None:
    """
    Przepisuje sekrety z st.secrets do zmiennych środowiskowych.

    core/db.py celowo nie importuje streamlita (korzysta z niego też skrypt
    skanujący w GitHub Actions, gdzie streamlita nie ma), więc adres bazy
    i token czyta wyłącznie ze zmiennych środowiskowych. Ta funkcja jest
    mostkiem między jednym a drugim i MUSI wykonać się przed pierwszym
    dotknięciem bazy — stąd wywołanie tuż poniżej, przed importami ui/.

    Brak sekretów nie jest błędem: appka przechodzi wtedy w tryb lokalnego
    pliku data/history.db.
    """
    try:
        for klucz in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
            wartosc = st.secrets.get(klucz)
            if wartosc and not os.environ.get(klucz):
                os.environ[klucz] = str(wartosc)
    except Exception:  # noqa: BLE001
        # Brak pliku secrets.toml przy pracy lokalnej — normalna sytuacja.
        pass


_zastosuj_sekrety_streamlit()

# core/db.py można zaimportować przed st.set_page_config() — w przeciwieństwie
# do ui.common NIE wykonuje żadnych komend Streamlita przy imporcie (nie ma
# w nim funkcji z cache'em ani niczego, co rysuje). Jest tu potrzebny wcześnie,
# bo pytajnik przy tytule pokazuje tryb pracy bazy.
from core import db  # noqa: E402

# ---------------------------------------------------------------------------
# KOLEJNOŚĆ W TYM PLIKU JEST ISTOTNA — nie przestawiaj importów na górę!
#
# st.set_page_config() musi być pierwszą komendą Streamlita w całym przebiegu.
# Import ui.common wykonuje funkcje z cache'em (budowanie ALL_NAMES ze składów
# S&P), czyli komendy Streamlita — gdyby wykonał się przed set_page_config,
# appka wywaliłaby się przy starcie. Stąd importy modułów ui/ CELOWO stoją
# poniżej konfiguracji strony, z dopiskiem noqa dla lintera.
# ---------------------------------------------------------------------------
st.set_page_config(page_title="XTB Screener", layout="wide")

# Wyjaśnienia NIE stoją na wierzchu — chowamy je pod pytajnikiem obok tytułu
# i w stopce. Świadomy wymóg produktowy: ekran ma być przejrzysty, a opisy
# metodologii mają być dostępne wtedy, gdy ktoś ich szuka, a nie zajmować
# najlepsze miejsce na stronie przy każdym wejściu.
_tytul, _pomoc = st.columns([14, 1], vertical_alignment="bottom")
with _tytul:
    st.title("📊 XTB Stock & ETF Screener")
with _pomoc:
    with st.popover("❔", use_container_width=True, help="Skąd te dane?"):
        st.markdown(
            "**Dane:** Yahoo Finance, pobierane raz dziennie po zamknięciu "
            "rynków amerykańskich.\n\n"
            "**Uniwersum:** składy głównych indeksów (WIG, DAX, CAC40, FTSE100, "
            "IBEX35, OMX30, OBX, S&P 500 i 400) plus popularne ETF-y UCITS. "
            "Przed transakcją zweryfikuj dostępność instrumentu w platformie XTB "
            "— screener nie zna jej pełnej oferty.\n\n"
            "**Buy Score:** suma dziewięciu sygnałów technicznych i "
            "fundamentalnych. Im wyżej, tym więcej z nich zagrało naraz.\n\n"
            "**Czerwone flagi:** ostrzeżenia o kondycji spółki (zadłużenie, "
            "marże, wypłacalność dywidendy). Zero flag nie znaczy „dobra "
            "inwestycja\" — znaczy „nie znaleziono ostrzeżeń\"."
        )
        st.divider()
        # Cały blok w try/except, bo dotyka bazy — a nieobsłużony wyjątek
        # w Streamlicie psuje CAŁĄ stronę, nie tylko ten fragment. Chwilowa
        # niedostępność bazy zdalnej nie może wywalić appki przez kliknięcie
        # pytajnika.
        try:
            _tryb = db.tryb()
            _daty = db.list_dates()
            _ostatnia = _daty[0] if _daty else "brak"
            if _tryb == "zdalny":
                st.markdown(
                    f"**Źródło:** baza zdalna (Turso) · ostatnia migawka: `{_ostatnia}`"
                )
            else:
                st.warning(
                    f"**Tryb zapasowy — lokalna kopia bazy.** Ostatnia migawka: "
                    f"`{_ostatnia}`. Dane nie są odświeżane, bo appka nie ma "
                    f"dostępu do bazy zdalnej (brak sekretów `TURSO_DATABASE_URL` "
                    f"i `TURSO_AUTH_TOKEN`). To normalne przy uruchomieniu "
                    f"lokalnym; na produkcji oznacza problem z konfiguracją.",
                    icon="⚠️",
                )
        except Exception as _e:  # noqa: BLE001
            st.error(
                f"Nie udało się odczytać stanu bazy: {_e}. Jeśli widzisz to na "
                f"produkcji, sprawdź sekrety Turso i dostępność usługi.",
                icon="⚠️",
            )

# Subtelna, bezpieczna animacja hover na przyciskach/kartach — celuje w klasę
# .stButton, która jest stabilna w Streamlit od dawna, więc nie powinna się
# łatwo wysypać przy aktualizacji frameworka.
st.markdown(
    """
    <style>
    div.stButton > button {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        border-radius: 12px;
    }
    div.stButton > button:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 6px 14px rgba(0,0,0,0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

from core.scanner import compute_sentiment_index  # noqa: E402
from ui.common import (  # noqa: E402
    MODULE_REGISTRY, ALL_MODULE_KEYS, MODULE_CATEGORIES, MODULE_DESCRIPTIONS, _vix_level,
)
from ui.onboarding import render_onboarding_wizard  # noqa: E402
from ui.screener import render_screener  # noqa: E402
from ui.strategie import render_strategie  # noqa: E402
from ui.profil import render_profile  # noqa: E402
from ui.overview import render_overview  # noqa: E402
from ui.dashboard import render_dashboard  # noqa: E402
from ui.sector import render_sector  # noqa: E402
from ui.pe_anomaly import render_pe_anomaly  # noqa: E402
from ui.dividends import render_dividends  # noqa: E402
from ui.custom import render_custom  # noqa: E402
from ui.watchlist import render_watchlist  # noqa: E402
from ui.trade_review import render_trade_review  # noqa: E402
from ui.bt_strategy import render_bt_strategy  # noqa: E402
from ui.backtest import render_backtest  # noqa: E402


if not db.get_preference("onboarding_done", False):
    render_onboarding_wizard()
    st.stop()

if st.button("🎨 Uruchom kreator personalizacji ponownie", key="wiz_relaunch"):
    db.delete_preference("onboarding_done")
    st.session_state["onboarding_step"] = 1
    st.session_state.pop("wiz_manual_selected", None)
    st.rerun()

with st.expander("🧩 Wybierz widoczne moduły (zakładki)", expanded=False):
    st.caption(
        "Odznacz moduły, których nie używasz — znikną z widoku appki. Wybór "
        "zapisuje się jako domyślny i będzie pamiętany przy kolejnych wejściach "
        "(dopóki appka nie zostanie zredeployowana)."
    )
    saved_modules = db.get_preference("visible_modules", ALL_MODULE_KEYS)
    module_cols = st.columns(3)
    selected_modules: list[str] = []
    for i, (key, label) in enumerate(MODULE_REGISTRY):
        with module_cols[i % 3]:
            if st.checkbox(label, value=(key in saved_modules), key=f"mod_{key}"):
                selected_modules.append(key)

    mbsave, mbreset = st.columns(2)
    with mbsave:
        if st.button("💾 Zapisz jako domyślne", key="mod_save"):
            db.set_preference("visible_modules", selected_modules)
            st.success("Zapisano — te moduły będą domyślne przy kolejnych wejściach.")
    with mbreset:
        if st.button("↩️ Reset do wszystkich", key="mod_reset"):
            db.delete_preference("visible_modules")
            st.rerun()

if not selected_modules:
    st.warning("Odznaczono wszystkie moduły — zaznacz przynajmniej jeden powyżej, żeby coś zobaczyć.")
    st.stop()

with st.expander("📈 Ustawienia linków TradingView", expanded=False):
    st.caption(
        "TradingView dla niezalogowanych użytkowników przekierowuje ogólne linki do wykresu "
        "na stronę przeglądową spółki. Żeby linki w appce otwierały wykres bezpośrednio, "
        "wklej tu identyfikator SWOJEGO zapisanego layoutu z TradingView — to fragment "
        "adresu Twojego wykresu między `/chart/` a `/?symbol=`, np. dla adresu "
        "`tradingview.com/chart/PfVMrX1E/?symbol=NYSE:EL` to `PfVMrX1E`."
    )
    saved_layout_id = db.get_preference("tradingview_layout_id", "")
    layout_input = st.text_input(
        "Identyfikator layoutu TradingView", value=saved_layout_id, key="tv_layout_input",
        placeholder="np. PfVMrX1E",
    )
    tvsave, tvreset = st.columns(2)
    with tvsave:
        if st.button("💾 Zapisz layout", key="tv_layout_save"):
            db.set_preference("tradingview_layout_id", layout_input.strip())
            st.success("Zapisano — linki w appce będą teraz otwierać Twój layout.")
    with tvreset:
        if st.button("↩️ Wyczyść (wróć do ogólnego linku)", key="tv_layout_reset"):
            db.delete_preference("tradingview_layout_id")
            st.rerun()

# ---------------------------------------------------------------------------
# Budowa zakładek na bazie wybranych modułów (patrz panel "Wybierz widoczne
# moduły" na górze strony) i wywołanie odpowiednich funkcji render_*.
# ---------------------------------------------------------------------------
RENDER_FUNCS = {
    "screener": render_screener,
    "strategie": render_strategie,
    "profile": render_profile,
    "overview": render_overview,
    "dashboard": render_dashboard,
    "sector": render_sector,
    "pe_anomaly": render_pe_anomaly,
    "dividends": render_dividends,
    "custom": render_custom,
    "watchlist": render_watchlist,
    "trade_review": render_trade_review,
    "bt_strategy": render_bt_strategy,
    "backtest": render_backtest,
}


def _render_global_indicators_banner() -> None:
    """
    Pasek z VIX-em i wskaźnikiem nastrojów widoczny NAD zakładkami — czyli
    zawsze, niezależnie od tego, który moduł akurat oglądasz (Streamlit
    renderuje wszystko przed st.tabs() raz, poza samymi zakładkami).
    """
    vix = _vix_level()
    sentiment = None
    dates = db.list_dates()
    if dates:
        latest = db.load_snapshot(dates[0])
        stocks = latest[latest["Typ"] == "stock"] if "Typ" in latest.columns else latest

        def _pct_above(col: str):
            if col not in stocks.columns:
                return None
            valid = stocks.dropna(subset=[col, "Cena"])
            return float((valid["Cena"] > valid[col]).mean() * 100) if not valid.empty else None

        pct_sma50, pct_sma200 = _pct_above("SMA50"), _pct_above("SMA200")
        avg_rsi = float(stocks["RSI"].mean()) if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty else None
        sentiment = compute_sentiment_index(vix["value"] if vix else None, pct_sma50, pct_sma200, avg_rsi)

    with st.container(border=True):
        bc1, bc2, bc3 = st.columns([1, 1, 3])
        with bc1:
            if vix:
                st.metric(
                    "😨 VIX", vix["value"],
                    delta=f"{vix['change_pct']}%" if vix["change_pct"] is not None else None,
                    delta_color="inverse",
                    help="Indeks zmienności S&P500. <20 = spokojny rynek, 20-30 = podwyższona "
                         "zmienność, >30 = wysoki niepokój/panika.",
                )
            else:
                st.caption("😨 VIX: niedostępny")
        with bc2:
            if sentiment:
                st.metric(
                    "🎭 Nastroje", f"{sentiment['score']}/100",
                    help="Własny wskaźnik z VIX + szerokości rynku + RSI. <25 ekstremalny strach, "
                         "25-45 strach, 45-55 neutralnie, 55-75 chciwość, >75 ekstremalna chciwość.",
                )
            else:
                st.caption("🎭 Nastroje: brak danych")
        with bc3:
            st.caption(
                (f"**{sentiment['label']}** — " if sentiment else "")
                + "własna metodologia (VIX + szerokość rynku + śr. RSI), nie oficjalny CNN Fear & Greed. "
                "Pełne szczegóły w zakładce 🧪 Dashboard."
            )


_render_global_indicators_banner()

# ---------------------------------------------------------------------------
# NAWIGACJA PRZYCISKAMI (zamiast st.tabs)
#
# Powód nie jest wyłącznie estetyczny. st.tabs renderuje zawartość WSZYSTKICH
# zakładek przy każdym przebiegu skryptu — czyli ruch suwakiem w Screenerze
# przeliczał też Dashboard, oba backtesty i całą resztę. Przy nawigacji
# przyciskami wykonuje się wyłącznie oglądany moduł.
#
# UWAGA przy testowaniu: dawniej jedno wejście na stronę uruchamiało wszystkie
# 13 funkcji render_* i łapało każdy błąd importu. Teraz tak NIE jest — patrz
# scripts/sprawdz_moduly.py.
# ---------------------------------------------------------------------------
def _hex_na_rgb(hex_kolor: str) -> str:
    h = hex_kolor.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def _kolor_modulu(key: str) -> str:
    for _label, kolor, klucze in MODULE_CATEGORIES:
        if key in klucze:
            return kolor
    return "#8A8F98"


def _grupy_do_pokazania(widoczne: list[str]) -> list[tuple[str, str, list[str]]]:
    """Kategorie ograniczone do modułów włączonych przez użytkownika."""
    grupy = []
    przypisane: set[str] = set()
    for label, kolor, klucze in MODULE_CATEGORIES:
        w_grupie = [k for k in klucze if k in widoczne]
        przypisane.update(klucze)
        if w_grupie:
            grupy.append((label, kolor, w_grupie))
    # Moduł spoza kategorii nadal musi być dostępny.
    osierocone = [k for k in widoczne if k not in przypisane]
    if osierocone:
        grupy.append(("Pozostałe", "#8A8F98", osierocone))
    return grupy


def _style_nawigacji(widoczne: list[str], aktywny: str) -> None:
    """
    Koloruje przyciski nawigacji. Streamlit nadaje kontenerowi każdego widżetu
    klasę `st-key-<klucz>`, więc da się trafić w konkretny przycisk bez
    kruchych selektorów pozycyjnych.

    Podkład jest półprzezroczysty (rgba), dzięki czemu ten sam kolor działa
    na jasnym i na ciemnym motywie — nie trzeba wykrywać, który jest aktywny.
    """
    reguly = []
    for key in widoczne:
        rgb = _hex_na_rgb(_kolor_modulu(key))
        moc = "0.30" if key == aktywny else "0.10"
        grubosc = "5px" if key == aktywny else "4px"
        waga = "800" if key == aktywny else "600"
        reguly.append(
            f'.st-key-nav_{key} button {{'
            f' background-color: rgba({rgb}, {moc}) !important;'
            f' border: 1px solid rgba({rgb}, 0.35) !important;'
            f' border-left: {grubosc} solid rgb({rgb}) !important;'
            f' font-weight: {waga} !important;'
            f' text-align: left !important;'
            f' justify-content: flex-start !important;'
            f' }}'
            f'.st-key-nav_{key} button:hover {{'
            f' background-color: rgba({rgb}, 0.22) !important;'
            f' }}'
        )
    st.markdown("<style>" + "".join(reguly) + "</style>", unsafe_allow_html=True)


_etykiety = dict(MODULE_REGISTRY)
_widoczne = [key for key, _ in MODULE_REGISTRY if key in selected_modules]

# Moduł mógł zostać odznaczony po tym, jak był aktywny — wracamy do pierwszego.
_aktywny = st.session_state.get("aktywny_modul")
if _aktywny not in _widoczne:
    _aktywny = _widoczne[0]
    st.session_state["aktywny_modul"] = _aktywny

_style_nawigacji(_widoczne, _aktywny)

for _label_grupy, _kolor_grupy, _klucze in _grupy_do_pokazania(_widoczne):
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0 6px;'
        f'font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.09em;opacity:0.65;">'
        f'<span style="width:9px;height:9px;border-radius:3px;'
        f'background:{_kolor_grupy};display:inline-block;"></span>{_label_grupy}</div>',
        unsafe_allow_html=True,
    )
    _kolumny = st.columns(min(len(_klucze), 4))
    for _i, _key in enumerate(_klucze):
        with _kolumny[_i % len(_kolumny)]:
            if st.button(
                _etykiety[_key], key=f"nav_{_key}", use_container_width=True,
                help=MODULE_DESCRIPTIONS.get(_key),
            ):
                st.session_state["aktywny_modul"] = _key
                st.rerun()

st.divider()
RENDER_FUNCS[_aktywny]()


# ---------------------------------------------------------------------------
# Stopka — zastrzeżenia drobnym drukiem, na końcu strony zamiast na górze.
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Narzędzie do przeglądu i rankingu instrumentów, **nie porada inwestycyjna** "
    "— decyzje i ich skutki są po Twojej stronie. Wskaźniki liczone podczas "
    "codziennego skanu; newsy, wyniki finansowe, dane insiderów i korelacje "
    "pobierane na żądanie, po kliknięciu. Pełna metodologia — pod pytajnikiem "
    "przy tytule."
)
