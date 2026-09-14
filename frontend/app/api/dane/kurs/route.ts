/**
 * Kursy walut z NBP, tabela A.
 *
 * Bez parametru oddaje cztery waluty, w których notowane jest całe uniwersum
 * (USD, EUR, GBP, CHF) — jednym zapytaniem zamiast czterech. `?waluta=SEK`
 * dokłada dowolną inną.
 *
 * Po co pośrednik, skoro NBP jest publiczne: w rozmowie na claude.ai każda
 * nowa domena to osobne pytanie o zgodę. Kurs jest potrzebny przy KAŻDYM
 * liczeniu pozycji, więc api.nbp.pl byłoby drugim najczęstszym okienkiem
 * zaraz po naszym adresem. Tutaj mieści się w tej samej zgodzie, co reszta.
 */
import { odpowiedz, blad } from "@/lib/api";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const NBP = "https://api.nbp.pl/api/exchangerates/rates/a/";

/** Waluty notowań w uniwersum — tyle wystarcza w 99% przypadków. */
const DOMYSLNE = ["USD", "EUR", "GBP", "CHF"];

type Kurs = {
  waluta: string;
  kurs_pln: number | null;
  data: string | null;
  blad?: string;
};

async function pobierz(kod: string): Promise<Kurs> {
  try {
    const odp = await fetch(`${NBP}${kod.toLowerCase()}/?format=json`, {
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    if (!odp.ok) {
      return {
        waluta: kod,
        kurs_pln: null,
        data: null,
        blad: `NBP odpowiedziało ${odp.status}`,
      };
    }
    const dane = await odp.json();
    const notowanie = dane?.rates?.[0];
    return {
      waluta: kod,
      kurs_pln: typeof notowanie?.mid === "number" ? notowanie.mid : null,
      data: notowanie?.effectiveDate ?? null,
    };
  } catch (e) {
    return {
      waluta: kod,
      kurs_pln: null,
      data: null,
      blad: e instanceof Error ? e.message : String(e),
    };
  }
}

export async function GET(zadanie: Request): Promise<Response> {
  const zadana = new URL(zadanie.url).searchParams.get("waluta");
  if (zadana && !/^[A-Za-z]{3}$/.test(zadana)) {
    return blad(400, "Kod waluty to trzy litery", "Na przykład /api/dane/kurs?waluta=SEK");
  }

  const kody = zadana ? [zadana.toUpperCase()] : DOMYSLNE;
  const kursy = await Promise.all(kody.map(pobierz));

  return odpowiedz({
    zrodlo: "Narodowy Bank Polski, tabela A (kurs średni)",
    kursy,
    uwaga:
      "To kurs ŚREDNI NBP, nie kurs brokera. Przy przewalutowaniu u brokera " +
      "dochodzi spread (w XTB rzędu 0,5%), więc liczba akcji policzona z tego " +
      "kursu jest przybliżeniem, a nie wartością do dotrzymania co do sztuki.",
  });
}
