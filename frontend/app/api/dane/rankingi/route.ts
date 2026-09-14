/**
 * Czołówki wszystkich rankingów — punkt wyjścia, gdy pytanie brzmi
 * „co dziś warto obejrzeć", a nie „co sądzisz o konkretnej spółce".
 */
import { migawka } from "@/lib/dane";
import { odpowiedz, blad } from "@/lib/api";
import { wszystkieRankingi, ILE_W_RANKINGU } from "@/lib/publiczne";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(zadanie: Request): Promise<Response> {
  const parametry = new URL(zadanie.url).searchParams;
  const klucz = parametry.get("klucz");

  // Pusty parametr da w JavaScripcie Number("") === 0, a nie NaN — stąd jawne
  // sprawdzenie zamiast samego `Number(...) || domyślna`. Ta sama pułapka
  // zjadła kiedyś filtry w Screenerze i Dywidendach.
  const ileTekst = parametry.get("ile");
  const ileLiczba = ileTekst ? Number(ileTekst) : NaN;
  const ile = Number.isFinite(ileLiczba)
    ? Math.min(30, Math.max(1, Math.trunc(ileLiczba)))
    : ILE_W_RANKINGU;

  try {
    const m = await migawka();
    const wszystkie = wszystkieRankingi(m, ile);
    if (!klucz) return odpowiedz(wszystkie);

    const jeden = wszystkie.rankingi.find((r) => r.klucz === klucz);
    if (!jeden) {
      return blad(
        404,
        `Nie ma rankingu o kluczu ${klucz}`,
        `Dostępne klucze: ${wszystkie.rankingi.map((r) => r.klucz).join(", ")}`,
      );
    }
    return odpowiedz({ data_migawki: wszystkie.data_migawki, rankingi: [jeden] });
  } catch (e) {
    return blad(503, `Baza nie odpowiada: ${e instanceof Error ? e.message : String(e)}`);
  }
}
