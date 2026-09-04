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
    generate_brief, STRATEGY_MAX_SCORES, get_vix_level, compute_sentiment_index, green_flags,
    compute_stockrank, compute_snowflake, compute_correlation_matrix, get_insider_transactions,
    get_tradingview_url, analyze_trade,
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
    "Jakość fundamentalna (F-Score uproszczony)": (
        "Inspirowane Piotroski F-Score, ale liczone WYŁĄCZNIE na bieżącym stanie "
        "(bez porównań rok-do-roku z pełnych sprawozdań — to spowolniłoby skan "
        "~1300+ spółek). Sprawdza 8 sygnałów jakości: ROA, przepływy operacyjne, "
        "ROE, marża netto, wzrost EPS/przychodów, zadłużenie, marża brutto."
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
    "Jakość fundamentalna (F-Score uproszczony)": [
        "Ticker", "Nazwa", "Rynek", "Cena", "ROA (%)", "Przepływy operacyjne (mln)",
        "ROE (%)", "Marża netto (%)", "Wzrost EPS (%)", "Wzrost przychodów (%)",
        "Dług/Kapitał", "Marża brutto (%)", "Liczba flag",
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
                mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
                label=f"Personalizuj kolumny dla: {strategy_name}",
            )
            ranked = df[df["Typ"] == "stock"].sort_values(score_col, ascending=False).head(30)
            ranked = _with_tradingview_link(ranked)
            display_cols = [c for c in active_strategy_cols + [score_col] if c in ranked.columns]
            display_cols = list(dict.fromkeys(display_cols))  # usuń ewentualny duplikat score_col
            _render_table(ranked[display_cols], height=600)

        st.divider()
        st.subheader(
            "🔗 Zbieżność strategii",
            help="Spółki, które jednocześnie są w czołówce więcej niż jednej strategii — "
                 "silniejszy, wzajemnie potwierdzony sygnał niż wysoki wynik w tylko jednej.",
        )
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
            conv_top_n = st.slider(
                "Próg: TOP N per strategia", 5, 50, 15, key="conv_top_n",
                help="Ile najlepszych spółek per strategia liczy się jako 'w czołówce' przy sprawdzaniu zbieżności.",
            )
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

        st.subheader(
            "Szerokość rynku (breadth)",
            help="Wysoki % spółek nad SMA200 = szeroka hossa (ciągnie wiele spółek naraz). "
                 "Niski % przy rosnących indeksach = wzrost napędzany tylko kilkoma dużymi spółkami.",
        )
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

        c1.metric("% spółek > SMA200", f"{above200:.0f}%" if above200 is not None else "brak danych",
                  help="Ile % zeskanowanych spółek ma cenę powyżej 200-dniowej średniej — "
                       "klasyczny wyznacznik długoterminowej hossy/bessy.")
        c2.metric("% spółek > SMA50", f"{above50:.0f}%" if above50 is not None else "brak danych",
                  help="Jak wyżej, ale dla średniej 50-dniowej (trend średnioterminowy).")
        c3.metric("Średnie RSI (cały rynek)", f"{avg_rsi:.1f}" if avg_rsi is not None else "brak danych",
                  help="Średnie RSI całego rynku. >50 = generalnie trend wzrostowy, <50 = spadkowy.")
        c4.metric("% z Buy Score ≥ 5", f"{buy5:.0f}%" if buy5 is not None else "brak danych",
                  help="Ile % spółek ma wysoki Buy Score — więcej = więcej okazji technicznych naraz na rynku.")
        st.caption(
            "Wysoki % spółek nad SMA200 = szeroka hossa (ciągnie wiele spółek naraz). "
            "Niski % przy rosnących indeksach = wzrost napędzany tylko kilkoma dużymi spółkami."
        )

        def _show_heatmap(group_col: str, title: str, help_text: str) -> None:
            st.subheader(title, help=help_text)
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
            _show_heatmap(
                "Rynek", "Heatmapa rynków",
                "Który kraj/giełda ma teraz najwyższy średni Buy Score i największy spadek "
                "od ATH — szybki obraz, który rynek jest 'przeceniony', a który 'drogi'.",
            )
        with hm_col2:
            _show_heatmap(
                "Sektor", "Heatmapa sektorów",
                "Jak wyżej, ale w podziale na sektor gospodarki zamiast kraju notowania.",
            )

        st.subheader(
            "Rozkład RSI (cały rynek)",
            help="Histogram RSI całego zeskanowanego rynku. Dużo spółek po lewej (RSI<30) = "
                 "rynek generalnie wyprzedany, dużo po prawej (RSI>70) = wykupiony.",
        )
        if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty:
            counts, edges = np.histogram(stocks["RSI"].dropna(), bins=10, range=(0, 100))
            hist_df = pd.DataFrame(
                {"Liczba spółek": counts},
                index=[f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(counts))],
            )
            st.bar_chart(hist_df)
        else:
            st.info("Brak danych RSI do histogramu.")

        st.subheader(
            "Top ruchy dnia",
            help="Największe wzrosty/spadki ceny od poprzedniej migawki (dzień do dnia).",
        )
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
# TAB 5 — Dashboard (eksperymentalny): gęsty widok kafelkowy w stylu terminala
# ---------------------------------------------------------------------------
def _tile_header(title: str, note: str = "") -> None:
    st.markdown(f"**{title}**")
    if note:
        st.caption(note)


def render_dashboard():
    st.warning(
        "🧪 **Tryb eksperymentalny.** Układ inspirowany terminalami tradingowymi. "
        "VIX pochodzi z prawdziwego tickera giełdowego (^VIX) przez Yahoo Finance. "
        "**Wskaźnik nastrojów poniżej to własna metodologia appki** (VIX + szerokość "
        "rynku + RSI) — NIE jest to oficjalny CNN Fear & Greed Index, który nie ma "
        "publicznego API. Dane makro (Fed Funds Rate), pozycjonowanie futures/COT "
        "i towary wciąż wymagałyby dodatkowych, zewnętrznych źródeł — daj znać, "
        "jeśli chcesz je dodać."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
        return

    df = db.load_snapshot(dates[0])
    stocks = df[df["Typ"] == "stock"].copy()
    if "Rynek" not in stocks.columns:
        stocks["Rynek"] = "Nieznany"
    if "Sektor" not in stocks.columns:
        stocks["Sektor"] = "Nieznany"

    def _pct_above(col: str):
        if col not in stocks.columns:
            return None
        valid_rows = stocks.dropna(subset=[col, "Cena"])
        return float((valid_rows["Cena"] > valid_rows[col]).mean() * 100) if not valid_rows.empty else None

    pct_sma20 = _pct_above("SMA20")
    pct_sma50 = _pct_above("SMA50")
    pct_sma200 = _pct_above("SMA200")
    avg_rsi = float(stocks["RSI"].mean()) if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty else None
    vix = _vix_level()
    sentiment = compute_sentiment_index(vix["value"] if vix else None, pct_sma50, pct_sma200, avg_rsi)

    vc1, vc2 = st.columns(2)
    with vc1:
        with st.container(border=True):
            _tile_header("😨 VIX (indeks zmienności)", "Yahoo Finance, ticker ^VIX — dane realne")
            if vix:
                st.metric("VIX", vix["value"], delta=f"{vix['change_pct']}%" if vix["change_pct"] is not None else None,
                          delta_color="inverse",
                          help="Indeks zmienności S&P500. <20 = spokojny rynek, 20-30 = podwyższona "
                               "zmienność, >30 = wysoki niepokój/panika.")
                if vix["value"] > 30:
                    st.caption("🔴 Wysoka zmienność — podwyższony niepokój rynku.")
                elif vix["value"] > 20:
                    st.caption("🟡 Podwyższona zmienność.")
                else:
                    st.caption("🟢 Spokojny rynek.")
            else:
                st.caption("Nie udało się pobrać VIX (brak sieci albo Yahoo tymczasowo niedostępne).")
    with vc2:
        with st.container(border=True):
            _tile_header("🎭 Wskaźnik nastrojów (własna metodologia)", "VIX + szerokość rynku + śr. RSI — nie CNN Fear & Greed")
            if sentiment:
                st.metric(
                    "Wynik (0-100)", sentiment["score"],
                    help="Własny wskaźnik z VIX + szerokości rynku + RSI. <25 ekstremalny strach, "
                         "25-45 strach, 45-55 neutralnie, 55-75 chciwość, >75 ekstremalna chciwość.",
                )
                st.caption(f"**{sentiment['label']}**")
            else:
                st.caption("Za mało danych, żeby policzyć wskaźnik.")

    row1 = st.columns(3)
    row2 = st.columns(3)
    row3 = st.columns(3)

    with row1[0]:
        with st.container(border=True):
            _tile_header("🌍 RYNKI DZIŚ", "Śr. zmiana ceny per rynek")
            if len(dates) >= 2 and "Buy Score" in stocks.columns:
                prev = db.load_snapshot(dates[1])
                merged = stocks.merge(prev[["Ticker", "Cena"]], on="Ticker", suffixes=("", "_poprzednio"))
                merged = merged.dropna(subset=["Cena", "Cena_poprzednio"])
                merged = merged[merged["Cena_poprzednio"] != 0]
                if not merged.empty:
                    merged["Zmiana %"] = (merged["Cena"] - merged["Cena_poprzednio"]) / merged["Cena_poprzednio"] * 100
                    agg = merged.groupby("Rynek")["Zmiana %"].mean().round(2).sort_values(ascending=False)
                    for rynek, chg in agg.head(6).items():
                        arrow = "🟢▲" if chg > 0 else ("🔴▼" if chg < 0 else "⚪")
                        st.write(f"{arrow} **{rynek}** — {chg:+.2f}%")
                else:
                    st.caption("Brak wspólnych tickerów między migawkami.")
            else:
                st.caption("Potrzeba co najmniej 2 migawek, żeby pokazać zmianę dzień do dnia.")

    with row1[1]:
        with st.container(border=True):
            _tile_header("🔥 MAPA CIEPLNA SEKTORA", "Śr. Buy Score per sektor")
            valid = stocks[stocks["Sektor"] != "Nieznany"]
            if not valid.empty and "Buy Score" in valid.columns:
                agg = valid.groupby("Sektor")["Buy Score"].mean().round(2).sort_values(ascending=False)
                tile_cols = st.columns(3)
                for i, (sektor, score) in enumerate(agg.head(6).items()):
                    color = "#1b5e20" if score >= 5 else ("#7f0000" if score <= 2 else "#5c4d00")
                    with tile_cols[i % 3]:
                        st.markdown(
                            f"<div style='background-color:{color};border-radius:8px;padding:8px;"
                            f"text-align:center;margin-bottom:6px;'>"
                            f"<div style='font-size:0.7em;color:#ddd;overflow:hidden;text-overflow:ellipsis;"
                            f"white-space:nowrap;'>{sektor[:14]}</div>"
                            f"<div style='font-size:1.1em;font-weight:bold;color:white'>{score}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
            else:
                st.caption("Brak danych sektorowych w tej migawce.")

    with row1[2]:
        with st.container(border=True):
            _tile_header("📏 SZEROKOŚĆ RYNKU")

            any_data = False
            for label, pct in [("% > SMA20", pct_sma20), ("% > SMA50", pct_sma50), ("% > SMA200", pct_sma200)]:
                if pct is not None:
                    any_data = True
                    st.write(f"{label}: **{pct:.1f}%**")
                    st.progress(min(max(int(pct), 0), 100) / 100)
            if not any_data:
                st.caption("Brak danych technicznych w tej migawce.")

    with row2[0]:
        with st.container(border=True):
            _tile_header("🗺️ MAPA CIEPLNA RYNKÓW", "Śr. Buy Score per giełda")
            if "Buy Score" in stocks.columns and not stocks.empty:
                agg = stocks.groupby("Rynek")["Buy Score"].mean().round(2).sort_values(ascending=False)
                for rynek, score in agg.head(8).items():
                    st.write(f"**{rynek}**: {score}")
                    st.progress(min(max(score / 9, 0), 1))

    with row2[1]:
        with st.container(border=True):
            _tile_header("🎯 TOP SYGNAŁY KUPNA", "Najwyższy Buy Score dzisiaj")
            if "Buy Score" in stocks.columns and not stocks.empty:
                top = stocks.sort_values("Buy Score", ascending=False).head(6)
                for _, r in top.iterrows():
                    st.write(f"🟢 **{r['Ticker']}** — {r.get('Nazwa', '')} (score {r['Buy Score']})")

    with row2[2]:
        with st.container(border=True):
            _tile_header("🚩 NAJWIĘCEJ OSTRZEŻEŃ", "Spółki z największą liczbą czerwonych flag")
            if "Liczba flag" in stocks.columns and not stocks.empty:
                top_flags = stocks[stocks["Liczba flag"] > 0].sort_values("Liczba flag", ascending=False).head(6)
                if top_flags.empty:
                    st.caption("Brak spółek z ostrzeżeniami w tej migawce.")
                else:
                    for _, r in top_flags.iterrows():
                        st.write(f"🔴 **{r['Ticker']}** — {int(r['Liczba flag'])} flag(a/i)")

    with row3[0]:
        with st.container(border=True):
            _tile_header("📅 WYNIKI — WATCHLIST", "Sprawdzane na żądanie (max 10 spółek)")
            wl = db.load_watchlist()
            if wl.empty:
                st.caption("Watchlist jest pusta.")
            elif st.button("Sprawdź daty wyników", key="dash_earnings"):
                any_found = False
                for t in wl["Ticker"].head(10):
                    ed = _earnings_date(t)
                    if ed:
                        any_found = True
                        st.write(f"**{t}**: {ed}")
                if not any_found:
                    st.caption("Brak potwierdzonych dat dla obserwowanych spółek.")

    with row3[1]:
        with st.container(border=True):
            _tile_header("📊 ROZKŁAD RSI")
            if "RSI" in stocks.columns and not stocks["RSI"].dropna().empty:
                counts, edges = np.histogram(stocks["RSI"].dropna(), bins=10, range=(0, 100))
                hist_df = pd.DataFrame(
                    {"Liczba": counts},
                    index=[f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(counts))],
                )
                st.bar_chart(hist_df, height=180)
            else:
                st.caption("Brak danych RSI.")

    with row3[2]:
        with st.container(border=True):
            _tile_header("⭐ WATCHLIST")
            wl = db.load_watchlist()
            if wl.empty:
                st.caption("Pusta.")
            else:
                merge_cols = [c for c in ["Ticker", "Cena", "Buy Score"] if c in stocks.columns]
                merged_wl = wl.merge(stocks[merge_cols], on="Ticker", how="left") if merge_cols else wl
                for _, r in merged_wl.head(8).iterrows():
                    st.write(f"**{r['Ticker']}** — {r.get('Cena', '—')} (score {r.get('Buy Score', '—')})")

# ---------------------------------------------------------------------------
# TAB 6 — vs Sektor: dynamiczne porównanie spółki z medianą jej sektora
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
                st.subheader(
                    f"Wszystkie spółki w sektorze „{sector}”",
                    help="Pełna lista spółek z tego samego sektora w bieżącej migawce, do "
                         "bezpośredniego porównania obok siebie.",
                )
                default_sector_cols = ["Rynek", "Buy Score"] + [m for m, _ in SECTOR_METRICS]
                active_sector_cols = _personalize_columns(
                    pref_key="sector_columns",
                    available_columns=list(peers.columns),
                    default_columns=default_sector_cols,
                    mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
                    label="Personalizuj kolumny tej tabeli",
                )
                peers = _with_tradingview_link(peers)
                sector_cols = [c for c in active_sector_cols if c in peers.columns]
                sort_col = "Buy Score" if "Buy Score" in sector_cols else "Cena"
                _render_table(peers[sector_cols].sort_values(sort_col, ascending=False), height=400)
                st.download_button(
                    "⬇️ Pobierz CSV (wszystkie dane sektora)", peers.to_csv(index=False).encode("utf-8"),
                    file_name=f"sektor_{sector}_{dates[0]}.csv",
                )

# ---------------------------------------------------------------------------
# TAB 7 — Tanie vs Sektor: C/Z wyraźnie niższe niż mediana sektora + flagi
# ---------------------------------------------------------------------------
def render_pe_anomaly():
    st.write(
        "Szuka spółek, których **C/Z (P/E) jest wyraźnie niższe niż mediana ich "
        "własnego sektora** w bieżącej migawce — czyli potencjalnie tanie na tle "
        "bezpośrednich konkurentów, nie całego rynku. Razem z automatycznymi "
        "czerwonymi i zielonymi flagami, żeby odróżnić realną okazję od "
        "pułapki wartościowej (niskie C/Z, bo rynek słusznie wycenia problemy)."
    )
    dates = db.list_dates()
    if not dates:
        st.info("Brak danych — uruchom skan.")
        return

    df = db.load_snapshot(dates[0])
    stocks = df[df["Typ"] == "stock"].copy()
    if "Sektor" not in stocks.columns:
        st.info("Ta migawka nie ma jeszcze danych sektorowych — uruchom skan ponownie po aktualizacji kodu.")
        return

    stocks = stocks[stocks["Sektor"].notna() & (stocks["Sektor"] != "Nieznany")].copy()
    stocks["_pe_num"] = pd.to_numeric(stocks.get("C/Z (P/E)"), errors="coerce")
    # ujemne C/Z (spółka na stracie) psuje sensowność porównania - wykluczamy
    stocks = stocks[stocks["_pe_num"].notna() & (stocks["_pe_num"] > 0)]

    if stocks.empty:
        st.info("Brak spółek z dodatnim C/Z i rozpoznanym sektorem w tej migawce.")
        return

    sector_sizes = stocks.groupby("Sektor")["_pe_num"].size()
    sector_medians = stocks.groupby("Sektor")["_pe_num"].median()
    stocks["Mediana C/Z sektora"] = stocks["Sektor"].map(sector_medians).round(2)
    stocks["Spółek w sektorze"] = stocks["Sektor"].map(sector_sizes)
    stocks["Różnica vs sektor (%)"] = (
        (stocks["_pe_num"] - stocks["Mediana C/Z sektora"]) / stocks["Mediana C/Z sektora"] * 100
    ).round(1)

    c1, c2 = st.columns(2)
    with c1:
        min_sector_size = st.slider(
            "Min. liczba spółek w sektorze", 2, 15, 3,
            help="Za mało spółek w sektorze = mediana mało wiarygodna.",
        )
    with c2:
        max_diff = st.slider(
            "Maks. różnica vs mediana sektora (%)", -90, 0, -20,
            help="Niżej = szukasz spółek jeszcze taniej względem konkurencji.",
        )

    candidates = stocks[
        (stocks["Spółek w sektorze"] >= min_sector_size) & (stocks["Różnica vs sektor (%)"] <= max_diff)
    ].copy()
    candidates = candidates.sort_values("Różnica vs sektor (%)")

    st.caption(
        f"Znaleziono **{len(candidates)}** spółek co najmniej {abs(max_diff)}% taniej "
        "(wg C/Z) niż mediana ich własnego sektora."
    )

    if candidates.empty:
        st.info("Żadna spółka nie spełnia obecnych kryteriów — poluzuj suwaki powyżej.")
        return

    candidates = _with_tradingview_link(candidates)
    display_cols = [c for c in [
        "Ticker", "Nazwa", "Rynek", "Sektor", "Cena", "TradingView", "C/Z (P/E)",
        "Mediana C/Z sektora", "Różnica vs sektor (%)", "Spółek w sektorze",
        "ROE (%)", "Dług/Kapitał", "Liczba flag", "Buy Score",
    ] if c in candidates.columns]
    _render_table(candidates[display_cols], height=500)
    st.download_button(
        "⬇️ Pobierz CSV (wszystkie dane)", candidates.to_csv(index=False).encode("utf-8"),
        file_name=f"tanie_vs_sektor_{dates[0]}.csv",
    )

    st.divider()
    st.subheader(
        "🚩🟢 Flagi dla wybranej spółki",
        help="🔴 = automatyczne ostrzeżenia (np. wysoki dług, malejące przychody). 🟢 = "
             "automatyczne mocne strony (np. wysokie ROE, niski dług). Pomagają ocenić, czy "
             "niska wycena to okazja czy pułapka wartościowa.",
    )
    pick = st.selectbox(
        "Spółka", candidates["Ticker"].tolist(),
        format_func=lambda t: f"{t} — {candidates.set_index('Ticker').loc[t, 'Nazwa']}",
        key="pe_anomaly_pick",
    )
    row = candidates.set_index("Ticker").loc[pick].to_dict()
    col_r, col_g = st.columns(2)
    with col_r:
        st.markdown("**🔴 Czerwone flagi**")
        flags_text = row.get("Czerwone flagi", "Brak")
        if flags_text == "Brak" or not flags_text:
            st.success("Brak ostrzeżeń.")
        else:
            for f in str(flags_text).split("; "):
                st.write(f)
    with col_g:
        st.markdown("**🟢 Zielone flagi**")
        greens = green_flags(row)
        if not greens:
            st.caption("Brak wykrytych mocnych stron w automatycznej analizie.")
        else:
            for f in greens:
                st.write(f)

# ---------------------------------------------------------------------------
# TAB 8 — Dywidendy: wysoka stopa dywidendy, cena jeszcze nie wzrosła
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
            min_yield = st.slider(
                "Min. stopa dywidendy (%)", 0.0, 15.0, 4.0, 0.5,
                help="Minimalna stopa dywidendy z ostatniego roku względem obecnej ceny.",
            )
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
        candidates = _with_tradingview_link(candidates)
        active_dividend_cols = _personalize_columns(
            pref_key="dividends_columns",
            available_columns=list(candidates.columns),
            default_columns=default_dividend_cols,
            mandatory_columns=["Ticker", "Nazwa", "Cena", "TradingView"],
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
# TAB 9 — Własny scoring: kreator wag zamiast sztywnych strategii
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
                weights[col] = st.slider(
                    label, 0, 5, default, key=f"cw_{col}",
                    help=INDICATOR_HELP.get(col, "0 = pomiń ten wskaźnik całkowicie w Twojej formule."),
                )

        custom_score = _compute_custom_score(stocks, weights)
        if custom_score is None:
            st.warning("Ustaw przynajmniej jedną wagę większą od 0.")
        else:
            stocks["Własny wynik"] = custom_score
            ranked = stocks.sort_values("Własny wynik", ascending=False).head(30)
            ranked = _with_tradingview_link(ranked)
            active_cols = [col for _, col, _, _ in CUSTOM_COMPONENTS if weights.get(col, 0) > 0]
            show_cols = ["Ticker", "Nazwa", "Rynek", "Cena", "TradingView", "Własny wynik"] + active_cols + ["Liczba flag"]
            show_cols = [c for c in dict.fromkeys(show_cols) if c in ranked.columns]
            _render_table(ranked[show_cols], height=600)

            st.divider()
            st.subheader(
                "Backtest własnych wag",
                help="Sprawdza historyczną skuteczność DOKŁADNIE tej kombinacji wag na zapisanych "
                     "migawkach — wyższy średni zwrot i win rate = lepiej sprawdzająca się "
                     "formuła w przeszłości.",
            )
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
                    cw_top_n = st.slider(
                    "TOP N spółek", 1, 20, 5, key="cw_top_n",
                    help="Ile najlepszych spółek wg Twojej formuły 'kupujesz' w każdym oknie testowym.",
                )
                with bc2:
                    cw_max_hold = max(1, n_snapshots - 1)
                    if cw_max_hold < 2:
                        cw_hold = 1
                        st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
                    else:
                        cw_hold = st.slider(
                            "Trzymaj przez (liczba skanów)", 1, cw_max_hold, min(5, cw_max_hold), key="cw_hold",
                            help="Ile kolejnych skanów 'trzymasz' pozycję przed symulowaną sprzedażą.",
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
                        m1.metric("Śr. zwrot na okno", f"{cw_bt['Śr. zwrot %'].mean():.2f}%",
                                  help="Średni zwrot % z każdego przetestowanego okna (kupno TOP N, "
                                       "trzymanie K skanów, sprzedaż).")
                        m2.metric("Win rate (średni)", f"{cw_bt['Win rate %'].mean():.1f}%",
                                  help="Jaki % przetestowanych okien zakończył się zyskiem.")
                        m3.metric("Liczba przetestowanych okien", len(cw_bt),
                                  help="Ile historycznych okien czasowych zostało przetestowanych — "
                                       "więcej = bardziej wiarygodny wynik.")
                        equity = (1 + cw_bt["Śr. zwrot %"] / 100).cumprod() - 1
                        st.line_chart(pd.DataFrame(
                            {"Skumulowany zwrot %": (equity * 100).round(2)}, index=cw_bt["Data wyjścia"]
                        ))
                        _render_table(cw_bt, height=300)

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

# ---------------------------------------------------------------------------
# TAB 12 — Backtest strategii: czy TOP N wg danego score'a faktycznie zarabia?
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
            bt_top_n = st.slider(
                "TOP N spółek", 1, 20, 5,
                help="Ile najlepszych spółek wg wybranej strategii 'kupujesz' w każdym oknie testowym.",
            )
        with c3:
            max_hold = max(1, n_snapshots - 1)
            if max_hold < 2:
                bt_hold = 1
                st.caption("Trzymaj przez: 1 skan (za mało migawek na wybór zakresu)")
            else:
                bt_hold = st.slider(
                    "Trzymaj przez (liczba skanów)", 1, max_hold, min(5, max_hold),
                    help="Ile kolejnych skanów 'trzymasz' pozycję przed symulowaną sprzedażą.",
                )

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
            m1.metric("Śr. zwrot na okno", f"{bt_result['Śr. zwrot %'].mean():.2f}%",
                      help="Średni zwrot % z każdego przetestowanego okna (kupno TOP N, "
                           "trzymanie K skanów, sprzedaż).")
            m2.metric("Win rate (średni)", f"{bt_result['Win rate %'].mean():.1f}%",
                      help="Jaki % przetestowanych okien zakończył się zyskiem.")
            m3.metric("Liczba przetestowanych okien", len(bt_result),
                      help="Ile historycznych okien czasowych zostało przetestowanych — "
                           "więcej = bardziej wiarygodny wynik.")
            best, worst = bt_result["Śr. zwrot %"].max(), bt_result["Śr. zwrot %"].min()
            m4.metric("Najlepsze / najgorsze okno", f"{best:.1f}% / {worst:.1f}%",
                      help="Zwrot % najlepszego i najgorszego pojedynczego okna w teście.")

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
# TAB 13 — Backtest: jak wyglądała spółka X dni/tygodni/miesięcy temu
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
            back_days = st.slider(
                "Cofnij się o (dni handlowych)", 0, max_back, 0,
                help="Przesuwa punkt odniesienia wstecz w historii cen, żeby zobaczyć jak wyglądały "
                     "wskaźniki techniczne X dni handlowych temu.",
            )
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

active_modules = [(key, label) for key, label in MODULE_REGISTRY if key in selected_modules]
streamlit_tabs = st.tabs([label for _, label in active_modules])
for st_tab, (key, _label) in zip(streamlit_tabs, active_modules):
    with st_tab:
        RENDER_FUNCS[key]()
