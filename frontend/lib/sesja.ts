import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { DNI_SESJI, uzytkownikSesji, type Uzytkownik } from "./konta";

/**
 * Sesja widziana od strony stron i akcji serwerowych.
 *
 * DLACZEGO NIE `middleware.ts`. Middleware Next.js chodzi w środowisku Edge,
 * w którym nie ma `node:crypto` ani klienta bazy — a sprawdzenie sesji wymaga
 * obu. Można by sprawdzać w middleware samą OBECNOŚĆ ciasteczka, ale to
 * bardzo słaby strażnik: dowolna wartość ciasteczka by przeszła. Dlatego
 * każda chroniona strona woła `wymagajZalogowania()` u siebie na górze —
 * jawnie, jedną linijką, bez magii.
 */

export const CIASTECZKO = "sesja";

export async function zalogowany(): Promise<Uzytkownik | null> {
  const token = (await cookies()).get(CIASTECZKO)?.value ?? "";
  if (!token) return null;
  try {
    return await uzytkownikSesji(token);
  } catch (e) {
    // Brak tokenu zapisu albo padnięta baza nie może kończyć się białym
    // ekranem — traktujemy to jak brak sesji i pokazujemy logowanie.
    console.error("Nie udało się sprawdzić sesji:", e);
    return null;
  }
}

/** Wpuszcza dalej albo przekierowuje na logowanie. Woła się na górze strony. */
export async function wymagajZalogowania(): Promise<Uzytkownik> {
  const uzytkownik = await zalogowany();
  if (!uzytkownik) redirect("/logowanie");
  return uzytkownik;
}

export async function ustawCiasteczkoSesji(token: string): Promise<void> {
  (await cookies()).set(CIASTECZKO, token, {
    httpOnly: true, // JavaScript strony nie ma po co widzieć żetonu
    sameSite: "lax", // blokuje wysyłkę przy żądaniach z obcych witryn
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: DNI_SESJI * 24 * 60 * 60,
  });
}

export async function skasujCiasteczkoSesji(): Promise<void> {
  (await cookies()).delete(CIASTECZKO);
}
