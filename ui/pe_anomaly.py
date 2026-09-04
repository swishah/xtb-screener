"""
Modul Tanie vs Sektor (C/Z).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from core import db
from core.scanner import green_flags
from ui.common import (
    _render_table,
    _with_tradingview_link,
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
