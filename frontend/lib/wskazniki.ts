/**
 * Katalog wskaźników: co znaczą, jak je formatować i kiedy wartość jest dobra.
 *
 * Każdy wskaźnik dostaje w interfejsie KRÓTKĄ OCENĘ ("dobrze" / "przeciętnie" /
 * "słabo") oraz pytajnik z wyjaśnieniem i porównaniem do mediany branży.
 *
 * Ocena powstaje na dwa sposoby:
 *   1. PROGI BEZWZGLĘDNE — tam, gdzie wartość ma sens sama w sobie, niezależnie
 *      od branży (RSI, payout ratio, zadłużenie, beta).
 *   2. WZGLĘDEM MEDIANY BRANŻY — wszędzie indziej. Marża 8% jest słaba
 *      w oprogramowaniu i świetna w handlu detalicznym, więc porównywanie
 *      do stałej liczby wprowadzałoby w błąd.
 *
 * Progi bezwzględne ustawione na podstawie ROZKŁADÓW w tej bazie (kwartyle
 * z migawki 1281 spółek), nie z wyczucia — patrz komentarze przy wartościach.
 *
 * Zero importów z Node: plik trafia też do przeglądarki.
 */
import { liczba, type Instrument } from "./filtry";

export type Kierunek = "wyzej-lepiej" | "nizej-lepiej" | "neutralny";
export type Ocena = "dobrze" | "przeciętnie" | "słabo" | null;

export type DefWskaznika = {
  klucz: string;
  etykieta: string;
  jednostka?: string;
  kierunek: Kierunek;
  opis: string;
  /** Progi bezwzględne; gdy brak, ocena liczy się względem mediany branży. */
  progi?: { dobrze: number; slabo: number };
  /** Wskaźnik pokazujemy, ale świadomie NIE oceniamy. */
  bezOceny?: boolean;
};

export type GrupaWskaznikow = {
  nazwa: string;
  wskazniki: DefWskaznika[];
};

export const GRUPY: GrupaWskaznikow[] = [
  {
    nazwa: "Wycena",
    wskazniki: [
      {
        klucz: "C/Z (P/E)",
        etykieta: "C/Z",
        kierunek: "nizej-lepiej",
        opis:
          "Cena do zysku: ile płacisz za złotówkę rocznego zysku. Niżej znaczy " +
          "taniej, ale bardzo nisko bywa ostrzeżeniem — rynek może wyceniać " +
          "spodziewany spadek zysków. Mediana w tej bazie to około 22.",
      },
      {
        klucz: "Forward C/Z",
        etykieta: "Forward C/Z",
        kierunek: "nizej-lepiej",
        opis:
          "To samo co C/Z, ale liczone na PROGNOZOWANYM zysku z kolejnego roku. " +
          "Gdy jest wyraźnie niższe od zwykłego C/Z, analitycy spodziewają się " +
          "wzrostu zysków; gdy wyższe — spadku.",
      },
      {
        klucz: "C/WK (P/B)",
        etykieta: "C/WK",
        kierunek: "nizej-lepiej",
        opis:
          "Cena do wartości księgowej. Poniżej 1 płacisz mniej, niż wynosi " +
          "księgowa wartość majątku spółki. Wskaźnik ma sens głównie dla banków " +
          "i przemysłu; dla spółek technologicznych bywa mylący, bo ich wartość " +
          "tkwi w rzeczach, których bilans nie wykazuje.",
      },
      {
        klucz: "Kapitalizacja (mld)",
        etykieta: "Kapitalizacja",
        jednostka: " mld",
        kierunek: "neutralny",
        bezOceny: true,
        opis:
          "Wartość rynkowa całej spółki. Duże spółki są zwykle stabilniejsze, " +
          "małe dają większy potencjał wzrostu przy większym ryzyku. Ani duża, " +
          "ani mała nie jest sama w sobie lepsza.",
      },
    ],
  },
  {
    nazwa: "Rentowność",
    wskazniki: [
      {
        klucz: "ROE (%)",
        etykieta: "ROE",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Zwrot z kapitału własnego: ile zysku spółka wypracowuje z pieniędzy " +
          "właścicieli. Mediana w tej bazie to około 14%. Uwaga — wysokie ROE " +
          "przy dużym zadłużeniu jest efektem dźwigni, nie samej efektywności.",
      },
      {
        klucz: "ROA (%)",
        etykieta: "ROA",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Zwrot z aktywów: ile zysku daje cały majątek spółki, niezależnie od " +
          "tego, czy sfinansowano go kapitałem czy długiem. Odporniejszy na " +
          "dźwignię niż ROE. Mediana w bazie to około 5%.",
      },
      {
        klucz: "Marża Operac. (%)",
        etykieta: "Marża operacyjna",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Ile z każdej złotówki przychodu zostaje po kosztach działalności, " +
          "przed odsetkami i podatkiem. Mocno zależy od branży, dlatego ocena " +
          "porównuje ją z medianą sektora, a nie ze stałą liczbą.",
      },
      {
        klucz: "Marża netto (%)",
        etykieta: "Marża netto",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Ile z każdej złotówki przychodu zostaje na czysto, po wszystkich " +
          "kosztach, odsetkach i podatkach.",
      },
      {
        klucz: "Marża brutto (%)",
        etykieta: "Marża brutto",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Przychody minus bezpośredni koszt wytworzenia. Pokazuje siłę " +
          "cenową — im wyżej, tym większy zapas na koszty stałe i gorsze " +
          "kwartały. Różnice między branżami są ogromne.",
      },
    ],
  },
  {
    nazwa: "Wzrost",
    wskazniki: [
      {
        klucz: "Wzrost EPS (%)",
        etykieta: "Wzrost zysku na akcję",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Jak zmienił się zysk przypadający na jedną akcję. Wartość ujemna " +
          "znaczy, że zysk spadł. Bywa bardzo zmienna z kwartału na kwartał, " +
          "więc pojedynczy odczyt nie przesądza o trendzie.",
      },
      {
        klucz: "Wzrost przychodów (%)",
        etykieta: "Wzrost przychodów",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Zmiana sprzedaży. Stabilniejszy od zysku, bo trudniej nim sterować " +
          "księgowo. Rosnące przychody przy spadającym zysku wskazują na " +
          "presję kosztową.",
      },
      {
        klucz: "Zmiana ceny (1Y%)",
        etykieta: "Kurs 12 miesięcy",
        jednostka: "%",
        kierunek: "neutralny",
        bezOceny: true,
        opis:
          "Zmiana kursu przez ostatni rok. Sam w sobie nie mówi, czy spółka " +
          "jest dobra — duży spadek bywa okazją albo ostrzeżeniem, i właśnie " +
          "od odróżniania tych dwóch przypadków jest reszta wskaźników.",
      },
    ],
  },
  {
    nazwa: "Dywidenda",
    wskazniki: [
      {
        klucz: "Stopa Dyw. (%)",
        etykieta: "Stopa dywidendy",
        jednostka: "%",
        kierunek: "wyzej-lepiej",
        opis:
          "Roczna dywidenda w stosunku do ceny akcji. Bardzo wysoka bywa " +
          "pułapką: często wynika ze spadku kursu, a nie ze wzrostu wypłaty, " +
          "i zapowiada jej obcięcie. Sprawdź razem z payout ratio.",
      },
      {
        klucz: "Payout ratio (%)",
        etykieta: "Payout ratio",
        jednostka: "%",
        kierunek: "nizej-lepiej",
        // Progi z rozkładu: mediana 43%, trzeci kwartyl 70%, dziesiąty decyl 115%.
        progi: { dobrze: 60, slabo: 90 },
        opis:
          "Jaka część zysku idzie na dywidendę. Poniżej 60% zostaje zapas na " +
          "inwestycje i gorszy rok. Powyżej 90% spółka wypłaca prawie cały " +
          "zysk, a powyżej 100% — więcej, niż zarabia, czyli z oszczędności " +
          "albo długu. To rzadko da się utrzymać.",
      },
      {
        klucz: "Lata z dywidendą (3Y)",
        etykieta: "Lat z dywidendą (z 3)",
        kierunek: "wyzej-lepiej",
        progi: { dobrze: 3, slabo: 1 },
        opis:
          "Ile z ostatnich trzech lat spółka wypłaciła dywidendę. Trzy na trzy " +
          "znaczy nieprzerwaną historię w tym krótkim oknie — to nie to samo, " +
          "co wieloletni staż dywidendowy.",
      },
    ],
  },
  {
    nazwa: "Zadłużenie i ryzyko",
    wskazniki: [
      {
        klucz: "Dług/Kapitał",
        etykieta: "Dług do kapitału",
        jednostka: "%",
        kierunek: "nizej-lepiej",
        // Progi z rozkładu: mediana 71, trzeci kwartyl 133, dziesiąty decyl 228.
        progi: { dobrze: 50, slabo: 150 },
        opis:
          "Zadłużenie w stosunku do kapitału własnego, w procentach. 100 znaczy " +
          "tyle samo długu co kapitału. Mediana w tej bazie to około 71%. " +
          "Wysokie zadłużenie podnosi zysk w dobrych czasach i przyspiesza " +
          "kłopoty w złych.",
      },
      {
        klucz: "Beta",
        etykieta: "Beta",
        kierunek: "neutralny",
        opis:
          "Jak mocno kurs rusza się względem rynku. 1 znaczy „tak jak rynek”, " +
          "powyżej 1,3 — wyraźnie gwałtowniej w obie strony, poniżej 0,7 — " +
          "spokojniej. Mediana w bazie to około 0,84. To miara zmienności, " +
          "nie jakości spółki.",
        bezOceny: true,
      },
      {
        klucz: "Przepływy operacyjne (mln)",
        etykieta: "Przepływy operacyjne",
        jednostka: " mln",
        kierunek: "wyzej-lepiej",
        opis:
          "Gotówka wypracowana przez podstawową działalność. Zysk księgowy da " +
          "się poprawić zapisami, gotówki nie. Wartość ujemna znaczy, że " +
          "działalność pochłania pieniądze zamiast je przynosić.",
      },
      {
        klucz: "% udziałów instytucji",
        etykieta: "Udział instytucji",
        jednostka: "%",
        kierunek: "neutralny",
        bezOceny: true,
        opis:
          "Jaka część akcji jest w rękach funduszy i innych instytucji. Wysoki " +
          "udział bywa czytany jako wotum zaufania, ale oznacza też, że " +
          "wyjście dużego gracza mocniej ruszy kursem. Dane bywają niedokładne " +
          "i przekraczają 100%.",
      },
    ],
  },
  {
    nazwa: "Technika",
    wskazniki: [
      {
        klucz: "RSI",
        etykieta: "RSI",
        kierunek: "neutralny",
        opis:
          "Wskaźnik siły względnej, skala 0–100. Poniżej 30 mówi się " +
          "o wyprzedaniu (kurs spadał szybko), powyżej 70 o wykupieniu. " +
          "To sygnał o TEMPIE ruchu, nie o wartości spółki — sam w sobie " +
          "nie jest powodem do kupna ani sprzedaży.",
        bezOceny: true,
      },
      {
        klucz: "pct_from_ath",
        etykieta: "Od szczytu (ATH)",
        jednostka: "%",
        kierunek: "neutralny",
        bezOceny: true,
        opis:
          "O ile kurs jest poniżej historycznego maksimum. Duży dystans to " +
          "punkt wyjścia strategii Deep Value, ale dopiero razem ze zdrowymi " +
          "fundamentami odróżnia okazję od spadającego noża.",
      },
      {
        klucz: "volume_ratio",
        etykieta: "Wolumen vs średnia",
        jednostka: "×",
        kierunek: "neutralny",
        bezOceny: true,
        opis:
          "Dzisiejszy obrót w stosunku do średniej. Powyżej 1,3 dzieje się coś " +
          "nietypowego — warto sprawdzić newsy. Mediana w bazie to 0,92.",
      },
    ],
  },
];

/** Wszystkie wskaźniki na płasko — do wyszukiwania definicji po kluczu. */
export const WSZYSTKIE_WSKAZNIKI: DefWskaznika[] = GRUPY.flatMap((g) => g.wskazniki);

/**
 * Ocena wartości. Zwraca null, gdy nie ma czego oceniać — lepiej nie napisać
 * nic, niż napisać „przeciętnie” na podstawie niczego.
 */
export function ocen(
  def: DefWskaznika,
  wartosc: number | null,
  medianaSektora: number | null,
): Ocena {
  if (wartosc === null || def.bezOceny || def.kierunek === "neutralny") return null;

  if (def.progi) {
    const { dobrze, slabo } = def.progi;
    if (def.kierunek === "wyzej-lepiej") {
      if (wartosc >= dobrze) return "dobrze";
      if (wartosc <= slabo) return "słabo";
      return "przeciętnie";
    }
    if (wartosc <= dobrze) return "dobrze";
    if (wartosc >= slabo) return "słabo";
    return "przeciętnie";
  }

  if (medianaSektora === null) return null;

  // Margines liczony od WARTOŚCI BEZWZGLĘDNEJ mediany — inaczej przy ujemnej
  // medianie mnożenie odwracałoby kierunek porównania.
  const margines = Math.abs(medianaSektora) * 0.15;
  const lepszy =
    def.kierunek === "wyzej-lepiej"
      ? wartosc > medianaSektora + margines
      : wartosc < medianaSektora - margines;
  const gorszy =
    def.kierunek === "wyzej-lepiej"
      ? wartosc < medianaSektora - margines
      : wartosc > medianaSektora + margines;

  if (lepszy) return "dobrze";
  if (gorszy) return "słabo";
  return "przeciętnie";
}

/** Zdanie porównujące z branżą — trafia pod pytajnik, obok opisu wskaźnika. */
export function zdanieOSektorze(
  def: DefWskaznika,
  wartosc: number | null,
  mediana: number | null,
  sektor: string | undefined,
  liczbaSpolek: number,
): string | null {
  if (mediana === null || wartosc === null || !sektor) return null;
  const med = mediana.toLocaleString("pl-PL", { maximumFractionDigits: 2 });
  const jed = def.jednostka ?? "";
  const rel =
    Math.abs(wartosc - mediana) <= Math.abs(mediana) * 0.05
      ? "mniej więcej tyle samo"
      : wartosc > mediana
        ? "więcej"
        : "mniej";
  return `Mediana w sektorze „${sektor}” to ${med}${jed} (${liczbaSpolek} spółek) — ta spółka ma ${rel}.`;
}

/** Wartość wskaźnika w postaci gotowej do wyświetlenia. */
export function formatuj(def: DefWskaznika, surowa: unknown): string {
  const n = liczba(surowa);
  if (n === null) return "BRAK";
  const calkowita = Number.isInteger(n);
  const tekst = n.toLocaleString("pl-PL", {
    minimumFractionDigits: calkowita ? 0 : 2,
    maximumFractionDigits: calkowita ? 0 : 2,
  });
  return `${tekst}${def.jednostka ?? ""}`;
}

export function wartoscWskaznika(spolka: Instrument, klucz: string): number | null {
  return liczba(spolka[klucz]);
}
