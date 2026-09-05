/**
 * Kategorie i moduły — lustro MODULE_CATEGORIES z ui/common.py.
 *
 * Świadome powtórzenie: frontend i Streamlit to dwa osobne programy w dwóch
 * językach, a jedyne, co dzielą, to baza danych. Wspólny plik konfiguracyjny
 * kosztowałby więcej (parsowanie, synchronizacja) niż ta krótka lista. Przy
 * dodawaniu modułu trzeba dopisać go w OBU miejscach — po stronie Pythona
 * pilnuje tego scripts/sprawdz_moduly.py.
 *
 * `sciezka: null` znaczy "jeszcze nie przeniesione" — kafelek jest widoczny,
 * ale przygaszony i nieklikalny. Lepsze niż udawanie, że wszystko działa.
 */
export type Modul = {
  nazwa: string;
  opis: string;
  sciezka: string | null;
};

export type Kategoria = {
  etykieta: string;
  klasa: string;
  moduly: Modul[];
};

export const KATEGORIE: Kategoria[] = [
  {
    etykieta: "Przegląd rynku",
    klasa: "k1",
    moduly: [
      { nazwa: "Screener", opis: "Wszystko naraz, z filtrami", sciezka: "/screener" },
      { nazwa: "Globalny przegląd", opis: "Szerokość rynku, heatmapy", sciezka: null },
      { nazwa: "Dashboard", opis: "Widok kafelkowy", sciezka: null },
    ],
  },
  {
    etykieta: "Strategie",
    klasa: "k2",
    moduly: [
      { nazwa: "Strategie", opis: "5 gotowych rankingów", sciezka: "/strategie" },
      { nazwa: "Własny scoring", opis: "Twoje wagi wskaźników", sciezka: null },
    ],
  },
  {
    etykieta: "Analiza spółki",
    klasa: "k3",
    moduly: [
      { nazwa: "Profil spółki", opis: "Wybierz spółkę w screenerze", sciezka: "/screener" },
      { nazwa: "vs Sektor", opis: "Na tle mediany branży", sciezka: null },
      { nazwa: "Tanie vs sektor", opis: "Niskie C/Z w swoim sektorze", sciezka: "/tanie" },
    ],
  },
  {
    etykieta: "Dywidendy",
    klasa: "k4",
    moduly: [{ nazwa: "Dywidendy", opis: "Tanio przed sezonem", sciezka: null }],
  },
  {
    etykieta: "Moje",
    klasa: "k5",
    moduly: [
      { nazwa: "Watchlist", opis: "Obserwowane z notatkami", sciezka: null },
      { nazwa: "Analiza transakcji", opis: "Import z XTB", sciezka: null },
    ],
  },
  {
    etykieta: "Backtesty",
    klasa: "k6",
    moduly: [
      { nazwa: "Backtest strategii", opis: "Skuteczność wstecz", sciezka: null },
      { nazwa: "Backtest spółki", opis: "Jedna spółka w czasie", sciezka: null },
    ],
  },
];
