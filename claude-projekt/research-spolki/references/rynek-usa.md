# USA (NYSE, NASDAQ)

Najlepiej udokumentowany rynek — praktycznie każda warstwa danych jest dostępna publicznie
i aktualizowana regularnie. Jeśli czegoś brakuje w raporcie o spółce amerykańskiej, to
zwykle dlatego, że nie zostało wyszukane, a nie dlatego, że nie istnieje.

## Ceny i wskaźniki
- `/api/dane/spolka/<TICKER>` — podstawowe źródło wskaźników.
- `/api/dane/notowania/<TICKER>` — poziomy techniczne. Patrz `api-screenera.md`.
- Weryfikacja ceny: Yahoo Finance, Stooq.

## Raporty
- **SEC EDGAR** — źródło pierwotne. Formularze, które mają znaczenie dla researchu:
  - `10-K` — raport roczny. Sekcja *Risk Factors* to gotowa lista ryzyk spółkowych,
    ale czytaj ją krytycznie: zawiera też ryzyka wpisywane defensywnie przez prawników.
    Szukaj zmian względem poprzedniego roku — nowo dodane ryzyko jest sygnałem.
  - `10-Q` — kwartalny.
  - `8-K` — zdarzenia bieżące. Tu znajdziesz odpowiedź na „dlaczego spadło".
  - `DEF 14A` — proxy statement: wynagrodzenia zarządu, struktura akcjonariatu.
- **Earnings calls** — transkrypcje i nagrania. Sekcja Q&A z analitykami jest zwykle
  bardziej informatywna niż przygotowane wystąpienie zarządu.

## Short interest
- Raportowany dwa razy w miesiącu przez giełdy (FINRA), z opóźnieniem około tygodnia.
  Zawsze podawaj datę pomiaru, bo przy zmiennych spółkach dane sprzed dwóch tygodni
  mogą być nieaktualne.
- Metryki: short % of float, days to cover (short ratio), trend między kolejnymi odczytami.
- Wysoki short interest czytaj dwuznacznie: to zarówno sygnał negatywnego przekonania
  rynku, jak i potencjalne paliwo do short squeeze. Nie sprowadzaj tego do jednej strony.

## Analitycy
- Konsensus dostępny szeroko (Yahoo Finance, MarketWatch, TipRanks, Zacks).
- Zbierz: liczbę pokrywających analityków, rozkład rekomendacji, medianę i rozrzut cen
  docelowych, kierunek rewizji EPS w ostatnich 90 dniach.
- Rozrzut cen docelowych jest niedocenianą metryką — szeroki rozrzut oznacza brak zgody
  co do modelu biznesowego i zwykle wyższą zmienność po wynikach.

## Insiderzy
- **Formularze SEC Form 4** — transakcje w ciągu 2 dni roboczych.
- Odfiltruj transakcje automatyczne: plany `10b5-1` i realizacje opcji z wynagrodzenia
  nie niosą informacji o przekonaniu. Znaczenie mają otwarte zakupy z rynku.
- Formularze `13F` (fundusze, kwartalnie, z opóźnieniem 45 dni) i `13D/G` (znaczące
  pakiety, w tym aktywiści) — przydatne przy tezie o zmianie w spółce.

## Specyfika dla inwestora z Polski
- Podatek u źródła od dywidend: standardowo 30%, obniżany do 15% po złożeniu **W-8BEN**
  u brokera. Jeśli dywidenda jest częścią tezy, zaznacz to.
- Ryzyko walutowe USD/PLN nakłada się na wynik z akcji — przy horyzoncie
  krótkoterminowym potrafi przewyższyć ruch samego instrumentu.
- Sprawdź, czy instrument jest dostępny u brokera użytkownika, zanim zbudujesz plan wejścia.
