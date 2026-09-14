# Maszyna researchowa w Claude — jak to uruchomić

Ten katalog zawiera wszystko, czego potrzeba, żeby robić research spółek w przeglądarce,
z dowolnego komputera, bez Claude Code i bez włączonego domowego komputera.

```
claude-projekt/
├─ INSTRUKCJE-PROJEKTU.md      ← tekst do wklejenia w ustawieniach Projektu
└─ research-spolki/            ← skill do wgrania na konto Claude
   ├─ SKILL.md
   └─ references/
      ├─ api-screenera.md      kontrakt danych: co zwracają trasy /api/dane/*
      ├─ sprawozdania.md       jak czytać przychody, marże, koszty, przepływy
      ├─ pozycja.md            transze, przeliczanie na złote, ryzyko, płynność
      ├─ rynek-usa.md          SEC EDGAR, Form 4, FINRA, W-8BEN
      ├─ rynek-eu.md           raporty roczne, rejestry krótkiej sprzedaży
      └─ rynek-pl.md           ESPI/EBI, rejestr KNF, pokrycie analityczne
```

## Skąd biorą się dane

Aplikacja `xtb-screener.vercel.app` jest w całości za logowaniem — Claude w przeglądarce
nie ma jak się do niej dostać. Dlatego doszły **publiczne trasy tylko do odczytu**:

| trasa | co oddaje |
|---|---|
| `/api/dane` | spis treści, data i wiek migawki |
| `/api/dane/szukaj?q=` | nazwa spółki → ticker |
| `/api/dane/spolka/<TICKER>` | pełny wiersz migawki, kierunek zmian 7d/30d, mediany sektora, rankingi |
| `/api/dane/notowania/<TICKER>` | ATR, swingi, średnie, luki, zakres 52 tygodni, świece 1D/1W/1M |
| `/api/dane/finanse/<TICKER>` | sprawozdania: cztery lata i pięć kwartałów, z policzonymi marżami |
| `/api/dane/kurs` | kursy walut z NBP do przeliczenia pozycji na złote |
| `/api/dane/rankingi` | czołówki dziesięciu rankingów |

**Dlaczego tych tras jest siedem, a nie trzy.** Claude w rozmowie na claude.ai pyta
o zgodę przy każdej NOWEJ domenie, którą chce pobrać. Gdyby sprawozdania szły z SEC
i biznesradaru, a kursy z api.nbp.pl, jeden research kończyłby się serią okienek do
klikania. Wszystko, co da się policzyć po naszej stronie, wychodzi więc spod JEDNEGO
adresu — zatwierdzasz go raz i masz spokój. Sieć zostaje wyłącznie do rzeczy, których
w żadnej bazie nie ma: powodów spadków, transakcji insiderów, transkrypcji konferencji
— a i tam skill każe używać wyszukiwarki, bo ona zgody nie wymaga.

**Te trasy są publiczne — kto zna adres, zobaczy te liczby.** To była świadoma decyzja:
wszystkie te wartości są policzone z publicznych notowań, więc ich ujawnienie nikogo nie
naraża. Dane o Tobie — konta, watchlisty, alarmy, plany dnia, analiza transakcji — **nie
mają żadnej trasy** i zostają za logowaniem.

Poziomy techniczne liczą się **na żywo z dziesięciu lat notowań**, przy każdym zapytaniu,
więc nie zależą od tego, czy Twój komputer jest włączony. Kod jest lustrem
`core/poziomy.py`; zgodność sprawdza `scripts/porownaj_poziomy.py` (przy wdrożeniu:
380 porównań na pięciu rynkach, zero rozjazdów).

## Uruchomienie — trzy kroki

### 1. Wgraj skill na konto Claude

Spakuj katalog `research-spolki` do ZIP-a (razem z podkatalogiem `references`), a potem
na **claude.ai → Settings → Capabilities → Skills → Upload skill**. Jeśli masz tam już
starszą wersję `research-spolki`, podmień ją — nowa wie o API, stara opisuje plik
`data/snapshots/latest.json`, który nigdy nie powstał.

Gotowy ZIP: `claude-projekt/research-spolki.zip`.

### 2. Załóż Projekt

Na claude.ai → **Projects → Create project**, nazwij go np. „Research spółek".
Otwórz instrukcje Projektu i wklej całą treść `INSTRUKCJE-PROJEKTU.md` **od linii `---`
w dół** (to, co nad nią, to instrukcja dla Ciebie, nie dla modelu).

Upewnij się, że w Projekcie działa **wyszukiwanie w sieci** — bez niego zostaną same
dane ze screenera, a sprawozdania, powody spadków i transakcje insiderów wymagają sieci.

### 3. Sprawdź, że działa

Trzy pytania, każde sprawdza inną warstwę:

1. **„Co dziś warto obejrzeć?"** — powinien sięgnąć po `/api/dane/rankingi` i pokazać
   kilka spółek z uzasadnieniem. Sprawdza dostęp do API.
2. **„Zrób research MMM"** — powinien wyjść pełny raport ze strukturą z `SKILL.md`,
   z tabelą pięciu lat wyników i planem na trzy transze. Sprawdza skill i sieć.
3. **„Ile akcji KO kupię za 5000 zł?"** — powinien pobrać kurs z NBP, policzyć sztuki,
   podać resztę gotówki i sprawdzić płynność. Sprawdza `pozycja.md`.

Jeśli w odpowiedzi nie widzisz **daty migawki** ani **nazw poziomów** przy stopie
(np. „dołek swingu 1D z 2026-08-21"), to znaczy, że model nie sięgnął po API i zgaduje
— dopytaj wprost: „skąd masz te poziomy?".

## Gdy coś nie działa

| objaw | przyczyna |
|---|---|
| „nie mam dostępu do tego adresu" | wyszukiwanie/pobieranie w sieci wyłączone w Projekcie |
| migawka starsza niż 3 dni robocze | nie wykonał się codzienny skan (GitHub Actions) |
| `404` z `/api/dane/spolka/...` | zły ticker albo spółka spoza uniwersum — sprawdź `/api/dane/szukaj` |
| `404` z `/api/dane/notowania/...` | Yahoo nie zna tickera albo historia krótsza niż 60 sesji |
| poziomy bez nazw, „okolice 42,80" | model nie użył API — przypomnij o zasadzie nr 2 z instrukcji Projektu |
| pyta o zgodę na kolejne strony | sięga po źródło, które jest już w API — przypomnij zasadę „jedna domena" z instrukcji Projektu |

## Czego ta maszyna nie robi

- **Nie zna Twojego portfela.** Nie wie, co masz otwarte, więc nie ostrzeże, że
  proponuje drugą pozycję na spółce, którą już masz. Trzeba jej to powiedzieć.
- **Nie ma danych w czasie rzeczywistym.** Migawka jest z wczorajszego zamknięcia,
  notowania z ostatniej sesji. Do wejścia na otwarciu sprawdź kurs u brokera.
- **Nie zapisuje planów.** Plan dnia (`/plan` w aplikacji) to osobny mechanizm,
  z bramką kontrolną i rozliczaniem wyników. Raport z Claude jest materiałem do decyzji,
  nie wpisem do bazy.
- **Nie jest doradcą inwestycyjnym** i ma to napisane w instrukcjach.
