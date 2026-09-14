/**
 * Zamiana nazwy spółki na ticker. Pierwszy krok researchu — ticker zgadnięty
 * z pamięci modelu bywa tickerem innej spółki z innego rynku.
 */
import { migawka } from "@/lib/dane";
import { odpowiedz, blad } from "@/lib/api";
import { szukaj } from "@/lib/publiczne";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(zadanie: Request): Promise<Response> {
  const q = new URL(zadanie.url).searchParams.get("q") ?? "";
  if (!q.trim()) {
    return blad(400, "Brak frazy", "Podaj parametr q, np. /api/dane/szukaj?q=ferro");
  }

  try {
    const m = await migawka();
    const trafienia = szukaj(m.instrumenty, q);
    return odpowiedz({
      zapytanie: q,
      data_migawki: m.data,
      trafien: trafienia.length,
      trafienia,
      podpowiedz: trafienia.length
        ? null
        : "Brak w uniwersum. Ta spółka może nie być dostępna na XTB albo skan " +
          "nie obejmuje jej rynku — research da się zrobić z samej sieci, ale " +
          "bez naszych scoringów.",
    });
  } catch (e) {
    return blad(503, `Baza nie odpowiada: ${e instanceof Error ? e.message : String(e)}`);
  }
}
