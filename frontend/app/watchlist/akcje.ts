"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { migawkaBezpieczna } from "@/lib/dane";
import {
  dodajListe,
  dodajObserwowana,
  pierwszaLista,
  przeniesDoListy,
  przeniesStaraWatchliste,
  usunListe,
  usunObserwowana,
  usunZeWszystkichList,
  zapiszNotatke,
  zmienNazweListy,
} from "@/lib/obserwowane";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Akcje watchlist. Każda zaczyna się od `wymagajZalogowania()` — akcja
 * serwerowa jest zwykłym punktem wejścia po sieci, więc sprawdzenie sesji
 * na stronie NIE wystarcza.
 *
 * Wszystkie funkcje zapisujące dostają id użytkownika i filtrują po nim
 * w samym SQL-u, więc podanie cudzego tickera albo cudzego id listy nic
 * nie daje.
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

function id(dane: FormData, pole: string): number {
  const n = Number(dane.get(pole));
  return Number.isFinite(n) ? n : 0;
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
    id(dane, "lista"),
    ticker,
    String(dane.get("notatka") ?? ""),
  );
  wroc(powrot, wynik.ok ? "dodany" : wynik.powod);
}

export async function usun(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  await usunObserwowana(
    uzytkownik.id,
    id(dane, "lista"),
    String(dane.get("ticker") ?? ""),
  );
  wroc(adresPowrotu(dane.get("powrot")), "usuniety");
}

export async function notatka(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  await zapiszNotatke(
    uzytkownik.id,
    id(dane, "lista"),
    String(dane.get("ticker") ?? ""),
    String(dane.get("notatka") ?? ""),
  );
  wroc(adresPowrotu(dane.get("powrot")), "notatka");
}

export async function przeniesSpolke(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const ok = await przeniesDoListy(
    uzytkownik.id,
    id(dane, "lista"),
    id(dane, "naListe"),
    String(dane.get("ticker") ?? ""),
  );
  wroc(adresPowrotu(dane.get("powrot")), ok ? "przeniesiona" : "jestJuzTam");
}

export async function przenies(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const ile = await przeniesStaraWatchliste(uzytkownik.id, id(dane, "lista"));
  wroc(adresPowrotu(dane.get("powrot")), `przeniesiono-${ile}`);
}

/**
 * Gwiazdka na profilu spółki — dokłada do listy domyślnej.
 *
 * Profil nie wie nic o listach i nie musi: decyzja „obserwuję tę spółkę"
 * zapada przy oglądaniu spółki, a przypisanie do właściwej listy jest
 * czynnością porządkową, którą robi się później na samej watchliście.
 */
export async function obserwujZProfilu(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const powrot = adresPowrotu(dane.get("powrot"));
  const ticker = String(dane.get("ticker") ?? "").trim().toUpperCase();

  const { instrumenty } = await migawkaBezpieczna();
  if (!instrumenty.some((i) => String(i.Ticker) === ticker)) {
    wroc(powrot, "nieznany");
  }

  const lista = await pierwszaLista(uzytkownik.id);
  const wynik = await dodajObserwowana(uzytkownik.id, lista, ticker);
  wroc(powrot, wynik.ok ? "dodany" : wynik.powod);
}

/** Gwiazdka na profilu — zdejmuje spółkę ze WSZYSTKICH list. */
export async function przestanObserwowac(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  await usunZeWszystkichList(uzytkownik.id, String(dane.get("ticker") ?? ""));
  wroc(adresPowrotu(dane.get("powrot")), "usuniety");
}

export async function nowaLista(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const powrot = adresPowrotu(dane.get("powrot"));
  const wynik = await dodajListe(uzytkownik.id, String(dane.get("nazwa") ?? ""));
  if (!wynik.ok) wroc(powrot, `lista-${wynik.powod}`);
  // Po założeniu listy przechodzimy od razu na nią — inaczej trzeba by jej
  // szukać wśród zakładek, a właśnie po to się ją zakładało.
  revalidatePath("/watchlist");
  redirect(`/watchlist?lista=${wynik.id}&wl=lista-dodana`);
}

export async function zmienNazwe(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const ok = await zmienNazweListy(
    uzytkownik.id,
    id(dane, "lista"),
    String(dane.get("nazwa") ?? ""),
  );
  wroc(adresPowrotu(dane.get("powrot")), ok ? "lista-nazwa" : "lista-duplikat");
}

export async function skasujListe(dane: FormData): Promise<void> {
  const uzytkownik = await wymagajZalogowania();
  const wynik = await usunListe(uzytkownik.id, id(dane, "lista"));
  if (!wynik.ok) {
    wroc(adresPowrotu(dane.get("powrot")), `lista-${wynik.powod}`);
  }
  revalidatePath("/watchlist");
  redirect("/watchlist?wl=lista-usunieta");
}
