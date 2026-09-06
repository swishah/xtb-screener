"""
Rewizje analityków — zmiana ceny docelowej i rekomendacji w czasie.

DLACZEGO TO ISTNIEJE: w rankingu AAII, prowadzonym na żywo od 1998 roku,
dwa najlepsze screeny spośród kilkudziesięciu to właśnie rewizje prognoz —
21,9% i 21,2% rocznie przy 8,9% dla S&P 500 Total Return. Nie backtest,
tylko wyniki publikowane na bieżąco. Mechanizm jest opisany w literaturze:
rynek reaguje na rewizje z opóźnieniem, więc kurs dryfuje w stronę, którą
wskazała zmiana prognozy.

CZYM TO SIĘ RÓŻNI OD RESZTY: wszystkie pozostałe strategie patrzą na
pojedynczą migawkę. Ta jako jedyna używa HISTORII — porównuje dzisiejszą
cenę docelową z tą sprzed około miesiąca. Dlatego nie dało się jej dodać
wcześniej: potrzebowała zgromadzonych migawek, a nie nowego źródła danych.
Kolumna z ceną docelową istnieje od 2026-08-10.

DWIE PUŁAPKI, KTÓRE TRZEBA ZNAĆ:

1. **Uzupełnianie luk NIE jest rewizją.** Od 2026-09-05 dokładamy
   rekomendacje ze stockanalysis.com i biznesradar.pl tam, gdzie Yahoo ich
   nie ma. Spółka, która wczoraj nie miała rekomendacji, a dziś ma, wygląda
   jak potężna podwyżka — a to tylko pojawienie się danych. Dlatego liczymy
   zmianę WYŁĄCZNIE wtedy, gdy obie migawki mają prawdziwą wartość.

2. **Zmiana źródła też nie jest rewizją.** Ceny docelowe z różnych źródeł
   nie są wprost porównywalne. Uzupełnianie dotyka tylko pustych pól, więc
   dziś ten przypadek nie występuje — ale gdyby kiedyś zaczęło nadpisywać,
   trzeba tu dołożyć porównanie kolumny „Źródło rekomendacji".
"""
from __future__ import annotations

from datetime import datetime

# Ile dni wstecz szukamy punktu odniesienia. Miesiąc to okno używane
# w screenach rewizyjnych i wystarczająco długie, żeby pojedyncza korekta
# nie ginęła w szumie.
DNI_WSTECZ = 30

# Granice akceptowalnego okna. Poniżej dolnej zmiany są za drobne, żeby
# cokolwiek znaczyły; powyżej górnej to już nie jest „bieżąca" rewizja.
MIN_DNI = 12
MAKS_DNI = 75

# Wszystkie warianty słowne, jakie mogą trafić do kolumny z rekomendacją —
# z Yahoo (core/scanner.py), ze stockanalysis i z biznesradar.
SKALA = {
    "silne sprzedaj": 1.0,
    "sprzedaj": 1.0,
    "redukuj": 2.0,
    "trzymaj": 3.0,
    "neutralnie": 3.0,
    "akumuluj": 4.0,
    "kupuj": 4.0,
    "silne kupuj": 5.0,
}

PUSTE = ("", "brak", "nan", "none")


def _liczba(wartosc):
    if wartosc is None or isinstance(wartosc, str):
        return None
    try:
        f = float(wartosc)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _ocena(wartosc) -> float | None:
    """Rekomendacja słowna na liczbę. None, gdy pole jest puste."""
    w = str(wartosc or "").strip().lower()
    if w in PUSTE:
        return None
    return SKALA.get(w)


def kandydaci_odniesienia(daty: list[str], na_dzien: str | None = None) -> list[str]:
    """
    Migawki mieszczące się w oknie, uszeregowane od najbliższej DNI_WSTECZ.

    Zwraca LISTĘ, a nie jedną datę, bo sama data to za mało: migawka może
    istnieć, a mimo to nie mieć kolumny z ceną docelową. Tak było naprawdę —
    kolumna pojawiła się dopiero 2026-08-10, więc pierwszy wybór (2026-08-08)
    dawał zero policzonych rewizji, po cichu. Wołający ma przejść listę
    i wziąć pierwszą migawkę, która faktycznie niesie dane.
    """
    if not daty:
        return []
    try:
        dzis = datetime.strptime(na_dzien or daty[0], "%Y-%m-%d")
    except ValueError:
        return []

    pasujace = []
    for d in daty:
        try:
            kiedy = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        wiek = (dzis - kiedy).days
        if MIN_DNI <= wiek <= MAKS_DNI:
            pasujace.append((abs(wiek - DNI_WSTECZ), d))
    pasujace.sort()
    return [d for _, d in pasujace]


def wybierz_odniesienie(daty: list[str], na_dzien: str | None = None) -> str | None:
    """Pierwszy kandydat albo None. Wygodne, gdy nie trzeba sprawdzać danych."""
    kandydaci = kandydaci_odniesienia(daty, na_dzien)
    return kandydaci[0] if kandydaci else None


def ma_dane_odniesienia(wiersze: list[dict], minimum: int = 50) -> bool:
    """
    Czy migawka nadaje się na punkt odniesienia — czyli czy w ogóle niesie
    ceny docelowe. Bez tego sprawdzenia porównanie wychodzi puste, a skan
    raportuje sukces.
    """
    ile = 0
    for r in wiersze:
        if _liczba(r.get("Cena docelowa (analitycy)")) is not None:
            ile += 1
            if ile >= minimum:
                return True
    return False


def uzupelnij(rows: list[dict], stare: dict[str, dict], data_odniesienia: str) -> int:
    """
    Dopisuje do wierszy trzy kolumny opisujące rewizję. Zwraca liczbę spółek,
    dla których udało się cokolwiek policzyć.

    `stare` to słownik {ticker: wiersz} z migawki odniesienia.
    """
    policzone = 0
    for r in rows:
        r["Zmiana ceny docelowej (%)"] = "BRAK"
        r["Zmiana rekomendacji"] = "BRAK"
        r["Rewizja od dnia"] = data_odniesienia if stare else "BRAK"

        poprzedni = stare.get(str(r.get("Ticker", "")))
        if not poprzedni:
            continue

        cel_teraz = _liczba(r.get("Cena docelowa (analitycy)"))
        cel_wtedy = _liczba(poprzedni.get("Cena docelowa (analitycy)"))
        # Obie wartości muszą istnieć — patrz pułapka nr 1 w nagłówku modułu.
        if cel_teraz and cel_wtedy and cel_wtedy > 0:
            r["Zmiana ceny docelowej (%)"] = round(
                ((cel_teraz - cel_wtedy) / cel_wtedy) * 100, 2
            )
            policzone += 1

        ocena_teraz = _ocena(r.get("Rekomendacja analityków"))
        ocena_wtedy = _ocena(poprzedni.get("Rekomendacja analityków"))
        if ocena_teraz is not None and ocena_wtedy is not None:
            if ocena_teraz > ocena_wtedy:
                r["Zmiana rekomendacji"] = "Podniesiona"
            elif ocena_teraz < ocena_wtedy:
                r["Zmiana rekomendacji"] = "Obniżona"
            else:
                r["Zmiana rekomendacji"] = "Bez zmian"
    return policzone
