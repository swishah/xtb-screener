/**
 * Wspólna obsługa odpowiedzi publicznych tras `/api/dane/*`.
 *
 * Dwie rzeczy, które muszą być JEDNAKOWE we wszystkich trasach: nagłówek
 * buforowania i kształt błędu. Rozjazd któregokolwiek z nich objawiłby się
 * dopiero po stronie modelu, który dostałby raz JSON, a raz stronę błędu
 * Next.js w HTML-u — i nie miałby jak tego odróżnić.
 */

/**
 * Bufor: migawka zmienia się raz na dobę, więc kwadrans po stronie brzegu
 * Vercela nie postarza niczego, a oszczędza odpytywanie bazy przy każdej
 * kolejnej spółce z tej samej rozmowy.
 */
const BUFOR = "public, s-maxage=900, stale-while-revalidate=3600";

export function odpowiedz(dane: unknown, status = 200): Response {
  return Response.json(dane, {
    status,
    headers: { "Cache-Control": BUFOR },
  });
}

/**
 * Błąd ZAWSZE jako JSON z polem `blad` i `podpowiedz`.
 *
 * Model, który dostaje 404, musi wiedzieć, co zrobić dalej — stąd
 * podpowiedź w treści zamiast samego kodu stanu.
 */
export function blad(status: number, opis: string, podpowiedz?: string): Response {
  return Response.json(
    { blad: opis, podpowiedz: podpowiedz ?? null },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}
