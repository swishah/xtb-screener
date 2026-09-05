"""
Rekomendacje analityków dla GPW — uzupełnienie luki w danych Yahoo Finance.

DLACZEGO TO ISTNIEJE: Yahoo pokrywa rekomendacjami 90% spółek z S&P 500, ale
tylko 15% ze sWIG80 i 61% z WIG20+mWIG40. Bez rekomendacji zostają tam nawet
mBank, Orange Polska i Inter Cars — spółki, które w Polsce mają solidne
pokrycie analityczne. To nie jest brak zainteresowania analityków, tylko brak
danych u jednego dostawcy.

ŹRÓDŁO: biznesradar.pl publikuje JEDNĄ zbiorczą stronę z ostatnimi
rekomendacjami dla całej giełdy — przy ostatnim sprawdzeniu 217 rekomendacji
dla 144 spółek. Dzięki temu wystarczy JEDNO zapytanie na skan zamiast
odpytywania każdej spółki osobno. Ścieżka jest dozwolona w robots.txt serwisu
(Allow: / z wyjątkami, które jej nie dotyczą).

DWA OGRANICZENIA, KTÓRE TRZEBA ZNAĆ:

1. To scraping HTML, nie API. Przebudowa strony po stronie serwisu zepsuje
   parsowanie. Dlatego każdy błąd jest łapany i kończy się PUSTYM wynikiem,
   nie wyjątkiem — skan ma iść dalej, a spółki zostają z tym, co daje Yahoo.
2. Metodologia jest INNA niż u Yahoo. Yahoo podaje konsensus wielu analityków
   naraz; tutaj mamy pojedyncze rekomendacje domów maklerskich, w polskiej
   pięciostopniowej skali. Dlatego wynik trafia do osobnej kolumny ze
   wskazaniem źródła — mieszanie tych dwóch rzeczy bez oznaczenia
   wprowadzałoby w błąd.
"""
from __future__ import annotations

import html
import re
import urllib.request
from datetime import datetime, timedelta

ADRES = "https://www.biznesradar.pl/rekomendacje/"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Rekomendacje starsze niż rok przestają opisywać bieżącą sytuację spółki.
MIESIECY_WSTECZ = 12

# Polska skala pięciostopniowa na liczby — żeby dało się policzyć konsensus
# z kilku rekomendacji różnych domów maklerskich.
SKALA = {
    "kupuj": 5.0,
    "akumuluj": 4.0,
    "trzymaj": 3.0,
    "neutralnie": 3.0,
    "redukuj": 2.0,
    "sprzedaj": 1.0,
}

# Powrót z liczby na słowo. Progi w połowie odległości między stopniami.
PROGI = [
    (4.5, "Kupuj"),
    (3.5, "Akumuluj"),
    (2.5, "Trzymaj"),
    (1.5, "Redukuj"),
    (0.0, "Sprzedaj"),
]


def _tekst(html_fragment: str) -> str:
    """Zawartość komórki bez znaczników i nadmiarowych spacji."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html_fragment))).strip()


def _liczba(tekst: str) -> float | None:
    """Polski zapis liczby (przecinek dziesiętny, spacje w tysiącach) na float."""
    t = tekst.replace("\xa0", "").replace(" ", "").replace(",", ".")
    t = re.sub(r"[^0-9.\-]", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def pobierz_surowe(adres: str = ADRES) -> list[dict]:
    """
    Pojedyncze rekomendacje z tabeli. Zwraca listę słowników; przy jakimkolwiek
    problemie — pustą listę, nigdy wyjątek.
    """
    try:
        req = urllib.request.Request(
            adres, headers={"User-Agent": UA, "Accept-Language": "pl,en;q=0.8"}
        )
        with urllib.request.urlopen(req, timeout=30) as odp:
            strona = odp.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Rekomendacje GPW: nie udało się pobrać ({type(e).__name__}).")
        return []

    wynik: list[dict] = []
    for wiersz in re.findall(r"<tr[^>]*>(.*?)</tr>", strona, re.S):
        kom = [_tekst(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", wiersz, re.S)]
        # Układ kolumn: profil | rodzaj | cena docelowa | kurs aktualny |
        # CD/K | kurs z dnia wydania | data | autor | plik
        if len(kom) < 8:
            continue
        rodzaj = kom[1].lower().strip()
        if rodzaj not in SKALA:
            continue

        # "AGO (AGORA)" -> AGO
        m = re.match(r"([A-Z0-9]+)\s*\(", kom[0])
        if not m:
            continue

        data = None
        m_data = re.match(r"(\d{4}-\d{2}-\d{2})", kom[6])
        if m_data:
            try:
                data = datetime.strptime(m_data.group(1), "%Y-%m-%d")
            except ValueError:
                data = None

        wynik.append(
            {
                "ticker_gpw": m.group(1),
                "rodzaj": rodzaj,
                "cena_docelowa": _liczba(kom[2]),
                "data": data,
                "autor": kom[7],
            }
        )
    return wynik


def rekomendacje_gpw() -> dict[str, dict]:
    """
    Konsensus per spółka, kluczowany tickerem w formacie Yahoo (AGO.WA).

    Zwraca: {ticker: {"rekomendacja", "cena_docelowa", "liczba", "ostatnia", "domy"}}
    """
    surowe = pobierz_surowe()
    if not surowe:
        return {}

    granica = datetime.now() - timedelta(days=30 * MIESIECY_WSTECZ)
    wg_spolki: dict[str, list[dict]] = {}
    for r in surowe:
        if r["data"] is None or r["data"] < granica:
            continue
        wg_spolki.setdefault(r["ticker_gpw"], []).append(r)

    wynik: dict[str, dict] = {}
    for ticker_gpw, pozycje in wg_spolki.items():
        oceny = [SKALA[p["rodzaj"]] for p in pozycje]
        srednia = sum(oceny) / len(oceny)
        slowo = next(s for prog, s in PROGI if srednia >= prog)

        cele = [p["cena_docelowa"] for p in pozycje if p["cena_docelowa"]]
        # Mediana, nie średnia: jedna skrajna wycena nie ma przesuwać całości.
        cel = None
        if cele:
            posortowane = sorted(cele)
            srodek = len(posortowane) // 2
            cel = (
                posortowane[srodek]
                if len(posortowane) % 2
                else (posortowane[srodek - 1] + posortowane[srodek]) / 2
            )

        najnowsza = max(p["data"] for p in pozycje)
        domy = sorted({
            re.search(r"\(([^)]+)\)", p["autor"]).group(1)
            for p in pozycje
            if re.search(r"\(([^)]+)\)", p["autor"])
        })

        wynik[f"{ticker_gpw}.WA"] = {
            "rekomendacja": slowo,
            "cena_docelowa": round(cel, 2) if cel else None,
            "liczba": len(pozycje),
            "ostatnia": najnowsza.strftime("%Y-%m-%d"),
            "domy": ", ".join(domy),
        }
    return wynik
