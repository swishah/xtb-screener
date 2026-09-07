"""
Bramka kontrolna planów wejścia — mechaniczne sprawdzenie przed zapisem.

PO CO TO ISTNIEJE. Plan wejścia wychodzi z warstwy oceniającej, czyli
z modelu językowego. Model potrafi podać liczbę, która brzmi wiarygodnie
i której nikt nie sprawdza: stop-loss dwa grosze pod ceną, cel wzięty
z sufitu, poziom, którego nie ma na żadnym wykresie. Bramka to jedyne
miejsce, w którym takie rzeczy się zatrzymują — i dlatego jest ZWYKŁYM
KODEM, deterministycznym i testowalnym, a nie kolejnym promptem.

DWIE KATEGORIE WYNIKU, CELOWO ROZDZIELONE:

  * **odrzucenie** — plan jest wewnętrznie sprzeczny albo bezużyteczny
    (stop nad wejściem, R:R poniżej progu, poziom spoza dossier). Taki plan
    nie trafia do bazy w ogóle.
  * **uwaga** — plan jest poprawny, ale coś w nim osłabia tezę (wysoki
    short, payout ponad 100%, wolumen poniżej średniej). Trafia do bazy
    razem z ostrzeżeniem, bo to jest informacja dla człowieka, a nie powód
    do wyrzucenia pomysłu.

WSZYSTKO LICZYMY DLA POZYCJI DŁUGIEJ. Krótka sprzedaż odwraca każdą regułę
(stop nad wejściem, cel poniżej) i wymagałaby własnego kompletu progów.
Dopóki plany dotyczą kupowania, wymuszamy `kierunek == "long"` — lepiej
odrzucić jawnie niż policzyć R:R ze znakiem na odwrót.
"""
from __future__ import annotations

# Minimalny stosunek zysku do ryzyka. Poniżej 1,5 nawet skuteczność 50%
# nie wystarcza, żeby wyjść na swoje po kosztach.
MIN_RR = 1.5

# Jak daleko od bieżącego kursu może leżeć strefa wejścia. Zlecenie oddalone
# o więcej po prostu się nie doczeka — to nie jest plan, tylko życzenie.
MAKS_DYSTANS_WEJSCIA_PCT = 5.0

# Odległość stopa wyrażona w ATR. Oba końce są istotne:
#  * powyżej 3 ATR to już nie stop, tylko nadzieja — strata przed jego
#    dotknięciem jest większa niż zakładany zysk przy typowym R:R,
#  * poniżej 0,5 ATR stop leży W ZASIĘGU ZWYKŁEGO SZUMU danej spółki
#    i zostanie zabrany przypadkiem, bez żadnej zmiany w tezie.
# Ten drugi warunek jest równie ważny co pierwszy i bywa pomijany.
MIN_SL_W_ATR = 0.5
MAKS_SL_W_ATR = 3.0

# O ile procent podany poziom może się różnić od poziomu z dossier, żeby
# uznać, że plan powołuje się na istniejący poziom, a nie zmyślony.
TOLERANCJA_POZIOMU_PCT = 0.5

# Poziomy grubo poza zakresem roku to prawie zawsze pomyłka skali —
# na przykład funty zamiast pensów przy spółce z Londynu.
MARGINES_ZAKRESU = 0.20


def _liczba(w) -> float | None:
    try:
        x = float(w)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # odsiewa NaN


def _najblizszy_poziom(wartosc: float, poziomy: list[dict]) -> dict | None:
    """Poziom z dossier najbliższy podanej wartości, o ile mieści się w tolerancji."""
    najlepszy = None
    najmniejsza = None
    for p in poziomy:
        w = _liczba(p.get("wartosc"))
        if w is None or w <= 0:
            continue
        roznica = abs(w - wartosc) / w * 100
        if najmniejsza is None or roznica < najmniejsza:
            najmniejsza, najlepszy = roznica, p
    if najlepszy is None or najmniejsza > TOLERANCJA_POZIOMU_PCT:
        return None
    return najlepszy


def sprawdz(plan: dict, dossier: dict) -> dict:
    """
    Sprawdza jeden plan wobec jego dossier.

    Zwraca `{"ok": bool, "powody": [...], "uwagi": [...], "rr": float|None,
    "sl_w_atr": float|None}`. `powody` są wypełnione wyłącznie przy
    odrzuceniu — to lista przyczyn, a nie jedna, żeby nie poprawiać planu
    po jednym błędzie naraz.
    """
    powody: list[str] = []
    uwagi: list[str] = []

    kurs = _liczba(dossier.get("kurs"))
    atr = _liczba(dossier.get("atr"))
    poziomy = dossier.get("poziomy") or []

    if kurs is None or kurs <= 0:
        return {"ok": False, "powody": ["dossier bez kursu"], "uwagi": [],
                "rr": None, "sl_w_atr": None}

    if str(plan.get("kierunek", "long")).lower() != "long":
        powody.append("obsługujemy wyłącznie pozycje długie")

    od = _liczba(plan.get("wejscie_od"))
    do = _liczba(plan.get("wejscie_do"))
    sl = _liczba(plan.get("sl"))
    tp1 = _liczba(plan.get("tp1"))
    tp2 = _liczba(plan.get("tp2"))

    if od is None or do is None or sl is None or tp1 is None:
        return {"ok": False, "powody": ["brak kompletu poziomów planu"],
                "uwagi": [], "rr": None, "sl_w_atr": None}

    if od > do:
        od, do = do, od  # strefa podana od góry — porządkujemy, to nie błąd
    srodek = (od + do) / 2

    # --- spójność wewnętrzna ------------------------------------------------
    if sl >= od:
        powody.append(f"stop {sl} nie leży poniżej dolnej granicy wejścia {od}")
    if tp1 <= do:
        powody.append(f"cel {tp1} nie leży powyżej górnej granicy wejścia {do}")
    if tp2 is not None and tp2 <= tp1:
        powody.append(f"drugi cel {tp2} nie leży powyżej pierwszego {tp1}")

    # --- ryzyko do zysku ----------------------------------------------------
    rr = None
    if sl < srodek < tp1:
        ryzyko = srodek - sl
        rr = round((tp1 - srodek) / ryzyko, 2) if ryzyko > 0 else None
        if rr is not None and rr < MIN_RR:
            powody.append(f"stosunek zysku do ryzyka {rr} poniżej progu {MIN_RR}")

    # --- stop wobec zmienności ---------------------------------------------
    sl_w_atr = None
    if atr and atr > 0 and sl < srodek:
        sl_w_atr = round((srodek - sl) / atr, 2)
        if sl_w_atr > MAKS_SL_W_ATR:
            powody.append(
                f"stop oddalony o {sl_w_atr} ATR — powyżej {MAKS_SL_W_ATR} "
                f"to już nie stop, tylko nadzieja"
            )
        elif sl_w_atr < MIN_SL_W_ATR:
            powody.append(
                f"stop oddalony o {sl_w_atr} ATR — poniżej {MIN_SL_W_ATR} "
                f"leży w zasięgu zwykłego szumu i zostanie zabrany przypadkiem"
            )
    elif not atr:
        uwagi.append("brak ATR w dossier — nie dało się sprawdzić stopu wobec zmienności")

    # --- osiągalność wejścia ------------------------------------------------
    dystans = abs(srodek - kurs) / kurs * 100
    if dystans > MAKS_DYSTANS_WEJSCIA_PCT:
        powody.append(
            f"strefa wejścia oddalona o {dystans:.1f}% od kursu {kurs} — "
            f"powyżej {MAKS_DYSTANS_WEJSCIA_PCT}% takie zlecenie się nie doczeka"
        )

    # --- poziomy muszą pochodzić z dossier ----------------------------------
    # To jest sedno bramki: model nie ma prawa podać liczby, której nie ma
    # na policzonej liście. Sprawdzamy stop, bo od niego zależy strata,
    # i pierwszy cel, bo od niego zależy cały rachunek R:R.
    trafiony = _najblizszy_poziom(sl, poziomy)
    if trafiony is None:
        powody.append(f"stop {sl} nie odpowiada żadnemu poziomowi z dossier")
    else:
        podany = str(plan.get("sl_poziom") or "")
        if podany and podany != trafiony["id"]:
            uwagi.append(
                f"plan powołuje się na poziom „{podany}”, a wartość {sl} "
                f"odpowiada poziomowi „{trafiony['id']}”"
            )
    if _najblizszy_poziom(tp1, poziomy) is None:
        powody.append(f"cel {tp1} nie odpowiada żadnemu poziomowi z dossier")

    # --- skala i zakres -----------------------------------------------------
    zakres = dossier.get("zakres_52t") or {}
    dol, gora = _liczba(zakres.get("min")), _liczba(zakres.get("maks"))
    if dol and gora and gora > dol:
        rozpietosc = gora - dol
        granica_dol = dol - rozpietosc * MARGINES_ZAKRESU
        granica_gora = gora + rozpietosc * MARGINES_ZAKRESU
        for etykieta, wartosc in (("wejście", srodek), ("stop", sl), ("cel", tp1)):
            if not (granica_dol <= wartosc <= granica_gora):
                powody.append(
                    f"{etykieta} {wartosc} leży poza zakresem 52 tygodni "
                    f"({dol}–{gora}) — sprawdź, czy to nie pomyłka skali waluty"
                )

    return {
        "ok": not powody,
        "powody": powody,
        "uwagi": uwagi + _uwagi_z_danych(dossier),
        "rr": rr,
        "sl_w_atr": sl_w_atr,
    }


def mozliwy_plan(dossier: dict) -> tuple[bool, str]:
    """
    Czy dla tej spółki DA SIĘ w ogóle ułożyć plan przechodzący bramkę.

    Używane przy budowaniu dossier, żeby nie oddawać do oceny spółek, których
    i tak nikt nie przepuści. Sprawdzamy WYŁĄCZNIE niemożliwość strukturalną,
    czyli brak miejsca na stop albo brak czegokolwiek powyżej kursu — a nie
    to, czy plan byłby dobry. Ocena należy do warstwy wyżej; tutaj odsiewamy
    tylko przypadki, w których żaden wybór poziomów nie jest poprawny.

    Progi biorą się z tych samych stałych co `sprawdz()`, więc obie funkcje
    nie mogą się rozjechać. Wejście przybliżamy kursem — bramka i tak nie
    wpuści strefy dalszej niż `MAKS_DYSTANS_WEJSCIA_PCT`.
    """
    kurs = _liczba(dossier.get("kurs"))
    atr = _liczba(dossier.get("atr"))
    poziomy = dossier.get("poziomy") or []
    if kurs is None or kurs <= 0:
        return False, "brak kursu"
    if not atr or atr <= 0:
        return False, "brak ATR — nie da się sprawdzić stopu wobec zmienności"

    stopy = [
        p for p in poziomy
        if (w := _liczba(p.get("wartosc"))) is not None
        and MIN_SL_W_ATR * atr <= kurs - w <= MAKS_SL_W_ATR * atr
    ]
    if not stopy:
        return False, (
            f"żaden poziom nie leży w paśmie {MIN_SL_W_ATR}–{MAKS_SL_W_ATR} ATR "
            f"pod kursem — nie ma gdzie postawić stopa"
        )

    if not any((w := _liczba(p.get("wartosc"))) is not None and w > kurs
               for p in poziomy):
        return False, "żaden poziom nie leży powyżej kursu — nie ma gdzie wyjść"

    return True, ""


def _uwagi_z_danych(dossier: dict) -> list[str]:
    """
    Ostrzeżenia z fundamentów i z rynku — osłabiają tezę, ale jej nie obalają.

    Świadomie NIE odrzucamy przez nie planu. Wysoki short bywa powodem, żeby
    trzymać się z daleka, ale bywa też paliwem do gwałtownego odbicia; to
    jest informacja dla człowieka, nie wyrok.
    """
    uwagi: list[str] = []
    dane = dossier.get("migawka") or {}

    def num(klucz):
        return _liczba(dane.get(klucz))

    flagi = num("Liczba flag")
    if flagi and flagi >= 3:
        uwagi.append(f"{int(flagi)} czerwonych flag w danych fundamentalnych")

    short = num("Krótkie pozycje (%)")
    if short and short >= 5:
        uwagi.append(f"krótkie pozycje {short}% wyemitowanego kapitału")

    payout = num("Payout ratio (%)")
    if payout and payout > 100:
        uwagi.append(f"payout ratio {payout}% — spółka wypłaca więcej, niż zarabia")

    wolumen = (dossier.get("wolumen") or {}).get("krotnosc")
    krotnosc = _liczba(wolumen)
    if krotnosc is not None and krotnosc < 0.6:
        uwagi.append(
            f"wolumen {krotnosc}× średniej — ruch bez potwierdzenia obrotem"
        )

    trend = dossier.get("trend") or {}
    if trend.get("1w") == "spadkowy" and trend.get("1m") == "spadkowy":
        uwagi.append("trend tygodniowy i miesięczny spadkowy — wejście pod prąd")

    return uwagi
