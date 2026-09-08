"use server";

import { redirect } from "next/navigation";
import {
  MIN_DLUGOSC_HASLA,
  posprzataj,
  sprawdzHaslo,
  ustawHasloKodem,
  ustawHasloZetonem,
  utworzKonto,
  utworzSesje,
  utworzZetonResetu,
  zmienHaslo,
} from "@/lib/konta";
import { adresAplikacji, pocztaSkonfigurowana, wyslijMail } from "@/lib/poczta";
import {
  CIASTECZKO,
  skasujCiasteczkoSesji,
  ustawCiasteczkoSesji,
  zalogowany,
} from "@/lib/sesja";
import { cookies } from "next/headers";
import { usunSesje } from "@/lib/konta";

/**
 * Akcje serwerowe formularzy logowania.
 *
 * DZIAŁAJĄ BEZ JAVASCRIPTU. Formularze wysyłają się normalnym POST-em,
 * a akcja kończy się przekierowaniem. Dzięki temu logowanie działa nawet
 * przy zablokowanych skryptach i nie wymaga ani jednego komponentu
 * klienckiego — spójnie z resztą frontendu.
 *
 * BŁĘDY WRACAJĄ JAKO KRÓTKIE KODY w adresie (`?blad=dane`), a nie jako
 * gotowe zdania. Adres nie jest miejscem na komunikaty: da się w nim wstawić
 * dowolny tekst, więc strona wyświetlająca go wprost byłaby tablicą
 * ogłoszeniową dla kogoś, kto podeśle spreparowany link.
 */

export async function zaloguj(dane: FormData): Promise<void> {
  const email = String(dane.get("email") ?? "");
  const haslo = String(dane.get("haslo") ?? "");
  if (!email || !haslo) redirect("/logowanie?blad=puste");

  const uzytkownik = await sprawdzHaslo(email, haslo);
  if (!uzytkownik) redirect("/logowanie?blad=dane");

  const token = await utworzSesje(uzytkownik.id);
  await ustawCiasteczkoSesji(token);
  // Sprzątanie przy okazji logowania — nie potrzeba do tego osobnego crona.
  posprzataj().catch(() => {});
  redirect("/");
}

export async function wyloguj(): Promise<void> {
  const token = (await cookies()).get(CIASTECZKO)?.value ?? "";
  await usunSesje(token);
  await skasujCiasteczkoSesji();
  redirect("/logowanie?info=wylogowano");
}

export async function zarejestruj(dane: FormData): Promise<void> {
  const kod = process.env.KOD_REJESTRACJI;
  if (!kod) redirect("/rejestracja?blad=zamknieta");
  if (String(dane.get("kod") ?? "") !== kod) {
    redirect("/rejestracja?blad=kod");
  }

  const email = String(dane.get("email") ?? "");
  const haslo = String(dane.get("haslo") ?? "");
  const powtorz = String(dane.get("powtorz") ?? "");
  if (haslo !== powtorz) redirect("/rejestracja?blad=rozne");

  const wynik = await utworzKonto(email, haslo);
  if (!wynik.ok) {
    const kodBledu = wynik.powod.includes("już istnieje")
      ? "istnieje"
      : wynik.powod.includes("adres")
        ? "email"
        : "haslo";
    redirect(`/rejestracja?blad=${kodBledu}`);
  }

  const token = await utworzSesje(wynik.id);
  await ustawCiasteczkoSesji(token);
  redirect("/");
}

export async function poprosOReset(dane: FormData): Promise<void> {
  const email = String(dane.get("email") ?? "");
  if (!email) redirect("/reset?blad=puste");

  if (!pocztaSkonfigurowana()) {
    redirect("/reset?blad=poczta");
  }

  const token = await utworzZetonResetu(email);
  // Gdy konta nie ma, token jest pusty i NIC nie wysyłamy — ale komunikat
  // dla użytkownika jest ten sam. Inaczej formularz mówiłby obcym, które
  // adresy są zarejestrowane.
  if (token) {
    const link = `${adresAplikacji()}/reset/nowe?token=${encodeURIComponent(token)}`;
    await wyslijMail(
      email,
      "Zmiana hasła — XTB Screener",
      "Ktoś (mam nadzieję, że Ty) poprosił o zmianę hasła do XTB Screenera.\n\n" +
        `Kliknij ten link, żeby ustawić nowe hasło:\n${link}\n\n` +
        "Link działa przez godzinę i tylko raz.\n\n" +
        "Jeśli to nie Ty prosiłeś o zmianę — zignoruj tę wiadomość. " +
        "Twoje hasło pozostaje bez zmian.",
    );
  }
  redirect("/reset?info=wyslano");
}

/**
 * Reset hasła KODEM, bez poczty — jeden formularz zamiast maila z linkiem.
 *
 * Kody błędów są celowo ubogie: `dane` znaczy „adres, kod albo blokada",
 * bez rozróżnienia. Gdyby strona mówiła, które z nich zawiodło, formularz
 * zdradzałby listę zarejestrowanych adresów i potwierdzał trafienie w kod.
 */
export async function resetujKodem(dane: FormData): Promise<void> {
  const email = String(dane.get("email") ?? "");
  const kod = String(dane.get("kod") ?? "");
  const haslo = String(dane.get("haslo") ?? "");
  const powtorz = String(dane.get("powtorz") ?? "");

  if (!email || !kod || !haslo) redirect("/reset?blad=puste");
  if (haslo !== powtorz) redirect("/reset?blad=rozne");

  const wynik = await ustawHasloKodem(email, kod, haslo);
  if (!wynik.ok) redirect(`/reset?blad=${wynik.powod ?? "dane"}`);

  redirect("/logowanie?info=haslo");
}

export async function ustawNoweHaslo(dane: FormData): Promise<void> {
  const token = String(dane.get("token") ?? "");
  const haslo = String(dane.get("haslo") ?? "");
  const powtorz = String(dane.get("powtorz") ?? "");
  const wroc = `/reset/nowe?token=${encodeURIComponent(token)}`;

  if (!token) redirect("/reset?blad=zeton");
  if (haslo !== powtorz) redirect(`${wroc}&blad=rozne`);
  if (haslo.length < MIN_DLUGOSC_HASLA) redirect(`${wroc}&blad=krotkie`);

  const wynik = await ustawHasloZetonem(token, haslo);
  if (!wynik.ok) redirect("/reset?blad=zeton");
  redirect("/logowanie?info=haslo");
}

export async function zmienWlasneHaslo(dane: FormData): Promise<void> {
  const uzytkownik = await zalogowany();
  if (!uzytkownik) redirect("/logowanie");

  const stare = String(dane.get("stare") ?? "");
  const nowe = String(dane.get("nowe") ?? "");
  const powtorz = String(dane.get("powtorz") ?? "");

  // Zmiana hasła wymaga podania starego — inaczej wystarczyłoby dorwać się
  // do niezablokowanego ekranu, żeby przejąć konto na stałe.
  if (!(await sprawdzHaslo(uzytkownik.email, stare))) {
    redirect("/konto?blad=stare");
  }
  if (nowe !== powtorz) redirect("/konto?blad=rozne");

  const wynik = await zmienHaslo(uzytkownik.id, nowe);
  if (!wynik.ok) redirect("/konto?blad=krotkie");

  // zmienHaslo kasuje wszystkie sesje, więc trzeba zalogować się na nowo.
  await skasujCiasteczkoSesji();
  redirect("/logowanie?info=haslo");
}
