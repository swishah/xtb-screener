"""
Krótkie pozycje — ile kapitału spółki jest sprzedane na krótko.

DWA ŹRÓDŁA, BO NIE MA JEDNEGO. Zmierzone na próbce 88 spółek z 11 rynków:
pola o krótkiej sprzedaży w `tk.info` są dostępne dla 8/8 spółek z USA
i dla 0/8 z KAŻDEGO rynku europejskiego. Yahoo po prostu ich tam nie ma.
Europa ma za to coś, czego nie ma Ameryka: z mocy przepisów o krótkiej
sprzedaży pozycje powyżej progu są JAWNE i publikowane przez nadzory.

  1. **USA — Yahoo, za darmo.** Skan i tak pobiera `tk.info` raz na spółkę,
     więc `shortPercentOfFloat`, `sharesShort` i `shortRatio` nie kosztują
     ani jednego zapytania więcej.
  2. **Londyn — rejestr FCA.** Jeden plik XLSX na wszystkie spółki, więc
     jedno pobranie na skan. Zawiera pojedyncze pozycje konkretnych funduszy,
     co daje informację, której dane amerykańskie nie mają: KTO gra na spadek.
  3. **Warszawa — rejestr KNF (rss.knf.gov.pl).** Jedno zapytanie JSON na
     całą giełdę. Próg jawności to 0,5% wyemitowanego kapitału, czyli wyżej
     niż brytyjskie 0,2% — pozycji jest więc mniej, ale każda jest istotna.
  4. **Frankfurt — Bundesanzeiger.** Gotowy eksport CSV całej listy, ale za
     sesją: najpierw trzeba wejść na stronę po ciasteczko, bo adres pliku
     zawiera identyfikator stanu strony. Próg też 0,5%.
  5. **Madryt — CNMV.** Osobny arkusz z pozycjami otwartymi, ale plik jest
     w STARYM formacie XLS (OLE2) — stąd jedyna w projekcie zależność `xlrd`.
  6. **Sztokholm — Finansinspektionen.** Jedyny rejestr bez pliku: dane są
     wprost w tabeli HTML strony. Zbiorcza tabela daje sumę na emitenta,
     a szczegóły (kto i ile) siedzą na podstronach — dociągamy je WYŁĄCZNIE
     dla spółek, które faktycznie dopasowaliśmy, więc kilkanaście zapytań,
     nie trzysta.
  7. **Oslo — Finanstilsynet (ssr.finanstilsynet.no).** Jedyny rejestr
     z prawdziwym API JSON: jedno zapytanie daje całą giełdę, bez sesji,
     bez pliku i bez udawania przeglądarki. Podaje też ISIN, którego my
     nie mamy — patrz niżej.
  8. **Paryż — AMF przez data.gouv.fr.** Najczystsze źródło w zestawie:
     oficjalne otwarte dane na Licencji Otwartej 2.0, aktualizowane codziennie,
     wprost przeznaczone do przetwarzania automatycznego. Żadnych wątpliwości
     co do dozwolonego użycia.

DWIE LICZBY, KTÓRE WYGLĄDAJĄ TAK SAMO, A ZNACZĄ CO INNEGO. Yahoo podaje
procent **wolnego obrotu** (free float), FCA — procent **wyemitowanego
kapitału**. Przy spółce z dużym pakietem kontrolnym te dwie miary potrafią
się różnić kilkukrotnie. Dlatego zapisujemy źródło osobno i profil spółki
mówi wprost, co jest czym. **Nie sklejaj tych wartości w jedną kolumnę bez
źródła.**

CZEGO NIE MA. Wiedeń i Lizbona mają własne rejestry u własnych nadzorów,
każdy w innym formacie — osobna praca na każdy kraj, NIE zrobiona. **Mediolan jest zablokowany świadomie:** CONSOB odsiewa
klienty niebędące przeglądarką stroną CAPTCHA (Radware), a obchodzenia
zabezpieczeń przed botami nie robimy. Ich plik jest zresztą wzorowy —
gdyby CONSOB udostępnił dostęp programistyczny (adres kontaktowy:
shortselling-service@consob.it), dopisanie Mediolanu to kwadrans.
Brak danych o shortach dla tych rynków nie znaczy „brak shortów", tylko
„nie sprawdzamy". Profil spółki mówi to wprost, żeby nikt nie wziął pustego
pola za zielone światło.

DOPASOWANIE IDZIE PO NAZWIE, BO ISIN-ÓW NIE MAMY — i to nie jest lenistwo.
Rejestry identyfikują spółki nazwą i numerem ISIN; my mamy tickery Yahoo.
Sprawdziłem `yfinance.Ticker(...).isin` i **ODRZUCIŁEM**: dla MDV.WA, JSW.WA
i KRU.WA zwraca ISIN-y INDYJSKIE, dla ALE.WA australijski. Yahoo szuka po
nazwie i trafia w obce spółki, a wynik wygląda na poprawny. Użycie tego
przypisałoby cudze pozycje krótkie naszym spółkom — gorzej niż brak danych.
**Nie wracaj do `yfinance.isin` bez sprawdzenia, czy to naprawiono.**

Zostaje dopasowanie po znormalizowanej nazwie. Na 71 spółkach z Londynu
trafia w 26 (część reszty to ETF-y, które pozycji krótkich nie mają
z definicji); na GPW trafia we wszystkich 7 emitentów, którzy w ogóle są
w naszym uniwersum. To ograniczenie, nie błąd — ale nie udawaj, że pokrycie
jest pełne.
"""
from __future__ import annotations

import csv
import html
import http.cookiejar
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict

# Jeden plik na całą giełdę — historia zgłoszeń od 2013 roku.
ADRES_FCA = "https://www.fca.org.uk/publication/data/short-positions-daily-update.xlsx"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Końcówki prawne i szum, które przeszkadzają w dopasowaniu nazw.
_SZUM = re.compile(
    r"\b(plc|p\.l\.c|ltd|limited|public|group|holdings?|company|co|inc|"
    r"corp|corporation|the|ordinary|shares?|sa|nv|ag|se)\b",
    re.I,
)


def rdzen_nazwy(nazwa: str) -> str:
    """Nazwa bez form prawnych i interpunkcji — podstawa dopasowania."""
    t = str(nazwa or "").lower().replace("&", " and ")
    t = _SZUM.sub(" ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _liczba(wartosc):
    if wartosc is None or isinstance(wartosc, str):
        return None
    try:
        f = float(wartosc)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


# ---------------------------------------------------------------------------
# Wspólne dopasowanie nazw (Frankfurt, Paryż, Madryt)
# ---------------------------------------------------------------------------

# Formy prawne i spójniki, które nie niosą tożsamości spółki.
_FORMY = re.compile(
    r"\b(sa|sas|spa|se|ag|nv|plc|ltd|limited|inc|corp|corporation|gmbh|kgaa|"
    r"kg|srl|sl|slu|sau|sapa|scpa|aktiengesellschaft|company|co|the|group|"
    r"grupo|gruppo|groupe|holding|holdings|corporacion|corporation|and|y|"
    r"et|de|des|du|s|a)\b",
    re.I,
)
_ZNAKI = str.maketrans(
    "áàâäéèêëíìîïóòôöúùûüñçłąęśżźćı",
    "aaaaeeeeiiiioooouuuunclaeszzci",
)


def slowa(nazwa: str) -> str:
    """
    Znormalizowana nazwa Z ODSTĘPAMI — inaczej niż `klucz_*`, które je usuwają.

    Odstępy są tu potrzebne, bo dopasowanie działa na CAŁYCH SŁOWACH.
    Bez nich „bayer" pasowałoby do „bayerischemotorenwerke".
    """
    t = str(nazwa or "").lower().translate(_ZNAKI).replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = _FORMY.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def dopasuj_po_nazwach(
    nasze: list[tuple[str, str]], rejestr: dict[str, dict]
) -> dict[str, str]:
    """
    Łączy nasze spółki z wpisami rejestru. Zwraca {ticker: klucz_rejestru}.

    ŁĄCZYMY WYŁĄCZNIE PRZEZ RÓWNOŚĆ znormalizowanych nazw. To wynik trzech
    kolejnych prób, z których każda przypisała komuś cudzą pozycję:

    1. Zwykłe „czy jedna nazwa zawiera drugą" dawało: Bayer → Bayerische
       Motoren Werke (czyli BMW), Infineon → E.ON („eon" siedzi w „infineon"),
       RWE → Friedrich Vorwerk, Continental → InterContinental Hotels.
    2. Wymóg granic słów odsiał tamte cztery, ale wpuścił **Fresenius SE →
       Fresenius Medical Care**. To dwie różne spółki dzielące markę,
       a strukturalnie „fresenius medical care" wygląda dokładnie tak samo
       jak „amadeus it" — nazwa nasza plus dodatkowe słowa. Z samych nazw
       nie da się ich rozróżnić.
    3. Wzajemna jednoznaczność (jeden wpis ↔ jedna nasza spółka) pomaga tam,
       gdzie obie strony są w naszym uniwersum (Société Générale kontra
       Michelin), ale nie ratuje przypadku Fresenius, bo Fresenius Medical
       Care u nas nie występuje.

    CENA: tracimy trafienia, które człowiek uznałby za oczywiste — Amadeus IT
    Group, Cellnex Telecom, Laboratorios Rovi, Meliá Hotels International,
    Michelin pod pełną nazwą. To około jednej trzeciej możliwych dopasowań.
    Świadomie, bo **przypisanie cudzego shortu jest gorsze niż jego brak**:
    puste pole użytkownik przeczyta jako „nie wiadomo", a błędne 1,44% jako
    fakt o swojej spółce.

    Gdyby kiedyś udało się zdobyć ISIN-y dla naszych tickerów, dopasowanie
    stanie się jednoznaczne i cały ten problem znika. `yfinance.isin` do tego
    NIE nadaje się — patrz nagłówek modułu.
    """
    wynik: dict[str, str] = {}
    for ticker, nazwa in nasze:
        k = slowa(nazwa)
        if k and k in rejestr:
            wynik[ticker] = k
    return wynik


def _uzupelnij_z_rejestru(
    rows: list[dict], sufiks: str, rejestr: dict[str, dict], zrodlo: str,
) -> int:
    """Wspólny zapis danych do wierszy — identyczny dla każdego rejestru."""
    nasze = [r for r in rows if str(r.get("Ticker", "")).endswith(sufiks)]
    if not nasze or not rejestr:
        return 0

    pary = dopasuj_po_nazwach(
        [(str(r["Ticker"]), str(r.get("Nazwa", ""))) for r in nasze], rejestr
    )
    uzupelnione = 0
    for r in nasze:
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        klucz_rejestru = pary.get(str(r["Ticker"]))
        if not klucz_rejestru:
            continue
        dane = rejestr[klucz_rejestru]
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short: liczba pozycji"] = dane["liczba"]
        r["Short: największy gracz"] = (
            f"{dane['najwiekszy_kto']} ({dane['najwiekszy_ile']}%)"
        )
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = zrodlo
        uzupelnione += 1
    return uzupelnione


# ---------------------------------------------------------------------------
# USA — z danych, które skan i tak pobiera
# ---------------------------------------------------------------------------

def z_yahoo(info: dict) -> dict:
    """
    Kolumny o krótkiej sprzedaży z `tk.info`. Zero dodatkowych zapytań.

    `shortPercentOfFloat` to udział w WOLNYM OBROCIE, nie w całym kapitale —
    patrz ostrzeżenie w nagłówku modułu.
    """
    puste = {
        "Krótkie pozycje (%)": "BRAK",
        "Short: dni do pokrycia": "BRAK",
        "Short: liczba akcji (mln)": "BRAK",
        "Źródło shortów": "BRAK",
    }
    if not isinstance(info, dict):
        return puste

    procent = _liczba(info.get("shortPercentOfFloat"))
    if procent is None:
        return puste

    akcje = _liczba(info.get("sharesShort"))
    dni = _liczba(info.get("shortRatio"))
    return {
        "Krótkie pozycje (%)": round(procent * 100, 2),
        "Short: dni do pokrycia": round(dni, 1) if dni is not None else "BRAK",
        "Short: liczba akcji (mln)": (
            round(akcje / 1e6, 2) if akcje is not None else "BRAK"
        ),
        "Źródło shortów": "Yahoo — % wolnego obrotu",
    }


# ---------------------------------------------------------------------------
# Londyn — rejestr FCA
# ---------------------------------------------------------------------------

def rejestr_fca(adres: str = ADRES_FCA) -> dict[str, dict]:
    """
    Otwarte pozycje krótkie z rejestru FCA, kluczowane rdzeniem nazwy spółki.

    Plik zawiera CAŁĄ HISTORIĘ zgłoszeń, także zamknięcia (0%). Pozycja jest
    otwarta, gdy NAJNOWSZY wpis danego funduszu na daną spółkę jest większy
    od zera — bez tego kroku policzylibyśmy dawno zamknięte pozycje.

    Nigdy nie rzuca wyjątkiem: przy problemie zwraca pusty słownik, a skan
    idzie dalej.
    """
    try:
        import openpyxl
    except ImportError:
        print("⚠️ Shorty FCA: brak openpyxl — pomijam.")
        return {}

    try:
        req = urllib.request.Request(adres, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as odp:
            dane = odp.read()
        wb = openpyxl.load_workbook(io.BytesIO(dane), read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty FCA: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    najnowsze: dict[tuple, tuple] = {}
    nazwy: dict[str, str] = {}
    try:
        for wiersz in ws.iter_rows(min_row=2, values_only=True):
            if not wiersz or len(wiersz) < 5:
                continue
            posiadacz, emitent, isin, procent, data = wiersz[:5]
            if not isin or procent is None:
                continue
            klucz = (str(posiadacz), str(isin))
            poprzedni = najnowsze.get(klucz)
            if poprzedni is None or str(data) > poprzedni[2]:
                najnowsze[klucz] = (str(posiadacz), _liczba(procent) or 0.0, str(data))
            nazwy[str(isin)] = str(emitent)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty FCA: błąd przy czytaniu arkusza ({type(e).__name__}).")
        return {}

    wg_isin: dict[str, list[tuple]] = defaultdict(list)
    for (_, isin), wpis in najnowsze.items():
        if wpis[1] > 0:
            wg_isin[isin].append(wpis)

    wynik: dict[str, dict] = {}
    for isin, pozycje in wg_isin.items():
        klucz = rdzen_nazwy(nazwy.get(isin, ""))
        if not klucz:
            continue
        najwiekszy = max(pozycje, key=lambda p: p[1])
        istniejacy = wynik.get(klucz)
        suma = round(sum(p[1] for p in pozycje), 2)
        # Ta sama spółka bywa pod kilkoma ISIN-ami; zostawiamy większą sumę.
        if istniejacy and istniejacy["procent"] >= suma:
            continue
        wynik[klucz] = {
            "procent": suma,
            "liczba": len(pozycje),
            "najwiekszy_kto": najwiekszy[0],
            "najwiekszy_ile": round(najwiekszy[1], 2),
            "data": max(p[2] for p in pozycje)[:10],
        }

    print(f"📉 Shorty FCA: {len(wynik)} spółek z otwartą pozycją krótką.")
    return wynik


def uzupelnij_fca(rows: list[dict]) -> int:
    """
    Dokłada dane o shortach spółkom z Londynu. Zwraca liczbę uzupełnionych.

    Dotyka WYŁĄCZNIE tickerów `.L` — dla reszty rynków nie mamy rejestru,
    a wpisanie im czegokolwiek sugerowałoby, że sprawdziliśmy.
    """
    londyn = [r for r in rows if str(r.get("Ticker", "")).endswith(".L")]
    if not londyn:
        return 0

    rejestr = rejestr_fca()
    if not rejestr:
        return 0

    uzupelnione = 0
    for r in londyn:
        # Yahoo nie ma danych dla Londynu, ale gdyby kiedyś miał — nie
        # nadpisujemy tego, co już jest.
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        dane = rejestr.get(rdzen_nazwy(r.get("Nazwa", "")))
        if not dane:
            continue
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short: liczba pozycji"] = dane["liczba"]
        r["Short: największy gracz"] = (
            f"{dane['najwiekszy_kto']} ({dane['najwiekszy_ile']}%)"
        )
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = "FCA — % wyemitowanego kapitału"
        uzupelnione += 1

    print(f"📉 Shorty: uzupełniono {uzupelnione} spółek z Londynu "
          f"(sprawdzono {len(londyn)}).")
    return uzupelnione


# ---------------------------------------------------------------------------
# Warszawa — rejestr KNF
# ---------------------------------------------------------------------------

# Adres i kształt zapytania odtworzone z tego, co wysyła sama strona rejestru.
# Siatka jest w bibliotece w2ui: `cmd` musi być dokładnie "get", a `method`
# dokładnie "Default" — przy innych wartościach serwer odpowiada pustką
# albo błędem 503.
ADRES_KNF = "https://rss.knf.gov.pl/rss_pub/JSON"
ZAPYTANIE_KNF = {
    "cmd": "get",
    "language": "pl",
    "search": [],
    "limit": 10000,
    "offset": 0,
    "method": "Default",
    "sort": [{"field": "HOLDER_FULL_NAME", "direction": "asc"}],
    "searchLogic": "AND",
    "searchValue": "",
}

# Formy prawne do usunięcia. UWAGA: NIE ma tu "grupa" — KNF pisze nazwy
# łącznie ("GRUPAAZOTY"), a my z odstępem ("Grupa Azoty"). Usunięcie słowa
# z jednej strony, a nie z drugiej, rozjeżdżałoby dopasowanie.
_SZUM_PL = re.compile(r"\b(sa|s a|spolka|spółka|akcyjna)\b", re.I)

_OGONKI = str.maketrans("ąćęłńóśźż", "acelnoszz")


def klucz_gpw(nazwa: str) -> str:
    """Nazwa bez odstępów, ogonków i form prawnych — do dopasowania z KNF."""
    t = str(nazwa or "").lower().translate(_OGONKI)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = _SZUM_PL.sub(" ", t)
    return re.sub(r"\s+", "", t)


def _procent_z_tekstu(wartosc) -> float | None:
    """
    Procent podany JAKO TEKST — tak zwraca go rejestr KNF ("0.52").

    Zwykłe `_liczba()` celowo odrzuca stringi, bo w migawce tekst w polu
    liczbowym znaczy "BRAK". Tutaj jest odwrotnie: tekst to normalna postać
    danych, więc parsujemy go wprost, z przecinkiem dziesiętnym włącznie.
    """
    if wartosc is None:
        return None
    if isinstance(wartosc, (int, float)):
        return _liczba(wartosc)
    try:
        return float(str(wartosc).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _wspolny_prefiks(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def rejestr_knf(adres: str = ADRES_KNF) -> dict[str, dict]:
    """
    Aktualne pozycje krótkie z rejestru KNF, kluczowane skrótem nazwy emitenta.

    Rejestr zawiera WYŁĄCZNIE pozycje otwarte, więc nie trzeba — inaczej niż
    przy FCA — odsiewać zamknięć. Nigdy nie rzuca wyjątkiem.
    """
    try:
        dane = urllib.parse.urlencode(
            {"request": json.dumps(ZAPYTANIE_KNF)}
        ).encode()
        req = urllib.request.Request(
            adres,
            data=dane,
            headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://rss.knf.gov.pl/rss_pub/",
            },
        )
        with urllib.request.urlopen(req, timeout=40) as odp:
            odpowiedz = json.loads(odp.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty KNF: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    rekordy = odpowiedz.get("records") or []
    if not rekordy:
        print("ℹ️ Shorty KNF: rejestr pusty albo w innym formacie — pomijam.")
        return {}

    wg_emitenta: dict[str, list[tuple]] = defaultdict(list)
    for r in rekordy:
        emitent = str(r.get("ISSUER_NAME") or "")
        procent = _procent_z_tekstu(r.get("NET_SHORT_POSITION_O"))
        if not emitent or procent is None:
            continue
        # Nazwy funduszy przychodzą z encjami HTML ("QUBE RESEARCH &amp; ...").
        posiadacz = html.unescape(str(r.get("HOLDER_FULL_NAME") or "")).strip()
        wg_emitenta[emitent].append(
            (posiadacz, procent, str(r.get("POSITION_DATE") or "")[:10])
        )

    wynik: dict[str, dict] = {}
    for emitent, pozycje in wg_emitenta.items():
        k = klucz_gpw(emitent)
        if not k:
            continue
        najwiekszy = max(pozycje, key=lambda p: p[1])
        wynik[k] = {
            "procent": round(sum(p[1] for p in pozycje), 2),
            "liczba": len(pozycje),
            "najwiekszy_kto": najwiekszy[0],
            "najwiekszy_ile": round(najwiekszy[1], 2),
            "data": max(p[2] for p in pozycje),
        }

    print(f"📉 Shorty KNF: {len(wynik)} spółek z otwartą pozycją krótką.")
    return wynik


def dopasuj_gpw(klucz_naszej: str, rejestr: dict[str, dict]) -> dict | None:
    """
    Szuka emitenta z rejestru KNF dla naszej spółki.

    KNF używa skrótów giełdowych ("DINOPL", "KETY"), a my nazw z Yahoo
    ("Dino Polska", "Grupa Kęty"), więc sama równość nie wystarcza. Trzy
    coraz luźniejsze próby, ale KAŻDA akceptowana tylko wtedy, gdy daje
    JEDNO trafienie — przy dwóch kandydatach wolimy nie pokazać nic niż
    przypisać cudzą pozycję. (Realna kolizja w uniwersum: Asseco BS
    i Asseco POL dzielą sześć pierwszych znaków.)
    """
    if not klucz_naszej:
        return None

    if klucz_naszej in rejestr:
        return rejestr[klucz_naszej]

    zawierajace = [
        v for k, v in rejestr.items()
        if len(k) >= 4 and (k in klucz_naszej or klucz_naszej in k)
    ]
    if len(zawierajace) == 1:
        return zawierajace[0]

    # Prefiks musi stanowić WIĘKSZOŚĆ krótszej z nazw, nie tylko mieć pięć
    # znaków. Sam próg długości okazał się za słaby: "GRUPAAZOTY"
    # i "grupapracuj" dzielą pięć pierwszych liter, przez co Grupa Pracuj
    # dostała pozycję krótką Grupy Azoty. Przy udziale 70% ta para odpada
    # (5 z 10 znaków), a "DINOPL" wobec "dinopolska" przechodzi (5 z 6).
    oceny = []
    for k, v in rejestr.items():
        wspolne = _wspolny_prefiks(k, klucz_naszej)
        krotsza = min(len(k), len(klucz_naszej))
        if wspolne >= 5 and krotsza and wspolne / krotsza >= 0.7:
            oceny.append((wspolne, v))
    if not oceny:
        return None
    naj = max(p for p, _ in oceny)
    najlepsze = [v for p, v in oceny if p == naj]
    return najlepsze[0] if len(najlepsze) == 1 else None


def uzupelnij_knf(rows: list[dict]) -> int:
    """Dokłada dane o shortach spółkom z GPW. Zwraca liczbę uzupełnionych."""
    gpw = [r for r in rows if str(r.get("Ticker", "")).endswith(".WA")]
    if not gpw:
        return 0

    rejestr = rejestr_knf()
    if not rejestr:
        return 0

    uzupelnione = 0
    for r in gpw:
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        dane = dopasuj_gpw(klucz_gpw(r.get("Nazwa", "")), rejestr)
        if not dane:
            continue
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short: liczba pozycji"] = dane["liczba"]
        r["Short: największy gracz"] = (
            f"{dane['najwiekszy_kto']} ({dane['najwiekszy_ile']}%)"
        )
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = "KNF — % wyemitowanego kapitału"
        uzupelnione += 1

    print(f"📉 Shorty: uzupełniono {uzupelnione} spółek z GPW "
          f"(sprawdzono {len(gpw)}).")
    return uzupelnione


# ---------------------------------------------------------------------------
# Frankfurt — Bundesanzeiger
# ---------------------------------------------------------------------------

# Strona publikacji pozycji krótkich. Adres pliku CSV zawiera identyfikator
# stanu strony (Wicket), więc nie da się go wpisać na sztywno — trzeba wejść
# na stronę, wziąć ciasteczko sesji i wyłuskać link z HTML-a.
ADRES_BUNDESANZEIGER = "https://www.bundesanzeiger.de/pub/de/nlp"

# UWAGA CO DO robots.txt. Plik zawiera "Disallow: /nlp" z komentarzem, że
# sekcja NLP nie ma być indeksowana. Nasza ścieżka to /pub/de/nlp, więc
# literalnie ta reguła jej nie obejmuje (dopasowanie w robots.txt idzie od
# początku ścieżki), ale INTENCJA operatora jest czytelna. Robimy JEDNO
# pobranie na dobę, tego samego pliku, który serwis sam udostępnia przyciskiem
# „Als CSV herunterladen", na własny użytek i bez publikowania dalej.
# Gdyby to miało być problemem — wystarczy usunąć wywołanie `uzupelnij_de`
# ze skanu, reszta modułu działa bez zmian.

_SZUM_DE = re.compile(
    r"\b(aktiengesellschaft|ag|se|kgaa|kg|gmbh|co|company|holding|holdings|"
    r"group|gruppe|plc|ltd|limited|nv|sa|inc|the)\b",
    re.I,
)
_UMLAUTY = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))


def rejestr_bundesanzeiger(adres: str = ADRES_BUNDESANZEIGER) -> dict[str, dict]:
    """
    Aktualne pozycje krótkie z Bundesanzeigera, kluczowane skrótem nazwy.

    Lista zawiera wyłącznie pozycje otwarte (sprawdzone: wszystkie 476 wpisów
    ma co najmniej 0,5%, czyli próg jawności), więc nie trzeba odsiewać
    zamknięć jak przy FCA. Nigdy nie rzuca wyjątkiem.
    """
    try:
        jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        req = urllib.request.Request(adres, headers={"User-Agent": UA})
        with op.open(req, timeout=60) as odp:
            html_strony = odp.read().decode("utf-8", "replace")

        m = re.search(r'href="([^"]*csv[^"]*)"', html_strony)
        if not m:
            print("⚠️ Shorty Bundesanzeiger: nie znalazłem linku do CSV — "
                  "strona pewnie się zmieniła.")
            return {}

        req = urllib.request.Request(
            m.group(1), headers={"User-Agent": UA, "Referer": adres}
        )
        with op.open(req, timeout=90) as odp:
            tekst = odp.read().decode("utf-8-sig", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty Bundesanzeiger: nie udało się pobrać "
              f"({type(e).__name__}).")
        return {}

    wg_emitenta: dict[str, list[tuple]] = defaultdict(list)
    try:
        for w in csv.DictReader(io.StringIO(tekst)):
            emitent = (w.get("Emittent") or "").strip()
            procent = _procent_z_tekstu(w.get("Position"))
            if not emitent or procent is None:
                continue
            wg_emitenta[emitent].append(
                ((w.get("Positionsinhaber") or "").strip(),
                 procent,
                 (w.get("Datum") or "")[:10])
            )
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty Bundesanzeiger: błąd przy czytaniu CSV "
              f"({type(e).__name__}).")
        return {}

    wynik: dict[str, dict] = {}
    for emitent, pozycje in wg_emitenta.items():
        k = slowa(emitent)
        if not k:
            continue
        najwiekszy = max(pozycje, key=lambda x: x[1])
        wynik[k] = {
            "procent": round(sum(x[1] for x in pozycje), 2),
            "liczba": len(pozycje),
            "najwiekszy_kto": najwiekszy[0],
            "najwiekszy_ile": round(najwiekszy[1], 2),
            "data": max(x[2] for x in pozycje),
        }

    print(f"📉 Shorty Bundesanzeiger: {len(wynik)} emitentów z otwartą "
          f"pozycją krótką.")
    return wynik


def uzupelnij_de(rows: list[dict]) -> int:
    """
    Dokłada dane o shortach spółkom z Frankfurtu.

    Dopasowanie robi wspólne `dopasuj_po_nazwach()`. Niemieckie nazwy to
    właśnie ten materiał, na którym powstała reguła całych słów — zwykłe
    „czy jedna zawiera drugą" dawało tu same pomyłki:

        Bayer       ~ Bayerische Motoren Werke   (czyli BMW)
        Infineon    ~ E.ON                       ("eon" siedzi w "infineon")
        RWE         ~ Friedrich Vorwerk          ("rwe" w "vorwerk")
        Continental ~ InterContinental Hotels
        Fresenius   ~ Fresenius Medical Care     (inna spółka!)

    Wszystkie cztery odpadają, gdy wymagamy granic słów. **Nie luzuj tego
    dopasowania** — przypisanie cudzego shortu jest gorsze niż jego brak.
    """
    niemieckie = [r for r in rows if str(r.get("Ticker", "")).endswith(".DE")]
    if not niemieckie:
        return 0
    ile = _uzupelnij_z_rejestru(
        rows, ".DE", rejestr_bundesanzeiger(),
        "Bundesanzeiger — % wyemitowanego kapitału",
    )
    print(f"📉 Shorty: uzupełniono {ile} spółek z Frankfurtu "
          f"(sprawdzono {len(niemieckie)}).")
    return ile


# ---------------------------------------------------------------------------
# Paryż — AMF przez data.gouv.fr
# ---------------------------------------------------------------------------

# Adres PLIKU zmienia się codziennie (zawiera znacznik czasu), więc pytamy
# o niego API portalu. Ono jest stałe.
API_AMF = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "historique-des-positions-courtes-nettes-sur-actions-rendues-"
    "publiques-depuis-le-1er-novembre-2012/"
)

_SZUM_FR = re.compile(
    r"\b(sa|sas|sca|se|scr|societe|group|groupe|holding|holdings|company|co|"
    r"plc|ltd|limited|nv|ag|inc|the|et|and)\b",
    re.I,
)
_AKCENTY = str.maketrans("àâäçéèêëîïôöùûüÿœæ", "aaaceeeeiioouuuyoa")


def rejestr_amf(api: str = API_AMF) -> dict[str, dict]:
    """
    Otwarte pozycje krótkie z rejestru AMF, kluczowane skrótem nazwy emitenta.

    KTÓRA POZYCJA JEST OTWARTA — to tu najłatwiej się pomylić. Plik ma pełną
    historię od 2012 (40 tys. wierszy), a każdy wiersz to jedno ZGŁOSZENIE,
    nie jedna pozycja: ten sam fundusz zgłasza tę samą pozycję wielokrotnie,
    gdy ją zmienia. Sumowanie wszystkiego bez daty końca publikacji dawało
    Valeo 720% kapitału na krótko, czyli wynik fizycznie niemożliwy.

    Poprawnie: dla każdej pary (fundusz, ISIN) bierzemy NAJNOWSZE zgłoszenie
    i uznajemy pozycję za otwartą tylko wtedy, gdy nie ma ono daty końca
    publikacji. Po tej poprawce najwyższa suma to 13,3% (Ubisoft) — wartość,
    która ma sens.
    """
    try:
        req = urllib.request.Request(api, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as odp:
            meta = json.loads(odp.read().decode("utf-8", "replace"))
        url = next(
            r["url"] for r in meta.get("resources", [])
            if str(r.get("format", "")).lower() == "csv"
        )
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as odp:
            tekst = odp.read().decode("utf-8-sig", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty AMF: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    POSIADACZ = "Detenteur de la position courte nette"
    EMITENT = "Emetteur / issuer"
    POCZATEK = "Date de debut position"
    KONIEC = "Date de fin de publication position"

    najnowsze: dict[tuple, tuple] = {}
    try:
        for w in csv.DictReader(io.StringIO(tekst), delimiter=";"):
            isin = (w.get("code ISIN") or "").strip()
            posiadacz = (w.get(POSIADACZ) or "").strip()
            if not isin or not posiadacz:
                continue
            data = (w.get(POCZATEK) or "")[:10]
            klucz = (posiadacz, isin)
            if klucz not in najnowsze or data > najnowsze[klucz][0]:
                najnowsze[klucz] = (data, w)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty AMF: błąd przy czytaniu CSV ({type(e).__name__}).")
        return {}

    wg_emitenta: dict[str, list[tuple]] = defaultdict(list)
    for data, w in najnowsze.values():
        if (w.get(KONIEC) or "").strip():
            continue  # publikacja zakończona — pozycja zamknięta
        procent = _procent_z_tekstu(w.get("Ratio"))
        emitent = (w.get(EMITENT) or "").strip()
        if procent is None or not emitent:
            continue
        wg_emitenta[emitent].append(
            ((w.get(POSIADACZ) or "").strip(), procent, data)
        )

    wynik: dict[str, dict] = {}
    for emitent, pozycje in wg_emitenta.items():
        k = slowa(emitent)
        if not k:
            continue
        najwiekszy = max(pozycje, key=lambda x: x[1])
        wynik[k] = {
            "procent": round(sum(x[1] for x in pozycje), 2),
            "liczba": len(pozycje),
            "najwiekszy_kto": najwiekszy[0],
            "najwiekszy_ile": round(najwiekszy[1], 2),
            "data": max(x[2] for x in pozycje),
        }

    print(f"📉 Shorty AMF: {len(wynik)} emitentów z otwartą pozycją krótką.")
    return wynik


def uzupelnij_fr(rows: list[dict]) -> int:
    """
    Dokłada dane o shortach spółkom z Paryża.

    To francuskie dane wymusiły regułę wzajemnej jednoznaczności: bez niej
    **Société Générale** dostawało pozycję krótką **Michelina**, bo pełna
    nazwa Michelina to „Compagnie Générale des Établissements Michelin"
    i słowo „générale" pasuje do obu. Teraz wpis trafia do Michelina,
    a Société Générale nie dostaje nic — czyli poprawnie.
    """
    francuskie = [r for r in rows if str(r.get("Ticker", "")).endswith(".PA")]
    if not francuskie:
        return 0
    ile = _uzupelnij_z_rejestru(
        rows, ".PA", rejestr_amf(), "AMF — % wyemitowanego kapitału"
    )
    print(f"📉 Shorty: uzupełniono {ile} spółek z Paryża "
          f"(sprawdzono {len(francuskie)}).")
    return ile


# ---------------------------------------------------------------------------
# Madryt — CNMV
# ---------------------------------------------------------------------------

# Stały adres, ale plik jest w STARYM formacie XLS (OLE2), którego openpyxl
# nie czyta — stąd zależność `xlrd`. To jedyne miejsce w projekcie, które
# jej potrzebuje.
ADRES_CNMV = "https://www.cnmv.es/DocPortal/Posiciones-Cortas/NetShortPositions.xls"


def rejestr_cnmv(adres: str = ADRES_CNMV) -> dict[str, dict]:
    """
    Aktualne pozycje krótkie z rejestru CNMV, kluczowane znormalizowaną nazwą.

    Plik ma osobny arkusz „Última_-_Current" wyłącznie z pozycjami otwartymi,
    więc — tak jak przy CONSOB — nie trzeba odsiewać historii. Arkusze
    „Serie" i „Anteriores" celowo pomijamy.
    """
    try:
        import xlrd
    except ImportError:
        print("⚠️ Shorty CNMV: brak biblioteki xlrd — pomijam.")
        return {}

    try:
        req = urllib.request.Request(adres, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as odp:
            dane = odp.read()
        wb = xlrd.open_workbook(file_contents=dane)
        nazwa_arkusza = next(
            (n for n in wb.sheet_names() if "Current" in n or "ltima" in n), None
        )
        if not nazwa_arkusza:
            print("⚠️ Shorty CNMV: nie ma arkusza z aktualnymi pozycjami.")
            return {}
        ws = wb.sheet_by_name(nazwa_arkusza)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty CNMV: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    try:
        # Nagłówek nie stoi w pierwszym wierszu — szukamy go po kolumnie ISIN.
        naglowek = next(
            i for i in range(ws.nrows)
            if any("ISIN" in str(ws.cell_value(i, j)) for j in range(ws.ncols))
        )
    except StopIteration:
        print("⚠️ Shorty CNMV: nie znalazłem nagłówka — plik pewnie się zmienił.")
        return {}

    wg_emitenta: dict[str, list[tuple]] = defaultdict(list)
    for i in range(naglowek + 1, ws.nrows):
        try:
            emitent = str(ws.cell_value(i, 2)).strip()
            posiadacz = str(ws.cell_value(i, 3)).strip()
            data = str(ws.cell_value(i, 4)).strip()[:10]
            procent = _procent_z_tekstu(ws.cell_value(i, 5))
        except IndexError:
            continue
        if not emitent or procent is None:
            continue
        wg_emitenta[emitent].append((posiadacz, procent, data))

    wynik: dict[str, dict] = {}
    for emitent, pozycje in wg_emitenta.items():
        k = slowa(emitent)
        if not k:
            continue
        najwiekszy = max(pozycje, key=lambda x: x[1])
        wynik[k] = {
            "procent": round(sum(x[1] for x in pozycje), 2),
            "liczba": len(pozycje),
            "najwiekszy_kto": najwiekszy[0],
            "najwiekszy_ile": round(najwiekszy[1], 2),
            "data": max(x[2] for x in pozycje),
        }

    print(f"📉 Shorty CNMV: {len(wynik)} emitentów z otwartą pozycją krótką.")
    return wynik


def uzupelnij_es(rows: list[dict]) -> int:
    """Dokłada dane o shortach spółkom z Madrytu."""
    hiszpanskie = [r for r in rows if str(r.get("Ticker", "")).endswith(".MC")]
    if not hiszpanskie:
        return 0
    ile = _uzupelnij_z_rejestru(
        rows, ".MC", rejestr_cnmv(), "CNMV — % wyemitowanego kapitału"
    )
    print(f"📉 Shorty: uzupełniono {ile} spółek z Madrytu "
          f"(sprawdzono {len(hiszpanskie)}).")
    return ile


# ---------------------------------------------------------------------------
# Sztokholm — Finansinspektionen
# ---------------------------------------------------------------------------

ADRES_FI = "https://www.fi.se/en/our-registers/net-short-positions/"
ADRES_FI_EMITENT = ADRES_FI + "emittent?id={lei}"

# Ile podstron emitentów wolno dociągnąć w jednym skanie. Zapora na wypadek,
# gdyby uniwersum urosło — sam rejestr ma ponad 300 pozycji.
LIMIT_FI_SZCZEGOLOW = 40

# Szwedzkie i nordyckie formy prawne. Osobno od wspólnej listy, bo dotyczą
# tylko tego rynku i nie ma powodu ruszać pozostałych.
_FORMY_SE = re.compile(r"\b(ab|publ|aktiebolaget|aktiebolag|asa|oyj|abp)\b", re.I)

# Klasa akcji na końcu NASZEJ nazwy („Atlas Copco B"). Rejestr podaje
# emitenta, nie serię, więc obie klasy mają tę samą pozycję krótką — i tak
# ma być, bo short dotyczy kapitału spółki, nie konkretnej serii.
_KLASA_AKCJI = re.compile(r"\s+[abc]$", re.I)

# Litery nordyckie NIE są ogonkami — „ø" to osobna litera, a nie „o" z kreską,
# więc rozkład Unicode ich nie tknie i wspólna tablica `_ZNAKI` też nie.
# Bez tego `slowa()` po prostu je WYRZUCA i „Vår Energi" robi się „v r energi",
# czyli jedno słowo rozpada się na dwa. Dopasowanie i tak działa, bo obie
# strony psują się tak samo — ale dwa różne słowa mogą wtedy zejść się do
# jednego klucza. Zmierzone: transliteracja nie zmienia liczby trafień
# (Oslo 16/21, Sztokholm 21/28) ani liczby wpisów w rejestrach.
_NORDYCKIE = str.maketrans({
    "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "å": "a", "Å": "a",
    "ð": "d", "Ð": "d", "đ": "d", "þ": "th", "Þ": "th",
})


def slowa_se(nazwa: str) -> str:
    """
    Normalizacja dla rynków nordyckich: Sztokholm i Oslo.

    Osobna od wspólnej `slowa()`, żeby nordyckie formy prawne i klasy akcji
    nie ruszały pozostałych rynków.
    """
    t = str(nazwa or "").translate(_NORDYCKIE).strip()
    t = _KLASA_AKCJI.sub("", t)
    return slowa(_FORMY_SE.sub(" ", t))


def _komorki(wiersz_html: str) -> list[str]:
    return [
        html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", wiersz_html, re.S)
    ]


def rejestr_fi(adres: str = ADRES_FI) -> dict[str, dict]:
    """
    Sumy pozycji krótkich na emitenta, prosto z tabeli na stronie FI.

    Jedyny rejestr, który nie udostępnia pliku — dane są w HTML-u. Zbiorcza
    tabela ma nazwę emitenta, kod LEI, datę i sumę procentową; szczegóły
    dociąga osobno `_szczegoly_fi()`.
    """
    try:
        req = urllib.request.Request(adres, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as odp:
            strona = odp.read().decode("utf-8", "replace")
        tabela = re.search(r"<table[^>]*>(.*?)</table>", strona, re.S)
        if not tabela:
            print("⚠️ Shorty FI: nie znalazłem tabeli — strona się zmieniła.")
            return {}
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty FI: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    wynik: dict[str, dict] = {}
    for wiersz in re.findall(r"<tr[^>]*>(.*?)</tr>", tabela.group(1), re.S):
        kom = _komorki(wiersz)
        if len(kom) < 4:
            continue
        procent = _procent_z_tekstu(kom[3])
        if procent is None or not kom[0]:
            continue
        k = slowa_se(kom[0])
        if not k:
            continue
        wynik[k] = {
            "procent": round(procent, 2),
            "liczba": None,          # uzupełni `_szczegoly_fi`, jeśli się uda
            "najwiekszy_kto": "",
            "najwiekszy_ile": None,
            "data": kom[2][:10],
            "lei": kom[1],
        }

    print(f"📉 Shorty FI: {len(wynik)} emitentów z otwartą pozycją krótką.")
    return wynik


def _szczegoly_fi(lei: str) -> tuple[int, str, float] | None:
    """Liczba zgłoszeń i największy gracz dla jednego emitenta. None przy błędzie."""
    if not lei:
        return None
    try:
        req = urllib.request.Request(
            ADRES_FI_EMITENT.format(lei=urllib.parse.quote(lei)),
            headers={"User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=45) as odp:
            strona = odp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None

    pozycje: list[tuple[str, float]] = []
    for tabela in re.findall(r"<table[^>]*>(.*?)</table>", strona, re.S):
        if "Position holder" not in tabela:
            continue
        for wiersz in re.findall(r"<tr[^>]*>(.*?)</tr>", tabela, re.S):
            kom = _komorki(wiersz)
            if len(kom) < 3:
                continue
            procent = _procent_z_tekstu(kom[2])
            if procent is None or not kom[0]:
                continue
            pozycje.append((kom[0], procent))
    if not pozycje:
        return None
    najwiekszy = max(pozycje, key=lambda x: x[1])
    return len(pozycje), najwiekszy[0], round(najwiekszy[1], 2)


def uzupelnij_se(rows: list[dict]) -> int:
    """
    Dokłada dane o shortach spółkom ze Sztokholmu.

    Dopasowanie idzie przez `slowa_se`, czyli tę samą regułę równości co
    wszędzie, tylko z nordyckimi formami prawnymi i obciętą klasą akcji.
    Dwie serie tej samej spółki (Atlas Copco A i B) dostają tę samą wartość
    i to jest poprawne — pozycja krótka dotyczy kapitału emitenta.

    CZĘŚĆ SPÓŁEK NIE MA SZCZEGÓŁÓW i to też nie jest błąd. Suma na stronie
    zbiorczej obejmuje również pozycje PONIŻEJ progu publikacji pojedynczych
    zgłoszeń, więc spółka może mieć realne 0,3% łącznie, a podstrona
    emitenta pozostaje pusta, bo żaden fundusz nie przekroczył progu.
    Zmierzone: 13 z 20 emitentów ma rozpisane pozycje, a te bez nich to
    właśnie największe spółki z najniższymi sumami (ABB 0,11%, Sandvik
    0,29%, AstraZeneca 0,30%). Wtedy pokazujemy samą sumę i datę.
    """
    szwedzkie = [r for r in rows if str(r.get("Ticker", "")).endswith(".ST")]
    if not szwedzkie:
        return 0

    rejestr = rejestr_fi()
    if not rejestr:
        return 0

    # Najpierw dopasowanie — dopiero potem dociągamy szczegóły, i tylko dla
    # trafionych. Odwrotna kolejność znaczyłaby 300 zapytań zamiast kilkunastu.
    pary: dict[str, str] = {}
    for r in szwedzkie:
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        k = slowa_se(r.get("Nazwa", ""))
        if k and k in rejestr:
            pary[str(r["Ticker"])] = k

    szczegoly: dict[str, tuple] = {}
    for k in list(dict.fromkeys(pary.values()))[:LIMIT_FI_SZCZEGOLOW]:
        dane = _szczegoly_fi(rejestr[k].get("lei", ""))
        if dane:
            szczegoly[k] = dane
        time.sleep(0.3)

    uzupelnione = 0
    for r in szwedzkie:
        k = pary.get(str(r["Ticker"]))
        if not k:
            continue
        dane = rejestr[k]
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = "FI — % wyemitowanego kapitału"
        if k in szczegoly:
            liczba, kto, ile = szczegoly[k]
            r["Short: liczba pozycji"] = liczba
            r["Short: największy gracz"] = f"{kto} ({ile}%)"
        uzupelnione += 1

    print(f"📉 Shorty: uzupełniono {uzupelnione} spółek ze Sztokholmu "
          f"(sprawdzono {len(szwedzkie)}, szczegóły dla {len(szczegoly)}).")
    return uzupelnione


# ---------------------------------------------------------------------------
# Oslo — Finanstilsynet (Short Sale Register)
# ---------------------------------------------------------------------------

# Strona rejestru rysuje tabelę z tego samego adresu. Pusty `query` znaczy
# „wszyscy emitenci" — jedno zapytanie na całą giełdę.
API_SSR = "https://ssr.finanstilsynet.no/api/issuers/homepageissuers?query="


def rejestr_ssr(api: str = API_SSR) -> dict[str, dict]:
    """
    Otwarte pozycje krótkie z norweskiego rejestru. Klucz = `slowa_se(nazwa)`.

    NAJCZYSTSZE ŹRÓDŁO PO AMF: zwykły JSON, bez sesji, bez pliku, bez
    ciasteczek. Sprawdzone, że odpowiada 200 także na żądanie BEZ nagłówka
    `User-Agent` — nie ma tu żadnego odsiewania klientów, więc niczego nie
    obchodzimy (inaczej niż CONSOB, patrz nagłówek modułu).

    DWIE RZECZY, KTÓRYCH TU CELOWO NIE ROBIMY:

    1. **Nie pobieramy podstron `/Home/Details/<ISIN>`** z rozpisaniem, kto
       i ile trzyma. Dokładnie ten adres jest w `robots.txt` pod `Disallow`.
       Skutkiem jest brak kolumn „liczba pozycji" i „największy gracz" dla
       Oslo — świadoma cena za trzymanie się reguł serwisu, nie brak danych.
    2. **Nie bierzemy ISIN-a do dopasowania.** Rejestr go podaje, ale my nie
       mamy ISIN-ów dla naszych tickerów (`yfinance.isin` odrzucone — patrz
       nagłówek modułu), więc nie ma czego z czym łączyć. Gdyby kiedyś się
       pojawiły, Oslo jest rynkiem, na którym zadziała to od ręki.

    ZERO ZNACZY BRAK POZYCJI, NIE BRAK DANYCH. Rejestr wymienia emitentów
    z HISTORIĄ zgłoszeń i pokazuje ich AKTUALNĄ sumę, więc pozycje pozamykane
    zostają w wykazie z wartością 0,00%. Zmierzone: 146 wpisów ze 183 ma
    dokładnie zero. Traktujemy je jak każdy inny brak — spółka zostaje bez
    danych, tak samo jak na pozostałych rynkach. Zapisanie „0,0%" sugerowałoby
    pomiar tam, gdzie po prostu nikt nie przekroczył progu jawności.

    KOLEJNOŚĆ MA ZNACZENIE: zera odsiewamy PRZED zbudowaniem klucza. 22 nazwy
    ze 183 występują w rejestrze dwa razy — ten sam emitent pod starym i nowym
    ISIN-em (Tomra, Borr Drilling, Nordic Mining...), bo zmiana ISIN-u zakłada
    nowy wpis zamiast zaktualizować stary. Stary wpis ZAWSZE ma 0,00% i datę
    sprzed lat. Przy odwróconej kolejności stary nadpisywałby nowy i Tomra
    wyszłaby jako spółka bez shortów zamiast 2,88%. Sprawdzone: żadna nazwa
    nie ma dwóch wpisów z otwartą pozycją, więc odsianie zer rozstrzyga
    wszystkie duplikaty jednoznacznie.
    """
    try:
        with urllib.request.urlopen(api, timeout=60) as odp:
            dane = json.loads(odp.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Shorty SSR: nie udało się pobrać rejestru ({type(e).__name__}).")
        return {}

    if not isinstance(dane, list):
        print("⚠️ Shorty SSR: odpowiedź nie jest listą — API się zmieniło.")
        return {}

    wynik: dict[str, dict] = {}
    for wpis in dane:
        if not isinstance(wpis, dict):
            continue
        procent = _liczba(wpis.get("shortPercent"))
        if procent is None or procent <= 0 or procent > 100:
            continue
        k = slowa_se(wpis.get("name", ""))
        if not k:
            continue
        wynik[k] = {
            "procent": round(procent, 2),
            "liczba": None,           # podstrony emitentów są pod Disallow
            "najwiekszy_kto": "",
            "najwiekszy_ile": None,
            "data": str(wpis.get("lastChange") or "")[:10],
        }

    print(f"📉 Shorty SSR: {len(wynik)} emitentów z otwartą pozycją krótką.")
    return wynik


def uzupelnij_no(rows: list[dict]) -> int:
    """
    Dokłada dane o shortach spółkom z Oslo.

    Dopasowanie przez `slowa_se`, czyli tę samą regułę równości co wszędzie.
    Równość odsiewa tu dwie prawdziwe pułapki: **Aker** (w rejestrze są Aker
    Solutions, Aker BP i Aker Horizons — trzy inne spółki) oraz **Kongsberg
    Gruppen** (w rejestrze Kongsberg Maritime i Kongsberg Automotive). Obie
    zostają bez danych i tak ma być.
    """
    norweskie = [r for r in rows if str(r.get("Ticker", "")).endswith(".OL")]
    if not norweskie:
        return 0

    rejestr = rejestr_ssr()
    if not rejestr:
        return 0

    uzupelnione = 0
    for r in norweskie:
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        dane = rejestr.get(slowa_se(r.get("Nazwa", "")))
        if not dane:
            continue
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = "SSR — % wyemitowanego kapitału"
        uzupelnione += 1

    print(f"📉 Shorty: uzupełniono {uzupelnione} spółek z Oslo "
          f"(sprawdzono {len(norweskie)}).")
    return uzupelnione


def domknij_kolumny(rows: list[dict]) -> None:
    """
    Dopisuje puste wartości tam, gdzie kolumn nie ma.

    Bez tego wiersze różniłyby się zestawem kluczy, a kolumna pojawiałaby się
    i znikała między instrumentami.
    """
    for r in rows:
        r.setdefault("Krótkie pozycje (%)", "BRAK")
        r.setdefault("Short: dni do pokrycia", "BRAK")
        r.setdefault("Short: liczba akcji (mln)", "BRAK")
        r.setdefault("Short: liczba pozycji", "BRAK")
        r.setdefault("Short: największy gracz", "BRAK")
        r.setdefault("Short z dnia", "BRAK")
        r.setdefault("Źródło shortów", "BRAK")
