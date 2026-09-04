"""
Kreator personalizacji uruchamiany przy pierwszym wejsciu.
"""
from __future__ import annotations

import streamlit as st
from core import db
from ui.common import (
    ALL_MODULE_KEYS,
    DEFAULT_SCREENER_COLUMNS,
    MODULE_DESCRIPTIONS,
    MODULE_REGISTRY,
)

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
