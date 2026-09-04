"""
Kontrola spójności modułów — zamiennik testu, który dawało st.tabs.

Zanim nawigacja zamieniła się z zakładek na przyciski, jedno wejście na stronę
wykonywało wszystkie 13 funkcji render_* naraz i łapało każdy błąd importu oraz
zasięgu. Teraz renderuje się tylko oglądany moduł, więc taki błąd mógłby siedzieć
tygodniami w rzadziej używanej zakładce.

Ten skrypt sprawdza to, co da się sprawdzić bez uruchamiania Streamlita:

1. czy każdy moduł ui/ w ogóle się importuje (łapie literówki, złe importy,
   błędy na poziomie modułu),
2. czy MODULE_REGISTRY, MODULE_DESCRIPTIONS i RENDER_FUNCS zgadzają się co do
   kluczy — rozjazd powodował już błąd w tym projekcie,
3. czy każdy moduł ma kategorię w MODULE_CATEGORIES (brak = wyląduje w grupie
   "Pozostałe", więc nie zniknie, ale to niedopatrzenie),
4. czy funkcje render_* faktycznie istnieją i są wywoływalne.

Uruchomienie:
    python scripts/sprawdz_moduly.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BLEDY: list[str] = []


def zglos(tresc: str) -> None:
    BLEDY.append(tresc)
    print(f"  BŁĄD: {tresc}")



def _klucze_render_funcs() -> dict[str, str]:
    """
    Wyciąga zawartość słownika RENDER_FUNCS z app.py bez wykonywania pliku.
    Zwraca {klucz modułu: nazwa funkcji}.
    """
    import ast

    zrodlo = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    for wezel in ast.parse(zrodlo).body:
        if isinstance(wezel, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id == "RENDER_FUNCS" for c in wezel.targets
        ):
            return {
                k.value: v.id
                for k, v in zip(wezel.value.keys, wezel.value.values)
                if isinstance(k, ast.Constant) and isinstance(v, ast.Name)
            }
    raise RuntimeError("nie znaleziono RENDER_FUNCS w app.py")


def main() -> int:
    print("1. Import modułów ui/")
    from ui.common import MODULE_REGISTRY, MODULE_DESCRIPTIONS, MODULE_CATEGORIES

    klucze_rejestru = [k for k, _ in MODULE_REGISTRY]
    # Nazwa pliku bywa inna niż klucz modułu (profile -> profil), więc mapujemy
    # po tym, co faktycznie leży w katalogu.
    katalog = Path(__file__).resolve().parent.parent / "ui"
    pliki = sorted(p.stem for p in katalog.glob("*.py") if p.stem != "__init__")

    zaimportowane = {}
    for nazwa in pliki:
        try:
            zaimportowane[nazwa] = importlib.import_module(f"ui.{nazwa}")
            print(f"   ok  ui/{nazwa}.py")
        except Exception as e:  # noqa: BLE001
            zglos(f"ui/{nazwa}.py nie importuje się: {type(e).__name__}: {e}")

    print("\n2. Zgodność kluczy")
    # RENDER_FUNCS czytamy z DRZEWA SKŁADNIOWEGO app.py, a nie przez import.
    # app.py jest skryptem Streamlita, nie modułem — import wykonałby całą
    # appkę od góry do dołu (łącznie z pobieraniem danych i renderowaniem),
    # co jest wolne, hałaśliwe i zupełnie niepotrzebne do sprawdzenia kluczy.
    render_funcs = _klucze_render_funcs()

    zestawy = {
        "MODULE_REGISTRY": set(klucze_rejestru),
        "MODULE_DESCRIPTIONS": set(MODULE_DESCRIPTIONS),
        "RENDER_FUNCS": set(render_funcs),
    }
    wzorzec = zestawy["MODULE_REGISTRY"]
    for nazwa, zbior in zestawy.items():
        if zbior != wzorzec:
            brak = wzorzec - zbior
            nadmiar = zbior - wzorzec
            zglos(f"{nazwa} rozjeżdża się z MODULE_REGISTRY — brakuje {brak or '{}'}, "
                  f"nadmiarowe {nadmiar or '{}'}")
        else:
            print(f"   ok  {nazwa}: {len(zbior)} kluczy")

    print("\n3. Kategorie")
    w_kategoriach: set[str] = set()
    for label, _kolor, klucze in MODULE_CATEGORIES:
        for k in klucze:
            if k in w_kategoriach:
                zglos(f"moduł '{k}' przypisany do więcej niż jednej kategorii")
            w_kategoriach.add(k)
        print(f"   ok  {label}: {len(klucze)}")
    osierocone = wzorzec - w_kategoriach
    if osierocone:
        zglos(f"moduły bez kategorii (trafią do 'Pozostałe'): {sorted(osierocone)}")
    widma = w_kategoriach - wzorzec
    if widma:
        zglos(f"kategorie wskazują nieistniejące moduły: {sorted(widma)}")

    print("\n4. Funkcje renderujące")
    for klucz, nazwa_fn in render_funcs.items():
        modul = next((m for m in zaimportowane.values()
                      if hasattr(m, nazwa_fn)), None)
        if modul is None:
            zglos(f"RENDER_FUNCS['{klucz}'] wskazuje na {nazwa_fn}(), "
                  f"której nie ma w żadnym module ui/")
        elif not callable(getattr(modul, nazwa_fn)):
            zglos(f"{nazwa_fn} nie jest funkcją")
    print(f"   ok  {len(render_funcs)} funkcji odnalezionych w ui/")

    print()
    if BLEDY:
        print(f"NIEPOWODZENIE — {len(BLEDY)} problem(ów).")
        return 1
    print("Wszystko spójne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
