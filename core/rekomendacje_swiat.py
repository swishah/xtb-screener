"""
Rekomendacje analityków dla giełd europejskich — druga warstwa uzupełniania.

DLACZEGO TO ISTNIEJE: Yahoo pokrywa rekomendacjami 82% spółek z USA, ale
tylko 35% z Londynu, 58% z Frankfurtu, 60% z Mediolanu, 63% z Wiednia i 50%
z Lizbony. Bez rekomendacji zostawały tam spółki wielkości HSBC, Vodafone,
RELX, voestalpine czy Sonae — czyli firmy, które mają po kilkanaście
raportów analitycznych rocznie. To brak danych u JEDNEGO dostawcy, nie brak
zainteresowania analityków.

ŹRÓDŁO: stockanalysis.com — jedna strona na spółkę, z konsensusem w tej samej
metodologii co Yahoo (uśredniona ocena wielu analityków + 12-miesięczna cena
docelowa). To ważne: dzięki temu wartości z tego źródła są PORÓWNYWALNE
z tymi z Yahoo, w odróżnieniu od biznesradar.pl, który podaje pojedyncze
rekomendacje polskich domów maklerskich (patrz core/rekomendacje.py).
Ścieżka /quote/ jest dozwolona w robots.txt serwisu (blokowane są tylko
/e/ i /p/).

CZEGO TO KOSZTUJE: jedno zapytanie NA SPÓŁKĘ, w odróżnieniu od biznesradar,
gdzie jedna strona daje całą giełdę. Dlatego odpytujemy WYŁĄCZNIE spółki
z faktyczną luką (~150 z ~1300) i robimy przerwę między zapytaniami. Przy
domyślnym limicie skan wydłuża się o kilka minut, nie o godziny.

TRZY OGRANICZENIA, KTÓRE TRZEBA ZNAĆ:

1. To scraping HTML. Przebudowa serwisu zepsuje parsowanie — dlatego błąd
   pojedynczej spółki jest pomijany, a brak całego źródła kończy się pustym
   wynikiem, nie wyjątkiem. Skan idzie dalej.
2. Ceny docelowe są w walucie notowania. Dla Londynu Yahoo i to źródło
   podają obie wartości w pensach, więc skala się zgadza — ale gdyby kiedyś
   przestała, cena docelowa wyszłaby 100× nie tak. Stąd kontrola
   _rozsadny_cel(): odrzucamy cel odbiegający od kursu więcej niż 5×.
3. Angielska skala (Strong Buy / Buy / Hold / Sell) jest tłumaczona na
   polską, taką samą jak reszta appki.
"""
from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.request

# Sufiks tickera Yahoo -> kod giełdy w adresach serwisu.
# Sprawdzone empirycznie: /quote/<kod>/<rdzen>/ zwraca 200 z sekcją analityków.
GIELDY = {
    "L": "lon",     # Londyn
    "DE": "etr",    # Frankfurt (Xetra)
    "MI": "bit",    # Mediolan (Borsa Italiana)
    "VI": "vie",    # Wiedeń
    "LS": "eli",    # Lizbona (Euronext Lisbon)
    "WA": "wse",    # Warszawa
    "PA": "epa",    # Paryż (Euronext Paris)
    "AS": "ams",    # Amsterdam
    "MC": "bme",    # Madryt
    "ST": "sto",    # Sztokholm
    "OL": "osl",    # Oslo
    "BR": "ebr",    # Bruksela
    "HE": "hel",    # Helsinki
    "CO": "cph",    # Kopenhaga
    "SW": "six",    # Zurych
}

ADRES = "https://stockanalysis.com/quote/{gielda}/{ticker}/"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Przerwa między zapytaniami. Nie jest to wymóg serwisu, tylko zwykła
# przyzwoitość — odpytujemy cudzy serwer setki razy pod rząd.
PRZERWA_S = 1.0

# Limit spółek na jeden skan. Zabezpieczenie przed sytuacją, w której
# uniwersum urośnie i skan zacznie trwać godzinami.
LIMIT = 250

# Angielska skala na polską, tę samą co w reszcie appki.
SKALA = {
    "strong buy": "Kupuj",
    "buy": "Kupuj",
    "outperform": "Akumuluj",
    "overweight": "Akumuluj",
    "hold": "Trzymaj",
    "neutral": "Trzymaj",
    "underperform": "Redukuj",
    "underweight": "Redukuj",
    "sell": "Sprzedaj",
    "strong sell": "Sprzedaj",
}


def _pobierz(adres: str) -> str:
    try:
        req = urllib.request.Request(adres, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as odp:
            return odp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        # 404 to normalna sytuacja: serwis po prostu nie zna tej spółki.
        return ""
    except Exception:  # noqa: BLE001
        return ""


def _liczba(tekst: str) -> float | None:
    t = tekst.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _rozsadny_cel(cel: float | None, kurs: float | None) -> float | None:
    """
    Odrzuca cenę docelową w innej skali niż kurs (pensy kontra funty).

    Analityk może się mylić o 100%, ale nie o 400% — wartość poza tym
    przedziałem to prawie na pewno rozjazd jednostek, a nie odważna prognoza.
    Lepiej nie pokazać nic niż pokazać cel 100× zawyżony.
    """
    if cel is None or cel <= 0:
        return None
    if kurs is None or kurs <= 0:
        return cel
    if not (0.2 <= cel / kurs <= 5.0):
        return None
    return cel


def rekomendacja_spolki(ticker: str, kurs: float | None = None) -> dict | None:
    """
    Konsensus dla jednej spółki albo None, gdy źródło jej nie zna.

    Zwraca: {"rekomendacja", "cena_docelowa", "liczba"}
    """
    if "." not in ticker:
        return None
    rdzen, sufiks = ticker.rsplit(".", 1)
    gielda = GIELDY.get(sufiks)
    if not gielda:
        return None

    strona = _pobierz(ADRES.format(gielda=gielda, ticker=rdzen))
    if not strona:
        return None

    # Zdanie podsumowania: "According to 18 analysts, the average rating for
    # OMV stock is "Hold."" — daje jednocześnie liczbę analityków i ocenę.
    m = re.search(
        r"According to\s+([0-9]+)\s+analysts?,\s*the average rating[^\"“]*[\"“]\s*"
        r"(Strong Buy|Buy|Outperform|Overweight|Hold|Neutral|Underperform|"
        r"Underweight|Sell|Strong Sell)",
        html.unescape(strona),
        re.I,
    )
    if not m:
        return None
    ilu = int(m.group(1))
    slowo = SKALA.get(m.group(2).strip().lower())
    if not slowo or ilu < 1:
        return None

    # Cena docelowa siedzi w wierszu tabeli: Price Target | 62.44 (-10.26%)
    cel = None
    m_cel = re.search(
        r"Price Target</a>.*?<td[^>]*>\s*([0-9][0-9,]*\.?[0-9]*)", strona, re.S
    )
    if not m_cel:
        m_cel = re.search(r'target:"([0-9][0-9,]*\.?[0-9]*)', strona)
    if m_cel:
        cel = _rozsadny_cel(_liczba(m_cel.group(1)), kurs)

    return {"rekomendacja": slowo, "cena_docelowa": cel, "liczba": ilu}


def uzupelnij(braki: list[tuple[str, float | None]], limit: int = LIMIT) -> dict[str, dict]:
    """
    Odpytuje źródło o podane spółki (ticker, kurs) i zwraca to, co znalazło.

    `braki` ma zawierać WYŁĄCZNIE spółki bez rekomendacji — każda pozycja to
    osobne zapytanie sieciowe.
    """
    wynik: dict[str, dict] = {}
    obsluzone = 0
    for ticker, kurs in braki:
        if obsluzone >= limit:
            print(f"ℹ️ Rekomendacje świat: osiągnięto limit {limit} zapytań.")
            break
        if "." not in ticker or ticker.rsplit(".", 1)[1] not in GIELDY:
            continue
        obsluzone += 1
        try:
            d = rekomendacja_spolki(ticker, kurs)
        except Exception:  # noqa: BLE001
            d = None
        if d:
            wynik[ticker] = d
        time.sleep(PRZERWA_S)
    return wynik
