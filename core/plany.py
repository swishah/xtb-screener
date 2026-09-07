"""
Rozliczanie planów wejścia podczas codziennego skanu.

PO CO. Plan, którego nikt nie rozlicza, jest opowieścią — po miesiącu pamięta
się trafienia i zapomina resztę. Rozliczanie jest mechaniczne i bezlitosne:
każdy plan dostaje wynik w R, także ten, który nigdy się nie uruchomił.
Dopiero to pozwala kiedyś powiedzieć, czy cały pomysł działa.

CO TO JEST „R". Jednostka ryzyka: różnica między zakładanym wejściem
a stop-lossem. Wynik +2R znaczy „zarobione dwa razy tyle, ile było na
stole", −1R to trafiony stop. Liczenie w R, a nie w procentach, pozwala
porównywać spółkę po 2 EUR ze spółką po 300 USD.

TRZY ZAŁOŻENIA, KTÓRE TRZEBA ZNAĆ, ŻEBY NIE UWIERZYĆ W ZA ŁADNE WYNIKI:

1. **Zlecenie wchodzi po GÓRNEJ granicy strefy.** Zlecenie z limitem stoi
   na `wejscie_do`, więc gdy kurs tam zejdzie, kupujemy dokładnie tam.
   To najgorsza cena w całej strefie, czyli założenie ostrożne.

2. **Gdy w jednej sesji kurs dotknął i stopa, i celu, uznajemy STOPA.**
   Ze świecy dziennej NIE DA SIĘ odczytać kolejności — nie wiadomo, czy
   najpierw był dołek, czy szczyt. Każde inne założenie zawyżałoby wyniki,
   a to jest jedyny błąd, którego przy narzędziu do pieniędzy nie wolno
   popełnić. Takie rozliczenia są oznaczone (`stan` z przyrostkiem `?`
   w opisie), żeby dało się policzyć, ilu przypadków dotyczy.

3. **`sesji_minelo` liczy PRZEBIEGI SKANU, nie sesje giełdowe.** Skan chodzi
   w dni robocze, więc dla większości rynków to jedno i to samo — ale święto
   w Oslo czy w Warszawie i tak przesunie licznik. Przy horyzoncie dziesięciu
   sesji błąd sięga dnia, dwóch. Świadomie nie komplikujemy tego kalendarzem
   giełdowym, bo horyzont i tak jest orientacyjny.

CO SIĘ Z CZYM ŁĄCZY: plany zakłada warstwa oceniająca po przejściu przez
`core/bramka.py`, a tutaj tylko posuwamy je do przodu. Ten moduł nie ocenia
i niczego nie zakłada.
"""
from __future__ import annotations

from datetime import date

from core import db

# Stany planu. `czeka` — zlecenie postawione, kurs jeszcze nie wszedł w strefę.
# `aktywny` — pozycja otwarta. Reszta to stany końcowe.
STANY_OTWARTE = ("czeka", "aktywny")
STANY_KONCOWE = ("sl", "tp1", "tp2", "wygasl", "anulowany")


def _liczba(wartosc):
    if wartosc is None or isinstance(wartosc, str):
        return None
    try:
        f = float(wartosc)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _zakres_sesji(wiersz: dict) -> tuple[float | None, float | None, float | None]:
    """
    Maksimum, minimum i zamknięcie ostatniej sesji.

    Zapasowy wariant na samą cenę jest tu z tego samego powodu co w alarmach:
    starsze migawki nie mają kolumn z ekstremami, a część instrumentów nie ma
    ich nigdy. Plan rozlicza się wtedy wyłącznie po zamknięciu — gubi ruchy
    w ciągu dnia, ale nie przestaje działać.
    """
    cena = _liczba(wiersz.get("Cena"))
    maks = _liczba(wiersz.get("Maksimum dnia"))
    mini = _liczba(wiersz.get("Minimum dnia"))
    return (maks if maks is not None else cena,
            mini if mini is not None else cena,
            cena)


def wynik_r(plan: dict, cena_wyjscia: float) -> float | None:
    """Wynik w jednostkach ryzyka, licząc wejście po górnej granicy strefy."""
    wejscie = _liczba(plan.get("wejscie_do"))
    sl = _liczba(plan.get("sl"))
    if wejscie is None or sl is None:
        return None
    ryzyko = wejscie - sl
    if ryzyko <= 0:
        return None
    return round((cena_wyjscia - wejscie) / ryzyko, 2)


def _rozlicz_aktywny(plan: dict, maks, mini, cena, dzien: str) -> dict | None:
    """
    Co się stało z otwartą pozycją w tej sesji. None = nic, plan zostaje.

    Kolejność sprawdzania jest tu istotna i celowo ostrożna: stop przed celem.
    """
    sl = _liczba(plan.get("sl"))
    tp1 = _liczba(plan.get("tp1"))
    tp2 = _liczba(plan.get("tp2"))

    trafiony_sl = sl is not None and mini is not None and mini <= sl
    trafiony_tp2 = tp2 is not None and maks is not None and maks >= tp2
    trafiony_tp1 = tp1 is not None and maks is not None and maks >= tp1

    if trafiony_sl:
        zmiany = {
            "stan": "sl",
            "data_zamkniecia": dzien,
            "cena_zamkniecia": sl,
            "wynik_r": wynik_r(plan, sl),
        }
        if trafiony_tp1:
            # Obie granice w jednej świecy — kolejności nie znamy, więc
            # zapisujemy najgorszą wersję i mówimy o tym wprost. Dopisujemy
            # do istniejących uwag, bo siedzą tam ostrzeżenia z bramki.
            stare = str(plan.get("uwagi") or "").strip()
            nota = "stop i cel w tej samej sesji — przyjęto stop"
            zmiany["uwagi"] = f"{stare}; {nota}" if stare else nota
        return zmiany

    if trafiony_tp2:
        return {"stan": "tp2", "data_zamkniecia": dzien,
                "cena_zamkniecia": tp2, "wynik_r": wynik_r(plan, tp2)}
    if trafiony_tp1:
        return {"stan": "tp1", "data_zamkniecia": dzien,
                "cena_zamkniecia": tp1, "wynik_r": wynik_r(plan, tp1)}

    horyzont = _liczba(plan.get("horyzont_sesji")) or 10
    if (plan.get("sesji_minelo") or 0) + 1 >= horyzont and cena is not None:
        # Horyzont minął, a kurs stoi w miejscu. Zamykamy po cenie z rynku —
        # plan bez końca nie jest planem, tylko otwartą pozycją bez tezy.
        return {"stan": "wygasl", "data_zamkniecia": dzien,
                "cena_zamkniecia": cena, "wynik_r": wynik_r(plan, cena)}
    return None


def rozlicz(rows: list[dict], dzien: str | None = None) -> list[dict]:
    """
    Posuwa wszystkie otwarte plany o jedną sesję. Zwraca opis tego, co się zmieniło.

    `rows` to wiersze dzisiejszej migawki — te same, które skan właśnie zapisał,
    więc rozliczenie nie kosztuje ani jednego zapytania do sieci.
    """
    dzien = dzien or date.today().isoformat()
    try:
        otwarte = db.plany_otwarte()
    except Exception as e:  # noqa: BLE001
        # Brak tabeli znaczy tyle, że nikt jeszcze nie zapisał planu.
        print(f"ℹ️ Plany: pomijam rozliczanie ({e}).")
        return []
    if not otwarte:
        return []

    kursy = {str(r.get("Ticker")): r for r in rows}
    zdarzenia: list[dict] = []

    for plan in otwarte:
        wiersz = kursy.get(str(plan["ticker"]))
        if wiersz is None:
            continue  # spółka wypadła z uniwersum — licznik nie rusza
        maks, mini, cena = _zakres_sesji(wiersz)
        if maks is None and mini is None and cena is None:
            continue

        stan_przed = plan["stan"]
        zmiany: dict = {}

        if stan_przed == "czeka":
            wejscie_do = _liczba(plan.get("wejscie_do"))
            weszlo = (wejscie_do is not None and mini is not None
                      and mini <= wejscie_do)
            if weszlo:
                plan["stan"] = "aktywny"
                zmiany.update({"stan": "aktywny", "data_wejscia": dzien})
                # Ta sama sesja może otworzyć i zamknąć pozycję — sprawdzamy
                # od razu, zamiast czekać do jutra.
                domkniecie = _rozlicz_aktywny(plan, maks, mini, cena, dzien)
                if domkniecie:
                    zmiany.update(domkniecie)
            else:
                horyzont = _liczba(plan.get("horyzont_sesji")) or 10
                if (plan.get("sesji_minelo") or 0) + 1 >= horyzont:
                    # Kurs nigdy nie wszedł w strefę. Wynik 0R, nie brak wyniku —
                    # niezrealizowane wejście to też informacja o jakości planu.
                    zmiany.update({"stan": "wygasl", "data_zamkniecia": dzien,
                                   "wynik_r": 0.0})
        else:
            domkniecie = _rozlicz_aktywny(plan, maks, mini, cena, dzien)
            if domkniecie:
                zmiany.update(domkniecie)

        zmiany["sesji_minelo"] = (plan.get("sesji_minelo") or 0) + 1
        db.aktualizuj_plan(plan["id"], **zmiany)

        if zmiany.get("stan") and zmiany["stan"] != stan_przed:
            zdarzenia.append({
                "id": plan["id"],
                "ticker": plan["ticker"],
                "nazwa": plan.get("teza", ""),
                "z": stan_przed,
                "na": zmiany["stan"],
                "wynik_r": zmiany.get("wynik_r"),
                "uwagi": zmiany.get("uwagi", ""),
            })

    return zdarzenia


def podsumowanie(plany: list[dict]) -> dict:
    """
    Statystyka zamkniętych planów: ile, jaka skuteczność, ile R łącznie.

    Plany nierozliczone są POMIJANE, a nie liczone jako zero — inaczej świeżo
    wystawiony plan psułby statystykę do czasu zamknięcia.
    """
    zamkniete = [p for p in plany if p.get("stan") in STANY_KONCOWE
                 and p.get("wynik_r") is not None]
    if not zamkniete:
        return {"liczba": 0, "trafione": 0, "skutecznosc": None,
                "suma_r": 0.0, "srednia_r": None}
    wyniki = [float(p["wynik_r"]) for p in zamkniete]
    trafione = sum(1 for w in wyniki if w > 0)
    # ŚREDNIĄ LICZYMY Z ZAOKRĄGLONEJ SUMY, nie z surowej — po to, żeby ta sama
    # statystyka policzona we frontendzie (`podsumowanie()` w lib/plany.ts)
    # dała identyczną liczbę. Sumowanie liczb zmiennoprzecinkowych zależy od
    # KOLEJNOŚCI składników, a obie strony czytają plany innym sortowaniem;
    # bez tego kroku 2,38 potrafi wyjść jako 2,3800000000000003 po jednej
    # stronie i średnia różni się o grosz bez żadnego powodu.
    suma = round(sum(wyniki), 2)
    return {
        "liczba": len(zamkniete),
        "trafione": trafione,
        "skutecznosc": round(trafione / len(zamkniete) * 100, 1),
        "suma_r": suma,
        "srednia_r": round(suma / len(wyniki), 2),
    }
