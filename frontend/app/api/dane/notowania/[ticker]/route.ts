/**
 * Poziomy techniczne liczone NA ŻYWO z surowego OHLC.
 *
 * DLACZEGO NIE Z MIGAWKI: migawka ma SMA i RSI, ale nie ma ani ATR, ani
 * swingów, ani luk — a bez nich nie da się postawić stop-lossa w miejscu,
 * które cokolwiek znaczy. Ma też dziurę, której do dziś nie wyjaśniono:
 * SMA200 i SMA50 bywają puste dla większości spółek. Licząc od zera z notowań
 * omijamy ten problem w całości.
 *
 * To JEDYNE źródło liczb, z których wolno budować plan wejścia. Poziom podany
 * przez model „z wykresu" brzmi wiarygodnie i nie da się go zweryfikować;
 * poziom policzony z notowań — owszem.
 */
import { odpowiedz, blad } from "@/lib/api";
import { dlaTickera } from "@/lib/poziomy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  zadanie: Request,
  { params }: { params: Promise<{ ticker: string }> },
): Promise<Response> {
  const { ticker } = await params;
  const t = decodeURIComponent(ticker ?? "").trim();
  if (!t) return blad(400, "Brak tickera");

  const zeSwiecami =
    (new URL(zadanie.url).searchParams.get("swiece") ?? "tak") !== "nie";

  try {
    const p = await dlaTickera(t);
    if (!p) {
      return blad(
        404,
        `Brak notowań dla ${t} albo historia krótsza niż 60 sesji`,
        "Sprawdź pisownię tickera przez /api/dane/szukaj. Świeże debiuty " +
          "i instrumenty wycofane z obrotu nie mają dość historii, żeby " +
          "policzyć poziomy — wtedy planu wejścia nie buduj.",
      );
    }

    const tresc: Record<string, unknown> = { ...p };
    if (!zeSwiecami) delete tresc.swiece;

    return odpowiedz({
      ticker: t,
      zrodlo: "Yahoo Finance (dzienne OHLC, 2 lata)",
      liczone: "core/poziomy.py — lustro w lib/poziomy.ts",
      ...tresc,
      uwaga_o_walucie: p.waluta_w_podjednostkach
        ? `Notowanie w subjednostkach waluty (${p.waluta}): wartości są ` +
          "w setnych częściach jednostki, czyli w pensach, a nie w funtach. " +
          "Plan ułożony w funtach byłby 100x nie taki."
        : null,
    });
  } catch (e) {
    return blad(
      503,
      `Nie udało się pobrać notowań: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
}
