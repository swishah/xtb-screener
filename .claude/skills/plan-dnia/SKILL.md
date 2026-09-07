---
name: plan-dnia
description: Buduje plany wejścia na dziś dla screenera XTB — czyta dossier kandydatów przygotowane rano przez GitHub Actions, analizuje wykresy 1D/1W/1M, wybiera poziomy wejścia, stop-lossa i celów, a potem zapisuje plany przez bramkę kontrolną. Używaj, gdy użytkownik prosi o plan dnia, pomysły na wejście, albo pyta, co dziś kupić.
---

# Plan dnia

Twoim zadaniem jest **wybrać** plany wejścia spośród policzonych poziomów.
Nie liczysz poziomów, nie zgadujesz wsparć i nie wymyślasz liczb — one już są
policzone z surowych notowań przez `core/poziomy.py`. Ty patrzysz na wykres,
oceniasz kontekst i decydujesz, KTÓRY z policzonych poziomów jest sensownym
wejściem, który stopem, a który celem.

**Wszystko robisz z katalogu `xtb-screener-main`.** Jeżeli pracujesz z katalogu
nadrzędnego, wołaj skrypty jako `xtb-screener-main/scripts/...`.

## Zasada, która przewyższa wszystkie pozostałe

**Każda liczba w planie musi być skopiowana z listy POZIOMY danej spółki,
znak w znak.** Bramka (`core/bramka.py`) odrzuca plan, którego stop albo cel
nie odpowiada żadnemu poziomowi z dossier. To nie jest formalność do obejścia
— to jedyny powód, dla którego temu narzędziu wolno ufać przy pieniądzach.

Jeśli plan odpada na bramce, **NIE poprawiaj liczb, żeby przeszedł**. Wybierz
inny poziom albo zrezygnuj z tej spółki. Przesunięcie stopa o dwa grosze,
żeby zmieścić się w R:R, jest dokładnie tym oszustwem, przed którym bramka ma
chronić — i będzie widoczne dopiero wtedy, gdy zabierze prawdziwe pieniądze.

## Krok 0: sprawdź, na jakiej bazie pracujesz

```bash
python scripts/pokaz_dossier.py --tryb
```

**Na Windowsie wołaj `py`, nie `python`** — `python` na PATH bywa zaślepką ze
Sklepu Windows, która nic nie uruchamia i wypisuje zachętę do instalacji.
Skrypty działają wywołane ścieżką bezwzględną z dowolnego katalogu, więc
`py "<ścieżka do repo>/scripts/pokaz_dossier.py" --tryb` jest bezpieczniejsze
niż poleganie na katalogu roboczym.

Jeżeli wyjdzie `lokalny`, **przerwij i powiedz o tym użytkownikowi**. Bez
zmiennych `TURSO_DATABASE_URL` i `TURSO_AUTH_TOKEN` wszystko idzie do
zamrożonej kopii `data/history.db`: dossier policzyłoby się na kursach sprzed
tygodni, a plany nie pojawiłyby się na stronie, bo ta czyta bazę zdalną.
Żaden krok się nie wywali — dlatego trzeba to sprawdzić na początku, a nie
zauważyć na końcu.

## Krok 1: sprawdź dossier

```bash
python scripts/pokaz_dossier.py --dni
```

Jeśli nie ma dossier na dziś (Actions robi je o 6:00 w dni robocze), zbuduj je:

```bash
python scripts/przygotuj_dossier.py
```

To potrwa minutę — pobiera po dziesięć lat notowań na spółkę.

## Krok 2: przeczytaj przegląd

```bash
python scripts/pokaz_dossier.py
```

Dostaniesz dla każdego kandydata: kurs, ATR, trendy 1D/1W/1M, zakres roku,
wolumen, **listę nazwanych poziomów** z odległością od kursu, niedomknięte
luki i wybrane dane fundamentalne.

Zwróć uwagę na `Wskazana przez N rankingów` — spółka widoczna z kilku stron
naraz (wycena + technika) to mocniejszy sygnał niż jedno trafienie.

## Krok 3: obejrzyj wykresy

Dla każdego kandydata, którego rozważasz:

```bash
python scripts/pokaz_dossier.py --ticker FRO.WA
```

Dostajesz świece dzienne (60), tygodniowe (52) i miesięczne (60). **Przeczytaj
je naprawdę**, nie prześlizguj się po nagłówku. Szukasz:

- **1M** — czy spółka jest w wieloletnim trendzie wzrostowym, czy w spadku.
  Wejście długie w miesięcznym trendzie spadkowym wymaga mocniejszego powodu.
- **1W** — gdzie leży średnioterminowa struktura: czy ostatnie tygodnie to
  konsolidacja, odbicie, czy kontynuacja.
- **1D** — konkret: czy kurs właśnie testuje wsparcie, wybija opór, wraca do
  luki. To tu wybierasz strefę wejścia.

Sprawdzaj też **zgodność trzech interwałów**. Trzy trendy wzrostowe naraz to
najczystsza sytuacja; 1M spadkowy przy 1D wzrostowym to odbicie w trendzie
spadkowym, które bywa krótkie — takiemu planowi należy się niższa pewność
i krótszy horyzont.

## Krok 4: ułóż plany

Dla wybranych spółek zapisz plik JSON (np. w katalogu tymczasowym):

```json
[
  {
    "ticker": "FRO.WA",
    "teza": "Trzy trendy wzrostowe, kurs wraca do SMA20 po wybiciu; wejście na teście średniej, stop pod nią, cel na szczycie swingu z sierpnia.",
    "wejscie_od": 35.82,
    "wejscie_do": 36.0,
    "sl": 35.41,
    "sl_poziom": "sma20",
    "tp1": 37.4,
    "tp2": null,
    "pewnosc": 4,
    "horyzont_sesji": 10
  }
]
```

Reguły układania:

- **`sl` i `tp1` MUSZĄ być wartościami z listy POZIOMY.** `sl_poziom` to `id`
  tego poziomu — bramka sprawdza, czy nazwa zgadza się z liczbą.
- **Strefa wejścia** leży najwyżej 5% od kursu. Zwykle: między kursem
  a najbliższym wsparciem, albo dokładnie na poziomie, który kurs ma
  przetestować.
- **Stop między 0,5 a 3 ATR** pod środkiem strefy. Bliżej — zabierze go zwykły
  szum spółki. Dalej — to już nie stop, tylko nadzieja.
- **R:R co najmniej 1,5** licząc od środka strefy do `tp1`.
- **`tp2` jest opcjonalne** — dawaj je, gdy wyżej jest wyraźny drugi poziom.
- **`pewnosc` 1–5.** Piątka należy się sytuacji, w której trzy interwały
  mówią to samo, poziom jest wyraźny i nic w danych nie zgrzyta. Nie rozdawaj
  czwórek hurtem; skala, w której wszystko ma 4, nie niesie informacji.
- **`teza` to jedno–dwa zdania po polsku**: co widzisz na wykresie i dlaczego
  akurat te poziomy. Bez ogólników typu „dobra spółka".

**Wszystko liczymy dla pozycji DŁUGICH.** Krótka sprzedaż nie jest obsługiwana.

## Krok 5: przepuść przez bramkę

Najpierw na sucho:

```bash
python scripts/zapisz_plany.py /ścieżka/do/plany.json --sucho
```

Przeczytaj raport. Przy odrzuceniu masz wypisany powód — **przeczytaj go
i zastanów się, czy plan da się poprawić UCZCIWIE** (inny poziom, inna spółka),
czy trzeba go po prostu skreślić. Potem zapis:

```bash
python scripts/zapisz_plany.py /ścieżka/do/plany.json
```

Zapisane plany widać na `/plan` we frontendzie. Codzienny skan rozlicza je sam.

## Ile planów

Do bazy trafia najwyżej **10 planów dziennie**; nadmiar jest odrzucany po
pewności i R:R. Ale **to jest limit, nie cel**. Jeżeli na dwadzieścia
kandydatów sensownych układów jest cztery — proponujesz cztery. Dołożenie
sześciu słabych po to, żeby lista wyglądała pełniej, psuje dokładnie tę
statystykę, dla której cały mechanizm powstał.

Dzień bez ani jednego planu jest poprawnym wynikiem i tak go zaraportuj.

## Czego nie robić

- **Nie zmieniaj poziomów, żeby przejść bramkę.** Wybierz inne albo odpuść.
- **Nie proponuj spółki, której nie ma w dossier** — bramka i tak ją odrzuci,
  bo nie ma dla niej policzonych poziomów.
- **Nie zawyżaj pewności**, żeby plan zmieścił się w dziesiątce.
- **Nie ruszaj planów już zapisanych.** Baza na to nie pozwala i to jest
  celowe: plan jest świadectwem tego, co się myślało tamtego dnia.
- **Nie dopisuj planu spółce, która ma już otwarty** — to podwójna pozycja
  pod jednym pomysłem.

## Na koniec

Zdaj krótki raport po polsku: ile planów zapisanych, co odpadło i dlaczego,
a przy każdym zapisanym planie jedno zdanie, co zdecydowało. Jeżeli któraś
spółka przeszła bramkę, ale coś w niej zgrzyta (uwagi z bramki: wysoki short,
payout ponad 100%, wolumen poniżej średniej) — powiedz to wprost, bo to
zostaje w bazie razem z planem.
