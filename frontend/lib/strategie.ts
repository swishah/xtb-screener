/**
 * Strategie — lustro STRATEGIES / STRATEGY_DESCRIPTIONS / STRATEGY_COLUMNS
 * ze strony Pythona (core/scanner.py oraz ui/strategie.py).
 *
 * Wyniki strategii są LICZONE PODCZAS SKANU i leżą gotowe w migawce, więc tutaj
 * niczego nie przeliczamy — wystarczy posortować. To celowa decyzja projektowa:
 * skan przetwarza ~1300 instrumentów raz dziennie, a nie przy każdym wejściu
 * na stronę.
 *
 * Maksima pochodzą ze STRATEGY_MAX_SCORES i były wyznaczone empirycznie —
 * wywołaniem funkcji na wyidealizowanych danych, nie liczeniem na piechotę.
 * Służą do pokazania wyniku jako części maksimum ("7 / 10").
 *
 * Zero importów z Node: plik trafia też do przeglądarki.
 */
export type Strategia = {
  klucz: string;
  nazwa: string;
  kolumnaScore: string;
  maks: number;
  opis: string;
  kolumny: string[];
};

export const STRATEGIE: Strategia[] = [
  {
    klucz: "deep-value",
    nazwa: "Deep Value (spadki od ATH)",
    kolumnaScore: "Score: Deep Value",
    maks: 10,
    opis:
      "Premiuje duży dystans od ATH, ale tylko gdy fundamenty (ROE, marża " +
      "operacyjna, wzrost EPS, zadłużenie) wciąż wyglądają zdrowo — ma to " +
      "odsiewać „spadające noże” od realnych okazji. UWAGA: to strategia " +
      "spółek PRZECENIONYCH, nie TANICH. Pomiar na migawce 2026-09-04: " +
      "mediana C/Z w czołówce 20,2 przy 21,6 w całym uniwersum (czyli bez " +
      "różnicy), za to mediana spadku od szczytu −54,8% przy −19,7%. Jeśli " +
      "szukasz niskiej wyceny, wybierz „Wartość złożona”.",
    kolumny: [
      "pct_from_ath", "ROE (%)", "Marża Operac. (%)", "Wzrost EPS (%)",
      "Dług/Kapitał", "RSI", "Liczba flag",
    ],
  },
  {
    klucz: "momentum",
    nazwa: "Momentum",
    kolumnaScore: "Score: Momentum",
    maks: 8,
    opis:
      "Premiuje spółki w silnym, potwierdzonym trendzie wzrostowym: cena nad " +
      "wszystkimi średnimi, byczy MACD, rosnący wolumen, blisko ATH, RSI " +
      "w zdrowej strefie (50–70, nie wykupione).",
    kolumny: [
      "RSI", "volume_ratio", "SMA20", "SMA50", "pct_from_ath", "Liczba flag",
    ],
  },
  {
    klucz: "dywidendowa",
    nazwa: "Dywidendowa",
    kolumnaScore: "Score: Dywidendowa",
    maks: 7,
    opis:
      "Premiuje solidną stopę dywidendy przy zdrowych fundamentach i historii " +
      "nieprzerwanych wypłat przez ostatnie 3 lata.",
    kolumny: [
      "Stopa Dyw. (%)", "Lata z dywidendą (3Y)", "C/Z (P/E)", "ROE (%)",
      "Dług/Kapitał", "Liczba flag",
    ],
  },
  {
    klucz: "dywidenda-okazja",
    nazwa: "Dywidenda-okazja (sezon dywidendowy)",
    kolumnaScore: "Score: Dywidenda-Okazja",
    maks: 13,
    opis:
      "Szuka spółek, które regularnie płacą dywidendę i zapłaciły w POPRZEDNIM " +
      "roku, ale JESZCZE NIE zapłaciły w bieżącym — wypłata jest więc dopiero " +
      "przed nimi. Plus payout ratio i wzrost przychodów, żeby odróżnić okazję " +
      "od pułapki dywidendowej.",
    kolumny: [
      "Stopa Dyw. (%)", "Dyw. w poprzednim roku", "Dyw. w tym roku",
      "Przyszła dywidenda", "Zmiana ceny (1Y%)", "Payout ratio (%)",
      "Wzrost przychodów (%)", "Marża netto (%)", "Liczba flag",
    ],
  },
  {
    klucz: "f-score",
    nazwa: "Jakość fundamentalna (F-Score uproszczony)",
    kolumnaScore: "Score: F-Score Lite",
    maks: 8,
    opis:
      "Inspirowane Piotroski F-Score, ale liczone WYŁĄCZNIE na bieżącym stanie — " +
      "bez porównań rok-do-roku z pełnych sprawozdań, bo to spowolniłoby skan " +
      "1300 spółek. Sprawdza osiem sygnałów jakości: ROA, przepływy operacyjne, " +
      "ROE, marżę netto, wzrost EPS i przychodów, zadłużenie, marżę brutto.",
    kolumny: [
      "ROA (%)", "Przepływy operacyjne (mln)", "ROE (%)", "Marża netto (%)",
      "Wzrost EPS (%)", "Wzrost przychodów (%)", "Dług/Kapitał",
      "Marża brutto (%)", "Liczba flag",
    ],
  },
  {
    klucz: "blisko-szczytu",
    nazwa: "Blisko szczytu (52 tyg.)",
    kolumnaScore: "Score: Blisko Szczytu",
    maks: 8,
    opis:
      "Wg George'a i Hwanga (Journal of Finance, 2004): bliskość rocznego " +
      "szczytu przewiduje przyszłe zwroty lepiej niż same przeszłe stopy " +
      "zwrotu, a efekt nie odwraca się w długim terminie. Liczy się jedna " +
      "rzecz — jak blisko 52-tygodniowego maksimum jest kurs — plus trzy " +
      "zabezpieczenia (RSI, wzrost EPS, zadłużenie), żeby odsiać jednorazowe " +
      "wystrzały. To NIE to samo co Momentum, które patrzy na średnie i MACD: " +
      "w migawce 2026-09-04 czołówki obu miały wspólne 2 spółki na 30.",
    kolumny: [
      "Sektor", "52-tyg. maksimum", "pct_from_ath", "RSI", "Wzrost EPS (%)",
      "Dług/Kapitał", "Liczba flag",
    ],
  },
  {
    klucz: "konserwatywna",
    nazwa: "Formuła konserwatywna (lite)",
    kolumnaScore: "Score: Konserwatywna",
    maks: 8,
    opis:
      "Wg Blitza i van Vlieta (2018): niska zmienność, oddawanie gotówki " +
      "akcjonariuszom i dodatnie momentum. W ich teście 15,1% rocznie w USA " +
      "od 1929, powtórzone w Europie, Japonii i na rynkach wschodzących. " +
      "„Lite” oznacza dwa świadome uproszczenia: beta zamiast zmienności " +
      "36-miesięcznej oraz sama dywidenda zamiast net payout yield, bo " +
      "historii skupu akcji własnych nie mamy. Spółki oddające gotówkę " +
      "głównie przez buyback są tu niedoszacowane.",
    kolumny: [
      "Beta", "Zmiana ceny (1Y%)", "Stopa Dyw. (%)", "Payout ratio (%)",
      "Liczba flag",
    ],
  },
  {
    klucz: "wartosc-zlozona",
    nazwa: "Wartość złożona (C/Z + C/WK + C/CF)",
    kolumnaScore: "Score: Wartość Złożona",
    maks: 11,
    opis:
      "Trzy miary wyceny zamiast jednej, każda ważona tak samo. Powstała, bo " +
      "pomiar pokazał, że Deep Value selekcjonuje spółki przecenione, a nie " +
      "tanie — czynnik wartości był u nas nieobsadzony. Literatura (Value " +
      "Composite O'Shaughnessy'ego) pokazuje, że mieszanka miar bije " +
      "pojedynczy wskaźnik, bo każda ma inną słabość. Oryginał używa sześciu " +
      "miar; my mamy trzy. Plus kontrola marży netto i ROE, żeby „tanio” nie " +
      "znaczyło „zarabia coraz mniej”.",
    kolumny: [
      "C/Z (P/E)", "C/WK (P/B)", "Kapitalizacja (mld)",
      "Przepływy operacyjne (mln)", "Marża netto (%)", "ROE (%)", "Liczba flag",
    ],
  },
];

export function znajdzStrategie(klucz: string | undefined): Strategia {
  return STRATEGIE.find((s) => s.klucz === klucz) ?? STRATEGIE[0];
}

/**
 * Nagłówki kolumn. Większość kluczy jest już czytelna po polsku — mapa
 * obejmuje tylko te, które zostały w kodzie po angielsku.
 */
const ETYKIETY: Record<string, string> = {
  pct_from_ath: "Od ATH",
  volume_ratio: "Wolumen ×",
  SMA20: "SMA20",
  SMA50: "SMA50",
  "Liczba flag": "Flagi",
  "Przepływy operacyjne (mln)": "Przepływy (mln)",
  "Lata z dywidendą (3Y)": "Lat z dyw.",
  "52-tyg. maksimum": "52-tyg. maks.",
  "Kapitalizacja (mld)": "Kap. (mld)",
  "Zmiana ceny (1Y%)": "Zmiana 1R",
  "Dyw. w poprzednim roku": "Dyw. rok temu",
  "Dyw. w tym roku": "Dyw. w tym roku",
  "Przyszła dywidenda": "Najbliższa dyw.",
};

export function etykieta(kolumna: string): string {
  return ETYKIETY[kolumna] ?? kolumna;
}

/** Kolumny procentowe — do dopisania znaku % przy wartości. */
export function czyProcent(kolumna: string): boolean {
  return kolumna.includes("(%)") || kolumna === "pct_from_ath";
}
