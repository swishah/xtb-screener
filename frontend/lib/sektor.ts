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
