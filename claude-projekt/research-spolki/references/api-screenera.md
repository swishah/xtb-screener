# Kontrakt danych — publiczne API screenera

Screener skanuje codziennie po zamknięciu sesji około 1300 akcji i ETF-ów dostępnych
na XTB. Wyniki siedzą w bazie, a te trasy są jedynym publicznym wyjściem z niej.

Adres bazowy: `https://xtb-screener.vercel.app`

Zacznij od `GET /api/dane` — trasa opisuje samą siebie: podaje datę i wiek migawki,
listę pozostałych tras z przykładami oraz to, czego w danych NIE MA. Jest generowana
z tego samego kodu, który obsługuje zapytania, więc nie rozjedzie się z rzeczywistością
tak, jak może rozjechać się ten plik.

## Trasy

| Trasa | Po co |
|---|---|
| `GET /api/dane` | spis treści, data i wiek migawki |
| `GET /api/dane/szukaj?q=<fraza>` | nazwa → ticker; szukaj tak, zamiast zgadywać |
| `GET /api/dane/spolka/<TICKER>` | wszystko, co skan wie o jednej spółce |
| `GET /api/dane/notowania/<TICKER>` | poziomy techniczne liczone na żywo z OHLC |
| `GET /api/dane/finanse/<TICKER>` | sprawozdania: 4 lata i 5 kwartałów, z policzonymi marżami |
| `GET /api/dane/kurs` | kursy walut z NBP do przeliczenia pozycji na złote |
| `GET /api/dane/rankingi` | czołówki dziesięciu rankingów |

## `/api/dane/spolka/<TICKER>`

```json
{
  "ticker": "MMM", "nazwa": "3M", "rynek": "USA (S&P 500)",
  "sektor": "Industrials", "branza": "...", "typ": "stock",
  "waluta": "USD", "waluta_w_podjednostkach": false,
  "migawka": {
    "data": "2026-09-12",
    "wiek_dni_roboczych": 1,
    "dane": { "Cena": 164.97, "RSI": 10.6, "Buy Score": 1, "C/Z (P/E)": 29.3, "...": "~80 kolumn" }
  },
  "kierunek_wskaznikow": [
    { "wskaznik": "RSI", "teraz": 10.6, "tydzien_temu": 19, "miesiac_temu": 67,
      "zmiana_7d": -8.4, "zmiana_30d": -56.4 }
  ],
  "na_tle_sektora": {
    "sektor": "Industrials", "spolek_w_probie": 231,
    "wskazniki": [
      { "kolumna": "C/Z (P/E)", "spolka": 29.3, "mediana_sektora": 26.48, "lepiej_znaczy": "nizej" }
    ]
  },
  "w_rankingach": [ { "ranking": "Wartość złożona", "miejsce": 3, "wynik": 15, "maks": 17 } ],
  "historia_ceny": [ { "d": "2026-08-08", "c": 182.9 } ]
}
```

Cztery rzeczy, które trzeba o tym wiedzieć:

1. **`kierunek_wskaznikow` jest ważniejszy niż sam poziom.** RSI 38 spadające z 62 przez
   dwa tygodnie to zupełnie inna sytuacja niż RSI 38 odbijające od 22. Ta sekcja
   odpowiada na pytanie „w którą stronę to idzie", którego z jednej migawki nie da się
   zadać.
2. **`na_tle_sektora` liczy MEDIANĘ, nie średnią**, i tylko dla akcji (ETF-y nie mają
   marż). Przy mniej niż pięciu spółkach w sektorze sekcja nie powstaje w ogóle, bo
   mediana z garstki opisuje przypadek, a nie branżę. `lepiej_znaczy` mówi, w którą
   stronę wypada dobrze — przy C/Z niżej, przy ROE wyżej.
3. **`historia_ceny` to NASZA historia skanów**, zaczynająca się 8 sierpnia 2026,
   a nie pełna historia notowań. Do wykresu wieloletniego użyj `/api/dane/notowania`.
4. **Wiek migawki.** `wiek_dni_roboczych` powyżej 3 znaczy, że skan prawdopodobnie się
   nie wykonał — zweryfikuj cenę w sieci i napisz o tym w raporcie.

## `/api/dane/notowania/<TICKER>`

Liczone na żywo z 10 lat dziennych świec skorygowanych o dywidendy i splity — dokładnie
tych samych danych, z których liczy je pythonowa część projektu.

```json
{
  "kurs": 164.97, "atr": 4.2131, "atr_pct": 2.55,
  "trend": { "1d": "spadkowy", "1w": "spadkowy", "1m": "wzrostowy" },
  "zakres_52t": { "min": 121.98, "maks": 198.4, "pozycja_pct": 56.3 },
  "wolumen": { "ostatni": 5123400, "srednia_20": 3211000, "krotnosc": 1.6 },
  "luki": [ { "data": "2026-09-08", "od": 170.1, "do": 172.4, "kierunek": "w dół" } ],
  "poziomy": [
    { "id": "sma200", "wartosc": 152.31, "opis": "średnia 200-sesyjna",
      "rodzaj": "średnia", "dystans_pct": -7.67 }
  ],
  "swiece": { "1d": [ { "d": "2026-09-12", "o": 1, "h": 2, "l": 3, "c": 4, "v": 5 } ], "1w": [], "1m": [] },
  "sesji_w_historii": 2516,
  "waluta": "USD", "waluta_w_podjednostkach": false
}
```

**Tabela `poziomy` jest tym, po co się tu przychodzi.** Zawiera nazwane poziomy
z odległością procentową od bieżącego kursu:

| `id` | co to jest |
|---|---|
| `swing_low_1..4` | ostatnie dołki swingu na interwale dziennym, od najnowszego |
| `swing_high_1..4` | ostatnie szczyty swingu |
| `sma20`, `sma50`, `sma200` | średnie sesyjne |
| `sma_tyg_10` | średnia 10-tygodniowa |
| `szczyt_52t`, `dolek_52t` | skrajne wartości ostatnich 252 sesji |
| `luka_N_od`, `luka_N_do` | brzegi niedomkniętych luk |

Swing to sesja, której maksimum (albo minimum) jest skrajne w promieniu pięciu sesji
w obie strony. **Ostatnich pięciu sesji nie ma na liście i to jest celowe** — dopóki
okno nie jest pełne, nie wiadomo, czy nie padnie tam wyższy szczyt, a poziom, który może
się jeszcze zmienić, nie nadaje się na stop-loss.

`atr` służy do rozstawienia transz i oceny stopa. Stop bliżej niż 0,5 ATR leży w zasięgu
zwykłego szumu danej spółki i zostanie zabrany przypadkiem; dalej niż 3 ATR to już nie
stop, tylko nadzieja.

Brak odpowiedzi 200 znaczy jedno z dwóch: zły ticker albo historia krótsza niż 60 sesji
(świeży debiut, instrument wycofany). W obu przypadkach planu wejścia nie buduj.

## `/api/dane/finanse/<TICKER>`

Cztery okresy roczne i pięć kwartalnych, ze wskaźnikami policzonymi po stronie serwera.

```json
{
  "ticker": "ALE.WA", "waluta_raportowania": "PLN",
  "lata": [
    { "okres": "2025-12-31", "waluta": "PLN",
      "TotalRevenue": 11458200000, "GrossProfit": 10734100000,
      "OperatingIncome": 2161300000, "NetIncome": 1517100000,
      "EBITDA": 2913500000, "OperatingCashFlow": 2869700000,
      "CapitalExpenditure": -712300000, "FreeCashFlow": 2157400000,
      "TotalDebt": 5136900000, "CashAndCashEquivalents": 2508200000,
      "marza_brutto_pct": 93.68, "marza_operacyjna_pct": 18.86,
      "marza_netto_pct": 13.24, "przeplywy_do_zysku": 1.89,
      "dynamika_przychodow_pct": 10.52, "dlug_netto_do_ebitda": 0.9 }
  ],
  "kwartaly": [ { "okres": "2026-03-31", "...": "węższy zestaw pozycji" } ],
  "uwagi": ["..."]
}
```

**Marże, dynamikę i relację przepływów do zysku liczy serwer** — nie licz ich ponownie
z liczb przepisanych do rozmowy. To najczęstsze miejsce, w którym mylą się okresy:
marża policzona z zysku za jeden rok i przychodów za inny wygląda dokładnie tak samo
jak poprawna.

Trzy rzeczy, o których trzeba pamiętać:

1. **`przeplywy_do_zysku` to najważniejsza pojedyncza kontrola.** Zdrowa spółka ma
   przepływy operacyjne zbliżone do zysku netto albo wyższe. Zysk rosnący przy płaskich
   przepływach to najczęstszy wczesny sygnał, że coś jest nie tak z jakością zysku.
   Wartość ujemna znaczy, że jedno z dwóch jest ujemne — sprawdź, które.
2. **Waluta sprawozdania bywa inna niż waluta notowania.** Spółka raportująca w euro,
   a notowana w złotych, ma wynik przesunięty o kurs.
3. **Liczby są surowe, bez korekt o zdarzenia jednorazowe.** Skokowa zmiana zysku netto
   przy stabilnych przychodach to zwykle odpis albo sprzedaż aktywów — sprawdź to
   w raporcie spółki, zanim policzysz z tego trend.

ETF-y i fundusze nie mają sprawozdań z definicji i trasa oddaje wtedy 404. Przy spółce
404 znaczy, że dostawca nie ma danych — wtedy dopiero szukaj w sieci.

## `/api/dane/kurs`

```
GET /api/dane/kurs              -> USD, EUR, GBP i CHF naraz
GET /api/dane/kurs?waluta=SEK   -> dowolna inna
```

NBP, tabela A, z datą notowania. To **kurs średni, nie kurs brokera** — przy
przewalutowaniu dochodzi spread, więc liczba akcji policzona z tego kursu jest
przybliżeniem, a nie wartością do dotrzymania co do sztuki.

## `/api/dane/rankingi`

Czołowa dziesiątka w każdym z dziewięciu rankingów strategii plus bazowy Buy Score.
`?klucz=<klucz>` zawęża do jednego, `?ile=<1-30>` zmienia długość listy.

Klucze: `deep-value`, `momentum`, `dywidendowa`, `dywidenda-okazja`, `f-score`,
`blisko-szczytu`, `konserwatywna`, `wartosc-zlozona`, `rewizje`, `buy-score`.
Każdy ranking przychodzi z własnym opisem — przeczytaj go, zanim zinterpretujesz wynik.

Dwie pułapki wbudowane w te rankingi, obie zmierzone na prawdziwych danych:

- **„Deep Value" NIE jest strategią wartości.** Selekcjonuje spółki PRZECENIONE, nie
  TANIE: mediana C/Z w jego czołówce była praktycznie taka sama jak w całym uniwersum,
  za to mediana spadku od szczytu −54,8% wobec −19,7%. Szukając niskiej wyceny, weź
  „Wartość złożoną".
- **Banki i ubezpieczyciele mają w „Wartości złożonej" sufit 14 z 17 punktów**, bo dla
  nich nie podaje się EBITDA. Tani bank wypada niżej niż równie tania spółka przemysłowa.
  To systematyczne przesunięcie, nie błąd.

## Jak czytać wartości

- **`"BRAK"` w polu liczbowym znaczy: dostawca nie podał wartości.** Nigdy nie traktuj
  tego jako zera i nie uzupełniaj z pamięci. Payout ratio `BRAK` to „nie wiadomo",
  a nie „nie wypłaca". Jeśli liczba jest potrzebna do tezy — poszukaj jej w sieci
  i zaznacz, że pochodzi stamtąd.
- **Ceny są w walucie notowania.** Yahoo podaje Londyn w PENSACH, więc kurs 122,30
  znaczy 1,22 funta; mówi o tym `waluta_w_podjednostkach`.
- **Kolumny `Score: ...` i `Buy Score` to autorskie scoringi** tego projektu, liczone
  wewnątrz jego uniwersum. Nie są standardem rynkowym i nie należy ich cytować bez
  wyjaśnienia, czym są i jaka jest skala.
- **Krótkie pozycje i rekomendacje analityków bywają puste dla całych rynków.**
  Skan pobiera je z dziewięciu rejestrów i trzech źródeł konsensusu, ale Wiedeń
  i Mediolan są niedostępne, a pokrycie analityczne mniejszych spółek z GPW jest rzadkie.
  Pusto znaczy „nie mamy", nie „zero".
