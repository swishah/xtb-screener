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
    STRATEGIES, backtest_strategy, get_fx_rates, get_next_earnings_date, get_ticker_news,
    generate_brief, STRATEGY_MAX_SCORES,
)

st.set_page_config(page_title="XTB Screener", layout="wide")
st.title("📊 XTB Stock & ETF Screener")
st.caption(
    "Dane historyczne/fundamentalne: Yahoo Finance. Uniwersum tickerów oparte o "
    "składy głównych indeksów + popularne ETF-y UCITS — zweryfikuj dostępność "
    "konkretnego instrumentu w platformie XTB przed transakcją."
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

# ---------------------------------------------------------------------------
# Wskaźniki dostępne do wyboru w Screenerze — pogrupowane, z wyjaśnieniami
# pokazywanymi jako dymek (hover) na nagłówku kolumny w tabeli.
# ---------------------------------------------------------------------------
INDICATOR_GROUPS: dict[str, list[str]] = {
    "Podstawowe": ["Rynek", "Typ", "Sektor", "Branża", "Waluta", "Cena (PLN)", "Kapitalizacja (mld)"],
    "Wycena": ["C/Z (P/E)", "Forward C/Z", "C/WK (P/B)"],
    "Rentowność i wzrost": [
        "ROE (%)", "Marża Operac. (%)", "Marża netto (%)", "Marża brutto (%)",
        "Wzrost przychodów (%)", "Wzrost EPS (%)",
    ],
    "Zadłużenie i bezpieczeństwo": ["Dług/Kapitał", "Payout ratio (%)", "Liczba flag", "Czerwone flagi"],
    "Dywidendy": [
        "Stopa Dyw. (%)", "Lata z dywidendą (3Y)", "Poprzednia dywidenda", "Przyszła dywidenda",
        "Dyw. w poprzednim roku", "Dyw. w tym roku",
    ],
    "Technika": [
        "RSI", "MACD", "SMA20", "SMA50", "SMA100", "SMA200", "bollinger_pct",
        "volume_ratio", "smc", "pct_from_ath", "ATH", "ATL", "Zmiana ceny (1Y%)",
    ],
    "Prognozy analityków i ryzyko": [
        "Beta", "52-tyg. maksimum", "52-tyg. minimum", "Cena docelowa (analitycy)",
        "Rekomendacja analityków", "Liczba analityków", "% udziałów instytucji",
    ],
    "Scoring": [
        "Buy Score", "Score: Deep Value", "Score: Momentum",
        "Score: Dywidendowa", "Score: Dywidenda-Okazja",
    ],
}

GROUP_ICONS: dict[str, str] = {
    "Podstawowe": "🏷️",
    "Wycena": "💵",
    "Rentowność i wzrost": "📈",
    "Zadłużenie i bezpieczeństwo": "🛡️",
    "Dywidendy": "💰",
    "Technika": "📊",
    "Prognozy analityków i ryzyko": "🔮",
    "Scoring": "🏆",
}

INDICATOR_HELP: dict[str, str] = {
    "Rynek": "Giełda/kraj notowania spółki.",
    "Typ": "Akcja (stock) czy fundusz notowany na giełdzie (etf).",
    "Sektor": "Sektor gospodarki wg klasyfikacji Yahoo Finance (np. Technology, Financial Services).",
    "Branża": "Węższa kategoria biznesu w ramach sektora (np. 'Software – Application').",
    "Waluta": "Waluta notowania spółki na jej giełdzie macierzystej.",
    "Cena (PLN)": "Cena przeliczona na złote wg bieżącego kursu — ułatwia porównania między rynkami.",
    "Kapitalizacja (mld)": (
        "Wartość rynkowa całej spółki (cena × liczba akcji), w mld jednostek waluty notowania. "
        "Duża kapitalizacja (>10 mld) = zwykle stabilniejsza, wolniej rosnąca spółka; "
        "mała (<2 mld) = większy potencjał wzrostu, ale i większe ryzyko."
    ),
    "C/Z (P/E)": (
        "Cena do zysku na akcję — ile lat zysku 'kosztuje' spółka przy obecnej cenie. "
        "Ogólnie <15 uznaje się za tanie, >25 za drogie. UWAGA: mocno zależy od sektora — "
        "spółki technologiczne/wzrostowe zwykle mają wyższe C/Z (20-40+) uzasadnione szybkim "
        "wzrostem, a banki/utilities/przemysł ciężki zwykle niższe (8-15). Porównuj w obrębie sektora."
    ),
    "Forward C/Z": (
        "C/Z liczone na PROGNOZOWANYM zysku za najbliższy rok, nie historycznym — niższe niż "
        "zwykłe C/Z sugeruje, że rynek oczekuje wzrostu zysków."
    ),
    "C/WK (P/B)": (
        "Cena do wartości księgowej — ile płacisz za 1 jednostkę majątku netto spółki. <1 może "
        "oznaczać niedowartościowanie (albo problemy), >3 typowe dla spółek z małym majątkiem "
        "trwałym (np. software). Najbardziej użyteczne przy bankach i spółkach majątkowych."
    ),
    "ROE (%)": (
        "Zwrot z kapitału własnego — jak efektywnie spółka pomnaża pieniądze akcjonariuszy. "
        ">15% uznaje się za dobre, >20% za bardzo dobre. Banki i spółki technologiczne zwykle "
        "mają wyższe ROE niż np. utilities czy przemysł ciężki."
    ),
    "Marża Operac. (%)": (
        "Zysk operacyjny / przychody — rentowność podstawowej działalności. >15% dobre, >25% "
        "bardzo dobre — ale np. handel detaliczny normalnie ma niskie marże (3-8%), a software wysokie (20-40%)."
    ),
    "Marża netto (%)": (
        "Zysk netto / przychody — ile z każdej złotówki przychodu zostaje czystego zysku. "
        "Ujemna = spółka traci pieniądze. Dobre wartości to zwykle 10-20%, zależnie od branży."
    ),
    "Marża brutto (%)": (
        "Przychody minus koszt wytworzenia / przychody. Wysoka (>50%) typowa dla software/farmacji, "
        "niska (10-25%) dla handlu/przemysłu — sama w sobie nie mówi, czy to dobrze czy źle."
    ),
    "Wzrost przychodów (%)": "Zmiana przychodów rok do roku. >10% to solidny wzrost, ujemny to sygnał ostrzegawczy.",
    "Wzrost EPS (%)": (
        "Zmiana zysku na akcję rok do roku — ważniejsza niż wzrost przychodów, bo pokazuje, "
        "czy wzrost faktycznie przekłada się na zysk dla akcjonariusza."
    ),
    "Dług/Kapitał": (
        "Zadłużenie względem kapitału własnego (%). <50% bezpiecznie, 50-150% umiarkowanie, "
        ">150% wysokie ryzyko. Branże kapitałochłonne (utilities, telekomy, nieruchomości) "
        "normalnie mają wyższy dług niż software."
    ),
    "Payout ratio (%)": (
        "Jaki % zysku spółka wypłaca jako dywidendę. <60% zwykle bezpieczne, >100% oznacza "
        "wypłacanie więcej niż się zarabia — sygnał ostrzegawczy."
    ),
    "Liczba flag": "Liczba automatycznych ostrzeżeń wykrytych w danych spółki. 0 = brak wykrytych problemów.",
    "Czerwone flagi": "Konkretne powody ostrzeżeń — np. ujemna marża, wysoki dług, malejące przychody.",
    "Stopa Dyw. (%)": (
        ">4% uznaje się za wysoką stopę, ale bardzo wysoka (>8%) bywa sygnałem, że rynek "
        "oczekuje cięcia dywidendy — zawsze sprawdź Payout ratio obok."
    ),
    "Lata z dywidendą (3Y)": "Ile z ostatnich 3 lat spółka wypłaciła dywidendę — 3 oznacza nieprzerwaną historię.",
    "Poprzednia dywidenda": "Data ostatniej faktycznie wypłaconej dywidendy.",
    "Przyszła dywidenda": "Najbliższa zapowiedziana data — BRAK, jeśli Yahoo nie ma potwierdzonej przyszłej daty (częste poza USA).",
    "Dyw. w poprzednim roku": "Czy spółka wypłaciła dywidendę w POPRZEDNIM roku kalendarzowym.",
    "Dyw. w tym roku": "Czy spółka wypłaciła już dywidendę w BIEŻĄCYM roku. 'Nie' + wypłata w zeszłym roku = wypłata jeszcze przed nią w tym roku.",
    "RSI": "Relative Strength Index (0-100). <30 = wyprzedanie (potencjalna okazja), >70 = wykupienie (ryzyko korekty).",
    "MACD": "Różnica krótko- i długoterminowej średniej kroczącej — dodatnia i rosnąca sugeruje trend wzrostowy.",
    "SMA20": "Średnia krocząca z 20 dni. Cena powyżej = krótkoterminowy trend wzrostowy.",
    "SMA50": "Średnia krocząca z 50 dni — trend średnioterminowy.",
    "SMA100": "Średnia krocząca z 100 dni.",
    "SMA200": "Średnia krocząca z 200 dni — klasyczny wyznacznik długoterminowej hossy/bessy.",
    "bollinger_pct": "Pozycja ceny we wstędze Bollingera (0 = dolna wstęga, 1 = górna). Blisko 0 = nisko względem niedawnej zmienności.",
    "volume_ratio": "Dzisiejszy wolumen względem średniej z 20 dni. >1.3 = wyraźnie podwyższone zainteresowanie.",
    "smc": "Prosty sygnał 'Smart Money Concept' — potencjalne wybicie z dołka poprzedzone zwiększonym wolumenem.",
    "pct_from_ath": (
        "% odległości ceny od historycznego maksimum. Duży spadek (<-30%) to podstawa strategii "
        "Deep Value — ale sprawdź fundamenty, żeby odróżnić okazję od spółki w realnych problemach."
    ),
    "ATH": "Historyczne maksimum ceny w analizowanym okresie (do 10 lat).",
    "ATL": "Historyczne minimum ceny w analizowanym okresie (do 10 lat).",
    "Zmiana ceny (1Y%)": "Zmiana ceny w ciągu ostatniego roku — pomaga ocenić, czy rynek już 'zauważył' spółkę.",
    "Beta": (
        "Zmienność spółki względem szerokiego rynku. Beta=1 = podobna zmienność do rynku, "
        ">1 = bardziej zmienna (większe wahania w obie strony), <1 = bardziej defensywna."
    ),
    "52-tyg. maksimum": "Najwyższa cena w ciągu ostatnich 12 miesięcy.",
    "52-tyg. minimum": "Najniższa cena w ciągu ostatnich 12 miesięcy.",
    "Cena docelowa (analitycy)": "Średnia cena docelowa wg analityków śledzących spółkę — konsensus rynkowy, nie gwarancja.",
    "Rekomendacja analityków": "Skrócona rekomendacja konsensusu (Kupuj/Trzymaj/Sprzedaj).",
    "Liczba analityków": "Ilu analityków wydało rekomendację — więcej zwykle oznacza bardziej wiarygodny konsensus.",
    "% udziałów instytucji": "Jaki % akcji jest w rękach funduszy/inwestorów instytucjonalnych.",
    "Buy Score": "Suma podstawowych sygnałów technicznych kupna (RSI, MACD, trend, wolumen, dystans od ATH).",
    "Score: Deep Value": "Premiuje duży dystans od ATH przy zdrowych fundamentach (ROE, marża, wzrost EPS, dług).",
    "Score: Momentum": "Premiuje spółki w silnym, potwierdzonym trendzie wzrostowym.",
    "Score: Dywidendowa": "Premiuje solidną stopę dywidendy przy zdrowych fundamentach i nieprzerwanej historii wypłat.",
    "Score: Dywidenda-Okazja": "Wysoka dywidenda przy cenie, która jeszcze się nie ruszyła, plus bezpieczny payout ratio.",
}

TEXT_COLUMNS = {
    "Ticker", "Nazwa", "Rynek", "Typ", "Sektor", "Branża", "Waluta",
    "Czerwone flagi", "Poprzednia dywidenda", "Przyszła dywidenda",
    "Dyw. w poprzednim roku", "Dyw. w tym roku",
    "smc", "Rekomendacja analityków",
}

DEFAULT_SCREENER_COLUMNS = [
    "Rynek", "Sektor", "C/Z (P/E)", "ROE (%)", "Stopa Dyw. (%)",
    "RSI", "pct_from_ath", "Buy Score", "Liczba flag",
]


def _column_config_for(columns: list[str]) -> dict:
    config = {}
    for col in columns:
        help_text = INDICATOR_HELP.get(col, "")
        if col in TEXT_COLUMNS:
            config[col] = st.column_config.TextColumn(col, help=help_text)
        else:
            config[col] = st.column_config.NumberColumn(col, help=help_text)
    return config


def _personalize_columns(
    pref_key: str,
    available_columns: list[str],
    default_columns: list[str],
    mandatory_columns: list[str],
    label: str = "Personalizuj widoczne wskaźniki",
) -> list[str]:
    """
    Selektor kolumn: kafelki kategorii na górze (klik = pokazuje listę
    wskaźników tej kategorii poniżej), zamiast wszystkich list naraz.
    Zapis/reset per pref_key — każda tabela ma własny, niezależny wybór.
    Zwraca finalną listę kolumn do wyświetlenia (mandatory_columns zawsze
    pierwsze, bez duplikatów).
    """
    with st.expander(f"🎛️ {label}", expanded=False):
        st.caption(
            f"{', '.join(mandatory_columns)} zawsze widoczne. Wybór zapisuje się "
            "jako domyślny i będzie pamiętany przy kolejnych wejściach "
            "(dopóki appka nie zostanie zredeployowana)."
        )
        saved_cols = db.get_preference(pref_key, default_columns)

        relevant_groups = [
            (name, [c for c in cols if c in available_columns and c not in mandatory_columns])
            for name, cols in INDICATOR_GROUPS.items()
        ]
        relevant_groups = [(name, cols) for name, cols in relevant_groups if cols]

        active_state_key = f"active_group__{pref_key}"
        if active_state_key not in st.session_state or st.session_state[active_state_key] not in dict(relevant_groups):
            st.session_state[active_state_key] = relevant_groups[0][0] if relevant_groups else None

        # inicjalizacja stanu każdej grupy (raz), żeby wartości przetrwały
        # przełączanie kafelków, nawet dla grup jeszcze nieotwartych
        for group_name, group_cols in relevant_groups:
            state_key = f"pick_{pref_key}_{group_name}"
            if state_key not in st.session_state:
                st.session_state[state_key] = [c for c in saved_cols if c in group_cols]

        if relevant_groups:
            st.caption("Wybierz kategorię, żeby zobaczyć jej wskaźniki:")
            tile_cols = st.columns(len(relevant_groups))
            for i, (group_name, group_cols) in enumerate(relevant_groups):
                with tile_cols[i]:
                    n_selected = len(st.session_state[f"pick_{pref_key}_{group_name}"])
                    is_active = st.session_state[active_state_key] == group_name
                    icon = GROUP_ICONS.get(group_name, "📁")
                    tile_label = f"{icon} {group_name}" + (f" ({n_selected})" if n_selected else "")
                    if st.button(
                        tile_label, key=f"tile_{pref_key}_{group_name}", use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state[active_state_key] = group_name
                        st.rerun()

            active_group = st.session_state[active_state_key]
            active_cols = dict(relevant_groups)[active_group]
            st.multiselect(
                f"Wskaźniki — {active_group}", active_cols,
                key=f"pick_{pref_key}_{active_group}",
            )

        chosen_cols: list[str] = []
        for group_name, _ in relevant_groups:
            chosen_cols.extend(st.session_state[f"pick_{pref_key}_{group_name}"])

        bsave, breset = st.columns(2)
        with bsave:
            if st.button("💾 Zapisz jako domyślne", key=f"save_{pref_key}"):
                db.set_preference(pref_key, chosen_cols)
                st.success("Zapisano.")
        with breset:
            if st.button("↩️ Reset do domyślnych", key=f"reset_{pref_key}"):
                db.delete_preference(pref_key)
                for group_name, _ in relevant_groups:
                    st.session_state.pop(f"pick_{pref_key}_{group_name}", None)
                st.session_state.pop(active_state_key, None)
                st.rerun()

    active = chosen_cols if chosen_cols else default_columns
    return list(mandatory_columns) + [
        c for c in active if c in available_columns and c not in mandatory_columns
    ]


# ---------------------------------------------------------------------------
# Kolorowanie tabel — wspólne dla całej appki. Każda funkcja jest owinięta
# w try/except per kolumna, więc nietypowe dane (np. "BRAK" wymieszane z
# liczbami) nigdy nie wywalają całej tabeli — w najgorszym razie ta jedna
# kolumna po prostu zostaje bez koloru.
# ---------------------------------------------------------------------------
GREEN_HIGHER_BETTER = [
    "Buy Score", "Score: Deep Value", "Score: Momentum", "Score: Dywidendowa",
    "Score: Dywidenda-Okazja", "Własny wynik", "ROE (%)", "Marża Operac. (%)",
    "Marża netto (%)", "Marża brutto (%)", "Wzrost przychodów (%)", "Wzrost EPS (%)",
    "Stopa Dyw. (%)", "Win rate %", "Deep Value Score", "Liczba strategii (w TOP N)",
]
RED_HIGHER_WORSE = ["Dług/Kapitał", "Liczba flag", "Payout ratio (%)", "C/Z (P/E)"]
DIVERGING_ZERO_CENTERED = [
    "Zmiana ceny (1Y%)", "Zmiana %", "pct_from_ath", "Śr. zwrot %", "Skumulowany zwrot %",
]


def _rsi_cell_style(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v < 30:
        return "background-color: #1b5e20; color: white"
    if v > 70:
        return "background-color: #7f0000; color: white"
    return ""


def _numeric_gradient_style(series: pd.Series, cmap: str, center: float | None = None) -> list[str]:
    """
    Liczy kolor tła komórki na bazie wartości liczbowej w kolumnie — sam
    konwertuje na liczby (errors='coerce'), więc nienumeryczne wartości typu
    'BRAK' po prostu zostają bez koloru zamiast wywalać całą tabelę (co robi
    wbudowany pandas .background_gradient() przy mieszanych typach danych).
    """
    try:
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors
    except Exception:  # noqa: BLE001
        return ["" for _ in series]

    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return ["" for _ in series]
    lo, hi = float(valid.min()), float(valid.max())
    if lo == hi:
        return ["" for _ in series]

    try:
        if center is not None:
            max_abs = max(abs(lo - center), abs(hi - center)) or 1.0
            norm = mcolors.TwoSlopeNorm(vmin=center - max_abs, vcenter=center, vmax=center + max_abs)
        else:
            norm = mcolors.Normalize(vmin=lo, vmax=hi)
        try:
            import matplotlib
            colormap = matplotlib.colormaps[cmap]
        except Exception:  # noqa: BLE001
            colormap = cm.get_cmap(cmap)
    except Exception:  # noqa: BLE001
        return ["" for _ in series]

    styles = []
    for v in numeric:
        if pd.isna(v):
            styles.append("")
            continue
        try:
            r, g, b, _ = colormap(norm(float(v)))
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = "white" if luminance < 0.6 else "black"
            styles.append(f"background-color: rgba({int(r * 255)},{int(g * 255)},{int(b * 255)},0.85); color: {text_color}")
        except Exception:  # noqa: BLE001
            styles.append("")
    return styles


def _style_table(df: pd.DataFrame):
    """Zwraca pandas.Styler z kolorowaniem wg znaczenia kolumn — albo surowy
    df bez zmian, jeśli stylowanie się nie powiedzie (np. brak matplotlib)."""
    try:
        styler = df.style
    except Exception:  # noqa: BLE001
        return df

    for col in GREEN_HIGHER_BETTER:
        if col in df.columns:
            try:
                styler = styler.apply(lambda s: _numeric_gradient_style(s, "Greens"), subset=[col])
            except Exception:  # noqa: BLE001
                pass

    for col in RED_HIGHER_WORSE:
        if col in df.columns:
            try:
                styler = styler.apply(lambda s: _numeric_gradient_style(s, "Reds"), subset=[col])
            except Exception:  # noqa: BLE001
                pass

    for col in DIVERGING_ZERO_CENTERED:
        if col in df.columns:
            try:
                styler = styler.apply(lambda s: _numeric_gradient_style(s, "RdYlGn", center=0.0), subset=[col])
            except Exception:  # noqa: BLE001
                pass

    if "RSI" in df.columns:
        try:
            styler = styler.map(_rsi_cell_style, subset=["RSI"])
        except Exception:  # noqa: BLE001
            try:
                styler = styler.applymap(_rsi_cell_style, subset=["RSI"])  # starsze pandas
            except Exception:  # noqa: BLE001
                pass

    return styler


def _render_table(df: pd.DataFrame, height: int = 600) -> None:
    """Wspólny renderer tabel: kolorowanie + dymki z wyjaśnieniami naraz,
    z bezpiecznym fallbackiem do zwykłej tabeli, gdyby coś nie zagrało."""
    columns = list(df.columns)
    config = _column_config_for(columns)
    try:
        st.dataframe(_style_table(df), use_container_width=True, height=height, column_config=config)
    except Exception:  # noqa: BLE001
        st.dataframe(df, use_container_width=True, height=height, column_config=config)


# (kolumna, kierunek "higher"/"lower" = co jest lepiej) — używane do dynamicznego
# porównania spółki z medianą JEJ WŁASNEGO sektora w bieżącej migawce.
SECTOR_METRICS: list[tuple[str, str]] = [
    ("C/Z (P/E)", "lower"),
    ("Forward C/Z", "lower"),
    ("C/WK (P/B)", "lower"),
    ("ROE (%)", "higher"),
    ("Marża Operac. (%)", "higher"),
    ("Marża netto (%)", "higher"),
    ("Marża brutto (%)", "higher"),
    ("Dług/Kapitał", "lower"),
    ("Wzrost przychodów (%)", "higher"),
    ("Wzrost EPS (%)", "higher"),
    ("Stopa Dyw. (%)", "higher"),
    ("Payout ratio (%)", "lower"),
    ("RSI", "lower"),
]


@st.cache_data(ttl=24 * 3600)
def _us_maps() -> tuple[dict, dict]:
    return get_sp500_map(), get_sp400_map()


@st.cache_data(ttl=6 * 3600)
def _fx_rates(currencies: tuple[str, ...]) -> dict[str, float]:
    return get_fx_rates(set(currencies), target="PLN")


@st.cache_data(ttl=6 * 3600)
def _earnings_date(ticker: str) -> str | None:
    return get_next_earnings_date(ticker)


@st.cache_data(ttl=2 * 3600)
def _ticker_news(ticker: str) -> list[dict]:
    return get_ticker_news(ticker)


sp500_map, sp400_map = _us_maps()
ALL_NAMES = {t: n for g in STOCK_GROUPS.values() for t, n in g.items()}
ALL_NAMES.update(ETF_MAP)
ALL_NAMES.update(sp500_map)
ALL_NAMES.update(sp400_map)

# ---------------------------------------------------------------------------
# Rejestr modułów (zakładek) — pozwala użytkownikowi wybrać, które moduły
# w ogóle chce mieć widoczne. Funkcje render_* są zdefiniowane niżej w pliku;
# same zakładki i wywołania budowane są dynamicznie na samym końcu skryptu.
# ---------------------------------------------------------------------------
MODULE_REGISTRY = [
    ("screener", "🔍 Screener"),
    ("strategie", "🧭 Strategie"),
    ("profile", "🔎 Profil spółki"),
    ("overview", "🌍 Globalny przegląd"),
    ("sector", "📊 vs Sektor"),
    ("dividends", "💰 Dywidendy"),
    ("custom", "🎛️ Własny scoring"),
    ("watchlist", "⭐ Watchlist"),
    ("bt_strategy", "📈 Backtest strategii"),
    ("backtest", "⏪ Backtest spółki"),
]
ALL_MODULE_KEYS = [key for key, _ in MODULE_REGISTRY]

MODULE_DESCRIPTIONS = {
    "screener": "Filtrowanie i przegląd wszystkich zeskanowanych spółek/ETF-ów naraz.",
    "strategie": "Gotowe strategie inwestycyjne (Deep Value, Momentum, Dywidendowa i inne).",
    "profile": "Wpisz spółkę i zobacz WSZYSTKIE jej dane naraz + krótki brief inwestycyjny.",
    "overview": "Kondycja całego rynku na raz — szerokość, heatmapy, top ruchy dnia.",
    "sector": "Porównanie spółki z medianą jej sektora — dynamicznie, na żywo.",
    "dividends": "Szukanie tanich spółek przed sezonem dywidendowym.",
    "custom": "Własny ranking na bazie wag wskaźników, które sam ustawisz.",
    "watchlist": "Lista obserwowanych spółek z Twoimi notatkami.",
    "bt_strategy": "Sprawdzenie historycznej skuteczności każdej strategii.",
    "backtest": "Szczegóły jednej spółki wstecz w czasie + najnowsze newsy.",
}

# "Profile inwestora" — jeden klik ustawia sensowny zestaw modułów i kolumn
# Screenera naraz, zamiast ręcznego przebijania się przez wszystkie opcje.
PROFILES = [
    {
        "key": "dividend",
        "label": "💰 Dywidendowy",
        "desc": "Szukam stabilnych spółek z wysoką, bezpieczną dywidendą.",
        "modules": ["screener", "strategie", "profile", "dividends", "watchlist", "backtest"],
        "screener_columns": [
            "Rynek", "Sektor", "Stopa Dyw. (%)", "Payout ratio (%)",
            "Dyw. w tym roku", "ROE (%)", "Liczba flag",
        ],
    },
    {
        "key": "deep_value",
        "label": "📉 Deep Value (okazje)",
        "desc": "Szukam spółek mocno przecenionych, ale wciąż zdrowych fundamentalnie.",
        "modules": ["screener", "strategie", "profile", "overview", "sector", "watchlist", "bt_strategy", "backtest"],
        "screener_columns": [
            "Rynek", "Sektor", "pct_from_ath", "ROE (%)",
            "Marża Operac. (%)", "Dług/Kapitał", "Liczba flag",
        ],
    },
    {
        "key": "momentum",
        "label": "🚀 Momentum",
        "desc": "Szukam spółek w silnym, potwierdzonym trendzie wzrostowym.",
        "modules": ["screener", "strategie", "profile", "overview", "custom", "bt_strategy", "backtest"],
        "screener_columns": [
            "Rynek", "RSI", "volume_ratio", "SMA50", "SMA200", "pct_from_ath", "Buy Score",
        ],
    },
    {
        "key": "everything",
        "label": "🧭 Chcę widzieć wszystko",
        "desc": "Pokaż mi pełen zestaw modułów i wskaźników — sam sobie dobiorę.",
        "modules": list(ALL_MODULE_KEYS),
        "screener_columns": list(DEFAULT_SCREENER_COLUMNS),
    },
]


def _card(title: str, desc: str, button_label: str, key: str, primary: bool = False) -> bool:
    """Klikalna 'karta' (obwiedziony kontener) z tytułem, opisem i przyciskiem
    wyboru. Zwraca True dokładnie w tym przebiegu, w którym kliknięto przycisk."""
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.caption(desc)
        return st.button(
            button_label, key=key, use_container_width=True,
            type="primary" if primary else "secondary",
        )


def render_onboarding_wizard() -> None:
    """Kreator powitalny pokazywany, dopóki użytkownik go nie ukończy albo
    nie pominie. Krok po kroku, kafelkami — zamiast jednej gęstej listy."""
    step = st.session_state.get("onboarding_step", 1)
    st.header("👋 Witaj w XTB Screenerze!")

    if step == 1:
        st.write(
            "Chcesz, żebym w kilku krokach dopasował widok appki do Twojego stylu "
            "inwestowania? Zajmie to dosłownie kilka kliknięć."
        )
        c1, c2 = st.columns(2)
        with c1:
            if _card("✨ Tak, dopasuj do mnie", "Wybierzesz profil albo moduły ręcznie.",
                      "Zaczynamy", "wiz_start", primary=True):
                st.session_state["onboarding_step"] = 2
                st.rerun()
        with c2:
            if _card("⏭️ Pomiń", "Pokaż mi od razu wszystkie moduły i wskaźniki.",
                      "Pomiń personalizację", "wiz_skip"):
                db.set_preference("visible_modules", ALL_MODULE_KEYS)
                db.set_preference("onboarding_done", True)
                st.rerun()

    elif step == 2:
        st.write("Wybierz profil, który najlepiej Cię opisuje:")
        profile_cols = st.columns(2)
        for i, profile in enumerate(PROFILES):
            with profile_cols[i % 2]:
                if _card(profile["label"], profile["desc"], "Wybierz ten profil",
                          f"wiz_profile_{profile['key']}"):
                    db.set_preference("visible_modules", profile["modules"])
                    db.set_preference("screener_columns", profile["screener_columns"])
                    st.session_state["onboarding_chosen_profile"] = profile["label"]
                    st.session_state["onboarding_step"] = 3
                    st.rerun()

        st.divider()
        if st.button("🧩 Żaden z tych — wybiorę moduły sam", key="wiz_manual"):
            st.session_state["onboarding_step"] = "manual"
            st.rerun()

    elif step == "manual":
        st.write("Kliknij moduły, które chcesz mieć widoczne — resztę zawsze dodasz później.")
        if "wiz_manual_selected" not in st.session_state:
            st.session_state["wiz_manual_selected"] = set(ALL_MODULE_KEYS)

        cols = st.columns(3)
        for i, (mkey, mlabel) in enumerate(MODULE_REGISTRY):
            with cols[i % 3]:
                is_selected = mkey in st.session_state["wiz_manual_selected"]
                with st.container(border=True):
                    st.markdown(f"### {mlabel}")
                    st.caption(MODULE_DESCRIPTIONS.get(mkey, ""))
                    btn_label = "✅ Wybrany" if is_selected else "➕ Dodaj"
                    if st.button(btn_label, key=f"wiz_mod_{mkey}", use_container_width=True,
                                  type="primary" if is_selected else "secondary"):
                        if is_selected:
                            st.session_state["wiz_manual_selected"].discard(mkey)
                        else:
                            st.session_state["wiz_manual_selected"].add(mkey)
                        st.rerun()

        st.divider()
        if st.button("✅ Zatwierdź wybór", key="wiz_manual_confirm", type="primary"):
            db.set_preference("visible_modules", list(st.session_state["wiz_manual_selected"]))
            st.session_state["onboarding_chosen_profile"] = "Twój własny wybór modułów"
            st.session_state["onboarding_step"] = 3
            st.rerun()

    elif step == 3:
        chosen = st.session_state.get("onboarding_chosen_profile", "Twój wybór")
        st.success(f"✅ Gotowe! Appka jest dopasowana: **{chosen}**.")
        st.caption(
            "Zawsze możesz to zmienić w panelu '🧩 Wybierz widoczne moduły' na górze "
            "strony, albo w personalizacji wskaźników wewnątrz każdej zakładki."
        )
        if st.button("🚀 Przejdź do appki", key="wiz_finish", type="primary"):
            db.set_preference("onboarding_done", True)
            st.rerun()


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

# ---------------------------------------------------------------------------
# TAB 1 — Screener na bazie ostatniej zapisanej migawki
# ---------------------------------------------------------------------------
def render_screener():
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
            mandatory_columns=["Ticker", "Nazwa", "Cena"],
        )

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
                _render_table(edf, height=300)
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
    "Dywidenda-okazja (sezon dywidendowy)": (
        "Szuka spółek, które regularnie płacą dywidendę i zapłaciły w POPRZEDNIM "
        "roku, ale JESZCZE NIE zapłaciły w bieżącym — wypłata jest więc dopiero "
        "przed nimi ('sezon dywidendowy' wciąż w toku). Plus sprawdzone payout "
        "ratio i wzrost przychodów, żeby odróżnić okazję od pułapki dywidendowej."
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
                mandatory_columns=["Ticker", "Nazwa", "Cena"],
                label=f"Personalizuj kolumny dla: {strategy_name}",
            )
            ranked = df[df["Typ"] == "stock"].sort_values(score_col, ascending=False).head(30)
            display_cols = [c for c in active_strategy_cols + [score_col] if c in ranked.columns]
            display_cols = list(dict.fromkeys(display_cols))  # usuń ewentualny duplikat score_col
            _render_table(ranked[display_cols], height=600)

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
                _render_table(conv_df[show_cols], height=400)

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

    m1, m2, m3, m4 = st.columns(4)
    cena = row.get("Cena")
    waluta = row.get("Waluta", "")
    m1.metric("Cena", f"{cena} {waluta}" if cena is not None else "BRAK")
    if waluta and waluta != "PLN":
        try:
            rate = _fx_rates((waluta,)).get(waluta)
            if rate and isinstance(cena, (int, float)):
                m2.metric("Cena (PLN)", f"{round(cena * rate, 2)} PLN")
        except Exception:  # noqa: BLE001
            pass
    m3.metric("Buy Score", row.get("Buy Score", "BRAK"))
    n_flags = row.get("Liczba flag", 0)
    m4.metric("Czerwone flagi", n_flags, delta=None)

    st.divider()
    st.subheader("📋 Brief inwestycyjny")
    for line in generate_brief(row):
        st.write(f"- {line}")
    if row.get("Czerwone flagi", "Brak") != "Brak":
        with st.expander("Zobacz treść czerwonych flag"):
            for f in str(row.get("Czerwone flagi", "")).split("; "):
                st.write(f)

    st.divider()
    st.subheader("🧭 Wszystkie strategie na raz")
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

    st.divider()
    st.subheader("📚 Wszystkie dane, wg kategorii")
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

# ---------------------------------------------------------------------------
# TAB 4 — Globalny przegląd: kondycja całego rynku, niezależnie od strategii
# ---------------------------------------------------------------------------
def render_overview():
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
                _render_table(merged.sort_values("Zmiana %", ascending=False).head(10)[show_cols], height=350)
            with cold:
                st.write("📉 Największe spadki")
                _render_table(merged.sort_values("Zmiana %", ascending=True).head(10)[show_cols], height=350)
        else:
            st.info("Top ruchy pojawią się po drugiej migawce (potrzebne porównanie dzień do dnia).")

# ---------------------------------------------------------------------------
# TAB 5 — vs Sektor: dynamiczne porównanie spółki z medianą jej sektora
# ---------------------------------------------------------------------------
def render_sector():
    st.write(
        "Sprawdza, jak konkretna spółka wypada na tle **mediany swojego sektora** "
        "w bieżącej migawce — to jest porównanie liczone na żywo na aktualnych "
        "danych (w przeciwieństwie do ogólnych progów w dymkach w Screenerze, "
        "które są statyczne)."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
    else:
        df = db.load_snapshot(dates[0])
        stocks = df[df["Typ"] == "stock"].copy()

        if "Sektor" not in stocks.columns:
            st.info("Ta migawka nie ma jeszcze danych sektorowych — uruchom skan ponownie po aktualizacji kodu.")
        else:
            stocks = stocks[stocks["Sektor"].notna() & (stocks["Sektor"] != "Nieznany")]
            if stocks.empty:
                st.info("Brak spółek z rozpoznanym sektorem w tej migawce.")
            else:
                ticker_choice = st.selectbox(
                    "Spółka", sorted(stocks["Ticker"].unique().tolist()),
                    format_func=lambda t: f"{t} — {stocks.set_index('Ticker').loc[t, 'Nazwa']}",
                    key="sector_ticker",
                )
                row = stocks[stocks["Ticker"] == ticker_choice].iloc[0]
                sector = row["Sektor"]
                peers = stocks[stocks["Sektor"] == sector]
                st.caption(f"Sektor: **{sector}** — {len(peers)} spółek w tej migawce (w tym {ticker_choice})")

                if len(peers) < 3:
                    st.warning(
                        "Za mało spółek w tym sektorze w bieżącej migawce, żeby mediana była "
                        "wiarygodna (potrzeba co najmniej 3 — zwiększ uniwersum albo poczekaj "
                        "na kolejne skany)."
                    )

                comp_rows = []
                for col, direction in SECTOR_METRICS:
                    if col not in peers.columns:
                        continue
                    numeric_peers = pd.to_numeric(peers[col], errors="coerce")
                    median_val = numeric_peers.median()
                    own_val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]

                    if pd.isna(own_val) or pd.isna(median_val):
                        ocena, diff_txt = "brak danych", "—"
                    else:
                        diff_pct = ((own_val - median_val) / abs(median_val) * 100) if median_val != 0 else None
                        better = (own_val > median_val) if direction == "higher" else (own_val < median_val)
                        if diff_pct is not None and abs(diff_pct) < 5:
                            ocena = "⚪ Podobnie do sektora"
                        elif better:
                            ocena = "🟢 Lepiej niż mediana"
                        else:
                            ocena = "🔴 Gorzej niż mediana"
                        diff_txt = f"{diff_pct:+.1f}%" if diff_pct is not None else "—"

                    comp_rows.append({
                        "Wskaźnik": col,
                        "Kierunek": "wyżej = lepiej" if direction == "higher" else "niżej = lepiej",
                        ticker_choice: None if pd.isna(own_val) else round(float(own_val), 2),
                        "Mediana sektora": None if pd.isna(median_val) else round(float(median_val), 2),
                        "Różnica": diff_txt,
                        "Ocena": ocena,
                    })

                st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, height=480, hide_index=True)

                st.divider()
                st.subheader(f"Wszystkie spółki w sektorze „{sector}”")
                default_sector_cols = ["Rynek", "Buy Score"] + [m for m, _ in SECTOR_METRICS]
                active_sector_cols = _personalize_columns(
                    pref_key="sector_columns",
                    available_columns=list(peers.columns),
                    default_columns=default_sector_cols,
                    mandatory_columns=["Ticker", "Nazwa", "Cena"],
                    label="Personalizuj kolumny tej tabeli",
                )
                sector_cols = [c for c in active_sector_cols if c in peers.columns]
                sort_col = "Buy Score" if "Buy Score" in sector_cols else sector_cols[-1]
                _render_table(peers[sector_cols].sort_values(sort_col, ascending=False), height=400)
                st.download_button(
                    "⬇️ Pobierz CSV (wszystkie dane sektora)", peers.to_csv(index=False).encode("utf-8"),
                    file_name=f"sektor_{sector}_{dates[0]}.csv",
                )

# ---------------------------------------------------------------------------
# TAB 6 — Dywidendy: wysoka stopa dywidendy, cena jeszcze nie wzrosła
# ---------------------------------------------------------------------------
def render_dividends():
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

        only_before_season = st.checkbox(
            "🗓️ Pokaż tylko spółki PRZED sezonem dywidendowym "
            "(płaciły w zeszłym roku, jeszcze nie zapłaciły w tym)",
            value=False,
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
        if only_before_season and "Dyw. w poprzednim roku" in candidates.columns and "Dyw. w tym roku" in candidates.columns:
            candidates = candidates[
                (candidates["Dyw. w poprzednim roku"] == "Tak") & (candidates["Dyw. w tym roku"] == "Nie")
            ]

        score_col = "Score: Dywidenda-Okazja"
        sort_col = score_col if score_col in candidates.columns else "Stopa Dyw. (%)"
        candidates = candidates.sort_values(sort_col, ascending=False)

        st.caption(f"Znaleziono **{len(candidates)}** spółek spełniających kryteria.")

        default_dividend_cols = [
            "Rynek", "Stopa Dyw. (%)", "Dyw. w poprzednim roku", "Dyw. w tym roku",
            "Poprzednia dywidenda", "Przyszła dywidenda", "Zmiana ceny (1Y%)",
            "Lata z dywidendą (3Y)", "Payout ratio (%)", "C/Z (P/E)", "ROE (%)",
            "Marża Operac. (%)", "Marża netto (%)", "Wzrost przychodów (%)",
            "Wzrost EPS (%)", "Dług/Kapitał", "Liczba flag",
        ]
        active_dividend_cols = _personalize_columns(
            pref_key="dividends_columns",
            available_columns=list(candidates.columns),
            default_columns=default_dividend_cols,
            mandatory_columns=["Ticker", "Nazwa", "Cena"],
        )
        display_cols = list(dict.fromkeys(
            [c for c in active_dividend_cols if c in candidates.columns] + [score_col]
        ))
        _render_table(candidates[display_cols], height=600)
        st.download_button(
            "⬇️ Pobierz CSV (wszystkie dane)", candidates.to_csv(index=False).encode("utf-8"),
            file_name=f"dywidendy_{dates[0]}.csv",
        )
        st.caption(
            "'Dyw. w poprzednim roku' / 'Dyw. w tym roku' pokazują, czy spółka jest jeszcze "
            "PRZED tegoroczną wypłatą (sedno tej strategii) czy już PO. Payout ratio i wzrost "
            "przychodów/marż pokazują, czy dywidenda jest bezpieczna. 'Przyszła dywidenda' "
            "pokazuje BRAK, jeśli Yahoo nie udostępnia potwierdzonej przyszłej daty (częste poza USA)."
        )

# ---------------------------------------------------------------------------
# TAB 7 — Własny scoring: kreator wag zamiast sztywnych strategii
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
                weights[col] = st.slider(label, 0, 5, default, key=f"cw_{col}")

        custom_score = _compute_custom_score(stocks, weights)
        if custom_score is None:
            st.warning("Ustaw przynajmniej jedną wagę większą od 0.")
        else:
            stocks["Własny wynik"] = custom_score
            ranked = stocks.sort_values("Własny wynik", ascending=False).head(30)
            active_cols = [col for _, col, _, _ in CUSTOM_COMPONENTS if weights.get(col, 0) > 0]
            show_cols = ["Ticker", "Nazwa", "Rynek", "Cena", "Własny wynik"] + active_cols + ["Liczba flag"]
            show_cols = [c for c in dict.fromkeys(show_cols) if c in ranked.columns]
            _render_table(ranked[show_cols], height=600)

            st.divider()
            st.subheader("Backtest własnych wag")
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
                    cw_top_n = st.slider("TOP N spółek", 1, 20, 5, key="cw_top_n")
                with bc2:
                    cw_max_hold = max(1, n_snapshots - 1)
                    if cw_max_hold < 2:
                        cw_hold = 1
                        st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
                    else:
                        cw_hold = st.slider(
                            "Trzymaj przez (liczba skanów)", 1, cw_max_hold, min(5, cw_max_hold), key="cw_hold"
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
                        m1.metric("Śr. zwrot na okno", f"{cw_bt['Śr. zwrot %'].mean():.2f}%")
                        m2.metric("Win rate (średni)", f"{cw_bt['Win rate %'].mean():.1f}%")
                        m3.metric("Liczba przetestowanych okien", len(cw_bt))
                        equity = (1 + cw_bt["Śr. zwrot %"] / 100).cumprod() - 1
                        st.line_chart(pd.DataFrame(
                            {"Skumulowany zwrot %": (equity * 100).round(2)}, index=cw_bt["Data wyjścia"]
                        ))
                        _render_table(cw_bt, height=300)

# ---------------------------------------------------------------------------
# TAB 8 — Watchlist: oznaczone tickery z własnymi notatkami
# ---------------------------------------------------------------------------
def render_watchlist():
    st.write(
        "Oznacz spółki jako obserwowane, z własną notatką (np. 'czekam na wyniki Q3'). "
        "Zapisywane w bazie — przetrwa między sesjami i restartami appki."
    )

    st.subheader("Dodaj do watchlisty")
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
    st.subheader("Twoja watchlist")
    wl = db.load_watchlist()

    if wl.empty:
        st.info("Watchlist jest pusta — dodaj pierwszą spółkę powyżej.")
    else:
        dates = db.list_dates()
        if dates:
            latest = db.load_snapshot(dates[0])
            wl = wl.merge(latest, on="Ticker", how="left")
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
            mandatory_columns=["Ticker", "Notatka"],
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

# ---------------------------------------------------------------------------
# TAB 9 — Backtest strategii: czy TOP N wg danego score'a faktycznie zarabia?
# ---------------------------------------------------------------------------
def render_bt_strategy():
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

            _render_table(bt_result, height=400)

# ---------------------------------------------------------------------------
# TAB 10 — Backtest: jak wyglądała spółka X dni/tygodni/miesięcy temu
# ---------------------------------------------------------------------------
def render_backtest():
    ticker = st.selectbox("Spółka / ETF", sorted(ALL_NAMES.keys()),
                           format_func=lambda t: f"{t} — {ALL_NAMES[t]}")

    with st.expander("📰 Najnowsze newsy dla tej spółki"):
        if st.button("Pobierz najnowsze nagłówki", key="news_btn"):
            with st.spinner("Pobieram newsy z Yahoo Finance..."):
                news_items = _ticker_news(ticker)
            if not news_items:
                st.info("Brak dostępnych newsów dla tej spółki (albo Yahoo ich nie udostępnia dla tego rynku).")
            else:
                for item in news_items:
                    date_part = f" — {item['date']}" if item.get("date") else ""
                    if item.get("link"):
                        st.markdown(f"**[{item['title']}]({item['link']})**{date_part}")
                    else:
                        st.markdown(f"**{item['title']}**{date_part}")
                    st.caption(item.get("publisher", "Nieznane źródło"))
                    st.divider()

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

# ---------------------------------------------------------------------------
# Budowa zakładek na bazie wybranych modułów (patrz panel "Wybierz widoczne
# moduły" na górze strony) i wywołanie odpowiednich funkcji render_*.
# ---------------------------------------------------------------------------
RENDER_FUNCS = {
    "screener": render_screener,
    "strategie": render_strategie,
    "profile": render_profile,
    "overview": render_overview,
    "sector": render_sector,
    "dividends": render_dividends,
    "custom": render_custom,
    "watchlist": render_watchlist,
    "bt_strategy": render_bt_strategy,
    "backtest": render_backtest,
}

active_modules = [(key, label) for key, label in MODULE_REGISTRY if key in selected_modules]
streamlit_tabs = st.tabs([label for _, label in active_modules])
for st_tab, (key, _label) in zip(streamlit_tabs, active_modules):
    with st_tab:
        RENDER_FUNCS[key]()
