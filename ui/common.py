"""
Wspoldzielone przez wszystkie moduly: stale wskaznikow, kolorowanie
tabel, pomocniki renderujace i funkcje z cache'em.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from config.markets import ETF_MAP, STOCK_GROUPS
from core import db
from core.scanner import get_fx_rates, get_next_earnings_date, get_sp400_map, get_sp500_map, get_ticker_news, get_tradingview_url, get_vix_level

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
    "TradingView": (
        "Link do wykresu spółki na TradingView. Najlepszy dostępny szacunek na bazie tickera — "
        "dla mniej popularnych spółek może czasem trafić na wyszukiwarkę zamiast wprost na wykres."
    ),
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
        if col == "TradingView":
            config[col] = st.column_config.LinkColumn(col, help=help_text, display_text="📈 Wykres")
        elif col in TEXT_COLUMNS:
            config[col] = st.column_config.TextColumn(col, help=help_text)
        else:
            config[col] = st.column_config.NumberColumn(col, help=help_text)
    return config


def _tradingview_url(ticker: str) -> str:
    """Link do wykresu, uwzględniający zapisany layout użytkownika (jeśli ustawiony
    w panelu '📈 Ustawienia linków TradingView' na górze strony)."""
    layout_id = db.get_preference("tradingview_layout_id", "")
    return get_tradingview_url(ticker, layout_id or None)


def _with_tradingview_link(df: pd.DataFrame) -> pd.DataFrame:
    """Dokłada kolumnę 'TradingView' z linkiem do wykresu każdej spółki —
    liczone na żywo z tickera, nic dodatkowego nie trzeba pobierać z sieci."""
    if "Ticker" not in df.columns or df.empty:
        return df
    df = df.copy()
    df["TradingView"] = df["Ticker"].apply(_tradingview_url)
    return df


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


def _render_radar_chart(labels: list[str], values: list[float]) -> None:
    """
    Wykres radarowy ('Snowflake') — wartości 0-100 na każdej osi. Tło wykresu
    jest celowo białe/nieprzezroczyste (nie przezroczyste), żeby tekst i osie
    były czytelne niezależnie od jasnego/ciemnego motywu Streamlita.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        st.info("Wykres radarowy niedostępny (brak matplotlib).")
        return

    n = len(labels)
    angles = [i / n * 2 * np.pi for i in range(n)]
    angles += angles[:1]
    vals = [0 if v is None or pd.isna(v) else float(v) for v in values]
    vals += vals[:1]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticks([25, 50, 75])
    ax.set_yticklabels(["25", "50", "75"], fontsize=6)
    ax.plot(angles, vals, linewidth=2, color="#2ecc71")
    ax.fill(angles, vals, color="#2ecc71", alpha=0.3)
    st.pyplot(fig, use_container_width=False)
    plt.close(fig)


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


@st.cache_data(ttl=1800)
def _vix_level() -> dict | None:
    return get_vix_level()


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
    ("dashboard", "🧪 Dashboard (eksperymentalny)"),
    ("sector", "📊 vs Sektor"),
    ("pe_anomaly", "🎯 Tanie vs Sektor (C/Z)"),
    ("dividends", "💰 Dywidendy"),
    ("custom", "🎛️ Własny scoring"),
    ("watchlist", "⭐ Watchlist"),
    ("trade_review", "📉 Analiza transakcji"),
    ("bt_strategy", "📈 Backtest strategii"),
    ("backtest", "⏪ Backtest spółki"),
]
ALL_MODULE_KEYS = [key for key, _ in MODULE_REGISTRY]

MODULE_DESCRIPTIONS = {
    "screener": "Filtrowanie i przegląd wszystkich zeskanowanych spółek/ETF-ów naraz.",
    "strategie": "Gotowe strategie inwestycyjne (Deep Value, Momentum, Dywidendowa i inne).",
    "profile": "Wpisz spółkę i zobacz WSZYSTKIE jej dane naraz + krótki brief inwestycyjny.",
    "overview": "Kondycja całego rynku na raz — szerokość, heatmapy, top ruchy dnia.",
    "dashboard": "Eksperymentalny widok kafelkowy w stylu terminala tradingowego.",
    "sector": "Porównanie spółki z medianą jej sektora — dynamicznie, na żywo.",
    "pe_anomaly": "Spółki wyraźnie tańsze (C/Z) niż mediana ich sektora, z czerwonymi i zielonymi flagami.",
    "dividends": "Szukanie tanich spółek przed sezonem dywidendowym.",
    "custom": "Własny ranking na bazie wag wskaźników, które sam ustawisz.",
    "watchlist": "Lista obserwowanych spółek z Twoimi notatkami.",
    "trade_review": "Wgraj historię swoich transakcji (np. z XTB) i zobacz, ile taniej mogłeś kupić.",
    "bt_strategy": "Sprawdzenie historycznej skuteczności każdej strategii.",
    "backtest": "Szczegóły jednej spółki wstecz w czasie + najnowsze newsy.",
}
