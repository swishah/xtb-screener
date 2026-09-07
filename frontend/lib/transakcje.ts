/**
 * Analiza transakcji — ile taniej dało się kupić i czy sprzedaż nie była
 * za wczesna.
 *
 * TU JEST RUCH SIECIOWY I TO JEST ŚWIADOME. Moduł pobiera historię cen
 * z Yahoo dla tickerów, które poda użytkownik — inaczej nie ma czego liczyć,
 * bo własne migawki sięgają dopiero sierpnia 2026, a transakcje bywają
 * starsze. Precedens jest: `lib/newsy.ts` odpytuje Google News przy każdym
 * otwarciu profilu spółki. Zasada zostaje ta sama co w Streamlicie: pobieramy
 * WYŁĄCZNIE na wyraźne żądanie, nigdy przy zwykłym wejściu na stronę.
 *
 * PLIK UŻYTKOWNIKA NIE JEST NIGDZIE ZAPISYWANY. Przechodzi przez pamięć
 * procesu na czas jednej analizy i tyle — nie ląduje w bazie ani na dysku.
 */

// ---------------------------------------------------------------------------
// Tłumaczenie tickerów XTB → Yahoo (lustro `xtb_to_yahoo` z scanner.py)
// ---------------------------------------------------------------------------

/** Sufiks XTB (kraj) na sufiks Yahoo (giełda). Pusty = Yahoo nie używa sufiksu. */
const SUFIKSY: Record<string, string> = {
  // zweryfikowane na prawdziwym eksporcie
  PL: "WA", US: "", DE: "DE", FR: "PA", CH: "SW", UK: "L", IT: "MI",
  // z konwencji Yahoo, NIESPRAWDZONE — brak w eksporcie testowym
  ES: "MC", NL: "AS", PT: "LS", BE: "BR", AT: "VI",
  SE: "ST", NO: "OL", DK: "CO", FI: "HE", CZ: "PR", IE: "IR", HU: "BD",
};

/** Sam sufiks nie wystarcza: spółka zmieniła nazwę albo Yahoo ma inny symbol. */
const WYJATKI: Record<string, string> = {
  "CCC.PL": "MDV.WA", // CCC przemianowane na Modivo, razem z tickerem
  "TUI.DE": "TUI1.DE", // Yahoo prowadzi TUI na Xetrze jako TUI1
};

export function xtbNaYahoo(ticker: string): string {
  const t = String(ticker ?? "").trim().toUpperCase();
  if (!t) return "";
  if (WYJATKI[t]) return WYJATKI[t];
  if (!t.includes(".")) return t;
  const i = t.lastIndexOf(".");
  const baza = t.slice(0, i);
  const sufiks = SUFIKSY[t.slice(i + 1)];
  // Nieznany sufiks zostawiamy bez zmian — lepiej spróbować i nie znaleźć
  // danych, niż z góry odrzucić symbol, który może być poprawny.
  if (sufiks === undefined) return t;
  return sufiks === "" ? baza : `${baza}.${sufiks}`;
}

// ---------------------------------------------------------------------------
// Historia cen z Yahoo
// ---------------------------------------------------------------------------

export type Notowania = {
  /** Dni w kolejności rosnącej, jako "RRRR-MM-DD". */
  dni: string[];
  zamkniecie: number[];
  najwyzsze: number[];
  najnizsze: number[];
  /** Waluta notowania z Yahoo — "GBp" znaczy pensy, nie funty. */
  waluta: string;
};

const CHART =
  "https://query1.finance.yahoo.com/v8/finance/chart/";

/**
 * Dzienna historia cen. `null`, gdy Yahoo nie zna tickera albo nie odpowiada.
 *
 * Używamy publicznego punktu `chart`, tego samego, z którego korzysta
 * yfinance po stronie Pythona — dostajemy z niego również WALUTĘ notowania,
 * co jest tu potrzebne do wykrycia pensów (patrz `skalaCeny`).
 */
export async function notowania(ticker: string): Promise<Notowania | null> {
  try {
    const odp = await fetch(
      `${CHART}${encodeURIComponent(ticker)}?range=10y&interval=1d`,
      {
        headers: { "User-Agent": "xtb-screener/1.0" },
        signal: AbortSignal.timeout(20000),
        cache: "no-store",
      },
    );
    if (!odp.ok) return null;
    const dane = await odp.json();
    const wynik = dane?.chart?.result?.[0];
    const znaczniki: number[] | undefined = wynik?.timestamp;
    const kw = wynik?.indicators?.quote?.[0];
    if (!znaczniki || !kw) return null;

    const dni: string[] = [];
    const zamkniecie: number[] = [];
    const najwyzsze: number[] = [];
    const najnizsze: number[] = [];
    for (let i = 0; i < znaczniki.length; i++) {
      const c = kw.close?.[i];
      const h = kw.high?.[i];
      const l = kw.low?.[i];
      // Yahoo wstawia null w dniach bez sesji — taki wiersz pomijamy w całości,
      // zamiast wciągać go jako zero i psuć minima.
      if (typeof c !== "number" || typeof h !== "number" || typeof l !== "number") {
        continue;
      }
      dni.push(new Date(znaczniki[i] * 1000).toISOString().slice(0, 10));
      zamkniecie.push(c);
      najwyzsze.push(h);
      najnizsze.push(l);
    }
    if (dni.length === 0) return null;
    return {
      dni,
      zamkniecie,
      najwyzsze,
      najnizsze,
      waluta: String(wynik?.meta?.currency ?? ""),
    };
  } catch {
    return null;
  }
}

/**
 * Ile razy pomnożyć cenę od brokera, żeby zgadzała się z notowaniem Yahoo.
 *
 * Część giełd (przede wszystkim LSE) Yahoo podaje w SUBJEDNOSTKACH waluty —
 * pensach zamiast funtów — co sygnalizuje małą literą w kodzie ("GBp" zamiast
 * "GBP"). Broker podaje funty, więc bez korekty porównanie wychodzi zawyżone
 * stukrotnie. Realny przypadek z historii projektu: Wizz Air kupiony po 10,75
 * GBP wobec notowania 1074 pensy dawał „mogłeś kupić taniej o 9795%".
 */
export function skalaCeny(waluta: string): number {
  const w = String(waluta ?? "");
  if (!w) return 1;
  return w !== w.toUpperCase() ? 100 : 1;
}

// ---------------------------------------------------------------------------
// Analiza pojedynczej transakcji
// ---------------------------------------------------------------------------

export type Transakcja = {
  instrument: string;
  tickerXtb: string;
  ticker: string;
  dataZakupu: string;
  cenaZakupu: number;
  dataSprzedazy: string | null;
  cenaSprzedazy: number | null;
  status: "zamknięta" | "otwarta";
};

export type WynikTransakcji = {
  ticker: string;
  instrument: string;
  dataZakupu: string;
  cenaZakupu: number;
  minPoZakupie: number;
  dataMinimum: string;
  ileTaniej: number;
  rsiWDniuZakupu: number | null;
  odSzczytuWDniuZakupu: number | null;
  cenaSprzedazy: number | null;
  maksPoSprzedazy: number | null;
  niewykorzystanyWzrost: number | null;
  przeskalowana: boolean;
};

function rsi(zamkniecie: number[], okres = 14): number | null {
  if (zamkniecie.length <= okres) return null;
  let zyski = 0;
  let straty = 0;
  for (let i = zamkniecie.length - okres; i < zamkniecie.length; i++) {
    const d = zamkniecie[i] - zamkniecie[i - 1];
    if (d > 0) zyski += d;
    else straty -= d;
  }
  if (straty === 0) return zyski === 0 ? null : 100;
  const rs = zyski / straty;
  return Math.round((100 - 100 / (1 + rs)) * 10) / 10;
}

/**
 * Analiza „po fakcie" jednej transakcji.
 *
 * Lustro `analyze_trade()` z `core/scanner.py`: minimum ceny w oknie po
 * zakupie, wskaźniki z DNIA ZAKUPU (żeby wiedzieć, czy kupno wypadło w dołku
 * czy w trakcie odbicia) i — gdy podano sprzedaż — maksimum po niej.
 */
export function analizujTransakcje(
  t: Transakcja,
  n: Notowania,
  oknoDni: number,
  przeskaluj: boolean,
): WynikTransakcji | null {
  const skala = przeskaluj ? skalaCeny(n.waluta) : 1;
  const cenaZakupu = t.cenaZakupu * skala;
  const cenaSprzedazy = t.cenaSprzedazy === null ? null : t.cenaSprzedazy * skala;

  const iZakupu = n.dni.findIndex((d) => d >= t.dataZakupu);
  if (iZakupu === -1) return null;

  const koniec = new Date(t.dataZakupu);
  koniec.setDate(koniec.getDate() + oknoDni);
  let granica = koniec.toISOString().slice(0, 10);
  // Gdy podano sprzedaż późniejszą niż okno, okno rozciągamy do niej —
  // inaczej „minimum po zakupie" pomijałoby czas, przez który trzymano papier.
  if (t.dataSprzedazy && t.dataSprzedazy > granica) granica = t.dataSprzedazy;

  let min = Infinity;
  let dataMin = "";
  for (let i = iZakupu; i < n.dni.length && n.dni[i] <= granica; i++) {
    if (n.najnizsze[i] < min) {
      min = n.najnizsze[i];
      dataMin = n.dni[i];
    }
  }
  if (!Number.isFinite(min) || cenaZakupu <= 0) return null;

  const doZakupu = n.zamkniecie.slice(0, iZakupu + 1);
  const szczytDoZakupu = Math.max(...n.najwyzsze.slice(0, iZakupu + 1));

  const wynik: WynikTransakcji = {
    ticker: t.ticker,
    instrument: t.instrument,
    dataZakupu: t.dataZakupu,
    cenaZakupu: Math.round(cenaZakupu * 100) / 100,
    minPoZakupie: Math.round(min * 100) / 100,
    dataMinimum: dataMin,
    ileTaniej: Math.round(((min - cenaZakupu) / cenaZakupu) * 10000) / 100,
    rsiWDniuZakupu: doZakupu.length >= 30 ? rsi(doZakupu) : null,
    odSzczytuWDniuZakupu:
      szczytDoZakupu > 0
        ? Math.round(((cenaZakupu - szczytDoZakupu) / szczytDoZakupu) * 1000) / 10
        : null,
    cenaSprzedazy: cenaSprzedazy === null ? null : Math.round(cenaSprzedazy * 100) / 100,
    maksPoSprzedazy: null,
    niewykorzystanyWzrost: null,
    przeskalowana: skala !== 1,
  };

  if (t.dataSprzedazy && cenaSprzedazy !== null && cenaSprzedazy > 0) {
    const iSprzedazy = n.dni.findIndex((d) => d >= t.dataSprzedazy!);
    if (iSprzedazy !== -1) {
      const maks = Math.max(...n.najwyzsze.slice(iSprzedazy));
      wynik.maksPoSprzedazy = Math.round(maks * 100) / 100;
      wynik.niewykorzystanyWzrost =
        Math.round(((maks - cenaSprzedazy) / cenaSprzedazy) * 10000) / 100;
    }
  }
  return wynik;
}

// ---------------------------------------------------------------------------
// Stan formularza analizy
// ---------------------------------------------------------------------------

/**
 * Typ i wartość początkowa stanu siedzą TUTAJ, a nie przy akcji serwerowej.
 *
 * Plik z dyrektywą `"use server"` może eksportować WYŁĄCZNIE funkcje
 * asynchroniczne — każdy inny eksport dociera do komponentu klienckiego jako
 * `undefined`. Objawiało się to dopiero w działaniu: strona zwracała 500
 * z „Cannot read properties of undefined (reading 'map')", bo `useActionState`
 * dostawał pusty stan początkowy. TypeScript tego nie łapie.
 */
export type StanAnalizy = {
  etap: "pusto" | "gotowe" | "blad";
  komunikat: string | null;
  wyniki: WynikTransakcji[];
  /** Pozycje, których nie dało się przeliczyć, wraz z powodem. */
  nieudane: string[];
  mapa: { xtb: string; yahoo: string; instrument: string }[];
  zrodloXtb: boolean;
  przeskalowane: string[];
  wczytanych: number;
  oknoDni: number;
};

export const STAN_POCZATKOWY: StanAnalizy = {
  etap: "pusto",
  komunikat: null,
  wyniki: [],
  nieudane: [],
  mapa: [],
  zrodloXtb: false,
  przeskalowane: [],
  wczytanych: 0,
  oknoDni: 90,
};
