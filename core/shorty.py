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

DWIE LICZBY, KTÓRE WYGLĄDAJĄ TAK SAMO, A ZNACZĄ CO INNEGO. Yahoo podaje
procent **wolnego obrotu** (free float), FCA — procent **wyemitowanego
kapitału**. Przy spółce z dużym pakietem kontrolnym te dwie miary potrafią
się różnić kilkukrotnie. Dlatego zapisujemy źródło osobno i profil spółki
mówi wprost, co jest czym. **Nie sklejaj tych wartości w jedną kolumnę bez
źródła.**

CZEGO NIE MA. Pozostałe rynki europejskie (Warszawa, Frankfurt, Paryż,
Mediolan, Madryt, Sztokholm, Oslo, Wiedeń, Lizbona) mają własne rejestry
u własnych nadzorów — KNF, BaFin, AMF, CONSOB, CNMV i tak dalej — każdy
w innym formacie. To osobna praca na każdy kraj i NIE jest zrobiona.
Brak danych o shortach dla tych rynków nie znaczy „brak shortów", tylko
„nie sprawdzamy". Profil spółki mówi to wprost, żeby nikt nie wziął pustego
pola za zielone światło.

DOPASOWANIE PO NAZWIE JEST STRATNE. Rejestr FCA identyfikuje spółki nazwą
i numerem ISIN, a my mamy tickery Yahoo — ISIN-ów nie mamy. Zostaje
dopasowanie po znormalizowanej nazwie, które na naszych 71 spółkach
z Londynu trafia w 25. Część reszty to ETF-y (nie mają pozycji krótkich
z definicji), część to nazwy zapisane inaczej niż u nas. To ograniczenie,
nie błąd — i lepsze niż brak danych, ale nie udawaj, że pokrycie jest pełne.
"""
from __future__ import annotations

import io
import re
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
