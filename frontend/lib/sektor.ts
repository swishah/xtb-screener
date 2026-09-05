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
import { liczba, type Instrument } from "./filtry";

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
