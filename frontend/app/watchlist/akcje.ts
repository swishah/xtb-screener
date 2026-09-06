"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { migawkaBezpieczna } from "@/lib/dane";
import {
  dodajObserwowana,
  przeniesStaraWatchliste,
  usunObserwowana,
  zapiszNotatke,
} from "@/lib/obserwowane";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Akcje watchlisty. Każda zaczyna się od `wymagajZalogowania()` — akcja
 * serwerowa jest zwykłym punktem wejścia po sieci, więc sprawdzenie sesji
 * na stronie NIE wystarcza.
 *
 * Wszystkie funkcje zapisujące dostają id użytkownika i filtrują po nim
 * w samym SQL-u, więc podanie cudzego tickera nic nie daje.
 *
 * Błędy wracają jako krótkie KODY w adresie, nigdy jako gotowe zdania —
 * w adres da się wpisać dowolny tekst, więc strona wyświetlająca go wprost
 * byłaby tablicą ogłoszeniową dla kogoś, kto podeśle spreparowany link.
 */

/** Bezpieczny adres powrotu: tylko ścieżka w tej aplikacji, nigdy obca. */
function adresPowrotu(surowy: unknown): string {
  const s = String(surowy ?? "");
  // "//zly.example" przeglądarka potraktowałaby jako adres bezwzględny
  // i wyprowadziła użytkownika poza aplikację — otwarte przekierowanie.
  if (!s.startsWith("/") || s.startsWith("//")) return "/watchlist";
  return s;
}

function wroc(powrot: string, kod: string): never {
  const zlaczenie = powrot.includes("?") ? "&" : "?";
  revalidatePath(powrot);
  redirect(`${powrot}${zlaczenie}wl=${kod}`);
}

export async function dodaj(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const powrot = adresPowrotu(dane.get("powrot"));
  const ticker = String(dane.get("ticker") ?? "").trim().toUpperCase();

  // Sprawdzamy, czy taki instrument w ogóle istnieje. Bez tego literówka
  // w polu tworzy wiersz, który już nigdy nie pokaże żadnych danych —
  // wyglądałby na obserwowaną spółkę, a byłby śmieciem.
  const { instrumenty } = await migawkaBezpieczna();
  if (!instrumenty.some((i) => String(i.Ticker) === ticker)) {
    wroc(powrot, "nieznany");
  }

  const wynik = await dodajObserwowana(
    uzytkownik.id,
    ticker,
    String(dane.get("notatka") ?? ""),
  );
  wroc(powrot, wynik.ok ? "dodany" : wynik.powod);
}

export async function usun(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  await usunObserwowana(uzytkownik.id, String(dane.get("ticker") ?? ""));
  wroc(adresPowrotu(dane.get("powrot")), "usuniety");
}

export async function notatka(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  await zapiszNotatke(
    uzytkownik.id,
    String(dane.get("ticker") ?? ""),
    String(dane.get("notatka") ?? ""),
  );
  wroc(adresPowrotu(dane.get("powrot")), "notatka");
}

export async function przenies(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const ile = await przeniesStaraWatchliste(uzytkownik.id);
  wroc(adresPowrotu(dane.get("powrot")), `przeniesiono-${ile}`);
}
