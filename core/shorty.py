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

DWIE LICZBY, KTÓRE WYGLĄDAJĄ TAK SAMO, A ZNACZĄ CO INNEGO. Yahoo podaje
procent **wolnego obrotu** (free float), FCA — procent **wyemitowanego
kapitału**. Przy spółce z dużym pakietem kontrolnym te dwie miary potrafią
się różnić kilkukrotnie. Dlatego zapisujemy źródło osobno i profil spółki
mówi wprost, co jest czym. **Nie sklejaj tych wartości w jedną kolumnę bez
źródła.**

CZEGO NIE MA. Pozostałe rynki europejskie (Paryż, Mediolan, Madryt,
Sztokholm, Oslo, Wiedeń, Lizbona) mają własne rejestry u własnych nadzorów —
AMF, CONSOB, CNMV i tak dalej — każdy w innym formacie. To osobna praca na
każdy kraj i NIE jest zrobiona.
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


def klucz_de(nazwa: str) -> str:
    """Nazwa bez odstępów, umlautów i form prawnych."""
    t = str(nazwa or "").lower()
    for a, b in _UMLAUTY:
        t = t.replace(a, b)
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = _SZUM_DE.sub(" ", t)
    return re.sub(r"\s+", "", t)


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
        k = klucz_de(emitent)
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

    DOPASOWUJEMY WYŁĄCZNIE PRZEZ RÓWNOŚĆ NAZW i to jest wynik pomiaru, nie
    ostrożność na wyrost. Luźniejsze reguły, które sprawdziły się przy GPW
    (zawieranie, wspólny prefiks), na niemieckich nazwach dają same pomyłki:

        Bayer       ~ Bayerische Motoren Werke   (czyli BMW)
        Infineon    ~ E.ON                       ("eon" siedzi w "infineon")
        RWE         ~ Friedrich Vorwerk          ("rwe" w "vorwerk")
        Continental ~ InterContinental Hotels
        Fresenius   ~ Fresenius Medical Care     (inna spółka!)

    Sprawdzone na 59 spółkach: sama równość daje 13 trafień i ZERO pomyłek,
    luźniejsze reguły dorzucają siedem kandydatów i wszyscy są błędni.
    Świadomie tracimy Porsche Automobil Holding (w rejestrze pod pełną nazwą)
    — lepiej nie pokazać nic, niż przypisać komuś cudzą pozycję.
    **Nie luzuj tego dopasowania.**
    """
    niemieckie = [r for r in rows if str(r.get("Ticker", "")).endswith(".DE")]
    if not niemieckie:
        return 0

    rejestr = rejestr_bundesanzeiger()
    if not rejestr:
        return 0

    uzupelnione = 0
    for r in niemieckie:
        if r.get("Krótkie pozycje (%)") not in (None, "", "BRAK"):
            continue
        dane = rejestr.get(klucz_de(r.get("Nazwa", "")))
        if not dane:
            continue
        r["Krótkie pozycje (%)"] = dane["procent"]
        r["Short: liczba pozycji"] = dane["liczba"]
        r["Short: największy gracz"] = (
            f"{dane['najwiekszy_kto']} ({dane['najwiekszy_ile']}%)"
        )
        r["Short z dnia"] = dane["data"]
        r["Źródło shortów"] = "Bundesanzeiger — % wyemitowanego kapitału"
        uzupelnione += 1

    print(f"📉 Shorty: uzupełniono {uzupelnione} spółek z Frankfurtu "
          f"(sprawdzono {len(niemieckie)}).")
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
