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
      "odsiewać „spadające noże” od realnych okazji.",
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
