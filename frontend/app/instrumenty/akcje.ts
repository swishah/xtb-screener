"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { migawkaBezpieczna } from "@/lib/dane";
import { dodajWlasny, sprawdzInstrument, usunWlasny } from "@/lib/instrumenty";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Akcje własnych instrumentów.
 *
 * Każda zaczyna się od `wymagajZalogowania()` — akcja serwerowa to zwykły
 * punkt wejścia po sieci, więc sprawdzenie sesji na stronie nie wystarcza.
 *
 * Lista jest WSPÓLNA dla całej instalacji (patrz `lib/instrumenty.ts`), więc
 * nie ma tu filtrowania po użytkowniku — jest jeden skan i jedno uniwersum.
 * Sprawdzenie sesji chroni przed dopisywaniem czegokolwiek z zewnątrz.
 */

function wroc(kod: string, dodatek = ""): never {
  revalidatePath("/instrumenty");
  redirect(`/instrumenty?wynik=${kod}${dodatek ? `&t=${encodeURIComponent(dodatek)}` : ""}`);
}

export async function sprawdz(dane: FormData): Promise<void> {
  await wymagajZalogowania();
  const wpisany = String(dane.get("ticker") ?? "").trim().toUpperCase();
  if (!wpisany) wroc("pusty");

  // Instrument już w uniwersum wbudowanym poznajemy po tym, że jest w migawce
  // — to dokładniejsze niż lista z konfiguracji, bo odbija to, co NAPRAWDĘ
  // jest skanowane.
  const { instrumenty } = await migawkaBezpieczna();
  const wSkanie = instrumenty.some(
    (i) => String(i.Ticker ?? "").toUpperCase() === wpisany,
  );
  if (wSkanie) wroc("wbudowany", wpisany);

  const wynik = await sprawdzInstrument(wpisany);
  if (!wynik.ok) wroc("brak", wpisany);

  // Ticker po tłumaczeniu też mógł już być w skanie (np. wklejone „ALE.PL"
  // przy Allegro, które w uniwersum siedzi jako „ALE.WA").
  if (
    wynik.ticker !== wpisany &&
    instrumenty.some((i) => String(i.Ticker ?? "").toUpperCase() === wynik.ticker)
  ) {
    wroc("wbudowany", wynik.ticker);
  }

  const p = new URLSearchParams({
    wynik: "znaleziony",
    t: wynik.ticker,
    n: wynik.nazwa,
    c: String(wynik.cena),
    w: wynik.waluta,
    typ: wynik.typ,
    g: wynik.gielda,
  });
  if (wynik.poprawionyZ) p.set("z", wynik.poprawionyZ);
  redirect(`/instrumenty?${p.toString()}`);
}

export async function dodaj(dane: FormData): Promise<void> {
  await wymagajZalogowania();
  const ticker = String(dane.get("ticker") ?? "");
  const nazwa = String(dane.get("nazwa") ?? "");
  const typ = String(dane.get("typ") ?? "stock");

  // Weryfikujemy PONOWNIE, mimo że formularz powstał po sprawdzeniu.
  // Formularz jest zwykłym POST-em, więc jego pola da się podmienić —
  // bez tego kroku dałoby się dopisać dowolny ticker z pominięciem kontroli.
  const wynik = await sprawdzInstrument(ticker);
  if (!wynik.ok) wroc("brak", ticker);

  const zapis = await dodajWlasny(wynik.ticker, nazwa || wynik.nazwa, typ);
  wroc(zapis.ok ? "dodany" : zapis.powod, wynik.ticker);
}

export async function usun(dane: FormData): Promise<void> {
  await wymagajZalogowania();
  const ticker = String(dane.get("ticker") ?? "");
  await usunWlasny(ticker);
  wroc("usuniety", ticker.trim().toUpperCase());
}
