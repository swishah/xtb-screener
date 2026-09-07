/**
 * Mediany wskaźników w obrębie sektora.
 *
 * Po co: marża 8% jest słaba w oprogramowaniu i bardzo dobra w handlu
 * detalicznym. Ocena „dobrze / słabo” bez odniesienia do branży wprowadzałaby
 * w błąd, dlatego większość wskaźników porównujemy z medianą sektora zamiast
 * ze stałą liczbą.
 *
 * MEDIANA, nie średnia — pojedyncza spółka z ROE 900% albo ujemnym zyskiem
 * przesunęłaby średnią tak, że przestałaby cokolwiek opisywać.
 *
 * Zero importów z Node.
 */
import { liczba, porownajRemis, type Instrument } from "./filtry";

export type StatystykiSektora = {
  sektor: string;
  liczbaSpolek: number;
  mediany: Record<string, number>;
};

function mediana(wartosci: number[]): number | null {
  if (wartosci.length === 0) return null;
  const s = [...wartosci].sort((a, b) => a - b);
  const srodek = Math.floor(s.length / 2);
  return s.length % 2 ? s[srodek] : (s[srodek - 1] + s[srodek]) / 2;
}

/**
 * Liczy mediany dla jednego sektora. Bierze pod uwagę wyłącznie AKCJE — ETF-y
 * nie mają marż ani ROE, a wrzucone do puli zaniżałyby liczebność próby.
 */
export function statystykiSektora(
  instrumenty: Instrument[],
  sektor: string | undefined,
  klucze: string[],
): StatystykiSektora | null {
  if (!sektor || sektor === "BRAK") return null;

  const wSektorze = instrumenty.filter(
    (i) => i.Typ === "stock" && i.Sektor === sektor,
  );
  // Przy garstce spółek mediana nie opisuje branży, tylko przypadek.
  if (wSektorze.length < 5) return null;

  const mediany: Record<string, number> = {};
  for (const klucz of klucze) {
    const wartosci = wSektorze
      .map((i) => liczba(i[klucz]))
      .filter((n): n is number => n !== null);
    const m = mediana(wartosci);
    if (m !== null) mediany[klucz] = m;
  }

  return { sektor, liczbaSpolek: wSektorze.length, mediany };
}


/**
 * Spółki tanie względem WŁASNEGO sektora, mierzone wskaźnikiem C/Z.
 *
 * Porównanie do sektora, nie do całego rynku: C/Z równe 12 jest drogie
 * w bankowości i tanie w oprogramowaniu, więc jedna liczba dla wszystkich
 * branż nie znaczy nic.
 *
 * Dwa świadome wykluczenia:
 *   - C/Z ujemne lub zerowe — spółka na stracie. Wskaźnik przestaje wtedy
 *     cokolwiek mierzyć, a wpuszczony do mediany psułby ją dla całej branży.
 *   - sektory poniżej progu liczebności — mediana z trzech spółek to nie
 *     opis branży, tylko przypadek.
 */
export type AnomaliaCZ = {
  spolka: Instrument;
  cz: number;
  medianaSektora: number;
  spolekWSektorze: number;
  roznicaProc: number;
};

export function anomalieCZ(
  instrumenty: Instrument[],
  minSpolek: number,
  maksRoznica: number,
): AnomaliaCZ[] {
  const kandydaci = instrumenty.filter((i) => {
    if (i.Typ !== "stock") return false;
    const sektor = i.Sektor;
    if (typeof sektor !== "string" || !sektor || sektor === "Nieznany" || sektor === "BRAK") {
      return false;
    }
    const cz = liczba(i["C/Z (P/E)"]);
    return cz !== null && cz > 0;
  });

  const wgSektora = new Map<string, number[]>();
  for (const i of kandydaci) {
    const s = String(i.Sektor);
    const cz = liczba(i["C/Z (P/E)"]) as number;
    const lista = wgSektora.get(s);
    if (lista) lista.push(cz);
    else wgSektora.set(s, [cz]);
  }

  const mediany = new Map<string, { med: number; ile: number }>();
  for (const [sektor, wartosci] of wgSektora) {
    const s = [...wartosci].sort((a, b) => a - b);
    const srodek = Math.floor(s.length / 2);
    const med = s.length % 2 ? s[srodek] : (s[srodek - 1] + s[srodek]) / 2;
    mediany.set(sektor, { med, ile: s.length });
  }

  const wynik: AnomaliaCZ[] = [];
  for (const spolka of kandydaci) {
    const stat = mediany.get(String(spolka.Sektor));
    if (!stat || stat.ile < minSpolek || stat.med <= 0) continue;
    const cz = liczba(spolka["C/Z (P/E)"]) as number;
    const roznicaProc = ((cz - stat.med) / stat.med) * 100;
    if (roznicaProc > maksRoznica) continue;
    wynik.push({
      spolka,
      cz,
      medianaSektora: stat.med,
      spolekWSektorze: stat.ile,
      roznicaProc,
    });
  }

  // Najtańsze względem branży na górze; przy remisie decyduje ta sama reguła
  // co w pozostałych rankingach.
  return wynik.sort((a, b) => {
    const r = a.roznicaProc - b.roznicaProc;
    return r !== 0 ? r : porownajRemis(a.spolka, b.spolka);
  });
}

// ---------------------------------------------------------------------------
// Porównanie jednej spółki z medianą jej sektora (moduł „vs Sektor")
// ---------------------------------------------------------------------------

/** Lustro `SECTOR_METRICS` z `ui/common.py` — te same wskaźniki i kierunki. */
export const WSKAZNIKI_SEKTORA: { kolumna: string; kierunek: "wyzej" | "nizej" }[] = [
  { kolumna: "C/Z (P/E)", kierunek: "nizej" },
  { kolumna: "Forward C/Z", kierunek: "nizej" },
  { kolumna: "C/WK (P/B)", kierunek: "nizej" },
  { kolumna: "ROE (%)", kierunek: "wyzej" },
  { kolumna: "Marża Operac. (%)", kierunek: "wyzej" },
  { kolumna: "Marża netto (%)", kierunek: "wyzej" },
  { kolumna: "Marża brutto (%)", kierunek: "wyzej" },
  { kolumna: "Dług/Kapitał", kierunek: "nizej" },
  { kolumna: "Wzrost przychodów (%)", kierunek: "wyzej" },
  { kolumna: "Wzrost EPS (%)", kierunek: "wyzej" },
  { kolumna: "Stopa Dyw. (%)", kierunek: "wyzej" },
  { kolumna: "Payout ratio (%)", kierunek: "nizej" },
  { kolumna: "RSI", kierunek: "nizej" },
];

/**
 * Poniżej tylu spółek mediana sektora przestaje cokolwiek znaczyć.
 *
 * Ta sama granica co w heatmapach Globalnego przeglądu — mediana z dwóch
 * spółek to po prostu jedna z nich, a wygląda jak charakterystyka branży.
 */
export const MIN_SPOLEK_W_SEKTORZE = 3;

export type Ocena = "lepiej" | "gorzej" | "podobnie" | "brak";

export type PorownanieWskaznika = {
  kolumna: string;
  kierunek: "wyzej" | "nizej";
  wartosc: number | null;
  mediana: number | null;
  /** Różnica w procentach względem mediany; null, gdy mediana wynosi zero. */
  roznica: number | null;
  ocena: Ocena;
};

/**
 * Porównuje spółkę z medianą jej sektora, wskaźnik po wskaźniku.
 *
 * PRÓG 5% NIE JEST OZDOBĄ. Bez niego spółka odstająca o 0,3% dostawałaby
 * zieloną albo czerwoną ocenę, sugerując różnicę tam, gdzie jej nie ma —
 * a przy medianach liczonych z kilkunastu spółek taki ruch to szum.
 */
export function porownajZSektorem(
  spolka: Instrument,
  rowiesnicy: Instrument[],
): PorownanieWskaznika[] {
  return WSKAZNIKI_SEKTORA.map(({ kolumna, kierunek }) => {
    const wartosci = rowiesnicy
      .map((r) => liczba(r[kolumna]))
      .filter((w): w is number => w !== null);
    const med = mediana(wartosci);
    const wlasna = liczba(spolka[kolumna]);

    if (wlasna === null || med === null) {
      return { kolumna, kierunek, wartosc: wlasna, mediana: med, roznica: null, ocena: "brak" as Ocena };
    }

    const roznica = med !== 0 ? ((wlasna - med) / Math.abs(med)) * 100 : null;
    let ocena: Ocena;
    if (roznica !== null && Math.abs(roznica) < 5) {
      ocena = "podobnie";
    } else {
      const lepiej = kierunek === "wyzej" ? wlasna > med : wlasna < med;
      ocena = lepiej ? "lepiej" : "gorzej";
    }
    return { kolumna, kierunek, wartosc: wlasna, mediana: med, roznica, ocena };
  });
}
