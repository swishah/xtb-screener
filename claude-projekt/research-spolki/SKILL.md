---
name: research-spolki
description: Przeprowadza pełny research pojedynczej spółki giełdowej (USA, Europa Zachodnia, GPW) i zwraca ustrukturyzowany raport inwestycyjny — teza, sprawozdania finansowe, wycena, analiza techniczna z policzonych poziomów, mocne i słabe strony, plan wejścia w transzach z konkretnymi kwotami w złotych, short interest, konsensus analityków, insiderzy. Używaj zawsze, gdy pojawia się ticker albo nazwa spółki giełdowej w kontekście analizy, wyceny, "co sądzisz o", "czy warto kupić", "przeanalizuj", "sprawdź spółkę", "zrób research", "ile kupić", a także gdy użytkownik omawia wyniki ze screenera albo pyta o poziomy wejścia — nawet jeśli nie użyje słowa "raport" ani "analiza".
---

# Research spółki

Ten skill produkuje jeden powtarzalny artefakt: raport inwestycyjny o stałej strukturze,
zakończony konkretną pozycją do zajęcia za konkretną kwotę.

Dwie zasady ważniejsze od wszystkich pozostałych:

1. **Nigdy nie uzupełniaj brakujących liczb z pamięci.** Dane rynkowe starzeją się
   w ciągu dni. Czego nie udało się pobrać, tego nie ma — wpisz `brak danych` i uwzględnij
   to w ocenie pewności. Raport z trzema dziurami i uczciwą oceną pewności jest wart
   więcej niż kompletnie wyglądający raport z wymyślonymi wskaźnikami.
2. **Każdy poziom cenowy w planie wejścia ma pochodzić z policzonej listy poziomów**
   (krok 2), skopiowany znak w znak. „Wsparcie w okolicach 42,80" wymyślone z wykresu
   brzmi wiarygodnie i **nie da się go zweryfikować**. Poziom policzony z notowań — owszem.
   Jeśli żaden policzony poziom nie pasuje do tezy, zrezygnuj ze spółki zamiast
   dosuwać liczby.

## Krok 0 — ustal spółkę i rynek

Zidentyfikuj giełdę po tickerze lub nazwie. Gdy masz samą nazwę albo nie jesteś pewien
sufiksu, **nie zgaduj** — zapytaj API screenera:

```
GET https://xtb-screener.vercel.app/api/dane/szukaj?q=ferro
```

Ticker zgadnięty z pamięci bywa tickerem innej spółki z innego rynku. Sufiksy: `.WA`
Warszawa, `.DE` Frankfurt, `.L` Londyn, `.PA` Paryż, `.MC` Madryt, `.MI` Mediolan,
`.AS` Amsterdam, `.ST` Sztokholm, `.OL` Oslo, `.LS` Lizbona, `.VI` Wiedeń; USA bez sufiksu.

Każdy rynek ma inne źródła i inne pułapki — przeczytaj właściwy plik, zanim zaczniesz
zbierać dane z sieci:

| Rynek | Plik referencyjny |
|---|---|
| USA (NYSE, NASDAQ) | `references/rynek-usa.md` |
| Europa Zachodnia | `references/rynek-eu.md` |
| Polska (GPW, NewConnect) | `references/rynek-pl.md` |

Przy podwójnym listingu wybierz rynek główny (największy wolumen), ale sprawdź różnicę
cen i płynności — przy parze GPW/USA ma to realne znaczenie dla wykonania zlecenia.

## Krok 1 — dane ze screenera

```
GET https://xtb-screener.vercel.app/api/dane/spolka/<TICKER>
```

Pełny kontrakt danych: `references/api-screenera.md`. Dostajesz cały wiersz z codziennego
skanu (wskaźniki techniczne i fundamentalne, autorskie scoringi, czerwone flagi), kierunek
zmiany kluczowych wskaźników przez 7 i 30 dni, mediany sektora i informację, w których
dzisiejszych rankingach ta spółka stoi.

- **Sprawdź `migawka.wiek_dni_roboczych`.** Powyżej 3 zweryfikuj cenę w sieci, zanim
  policzysz cokolwiek — poziomy wejścia z nieaktualnej ceny są bezużyteczne.
- **`BRAK` znaczy brak danych, nigdy zero.** Payout ratio `BRAK` to „nie wiadomo",
  a nie „nie wypłaca".
- Gdy tickera nie ma w uniwersum, zbierz wszystko z sieci i **napisz w raporcie, że
  spółka jest poza screenerem** — nie ma wtedy ani scoringów, ani flag, ani porównania
  z sektorem.

## Krok 2 — poziomy techniczne

```
GET https://xtb-screener.vercel.app/api/dane/notowania/<TICKER>
```

Liczone na żywo z dziesięciu lat surowego OHLC: ATR(14), swingi, średnie 20/50/200
i 10-tygodniowa, zakres 52 tygodni z pozycją kursu w nim, niedomknięte luki, trend na
trzech interwałach, świece 1D/1W/1M.

**To jest jedyne źródło liczb, z których wolno budować plan wejścia.** Pole `poziomy`
to gotowa lista nazwanych poziomów z odległością procentową od kursu — stamtąd bierzesz
stop i cele.

Analizę prowadź na trzech horyzontach, zawsze w tej kolejności, bo wnioski krótkoterminowe
mają sens tylko w ramie wyznaczonej przez dłuższy horyzont:

- **długi** (świece `1m`, pięć lat): struktura trendu, odległość od szczytu, strefy,
  które działały latami,
- **średni** (świece `1w` i średnie 50/200): formacja, kierunek trendu 1W,
- **krótki** (świece `1d`, RSI i MACD z migawki): najbliższe wsparcie i opór, wolumen.

Podawaj konkretne poziomy, nie opisy jakościowe.

## Krok 3 — warstwy, których screener nie ma

Screener liczy liczby. Te cztery warstwy wymagają wyszukiwania i są tym, co odróżnia
research od odczytania tabelki:

1. **Dlaczego jest tam, gdzie jest.** Przy dużym dystansie od szczytu znajdź KONKRETNY
   powód: wyniki poniżej oczekiwań, utrata kontraktu, zmiana regulacji, problem sektorowy.
   To jest centralne pytanie całego raportu — teza sprowadza się do tego, czy powód jest
   przejściowy, czy strukturalny.
2. **Konsensus analityków** — liczba rekomendacji, rozkład, mediana i ROZRZUT cen
   docelowych, kierunek rewizji z ostatnich 3 miesięcy. Kierunek rewizji niesie więcej
   informacji niż sam poziom ceny docelowej.
3. **Short interest** — procent, dni do pokrycia, trend. Uwaga: procent *free float*
   (Yahoo, USA) i procent *wyemitowanego kapitału* (rejestry europejskie) to dwie różne
   liczby. Podaj, która to.
4. **Insiderzy** — transakcje zarządu z 6–12 miesięcy. Otwarte zakupy z rynku niosą
   informację; realizacje opcji i sprzedaże w planach `10b5-1` zwykle nie.

## Krok 4 — sprawozdania finansowe

Przeczytaj `references/sprawozdania.md` i zbierz **pięć lat** (albo ile jest) przychodów,
marż, przepływów i zadłużenia plus ostatnie cztery kwartały. Bez tego kroku raport jest
opisem wykresu, a nie analizą spółki.

Minimum, które musi znaleźć się w raporcie: dynamika przychodów, co się dzieje z marżami
i DLACZEGO, przepływy operacyjne wobec zysku netto, zadłużenie wobec EBITDA i wobec
gotówki, oraz rozbicie kosztów, jeśli zarząd je pokazuje.

## Krok 5 — mocne i słabe strony

Osobna sekcja, po trzy do pięciu punktów, **każdy poparty liczbą albo faktem
ze źródła** — nie przymiotnikami. „Silna marka" to nie jest mocna strona; „marża brutto
62% przy medianie sektora 41% utrzymana przez pięć lat" jest.

Jeśli teza wychodzi pozytywna, znajdź i przedstaw **najmocniejszy argument niedźwiedzi,
jaki faktycznie istnieje w źródłach** — nie wersję ze słomy. I odwrotnie.

## Krok 6 — pozycja i plan wejścia

Reguły liczenia, przeliczanie walut, prowizje i limity płynności: `references/pozycja.md`.

**Domyślny limit to 5 000 zł na JEDNĄ spółkę** — tyle, ile użytkownik przeznacza
maksymalnie na pojedynczą pozycję. Jeśli poda inną kwotę, użyj jego.

Zawsze **trzy transze**, każda z ceną, kwotą w złotych, liczbą akcji i warunkiem:

```
T1 — [cena] [waluta] | [kwota] zł | [n] akcji | warunek: [co musi się wydarzyć]
T2 — [cena] [waluta] | [kwota] zł | [n] akcji | warunek: [...]
T3 — [cena] [waluta] | [kwota] zł | [n] akcji | warunek: [...]
```

Do tego obowiązkowo:

- **stop-loss** na nazwanym poziomie z kroku 2, z odległością w ATR i kwotą ryzyka w zł,
- **poziom unieważnienia tezy** — cena albo zdarzenie, po którym scenariusz przestaje
  obowiązywać i NIE dokupujesz niżej. Bez tego uśrednianie w dół nie ma granicy,
- **cele** dla horyzontu krótszego i dłuższego, osobno, z szacowanym czasem,
- **stosunek zysku do ryzyka** liczony od średniej ceny wejścia.

## Krok 7 — struktura raportu

```
# [Nazwa] ([giełda]: [ticker]) — research [data]

## Teza w trzech zdaniach
## Co się stało (dlaczego jest tu, gdzie jest)
## Sprawozdania: przychody, marże, koszty, gotówka, dług
## Fundamenty i wycena na tle sektora i własnej historii
## Analiza techniczna — długi / średni / krótki horyzont
## Mocne strony
## Słabe strony i ryzyka (konkretne, nie ogólne)
## Pozycjonowanie rynku (short interest, analitycy, insiderzy)
## Pozycja: transze, stop, unieważnienie, cele
## Czego nie udało się ustalić i jak to wpływa na pewność
```

Ostatnia sekcja jest obowiązkowa nawet wtedy, gdy jest pusta — napisz wprost, że komplet
danych był dostępny.

## Zasady, które łatwo zgubić

- **Ryzyka mają być spółkowe.** „Ryzyko rynkowe" i „ryzyko stopy procentowej" nie wnoszą
  nic. Ryzyko to konkretny kontrakt, konkretny klient, konkretne postępowanie, konkretny
  kowenant, konkretny termin zapadalności długu.
- **Waluta.** Przy spółkach zagranicznych wynik w złotych zależy też od kursu — przy
  horyzoncie kilkutygodniowym ruch waluty potrafi przewyższyć ruch akcji. Przy dywidendach
  zagranicznych wspomnij o podatku u źródła, jeśli dywidenda jest częścią tezy.
- **Notowania w subjednostkach.** Pole `waluta_w_podjednostkach` z API oznacza, że kurs
  jest w pensach, nie w funtach. Plan ułożony w funtach byłby 100x nie taki.
- **Scoringi ze screenera to rankingi wewnątrz tego uniwersum**, nie standard rynkowy.
  Nie cytuj ich bez wyjaśnienia, czym są.
- **Nie jest to rekomendacja inwestycyjna.** Raport ma pomóc podjąć własną decyzję, a nie
  ją zastąpić. Gdy dane są słabe, powiedz to wprost zamiast produkować pewność, której nie ma.
