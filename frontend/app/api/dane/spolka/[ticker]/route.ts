/**
 * Wszystko, co skan wie o jednej spółce.
 *
 * Uwaga na Next 15: `params` jest OBIETNICĄ, nie obiektem. Odczyt bez `await`
 * przechodzi kompilację i wywala się dopiero w działaniu.
 */
import { odpowiedz, blad } from "@/lib/api";
import { spolka } from "@/lib/publiczne";

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
    const dane = await spolka(t);
    if (!dane) {
      return blad(
        404,
        `Tickera ${t} nie ma w najnowszej migawce`,
        "Sprawdź pisownię przez /api/dane/szukaj?q=<nazwa>. Pamiętaj o sufiksie " +
          "rynku: .WA dla GPW, .DE dla Frankfurtu, .L dla Londynu, .PA dla Paryża. " +
          "Spółki z USA są bez sufiksu.",
      );
    }
    return odpowiedz(dane);
  } catch (e) {
    return blad(503, `Baza nie odpowiada: ${e instanceof Error ? e.message : String(e)}`);
  }
}
