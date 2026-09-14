# Sprawozdania finansowe — co wyciągnąć i jak to czytać

Screener podaje wskaźniki, czyli wynik dzielenia. Sprawozdanie pokazuje licznik
i mianownik osobno, a to dopiero mówi, CO SIĘ DZIEJE. C/Z 9 przy przychodach rosnących
12% rocznie i C/Z 9 przy przychodach spadających 8% rocznie to ta sama liczba opisująca
dwie zupełnie różne spółki.

**Minimum: cztery lata roczne i cztery ostatnie kwartały** (tyle oddaje trasa). Krótszy szereg nie pokaże
ani cyklu, ani trendu marż. Jeśli spółka ma mniej historii (debiut, wydzielenie), napisz
to wprost — to jest istotna informacja o ryzyku, nie brak danych do przemilczenia.

## Skąd brać

**Najpierw `GET https://xtb-screener.vercel.app/api/dane/finanse/<TICKER>`** — cztery
lata i pięć kwartałów, z policzonymi marżami, dynamiką przychodów, relacją przepływów
do zysku i długiem netto do EBITDA. Dane pochodzą z tego samego źródła, z którego liczy
je pythonowa część projektu, i obejmują także GPW oraz giełdy europejskie.

Do źródeł poniżej sięgaj **dopiero wtedy, gdy trasa czegoś nie ma** albo gdy potrzebujesz
treści, a nie liczb: podziału kosztów, komentarza zarządu, przyczyny odpisu, harmonogramu
zapadalności długu. Wtedy wybierz JEDNO źródło, nie pięć — każda nowa domena to osobne
pytanie do użytkownika o zgodę.


| Rynek | Źródło pierwotne | Wygodny agregat |
|---|---|---|
| USA | SEC EDGAR: `10-K` roczne, `10-Q` kwartalne | stockanalysis.com, macrotrends |
| Europa Zachodnia | dział relacji inwestorskich spółki, raporty roczne i półroczne | stockanalysis.com, marketscreener |
| GPW | raporty okresowe ESPI, pełne sprawozdanie roczne i półroczne | biznesradar, StockWatch |

Kwartalne raporty na GPW i w Europie bywają skrócone — pełne dane roczne są jedynym
kompletem. Nie porównuj wtedy „kwartału do kwartału" na danych o różnym zakresie.

## Co wyciągnąć — dziewięć pozycji

1. **Przychody** za cztery lata i kwartały, plus dynamika rok do roku. Szukaj przyspieszenia
   albo hamowania, nie samego poziomu.
2. **Marża brutto** — mówi o sile cenowej. Marża brutto, która spada trzy lata z rzędu,
   znaczy, że spółka nie umie przerzucić kosztów na klienta.
3. **Marża operacyjna** — mówi o dyscyplinie kosztowej. Rozjazd między marżą brutto
   (stabilną) a operacyjną (spadającą) wskazuje na rosnące koszty stałe, nie na presję rynku.
4. **Zysk netto** i **EPS**, z odnotowaniem zdarzeń jednorazowych: odpisów, sprzedaży
   aktywów, rezerw. Zysk netto podbity sprzedażą nieruchomości nie jest powtarzalny.
5. **Przepływy operacyjne** i ich relacja do zysku netto. To jest najważniejsza pojedyncza
   kontrola w całym sprawozdaniu — patrz niżej.
6. **Nakłady inwestycyjne** i wolne przepływy (operacyjne minus nakłady). Spółka z zyskiem
   i ujemnymi wolnymi przepływami przez kilka lat finansuje wzrost długiem.
7. **Zadłużenie**: dług netto, dług netto do EBITDA, harmonogram zapadalności. Termin
   zapadalności w ciągu 12–18 miesięcy przy wysokich stopach to konkretne ryzyko, nie ogólne.
8. **Rozbicie kosztów**, jeśli zarząd je pokazuje: surowce, wynagrodzenia, energia,
   frachty. Tu zwykle leży odpowiedź na pytanie, dlaczego marża się rusza.
9. **Liczba akcji** — rosnąca oznacza rozwodnienie (emisje, programy opcyjne), malejąca
   skup akcji własnych. Zysk na akcję potrafi rosnąć przy stojących w miejscu przychodach
   wyłącznie dzięki skupowi; to co innego niż wzrost biznesu.

## Pięć kontroli, które łapią najwięcej

1. **Przepływy operacyjne kontra zysk netto.** Zdrowa spółka ma przepływy zbliżone do
   zysku albo wyższe (amortyzacja). Zysk rosnący przy płaskich lub spadających przepływach
   to najczęstszy wczesny sygnał, że coś jest nie tak z jakością zysku.
2. **Należności i zapasy kontra przychody.** Rosnące szybciej niż przychody znaczą, że
   spółka sprzedaje na kredyt albo nie schodzi z towarem. Obie rzeczy kończą się odpisem.
3. **Marża po odjęciu zdarzeń jednorazowych.** Porównuj powtarzalne z powtarzalnym.
4. **Sezonowość.** Porównuj kwartał do tego samego kwartału rok wcześniej, nie do
   poprzedniego. Handel detaliczny w IV kwartale zawsze wygląda świetnie.
5. **Waluta sprawozdania kontra waluta notowania.** Spółka raportująca w euro i notowana
   w złotych (albo odwrotnie) ma wynik przesunięty o kurs — przy eksporterach to bywa
   większa pozycja niż cała marża operacyjna.

## Czego nie da się z tego wyczytać

- **Prognoz.** Prognoza zarządu (guidance) to deklaracja, nie dane. Podawaj ją jako
  cudzą wypowiedź z datą, nigdy jako liczbę w tabeli wyników.
- **Jakości zarządu.** Da się zmierzyć jej ślady: powtarzalność obietnic wobec wykonania,
  alokację kapitału (co zrobili z gotówką przez te lata), rozwodnienie.
- **Tego, co siedzi w pozycjach pozabilansowych** — leasingi, gwarancje, zobowiązania
  warunkowe. Jeśli spółka ma ich dużo, wspomnij o tym zamiast udawać, że dług netto
  opisuje całość.

## Jak to podać w raporcie

Tabela czterech lat z czterema wierszami (przychody, marża operacyjna, zysk netto,
przepływy operacyjne), a pod nią **trzy zdania o tym, co się w tych liczbach dzieje**.
Tabela bez wniosku jest przepisaniem cudzej strony; wniosek bez tabeli jest opinią.
