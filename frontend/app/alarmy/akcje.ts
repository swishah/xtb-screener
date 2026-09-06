"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { dodajAlarm, usunAlarm, wznowAlarm, type Kierunek } from "@/lib/alarmy";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Akcje alarmów. Każda zaczyna się od `wymagajZalogowania()` — akcja serwerowa
 * jest zwykłym punktem wejścia po sieci, więc sprawdzenie sesji na stronie
 * NIE wystarcza. Bez tego wystarczyłoby wysłać żądanie z pominięciem strony.
 *
 * `usunAlarm` i `wznowAlarm` dostają id użytkownika i filtrują po nim
 * w zapytaniu SQL — inaczej podanie cudzego id alarmu kasowałoby cudzy wpis.
 */

/** Bezpieczny adres powrotu: tylko ścieżka w tej aplikacji, nigdy obca. */
function adresPowrotu(surowy: unknown): string {
  const s = String(surowy ?? "");
  // Musi zaczynać się od pojedynczego ukośnika. "//zly.example" przeglądarka
  // potraktowałaby jako adres bezwzględny i wyprowadziła użytkownika poza
  // aplikację — klasyczne otwarte przekierowanie.
  if (!s.startsWith("/") || s.startsWith("//")) return "/alarmy";
  return s;
}

export async function dodaj(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const powrot = adresPowrotu(dane.get("powrot"));

  const kierunek: Kierunek =
    String(dane.get("kierunek")) === "ponizej" ? "ponizej" : "powyzej";

  const wynik = await dodajAlarm(uzytkownik.id, {
    ticker: String(dane.get("ticker") ?? "").toUpperCase(),
    nazwa: String(dane.get("nazwa") ?? ""),
    kierunek,
    cena: Number(dane.get("cena")),
    waluta: String(dane.get("waluta") ?? ""),
  });

  const zlaczenie = powrot.includes("?") ? "&" : "?";
  if (!wynik.ok) {
    redirect(`${powrot}${zlaczenie}alarm=${wynik.powod}`);
  }
  revalidatePath(powrot);
  redirect(`${powrot}${zlaczenie}alarm=dodany`);
}

export async function usun(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const id = Number(dane.get("id"));
  if (Number.isFinite(id)) await usunAlarm(uzytkownik.id, id);
  redirect(adresPowrotu(dane.get("powrot")));
}

export async function wznow(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const id = Number(dane.get("id"));
  if (Number.isFinite(id)) await wznowAlarm(uzytkownik.id, id);
  redirect(adresPowrotu(dane.get("powrot")));
}
