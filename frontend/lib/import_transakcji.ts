import ExcelJS from "exceljs";
import type { Transakcja } from "./transakcje";
import { xtbNaYahoo } from "./transakcje";

/**
 * Wczytywanie pliku z transakcjami. MODUŁ SERWEROWY — ciągnie `exceljs`,
 * więc nie wolno go importować z komponentu klienckiego.
 *
 * DLACZEGO `exceljs`, A NIE `xlsx` (SheetJS). Wersja SheetJS publikowana na
 * npm stoi na 0.18.5 i ma dwie niezałatane podatności — prototype pollution
 * i ReDoS — obie z adnotacją „No fix available", obie w SAMYM PARSERZE, czyli
 * dokładnie w kodzie, który dotyka wgranego pliku. Nowsze wydania SheetJS są
 * wyłącznie na własnym CDN autorów, poza npm. Przy projekcie, który ma działać
 * latami bez opieki, to zły układ. `exceljs` jest utrzymywany na npm; ciągnie
 * jedną pośrednią podatność (`uuid` przy generowaniu identyfikatorów), której
 * ścieżki tu w ogóle nie używamy.
 *
 * EKSPORT Z XTB NIE JEST ZWYKŁĄ TABELĄ: ma trzy arkusze, a nad właściwymi
 * danymi kilka wierszy metadanych (numer rachunku, zakres dat). Stąd sztywne
 * numery wierszy nagłówka, ustalone na prawdziwym pliku. Nazwy kolumn różnią
 * się wielkością liter między arkuszami („Open Price" kontra „Open price"),
 * więc szukamy ich bez rozróżniania wielkości.
 */

const ARKUSZ_ZAMKNIETE = "Closed Positions";
const ARKUSZ_OTWARTE = "Open Positions";
/** Numer wiersza nagłówka (1-based, jak liczy exceljs). */
const WIERSZ_NAGLOWKA: Record<string, number> = {
  [ARKUSZ_ZAMKNIETE]: 5,
  [ARKUSZ_OTWARTE]: 11,
};

export type WynikImportu = {
  transakcje: Transakcja[];
  zrodloXtb: boolean;
  /** Mapa tłumaczeń tickerów — pokazujemy ją użytkownikowi do sprawdzenia. */
  mapa: { xtb: string; yahoo: string; instrument: string }[];
  blad: string | null;
};

const PUSTY: WynikImportu = {
  transakcje: [],
  zrodloXtb: false,
  mapa: [],
  blad: null,
};

function naDate(w: unknown): string | null {
  if (w === null || w === undefined || w === "") return null;
  if (w instanceof Date) return w.toISOString().slice(0, 10);
  const s = String(w).trim();
  if (!s || s.toLowerCase() === "nan") return null;
  // "2024-03-15 10:22:31" albo "15.03.2024" — bierzemy samą datę.
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const pl = s.match(/^(\d{2})[.\/](\d{2})[.\/](\d{4})/);
  if (pl) return `${pl[3]}-${pl[2]}-${pl[1]}`;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

function naLiczbe(w: unknown): number | null {
  if (typeof w === "number") return Number.isFinite(w) ? w : null;
  if (w === null || w === undefined) return null;
  // Polskie eksporty potrafią mieć przecinek dziesiętny i spacje tysięcy.
  const s = String(w).trim().replace(/\s/g, "").replace(",", ".");
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function tekst(w: unknown): string {
  if (w === null || w === undefined) return "";
  if (typeof w === "object" && w !== null && "text" in w) {
    return String((w as { text: unknown }).text ?? "").trim();
  }
  const s = String(w).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

/** Indeks kolumny po nazwie, bez rozróżniania wielkości liter. */
function kolumna(naglowki: string[], ...nazwy: string[]): number {
  const mapa = new Map(naglowki.map((h, i) => [h.trim().toLowerCase(), i]));
  for (const n of nazwy) {
    const i = mapa.get(n.trim().toLowerCase());
    if (i !== undefined) return i;
  }
  return -1;
}

function wierszNaTablice(wiersz: ExcelJS.Row): string[] {
  const out: string[] = [];
  wiersz.eachCell({ includeEmpty: true }, (kom, nr) => {
    out[nr - 1] = tekst(kom.value);
  });
  return out;
}

function wartosciWiersza(wiersz: ExcelJS.Row): unknown[] {
  const out: unknown[] = [];
  wiersz.eachCell({ includeEmpty: true }, (kom, nr) => {
    out[nr - 1] = kom.value;
  });
  return out;
}

async function czytajXtb(bufor: Buffer): Promise<WynikImportu | null> {
  const skoroszyt = new ExcelJS.Workbook();
  try {
    await skoroszyt.xlsx.load(bufor as unknown as ArrayBuffer);
  } catch {
    return null;
  }
  if (!skoroszyt.getWorksheet(ARKUSZ_ZAMKNIETE)) return null; // to nie XTB

  const transakcje: Transakcja[] = [];
  for (const [nazwa, status] of [
    [ARKUSZ_ZAMKNIETE, "zamknięta"],
    [ARKUSZ_OTWARTE, "otwarta"],
  ] as const) {
    const arkusz = skoroszyt.getWorksheet(nazwa);
    if (!arkusz) continue;
    const naglowki = wierszNaTablice(arkusz.getRow(WIERSZ_NAGLOWKA[nazwa]));

    const kTic = kolumna(naglowki, "Ticker");
    const kOtwD = kolumna(naglowki, "Open Time (UTC)", "Open time (UTC)");
    const kOtwC = kolumna(naglowki, "Open Price", "Open price");
    const kTyp = kolumna(naglowki, "Type");
    const kNazwa = kolumna(naglowki, "Instrument", "Instrument/Position");
    const kZamD = kolumna(naglowki, "Close Time (UTC)", "Close time (UTC)");
    const kZamC = kolumna(naglowki, "Close Price", "Close price");
    if (kTic === -1 || kOtwD === -1 || kOtwC === -1) continue;

    arkusz.eachRow((wiersz, nr) => {
      if (nr <= WIERSZ_NAGLOWKA[nazwa]) return;
      const w = wartosciWiersza(wiersz);
      const tic = tekst(w[kTic]);
      if (!tic) return;
      // Arkusz pozycji otwartych ma też wiersze zbiorcze (suma po instrumencie)
      // — poznajemy je po braku daty otwarcia.
      const dataZakupu = naDate(w[kOtwD]);
      if (!dataZakupu) return;
      // Krótkie pozycje rządzą się odwrotną logiką niż pytanie „ile taniej
      // dało się kupić", więc ich nie analizujemy.
      if (kTyp !== -1) {
        const typ = tekst(w[kTyp]).toUpperCase();
        if (typ && typ !== "BUY") return;
      }
      const cenaZakupu = naLiczbe(w[kOtwC]);
      if (cenaZakupu === null) return;

      let instrument = kNazwa === -1 ? "" : tekst(w[kNazwa]);
      if (/^\d+$/.test(instrument)) instrument = "";

      transakcje.push({
        instrument,
        tickerXtb: tic,
        ticker: xtbNaYahoo(tic),
        dataZakupu,
        cenaZakupu,
        dataSprzedazy: kZamD === -1 ? null : naDate(w[kZamD]),
        cenaSprzedazy: kZamC === -1 ? null : naLiczbe(w[kZamC]),
        status,
      });
    });
  }

  if (transakcje.length === 0) return null;

  // W arkuszu pozycji otwartych kolumna "Instrument/Position" trzyma numer
  // pozycji zamiast nazwy spółki — uzupełniamy ją po tickerze z tych wierszy,
  // które nazwę mają.
  const nazwy = new Map<string, string>();
  for (const t of transakcje) {
    if (t.instrument && !nazwy.has(t.tickerXtb)) nazwy.set(t.tickerXtb, t.instrument);
  }
  for (const t of transakcje) {
    if (!t.instrument) t.instrument = nazwy.get(t.tickerXtb) ?? "";
  }

  const mapa = [...new Set(transakcje.map((t) => t.tickerXtb))]
    .sort()
    .map((xtb) => {
      const t = transakcje.find((x) => x.tickerXtb === xtb)!;
      return { xtb, yahoo: t.ticker, instrument: t.instrument };
    });

  return { transakcje, zrodloXtb: true, mapa, blad: null };
}

/** Nagłówki CSV, które rozpoznajemy bez pytania użytkownika. */
const CSV_TICKER = ["ticker", "symbol", "instrument"];
const CSV_DATA_ZAKUPU = ["data zakupu", "buy date", "open time", "open date", "data"];
const CSV_CENA_ZAKUPU = ["cena zakupu", "buy price", "open price", "cena"];
const CSV_DATA_SPRZEDAZY = ["data sprzedaży", "sell date", "close time", "close date"];
const CSV_CENA_SPRZEDAZY = ["cena sprzedaży", "sell price", "close price"];

function podzielCsv(linia: string): string[] {
  // Prosty podział z obsługą cudzysłowów — pola z przecinkiem w środku
  // zdarzają się w nazwach spółek („Company, Inc.").
  const pola: string[] = [];
  let biezace = "";
  let wCudzyslowie = false;
  for (let i = 0; i < linia.length; i++) {
    const z = linia[i];
    if (z === '"') {
      if (wCudzyslowie && linia[i + 1] === '"') {
        biezace += '"';
        i += 1;
      } else {
        wCudzyslowie = !wCudzyslowie;
      }
    } else if ((z === "," || z === ";") && !wCudzyslowie) {
      pola.push(biezace);
      biezace = "";
    } else {
      biezace += z;
    }
  }
  pola.push(biezace);
  return pola.map((p) => p.trim());
}

function czytajCsv(tresc: string, tlumaczXtb: boolean): WynikImportu {
  const linie = tresc.split(/\r?\n/).filter((l) => l.trim() !== "");
  if (linie.length < 2) {
    return { ...PUSTY, blad: "Plik CSV nie zawiera żadnych wierszy z danymi." };
  }
  const naglowki = podzielCsv(linie[0]);
  const kTic = kolumna(naglowki, ...CSV_TICKER);
  const kData = kolumna(naglowki, ...CSV_DATA_ZAKUPU);
  const kCena = kolumna(naglowki, ...CSV_CENA_ZAKUPU);
  if (kTic === -1 || kData === -1 || kCena === -1) {
    return {
      ...PUSTY,
      blad:
        "Nie rozpoznałem kolumn. Potrzebne są co najmniej: ticker, data zakupu " +
        "i cena zakupu. Znalezione nagłówki: " +
        naglowki.filter(Boolean).join(", "),
    };
  }
  const kDataS = kolumna(naglowki, ...CSV_DATA_SPRZEDAZY);
  const kCenaS = kolumna(naglowki, ...CSV_CENA_SPRZEDAZY);

  const transakcje: Transakcja[] = [];
  for (const linia of linie.slice(1)) {
    const p = podzielCsv(linia);
    const surowy = (p[kTic] ?? "").trim();
    const dataZakupu = naDate(p[kData]);
    const cenaZakupu = naLiczbe(p[kCena]);
    if (!surowy || !dataZakupu || cenaZakupu === null) continue;
    const cenaSprzedazy = kCenaS === -1 ? null : naLiczbe(p[kCenaS]);
    const dataSprzedazy = kDataS === -1 ? null : naDate(p[kDataS]);
    transakcje.push({
      instrument: "",
      tickerXtb: surowy.toUpperCase(),
      ticker: tlumaczXtb ? xtbNaYahoo(surowy) : surowy.toUpperCase(),
      dataZakupu,
      cenaZakupu,
      dataSprzedazy,
      cenaSprzedazy,
      status: dataSprzedazy && cenaSprzedazy !== null ? "zamknięta" : "otwarta",
    });
  }
  if (transakcje.length === 0) {
    return { ...PUSTY, blad: "Żaden wiersz nie miał kompletu: ticker, data i cena zakupu." };
  }
  return {
    transakcje,
    zrodloXtb: tlumaczXtb,
    mapa: tlumaczXtb
      ? [...new Set(transakcje.map((t) => t.tickerXtb))].sort().map((xtb) => ({
          xtb,
          yahoo: xtbNaYahoo(xtb),
          instrument: "",
        }))
      : [],
    blad: null,
  };
}

export async function wczytajPlik(
  nazwa: string,
  bufor: Buffer,
  tlumaczXtb: boolean,
): Promise<WynikImportu> {
  const n = nazwa.toLowerCase();
  if (n.endsWith(".xlsx") || n.endsWith(".xls")) {
    const xtb = await czytajXtb(bufor);
    if (xtb) return xtb;
    return {
      ...PUSTY,
      blad:
        "To nie wygląda na eksport z xStation (brak arkusza „Closed Positions”). " +
        "Zapisz plik jako CSV z kolumnami: ticker, data zakupu, cena zakupu.",
    };
  }
  if (n.endsWith(".csv") || n.endsWith(".txt")) {
    return czytajCsv(bufor.toString("utf-8"), tlumaczXtb);
  }
  return { ...PUSTY, blad: "Obsługiwane formaty to XLSX (eksport z XTB) i CSV." };
}
