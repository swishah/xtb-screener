# Europa Zachodnia (DAX, CAC 40, FTSE, IBEX, OMX, OBX)

Rynek pośredni między USA a GPW: dane są dostępne, ale rozproszone po krajowych
regulatorach i w kilku językach. Nie ma jednego EDGAR-a dla całej Europy.

## Ceny i wskaźniki
- `/api/dane/spolka/<TICKER>` i `/api/dane/notowania/<TICKER>` — patrz `api-screenera.md`.
  Uwaga na sufiksy: `.DE`, `.PA`, `.L`, `.MC`, `.ST`, `.OL`, `.MI`, `.AS`, `.LS`, `.VI`.
  Gdy nie masz pewności, sprawdź `/api/dane/szukaj?q=<nazwa>` zamiast zgadywać.
- Ta sama spółka bywa notowana na kilku giełdach — używaj notowania z rynku macierzystego,
  bo tam jest płynność i tam reaguje cena.

## Raporty
- Obowiązek publikacji raportów okresowych wynika z dyrektywy Transparency; raporty
  znajdziesz na stronach relacji inwestorskich (sekcja *Investors* / *Investoren*).
- Krajowe rejestry informacji regulowanej: Bundesanzeiger (DE), AMF (FR), FCA National
  Storage Mechanism (UK), CNMV (ES), Finansinspektionen (SE).
- Duże spółki publikują komplet materiałów po angielsku. Mniejsze — często tylko w języku
  krajowym. Jeśli musisz oprzeć się na tłumaczeniu, zaznacz to przy cytowanych liczbach.

## Short interest
- **To jest największa różnica względem USA.** W UE obowiązuje rozporządzenie SSR:
  zgłoszenie do krajowego regulatora od 0,5% kapitału, aktualizacja co 0,1%.
- Publiczne rejestry pozycji krótkich netto prowadzą: BaFin (DE), AMF (FR), CNMV (ES),
  FCA (UK), Finansinspektionen (SE), Finanstilsynet (NO).
- Dane pokazują **tylko duże zgłoszone pozycje** — nie zagregowany short interest jak w USA.
  Nie porównuj tych liczb bezpośrednio z amerykańskimi i nie pisz „short interest 1,2%"
  bez zaznaczenia, że to suma pozycji powyżej progu raportowania.
- Za to rejestry pokazują **nazwy funduszy**, czego nie ma w USA. Powracający fundusz
  budujący pozycję przez kilka miesięcy to mocniejszy sygnał niż sama liczba.

## Analitycy
- Pokrycie dobre dla głównych indeksów, słabnące przy mid- i small-capach.
- Źródła: Yahoo Finance, MarketScreener, agregaty na stronach giełd, raporty banków
  krajowych (Deutsche Bank, BNP, Santander, SEB, DNB).

## Insiderzy
- **Art. 19 MAR** — te same zasady co na GPW: powiadomienia o transakcjach osób
  zarządzających, publikowane przez spółkę i zbierane przez krajowego regulatora.
- Publiczne bazy: BaFin Directors' Dealings, AMF, CNMV.

## Specyfika dla inwestora z Polski
- Podatek u źródła od dywidend różni się per kraj i bywa wysoki: Niemcy ~26%, Francja
  ~25–28%, Szwajcaria 35%, Hiszpania 19%. Odzyskanie nadpłaty ponad stawkę z umowy
  o unikaniu podwójnego opodatkowania wymaga procedury i bywa nieopłacalne przy małych kwotach.
  Wielka Brytania nie pobiera podatku u źródła od dywidend — to realna przewaga.
- Ryzyko walutowe EUR/PLN, GBP/PLN, SEK/PLN, NOK/PLN. Przy krajach skandynawskich
  zmienność waluty bywa porównywalna ze zmiennością akcji.
