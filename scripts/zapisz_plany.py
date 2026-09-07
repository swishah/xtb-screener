"""
Zapis planów wejścia — jedyna droga, którą plan trafia do bazy.

TO JEST BRAMA, NIE FORMULARZ. Skrypt bierze propozycje z pliku JSON (napisane
przez warstwę oceniającą, czyli przez model), przepuszcza każdą przez
`core/bramka.py` i zapisuje WYŁĄCZNIE te, które przeszły. Odrzucone wypisuje
z powodem, żeby dało się zobaczyć, co i dlaczego nie weszło — cisza w tym
miejscu byłaby najgorsza z możliwych.

Ani jedno pole liczbowe nie jest tu poprawiane „w locie". Jeżeli stop leży
dwa grosze obok poziomu z dossier, plan odpada i tyle. Zaokrąglanie propozycji
do najbliższego poziomu wyglądałoby na uprzejmość, a znaczyłoby, że bramki
w praktyce nie ma.

CZEGO SKRYPT NIE PRZYJMUJE OD MODELU: `zrodla` (bierzemy z dossier, bo to
fakt, nie ocena), `rr` (liczy bramka), `stan`, `wynik_r` i cokolwiek
rozliczeniowego. Model podaje tezę, poziomy, pewność i horyzont — resztę
dokłada kod.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import bramka, db  # noqa: E402

# Ile planów zostaje na dany dzień. Dziesięć to tyle, ile człowiek jest
# w stanie przejrzeć rano; przy trzydziestu przegląd zamienia się w listę,
# której nikt nie czyta.
MAKS_PLANOW = 10

# Pewność w skali 1–5. Wąska celowo — model rozróżniający 73 od 76 punktów
# udaje precyzję, której nie ma.
MIN_PEWNOSC, MAKS_PEWNOSC = 1, 5

# Horyzont planu w sesjach. Poniżej trzech nie ma czego rozliczać, powyżej
# sześćdziesięciu to już nie plan wejścia, tylko inwestycja.
MIN_HORYZONT, MAKS_HORYZONT = 3, 60

MAKS_TEZA = 600


def _sprawdz_pola(p: dict) -> list[str]:
    """Kontrola tego, co podał model — zanim jeszcze policzymy cokolwiek."""
    bledy: list[str] = []
    teza = str(p.get("teza") or "").strip()
    if not teza:
        bledy.append("brak tezy — plan bez uzasadnienia jest bezwartościowy")
    elif len(teza) > MAKS_TEZA:
        bledy.append(f"teza dłuższa niż {MAKS_TEZA} znaków")

    try:
        pewnosc = int(p.get("pewnosc"))
    except (TypeError, ValueError):
        bledy.append("pewnosc musi być liczbą całkowitą 1–5")
    else:
        if not MIN_PEWNOSC <= pewnosc <= MAKS_PEWNOSC:
            bledy.append(f"pewnosc {pewnosc} poza skalą {MIN_PEWNOSC}–{MAKS_PEWNOSC}")

    horyzont = p.get("horyzont_sesji", 10)
    try:
        horyzont = int(horyzont)
    except (TypeError, ValueError):
        bledy.append("horyzont_sesji musi być liczbą całkowitą")
    else:
        if not MIN_HORYZONT <= horyzont <= MAKS_HORYZONT:
            bledy.append(
                f"horyzont_sesji {horyzont} poza zakresem "
                f"{MIN_HORYZONT}–{MAKS_HORYZONT}"
            )
    return bledy


def main() -> None:
    parser = argparse.ArgumentParser(description="Zapis planów przez bramkę.")
    parser.add_argument("plik", help="Plik JSON z listą propozycji.")
    parser.add_argument("--dzien", default=date.today().isoformat(),
                        help="Dzień planów (domyślnie dziś).")
    parser.add_argument("--dossier", default=None,
                        help="Dzień dossier, jeśli inny niż dzień planów.")
    parser.add_argument("--sucho", action="store_true",
                        help="Tylko sprawdź, nie zapisuj.")
    args = parser.parse_args()

    # TRYB BAZY MÓWIMY GŁOŚNO, ZANIM COKOLWIEK POLICZYMY.
    # Bez zmiennych TURSO_* wszystko idzie do zamrożonej kopii data/history.db:
    # plany powstałyby na cenach sprzed tygodni i nie pojawiłyby się na stronie,
    # bo ta czyta bazę zdalną. Nic by się nie wywaliło — i to jest właśnie
    # powód, dla którego ostrzeżenie musi być widoczne.
    if db.tryb() == "lokalny":
        print("=" * 70)
        print("⚠️  BAZA LOKALNA — plany trafią do zamrożonej kopii "
              "data/history.db,")
        print("    a NIE do bazy, z której czyta strona. Kursy w dossier są")
        print("    z ostatniej migawki w tym pliku, czyli nieaktualne.")
        print("    Ustaw TURSO_DATABASE_URL i TURSO_AUTH_TOKEN (token")
        print("    z prawem zapisu), żeby pracować na prawdziwych danych.")
        print("=" * 70)
    else:
        print("📡 Baza zdalna — plany zobaczysz na /plan.")

    sciezka = Path(args.plik)
    if not sciezka.exists():
        print(f"❌ Nie ma pliku {sciezka}.")
        sys.exit(1)
    try:
        propozycje = json.loads(sciezka.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ {sciezka} nie jest poprawnym JSON-em: {e}")
        sys.exit(1)
    if isinstance(propozycje, dict):
        propozycje = propozycje.get("plany", [])
    if not isinstance(propozycje, list) or not propozycje:
        print("❌ Oczekuję listy propozycji (albo obiektu z kluczem `plany`).")
        sys.exit(1)

    dzien_dossier = args.dossier or args.dzien
    wpisy = {w["ticker"]: w for w in db.wczytaj_dossier(dzien_dossier)}
    if not wpisy:
        dni = db.dni_dossier()
        print(f"❌ Brak dossier na {dzien_dossier}. "
              f"Dostępne: {', '.join(dni[:10]) or 'żadne'}")
        sys.exit(1)

    # Spółka z otwartym planem nie dostaje drugiego. Dwa plany na tę samą
    # spółkę to podwójna pozycja pod jednym pomysłem, a przy rozliczaniu
    # dwa razy ten sam wynik.
    zajete = {p["ticker"] for p in db.plany_otwarte()}

    przyjete: list[tuple[dict, dict]] = []
    odrzucone: list[tuple[str, list[str]]] = []
    widziane: set[str] = set()

    for p in propozycje:
        ticker = str(p.get("ticker") or "").strip().upper()
        if not ticker:
            odrzucone.append(("(bez tickera)", ["propozycja bez pola `ticker`"]))
            continue
        if ticker in widziane:
            odrzucone.append((ticker, ["druga propozycja dla tej samej spółki"]))
            continue
        widziane.add(ticker)

        if ticker in zajete:
            odrzucone.append((ticker, ["spółka ma już otwarty plan"]))
            continue
        dossier = wpisy.get(ticker)
        if dossier is None:
            odrzucone.append((ticker, [f"nie ma jej w dossier na {dzien_dossier}"]))
            continue

        bledy = _sprawdz_pola(p)
        ocena = bramka.sprawdz(p, dossier)
        bledy += ocena["powody"]
        if bledy:
            odrzucone.append((ticker, bledy))
            continue

        przyjete.append((p, dossier | {"_ocena": ocena}))

    # Kolejność: pewność, potem stosunek zysku do ryzyka, na końcu ticker —
    # żeby przy remisie wynik nie zależał od kolejności w pliku.
    przyjete.sort(
        key=lambda para: (
            -int(para[0]["pewnosc"]),
            -(para[1]["_ocena"]["rr"] or 0),
            para[0]["ticker"],
        )
    )

    ponad_limit = przyjete[MAKS_PLANOW:]
    przyjete = przyjete[:MAKS_PLANOW]

    print(f"📋 Propozycji: {len(propozycje)} | przez bramkę: "
          f"{len(przyjete) + len(ponad_limit)} | odrzuconych: {len(odrzucone)}")
    print()

    for ticker, powody in odrzucone:
        print(f"❌ {ticker}")
        for powod in powody:
            print(f"     • {powod}")

    if odrzucone:
        print()
    for p, dossier in przyjete:
        ocena = dossier["_ocena"]
        print(f"✔️ {p['ticker']}: {p['wejscie_od']}–{p['wejscie_do']} / "
              f"SL {p['sl']} ({p.get('sl_poziom', '?')}) / TP {p['tp1']}"
              f"{' → ' + str(p['tp2']) if p.get('tp2') else ''} | "
              f"R:R {ocena['rr']} | stop {ocena['sl_w_atr']} ATR | "
              f"pewność {p['pewnosc']}/5")
        for uwaga in ocena["uwagi"]:
            print(f"     ⚠️ {uwaga}")

    for p, _ in ponad_limit:
        print(f"➖ {p['ticker']}: przeszedł bramkę, ale nie zmieścił się "
              f"w limicie {MAKS_PLANOW} planów na dzień")

    if not przyjete:
        print("\nNic nie zostało do zapisania.")
        sys.exit(1)
    if args.sucho:
        print("\n🧪 Tryb suchy — nic nie zapisuję.")
        return

    for p, dossier in przyjete:
        ocena = dossier["_ocena"]
        db.zapisz_plan({
            "dzien": args.dzien,
            "ticker": p["ticker"],
            "kierunek": "long",
            "teza": str(p.get("teza", "")).strip(),
            "wejscie_od": min(float(p["wejscie_od"]), float(p["wejscie_do"])),
            "wejscie_do": max(float(p["wejscie_od"]), float(p["wejscie_do"])),
            "sl": float(p["sl"]),
            "sl_poziom": str(p.get("sl_poziom", "")),
            "tp1": float(p["tp1"]),
            "tp2": float(p["tp2"]) if p.get("tp2") is not None else None,
            "rr": ocena["rr"],
            "pewnosc": int(p["pewnosc"]),
            "horyzont_sesji": int(p.get("horyzont_sesji", 10)),
            # Źródła bierzemy z dossier, nie od modelu — to fakt o tym,
            # które rankingi wskazały spółkę, a nie element oceny.
            "zrodla": ", ".join(z["ranking"] for z in dossier.get("zrodla", [])),
            "uwagi": "; ".join(ocena["uwagi"]),
        })
    print(f"\n💾 Zapisano {len(przyjete)} planów na {args.dzien}.")


if __name__ == "__main__":
    main()
