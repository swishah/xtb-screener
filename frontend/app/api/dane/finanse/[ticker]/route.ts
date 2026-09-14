/**
 * Sprawozdania finansowe jednej spółki — cztery lata i pięć kwartałów.
 *
 * Istnieje po to, żeby research nie musiał chodzić po SEC, biznesradarze
 * i stockanalysis. Każda z tych domen to osobne pytanie o zgodę w rozmowie
 * na claude.ai; jeden nasz adres to jedno pytanie, raz.
 */
import { odpowiedz, blad } from "@/lib/api";
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
    const dane = await finanse(t);
    if (!dane) {
      return blad(
        404,
        `Brak sprawozdań dla ${t}`,
        "ETF-y i fundusze nie mają sprawozdań z definicji. Przy spółce sprawdź " +
          "pisownię tickera przez /api/dane/szukaj — a jeśli jest poprawna, " +
          "znaczy to, że dostawca nie ma danych i trzeba sięgnąć do raportu " +
          "spółki w sieci.",
      );
    }
    return odpowiedz(dane);
  } catch (e) {
    return blad(
      503,
      `Nie udało się pobrać sprawozdań: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
}
