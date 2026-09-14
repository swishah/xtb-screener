/**
 * Wszystko o jednej spółce w JEDNYM zapytaniu: migawka, poziomy, sprawozdania.
 *
 * DLACZEGO TA TRASA ISTNIEJE, SKORO DUBLUJE TRZY INNE. Narzędzie pobierania
 * stron w rozmowie na claude.ai przepuszcza wyłącznie adresy obecne DOSŁOWNIE
 * w rozmowie — model nie może sam złożyć adresu z szablonu, podstawiając
 * ticker. Instrukcja „wywołaj /api/dane/spolka/<TICKER>" jest więc
 * niewykonalna: adres bazowy przechodzi, bo stoi w instrukcjach Projektu,
 * a `/api/dane/spolka/DECK` już nie, bo nikt go nie napisał.
 *
 * Dopóki dane chodzą przez pobieranie stron, jedyną drogą jest wklejenie
 * adresu przez użytkownika. Ta trasa sprowadza to do JEDNEGO wklejenia
 * zamiast trzech — i to jest cały jej sens.
 *
 * Docelowo rolę tę przejmie łącznik (connector), który przyjmuje ticker jako
 * parametr narzędzia i nie podlega temu ograniczeniu.
 *
 * Sprawozdania i poziomy pobieramy RÓWNOLEGLE. Szeregowo byłoby to dwa
 * zapytania do Yahoo jedno po drugim, czyli dwa razy dłuższe czekanie
 * w rozmowie.
 */
import { odpowiedz, blad } from "@/lib/api";
import { spolka } from "@/lib/publiczne";
import { dlaTickera } from "@/lib/poziomy";
import { finanse } from "@/lib/finanse";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  _zadanie: Request,
  { params }: { params: Promise<{ ticker: string }> },
): Promise<Response> {
  const { ticker } = await params;
  const t = decodeURIComponent(ticker ?? "").trim();
  if (!t) return blad(400, "Brak tickera");

  try {
    // Brak którejkolwiek części NIE jest błędem całości: ETF nie ma
    // sprawozdań, świeży debiut nie ma poziomów, spółka spoza uniwersum nie
    // ma migawki. Oddajemy to, co jest, i mówimy wprost, czego brakuje —
    // raport z jedną dziurą jest wart więcej niż odmowa.
    const [dane, poziomy, sprawozdania] = await Promise.all([
      spolka(t).catch(() => null),
      dlaTickera(t).catch(() => null),
      finanse(t).catch(() => null),
    ]);

    if (!dane && !poziomy && !sprawozdania) {
      return blad(
        404,
        `Nie znalazłem niczego dla ${t}`,
        "Sprawdź pisownię tickera. Pamiętaj o sufiksie rynku: .WA dla GPW, " +
          ".DE dla Frankfurtu, .L dla Londynu; spółki z USA są bez sufiksu.",
      );
    }

    const brakuje: string[] = [];
    if (!dane) brakuje.push("migawka ze screenera (spółka spoza uniwersum XTB)");
    if (!poziomy) brakuje.push("poziomy techniczne (brak notowań albo historia krótsza niż 60 sesji)");
    if (!sprawozdania) brakuje.push("sprawozdania (ETF-y ich nie mają; przy spółce — brak danych u dostawcy)");

    return odpowiedz({
      ticker: t,
      zawiera: "migawka ze screenera, poziomy techniczne, sprawozdania finansowe",
      brakuje: brakuje.length ? brakuje : null,
      screener: dane,
      notowania: poziomy,
      finanse: sprawozdania,
    });
  } catch (e) {
    return blad(503, `Błąd: ${e instanceof Error ? e.message : String(e)}`);
  }
}
