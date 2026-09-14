# Pozycja: ile, po ile, za ile

Ten plik zamienia analizę w liczbę akcji. Bez niego raport kończy się zdaniem
„wygląda ciekawie", z którym nie da się nic zrobić.

## Limit

**Domyślnie 5 000 zł na JEDNĄ spółkę.** To jest maksymalna wartość pojedynczej pozycji,
nie całego portfela — spółek może być wiele, każda do pięciu tysięcy. Gdy użytkownik
poda inną kwotę, liczy się jego.

Limit dotyczy **sumy wszystkich transz**. Plan, w którym trzy transze dają razem
7 000 zł, jest planem na inną kwotę niż zadana i nie wolno go tak podać.

## Transze

Domyślny podział: **40 / 30 / 30**. Pierwsza transza przy obecnej cenie albo na
najbliższym wsparciu, kolejne na niższych poziomach.

**Rozstaw transz wyznacza ATR, nie okrągłe procenty.** Trzy transze co 5% na spółce,
która rusza się o 1% dziennie, to plan na pół roku; te same 5% na spółce o ATR 4%
to trzy transze w ciągu jednego tygodnia. Punkt wyjścia: T2 mniej więcej 1 ATR poniżej
T1, T3 mniej więcej 2 ATR poniżej T1 — a potem **przesuń każdą transzę na najbliższy
NAZWANY poziom** z tabeli `poziomy` (`/api/dane/notowania/<TICKER>`) i podaj jego nazwę.
Zlecenie stojące tuż pod wsparciem ma sens; zlecenie stojące w pustce nie ma żadnego.

Jeśli w okolicy nie ma żadnego nazwanego poziomu, napisz to i zejdź do dwóch transz.
Wymyślenie poziomu po to, żeby były trzy, jest dokładnie tym, czego ten mechanizm ma
nie robić.

## Przeliczenie na złote

Kurs walutowy bierz **z naszej trasy**, jednym zapytaniem po wszystkie waluty:

```
GET https://xtb-screener.vercel.app/api/dane/kurs
GET https://xtb-screener.vercel.app/api/dane/kurs?waluta=SEK
```

Pod spodem jest NBP, tabela A, z datą notowania — ale odpytywany po naszej stronie,
więc nie dokłada kolejnej domeny do zatwierdzania w rozmowie.

Kurs NBP to **kurs średni, nie kurs brokera** — przy przewalutowaniu u brokera dochodzi
spread. Traktuj wynik jako przybliżenie i powiedz to wprost zamiast podawać liczbę
akcji z dokładnością do sztuki, której i tak nie da się dotrzymać.

Uwaga na notowania w subjednostkach: gdy `waluta_w_podjednostkach` jest prawdą, kurs jest
w pensach. Cena w funtach to kurs podzielony przez 100 — **najpierw dziel, potem
przeliczaj**, inaczej wyjdzie stukrotny błąd.

## Liczba akcji

```
akcje w transzy = podłoga( kwota transzy w zł / (cena × kurs walutowy) )
```

Zaokrąglaj **w dół**, do całych akcji, i pokaż resztę gotówki. XTB udostępnia akcje
ułamkowe dla części instrumentów, ale plan na całe akcje wykonuje się zawsze — jeśli
użytkownik chce ułamkowe, poprosi.

**Sprawdź, czy jedna akcja mieści się w transzy.** Przy spółce po 900 USD transza
1 500 zł nie kupi ani jednej sztuki. Wtedy albo zrób jedną transzę zamiast trzech,
albo napisz wprost, że przy limicie 5 000 zł ta spółka nie daje się sensownie
poskładać. To jest realna odpowiedź, nie porażka.

## Płynność — kontrola, którą łatwo pominąć

```
dzienny obrót ≈ średni wolumen 20-sesyjny × cena
```

(`wolumen.srednia_20` z `/api/dane/notowania/<TICKER>`).

- pozycja poniżej **0,5% dziennego obrotu** — bez uwag,
- **0,5–2%** — napisz, że przy zleceniu z limitem może się realizować częściami,
- **powyżej 2%** — plan trzech transz jest teoretyczny; powiedz to i zaproponuj jedną
  transzę albo inną spółkę.

Przy 5 000 zł problem pojawi się prawie wyłącznie na małych spółkach z GPW
i NewConnect — i tam pojawi się naprawdę.

## Ryzyko

```
ryzyko w walucie = (średnia cena wejścia − stop) × łączna liczba akcji
ryzyko w zł      = ryzyko w walucie × kurs
```

Podaj je **w złotych i jako procent pozycji**. Jeżeli ryzyko przekracza mniej więcej
jedną trzecią wartości pozycji, stop jest za daleko — wróć do tabeli poziomów i poszukaj
bliższego albo zrezygnuj.

Stop-loss:

- **zawsze na nazwanym poziomie** z tabeli `poziomy`, z podaną nazwą,
- **nie bliżej niż 0,5 ATR** od ceny wejścia — bliżej leży w zasięgu zwykłego szumu
  i zostanie zabrany przypadkiem, bez żadnej zmiany w tezie,
- **nie dalej niż 3 ATR** — dalej to już nie stop, tylko nadzieja.

## Stosunek zysku do ryzyka

Licz od **średniej ceny wejścia ze wszystkich transz**, nie od pierwszej:

```
R:R = (cel − średnie wejście) / (średnie wejście − stop)
```

Poniżej 1,5 plan nie jest wart zachodu — przy trzech trafieniach na pięć wychodzi się
na zero. Napisz to zamiast przedstawiać taki układ jako okazję.

## Koszty i podatki

- **Prowizja XTB**: dla akcji i ETF-ów historycznie 0% do 100 000 EUR obrotu miesięcznie,
  powyżej 0,2% (minimum 10 EUR). **Sprawdź aktualną tabelę opłat** — zmienia się.
- **Przewalutowanie**: około 0,5% przy każdej konwersji, o ile rachunek nie jest
  prowadzony w walucie instrumentu. Przy pozycji 5 000 zł to ~25 zł w jedną stronę,
  czyli realna pozycja w rachunku wyniku przy kilkuprocentowym celu.
- **Podatek Belki 19%** od zysków i dywidend, rozliczany rocznie.
- **Podatek u źródła od dywidend zagranicznych**: USA 30%, obniżane do 15% po złożeniu
  **W-8BEN** u brokera. Jeśli dywidenda jest częścią tezy, policz ją po podatku.

## Unieważnienie tezy

Osobna linijka, obowiązkowa: **cena albo zdarzenie, po którym scenariusz przestaje
obowiązywać i NIE dokupuje się niżej.** Bez tego uśrednianie w dół nie ma granicy,
a trzecia transza zamienia się w czwartą, piątą i szóstą.

Unieważnieniem bywa cena (przebicie poziomu, na którym opiera się teza), ale częściej
zdarzenie: kolejny kwartał ze spadającą marżą, utrata kontraktu, zejście przepływów
operacyjnych poniżej zera, obniżka prognozy. Nazwij je konkretnie.

## Kształt wyjścia

```
Pozycja: [TICKER] — limit 5 000 zł, kurs [waluta]/PLN [x,xx] (NBP, [data])

T1  [cena] [waluta]  |  2 000 zł  |  [n] akcji  |  [nazwa poziomu]  |  warunek: [...]
T2  [cena] [waluta]  |  1 500 zł  |  [n] akcji  |  [nazwa poziomu]  |  warunek: [...]
T3  [cena] [waluta]  |  1 500 zł  |  [n] akcji  |  [nazwa poziomu]  |  warunek: [...]

Średnie wejście przy pełnej pozycji: [cena]      Razem: [n] akcji, [kwota] zł
Stop: [cena] ([nazwa poziomu], [x,x] ATR)        Ryzyko: [kwota] zł ([x]% pozycji)
Cel 1: [cena] ([x] tygodni)                      R:R: [x,x]
Cel 2: [cena] ([x] miesięcy)
Unieważnienie: [cena albo zdarzenie]
Płynność: pozycja to [x]% dziennego obrotu
```
