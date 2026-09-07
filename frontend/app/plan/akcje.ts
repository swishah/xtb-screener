"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { anulujPlan } from "@/lib/plany";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Jedyna akcja ekranu planów: anulowanie.
 *
 * Zaczyna się od `wymagajZalogowania()`, bo akcja serwerowa to zwykły punkt
 * wejścia po sieci — sprawdzenie sesji na stronie nie wystarcza.
 *
 * ANULOWAĆ MOŻNA WYŁĄCZNIE PLAN OTWARTY i pilnuje tego SQL, nie kod: filtr
 * `stan IN ('czeka','aktywny')` siedzi w samym UPDATE, więc podanie id planu
 * sprzed miesiąca nie zmienia niczego. Rozliczony wynik ma zostać nietknięty,
 * inaczej statystykę dałoby się wyczyścić z porażek.
 */
export async function anuluj(dane: FormData): Promise<void> {
  await wymagajZalogowania();

  const id = Number(dane.get("id"));
  const dzien = String(dane.get("dzien") ?? "");
  if (!Number.isInteger(id) || id <= 0) {
    wroc(dzien, "blad");
  }

  const udalo = await anulujPlan(id);
  wroc(dzien, udalo ? "anulowany" : "nieotwarty");
}

function wroc(dzien: string, wynik: string): never {
  revalidatePath("/plan");
  const p = new URLSearchParams({ wynik });
  if (dzien) p.set("dzien", dzien);
  redirect(`/plan?${p.toString()}`);
}
