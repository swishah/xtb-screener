# GPW / NewConnect

Najtrudniejszy rynek z trzech — brak zagregowanych API, dane rozproszone po portalach
i raportach bieżących. Za to wszystko, czego potrzebujesz, jest publiczne i darmowe.

## Ceny i wskaźniki
- `/api/dane/spolka/<TICKER>` (sufiks `.WA`) — podstawowe źródło.
- `/api/dane/notowania/<TICKER>` — poziomy techniczne z dziesięciu lat notowań.
- Stooq — weryfikacja ceny, gdy migawka ma więcej niż trzy dni robocze.
- Biznesradar — wskaźniki fundamentalne, porównania sektorowe, historia wskaźników.

Uwaga na płynność: przy małych spółkach z GPW spread i wolumen potrafią uniemożliwić
realizację planu transzowego. Zawsze sprawdź średni dzienny obrót i odnieś go do
zakładanej wielkości pozycji. Jeśli pozycja to więcej niż kilka procent dziennego obrotu,
napisz to w raporcie — plan trzech transz na spółce z obrotem 200 tys. zł dziennie
jest planem teoretycznym.

## Raporty i komunikaty
- **ESPI/EBI** — raporty bieżące i okresowe, źródło pierwotne dla „co się stało".
  Dostępne przez stronę relacji inwestorskich spółki i agregatory (Bankier, StockWatch, Infostrefa).
- Raport roczny i półroczny — jedyne wiarygodne źródło pełnych danych finansowych.
  Kwartalne bywają skrócone.
- Prezentacje wynikowe i transkrypcje konferencji — często zawierają prognozy zarządu,
  których nie ma w samym raporcie.

## Short interest
- **Rejestr krótkiej sprzedaży KNF** — publiczny rejestr znaczących pozycji krótkich
  netto. Obowiązek zgłoszenia od progu 0,5% kapitału, kolejne zmiany co 0,1%.
- Konsekwencja: pozycje poniżej 0,5% są niewidoczne. Brak wpisu w rejestrze **nie** oznacza
  braku shortów — oznacza brak dużych, zgłoszonych pozycji. Napisz to w raporcie
  zamiast raportować „short interest: 0%".
- Sprawdź też, czy spółka jest w koszyku instrumentów pochodnych GPW — dostępność
  kontraktów zmienia strukturę pozycjonowania.

## Analitycy
- Pokrycie analityczne na GPW jest rzadkie poza WIG20/mWIG40. Dla małych spółek często
  nie ma żadnych rekomendacji — to normalne, nie brak danych.
- Źródła: raporty domów maklerskich (DM BOŚ, Trigon, Erste, mBank, Santander, Ipopema),
  agregaty na Bankier i StockWatch.
- Osobna kategoria: **programy wsparcia pokrycia analitycznego GPW** — raporty
  sponsorowane przez giełdę dla mniejszych spółek. Są użyteczne, ale zaznacz, że są
  finansowane przez emitenta lub GPW, bo to zmienia wagę wniosków.

## Insiderzy
- Powiadomienia o transakcjach osób pełniących obowiązki zarządcze — raporty ESPI
  (art. 19 MAR). Publikowane przez spółkę, agregowane przez portale finansowe.
- Zwróć uwagę na transakcje głównego akcjonariusza i na wezwania — na GPW koncentracja
  akcjonariatu jest wysoka i ruch dominującego akcjonariusza waży więcej niż na rynkach
  rozwiniętych.

## Specyfika, o której łatwo zapomnieć
- **Skarb Państwa jako akcjonariusz** — przy spółkach z udziałem SP polityka dywidendowa
  i decyzje inwestycyjne podlegają czynnikom pozarynkowym. Wymień to jako osobne ryzyko.
- **Free float** — często niski. Przy free float poniżej 25% wyceny wskaźnikowe i reakcja
  na newsy są mniej przewidywalne.
- Podatek Belki 19% od zysków i dywidend; przy spółkach polskich brak podatku u źródła,
  co jest przewagą wobec zagranicznych dywidend.
