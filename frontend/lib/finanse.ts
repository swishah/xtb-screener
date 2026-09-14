/**
 * Sprawozdania finansowe pobierane PO STRONIE SERWERA.
 *
 * DLACZEGO TO TU JEST. Maszyna researchowa w Claude pyta użytkownika o zgodę
 * przy każdej NOWEJ domenie, którą chce pobrać. Skill wysyłał ją na SEC,
 * biznesradar, stockanalysis i Yahoo, więc jeden research kończył się lawiną
 * okienek „czy pozwolić na dostęp do...". Rozwiązaniem nie jest szybsze
 * klikanie, tylko ograniczenie liczby domen: wszystko, co da się pobrać
 * u nas, ma wychodzić spod JEDNEGO adresu, zatwierdzonego raz.
 *
 * ŹRÓDŁO: punkt `fundamentals-timeseries` Yahoo — ten sam, z którego korzysta
 * yfinance po stronie Pythona. Zmierzone: odpowiada 200 BEZ ciasteczka i bez
 * żetonu, także dla GPW (ALE.WA) i Frankfurtu (BAS.DE). Starszy punkt
 * `quoteSummary` odpowiada 401 („Invalid Cookie") i celowo go NIE używamy —
 * wymagałby podszywania się pod przeglądarkę.
 *
 * To NIE jest scraping: to publiczny punkt danych zwracający JSON, odpytywany
 * raz na spółkę, bez omijania czegokolwiek.
 */

/** Roczne pozycje, których naprawdę używa raport. Więcej = większa paczka. */
const POZYCJE_ROCZNE = [
  "TotalRevenue",
  "CostOfRevenue",
  "GrossProfit",
  "OperatingIncome",
  "NetIncome",
  "DilutedEPS",
  "EBITDA",
  "OperatingCashFlow",
  "CapitalExpenditure",
  "FreeCashFlow",
  "TotalDebt",
  "CashAndCashEquivalents",
  "StockholdersEquity",
  "DilutedAverageShares",
] as const;

/** Kwartalne — węższy zestaw, bo służą wyłącznie do oceny ostatnich trendów. */
const POZYCJE_KWARTALNE = [
  "TotalRevenue",
  "GrossProfit",
  "OperatingIncome",
  "NetIncome",
  "DilutedEPS",
  "OperatingCashFlow",
] as const;

const TIMESERIES =
  "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/";

/** Od 2015 roku — Yahoo i tak oddaje zwykle cztery ostatnie okresy roczne. */
const OD = 1420070400;

export type Okres = {
  okres: string;
  waluta: string;
  [pozycja: string]: string | number | null;
};

export type Finanse = {
  ticker: string;
  waluta_raportowania: string | null;
  lata: Okres[];
  kwartaly: Okres[];
  uwagi: string[];
};

function zaokr(x: number, cyfry: number): number {
  return Number(x.toFixed(cyfry));
}

function licz(a: unknown, b: unknown, mnoznik = 100): number | null {
  if (typeof a !== "number" || typeof b !== "number" || b === 0) return null;
  return zaokr((a / b) * mnoznik, 2);
}

type Punkt = {
  asOfDate?: string;
  currencyCode?: string;
  reportedValue?: { raw?: number };
};

/**
 * Jedno zapytanie po wszystkie serie naraz. Yahoo przyjmuje listę typów
 * rozdzieloną przecinkami, więc pełne sprawozdanie kosztuje jedno pobranie,
 * a nie czternaście.
 */
async function serie(
  ticker: string,
  przedrostek: "annual" | "quarterly",
  pozycje: readonly string[],
): Promise<Map<string, Map<string, { wartosc: number; waluta: string }>>> {
  const typy = pozycje.map((p) => `${przedrostek}${p}`).join(",");
  const adres =
    `${TIMESERIES}${encodeURIComponent(ticker)}` +
    `?symbol=${encodeURIComponent(ticker)}&type=${typy}` +
    `&period1=${OD}&period2=${Math.floor(Date.now() / 1000)}`;

  const odp = await fetch(adres, {
    headers: { "User-Agent": "xtb-screener/1.0" },
    signal: AbortSignal.timeout(20000),
    cache: "no-store",
  });
  if (!odp.ok) return new Map();

  const dane = await odp.json();
  const wyniki: unknown[] = dane?.timeseries?.result ?? [];

  // Klucz zewnętrzny: okres (data). Wewnętrzny: nazwa pozycji. Odwrotnie niż
  // przychodzi z Yahoo, bo raport czyta się wierszami po latach, nie kolumnami.
  const wgOkresu = new Map<string, Map<string, { wartosc: number; waluta: string }>>();
  for (const surowy of wyniki) {
    const r = surowy as Record<string, unknown>;
    const typ = (r.meta as { type?: string[] })?.type?.[0];
    if (!typ) continue;
    const nazwa = typ.replace(/^annual|^quarterly/, "");
    for (const p of (r[typ] as Punkt[]) ?? []) {
      const data = p?.asOfDate;
      const wartosc = p?.reportedValue?.raw;
      if (!data || typeof wartosc !== "number") continue;
      if (!wgOkresu.has(data)) wgOkresu.set(data, new Map());
      wgOkresu.get(data)!.set(nazwa, {
        wartosc,
        waluta: String(p.currencyCode ?? ""),
      });
    }
  }
  return wgOkresu;
}

function naOkresy(
  wgOkresu: Map<string, Map<string, { wartosc: number; waluta: string }>>,
  pozycje: readonly string[],
): Okres[] {
  return [...wgOkresu.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([data, pola]) => {
      const wiersz: Okres = { okres: data, waluta: "" };
      for (const p of pozycje) {
        const v = pola.get(p);
        wiersz[p] = v ? v.wartosc : null;
        if (v?.waluta) wiersz.waluta = v.waluta;
      }
      return wiersz;
    });
}

/**
 * Wskaźniki, dla których trzeba mieć licznik i mianownik osobno — dlatego
 * liczymy je tutaj, a nie zostawiamy modelowi. Marża policzona w rozmowie
 * bywa policzona z dwóch liczb z różnych lat.
 */
function dolozWskazniki(okresy: Okres[]): void {
  okresy.forEach((o, i) => {
    o.marza_brutto_pct = licz(o.GrossProfit, o.TotalRevenue);
    o.marza_operacyjna_pct = licz(o.OperatingIncome, o.TotalRevenue);
    o.marza_netto_pct = licz(o.NetIncome, o.TotalRevenue);

    // Najważniejsza pojedyncza kontrola w całym sprawozdaniu: zysk rosnący
    // przy płaskich przepływach operacyjnych to najczęstszy wczesny sygnał,
    // że coś jest nie tak z jakością zysku.
    o.przeplywy_do_zysku = licz(o.OperatingCashFlow, o.NetIncome, 1);

    const poprzedni = okresy[i - 1];
    o.dynamika_przychodow_pct =
      poprzedni && typeof o.TotalRevenue === "number"
        ? licz(
            o.TotalRevenue - (poprzedni.TotalRevenue as number),
            poprzedni.TotalRevenue,
          )
        : null;

    if (typeof o.TotalDebt === "number" && typeof o.CashAndCashEquivalents === "number") {
      const netto = o.TotalDebt - o.CashAndCashEquivalents;
      o.dlug_netto = netto;
      o.dlug_netto_do_ebitda = licz(netto, o.EBITDA, 1);
    }
  });
}

/**
 * Sprawozdania jednej spółki. `null`, gdy Yahoo nie ma dla niej danych —
 * dotyczy to ETF-ów, funduszy i części małych spółek, i jest to informacja,
 * nie awaria.
 */
export async function finanse(ticker: string): Promise<Finanse | null> {
  try {
    const [roczne, kwartalne] = await Promise.all([
      serie(ticker, "annual", POZYCJE_ROCZNE),
      serie(ticker, "quarterly", POZYCJE_KWARTALNE),
    ]);

    const lata = naOkresy(roczne, POZYCJE_ROCZNE);
    const kwartaly = naOkresy(kwartalne, POZYCJE_KWARTALNE);
    if (lata.length === 0 && kwartaly.length === 0) return null;

    dolozWskazniki(lata);
    dolozWskazniki(kwartaly);

    const waluta = lata.find((l) => l.waluta)?.waluta ?? null;
    const uwagi: string[] = [];
    if (lata.length < 4) {
      uwagi.push(
        `Tylko ${lata.length} okresów rocznych — krótsza historia niż zwykle. ` +
          "Przy debiucie albo wydzieleniu to sama w sobie jest informacja o ryzyku.",
      );
    }
    uwagi.push(
      "Waluta SPRAWOZDANIA bywa inna niż waluta notowania. Spółka raportująca " +
        "w euro, a notowana w złotych, ma wynik przesunięty o kurs.",
    );
    uwagi.push(
      "Liczby są takie, jak podał je Yahoo — bez korekt o zdarzenia jednorazowe. " +
        "Skokowa zmiana zysku netto przy stabilnych przychodach to zwykle odpis " +
        "albo sprzedaż aktywów; sprawdź to w raporcie spółki, zanim policzysz z tego trend.",
    );

    return { ticker, waluta_raportowania: waluta, lata, kwartaly, uwagi };
  } catch {
    return null;
  }
}
