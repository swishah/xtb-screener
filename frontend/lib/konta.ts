import {
  createHash,
  randomBytes,
  scrypt as scryptCb,
  timingSafeEqual,
  type ScryptOptions,
} from "node:crypto";
import { promisify } from "node:util";
import { klientZapisu } from "./dane";

/**
 * Konta użytkowników: rejestracja, logowanie, sesje, reset hasła.
 *
 * DLACZEGO BEZ BIBLIOTEKI DO UWIERZYTELNIANIA. NextAuth i spółka ciągną
 * kilkanaście zależności i własny model danych, a projekt ma żyć latami
 * u osoby, która nie programuje — każda zależność to coś, co się psuje przy
 * aktualizacji. Wszystko poniżej stoi na bibliotece standardowej Node.
 * To NIE jest "własna kryptografia": scrypt, SHA-256 i porównanie odporne na
 * pomiar czasu to gotowe, sprawdzone klocki. Własne jest tylko ich spięcie.
 *
 * DECYZJE, KTÓRYCH NIE ZMIENIAJ BEZ ZASTANOWIENIA:
 *
 * 1. **Hasła przez `scrypt`, nie przez SHA.** Zwykły skrót (nawet z solą)
 *    liczy się miliardy razy na sekundę na karcie graficznej. scrypt jest
 *    celowo powolny i pamięciożerny, więc łamanie siłowe przestaje się
 *    opłacać. Parametry zapisujemy RAZEM z hasłem, żeby dało się je kiedyś
 *    podnieść bez unieważniania starych kont.
 *
 * 2. **Sesja to losowy żeton, a w bazie leży jego SKRÓT.** Nie JWT: żetonu
 *    w JWT nie da się unieważnić przed wygaśnięciem, a my chcemy móc wylogować
 *    wszystkie urządzenia po zmianie hasła. Skrót w bazie znaczy, że wyciek
 *    samej bazy nie daje nikomu gotowych sesji.
 *
 * 3. **Logowanie nie zdradza, czy adres istnieje.** Ten sam komunikat i to samo
 *    opóźnienie w obu przypadkach — inaczej formularz logowania staje się
 *    wyszukiwarką kont.
 *
 * 4. **Rejestracja jest DOMYŚLNIE ZAMKNIĘTA.** Otwiera ją dopiero zmienna
 *    `KOD_REJESTRACJI`. Bez niej nikt nie założy konta, nawet znając adres
 *    aplikacji. To narzędzie osobiste, nie serwis.
 */

// promisify gubi wariant z opcjami, wiec typ podajemy jawnie.
const scrypt = promisify(scryptCb) as (
  haslo: string | Buffer,
  sol: string | Buffer,
  dlugosc: number,
  opcje: ScryptOptions,
) => Promise<Buffer>;

/** Parametry scrypt. Zapisywane przy haśle, więc można je kiedyś podnieść. */
const SCRYPT_N = 16384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const DLUGOSC_KLUCZA = 64;

/** Ile trwa sesja. 30 dni = logujesz się raz na miesiąc na urządzenie. */
export const DNI_SESJI = 30;

/** Żeton resetu żyje godzinę — dłużej nie ma powodu, a ryzyko rośnie. */
const MINUT_RESETU = 60;

/** Po tylu nieudanych próbach konto blokuje się na chwilę. */
const LIMIT_PROB = 10;
const MINUT_BLOKADY = 15;

export const MIN_DLUGOSC_HASLA = 10;

export type Uzytkownik = {
  id: number;
  email: string;
};

const SCHEMAT = [
  `CREATE TABLE IF NOT EXISTS uzytkownicy (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     email TEXT NOT NULL UNIQUE,
     haslo TEXT NOT NULL,
     utworzony TEXT NOT NULL,
     nieudane_proby INTEGER NOT NULL DEFAULT 0,
     zablokowany_do TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS sesje (
     token_skrot TEXT PRIMARY KEY,
     uzytkownik_id INTEGER NOT NULL,
     utworzona TEXT NOT NULL,
     wygasa TEXT NOT NULL
   )`,
  "CREATE INDEX IF NOT EXISTS idx_sesje_uzytkownik ON sesje(uzytkownik_id)",
  `CREATE TABLE IF NOT EXISTS zetony_resetu (
     token_skrot TEXT PRIMARY KEY,
     uzytkownik_id INTEGER NOT NULL,
     wygasa TEXT NOT NULL,
     uzyty INTEGER NOT NULL DEFAULT 0
   )`,
];

let schematGotowy = false;

async function zapewnijSchemat(): Promise<void> {
  if (schematGotowy) return;
  const db = klientZapisu();
  for (const polecenie of SCHEMAT) {
    await db.execute(polecenie);
  }
  schematGotowy = true;
}

// --- hasła -----------------------------------------------------------------

/** Zapis "scrypt$N$r$p$sól$klucz" — parametry razem z hasłem, patrz nagłówek. */
async function zahashuj(haslo: string): Promise<string> {
  const sol = randomBytes(16);
  const klucz = (await scrypt(haslo.normalize("NFKC"), sol, DLUGOSC_KLUCZA, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  }));
  return [
    "scrypt",
    SCRYPT_N,
    SCRYPT_R,
    SCRYPT_P,
    sol.toString("base64"),
    klucz.toString("base64"),
  ].join("$");
}

async function pasuje(haslo: string, zapisane: string): Promise<boolean> {
  const czesci = zapisane.split("$");
  if (czesci.length !== 6 || czesci[0] !== "scrypt") return false;
  const [, n, r, p, solB64, kluczB64] = czesci;
  try {
    const sol = Buffer.from(solB64, "base64");
    const oczekiwany = Buffer.from(kluczB64, "base64");
    const policzony = (await scrypt(haslo.normalize("NFKC"), sol, oczekiwany.length, {
      N: Number(n),
      r: Number(r),
      p: Number(p),
    }));
    // Porównanie odporne na pomiar czasu: zwykłe === kończy się na pierwszej
    // różnicy, co przy dużej liczbie prób zdradza, ile znaków się zgadza.
    return timingSafeEqual(policzony, oczekiwany);
  } catch {
    return false;
  }
}

/**
 * Hasło do porównania, gdy konta NIE MA. Liczymy je mimo wszystko, żeby
 * logowanie na nieistniejący adres trwało tyle samo co na istniejący —
 * inaczej czas odpowiedzi zdradza, które adresy są zarejestrowane.
 */
const HASLO_ATRAPA =
  "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$" +
  Buffer.alloc(DLUGOSC_KLUCZA).toString("base64");

// --- pomocnicze ------------------------------------------------------------

function skrot(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

function terazISO(): string {
  return new Date().toISOString();
}

function zaISO(ms: number): string {
  return new Date(Date.now() + ms).toISOString();
}

export function znormalizujEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Czy adres w ogóle wygląda na adres. Celowo luźne — walidacją jest wysyłka. */
export function poprawnyEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) && email.length <= 254;
}

export function rejestracjaOtwarta(): boolean {
  return Boolean(process.env.KOD_REJESTRACJI);
}

// --- konta -----------------------------------------------------------------

export async function utworzKonto(
  email: string,
  haslo: string,
): Promise<{ ok: true; id: number } | { ok: false; powod: string }> {
  const adres = znormalizujEmail(email);
  if (!poprawnyEmail(adres)) {
    return { ok: false, powod: "To nie wygląda na poprawny adres e-mail." };
  }
  if (haslo.length < MIN_DLUGOSC_HASLA) {
    return {
      ok: false,
      powod: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
    };
  }

  await zapewnijSchemat();
  const db = klientZapisu();
  const istnieje = await db.execute({
    sql: "SELECT id FROM uzytkownicy WHERE email = ?",
    args: [adres],
  });
  if (istnieje.rows.length > 0) {
    return { ok: false, powod: "Konto z tym adresem już istnieje." };
  }

  const wynik = await db.execute({
    sql: "INSERT INTO uzytkownicy (email, haslo, utworzony) VALUES (?, ?, ?)",
    args: [adres, await zahashuj(haslo), terazISO()],
  });
  return { ok: true, id: Number(wynik.lastInsertRowid ?? 0) };
}

/**
 * Sprawdza dane logowania. Zwraca użytkownika albo null — BEZ informacji,
 * czy zawiodło hasło, czy adres.
 */
export async function sprawdzHaslo(
  email: string,
  haslo: string,
): Promise<Uzytkownik | null> {
  await zapewnijSchemat();
  const db = klientZapisu();
  const adres = znormalizujEmail(email);
  const wynik = await db.execute({
    sql: "SELECT id, email, haslo, zablokowany_do, nieudane_proby FROM uzytkownicy WHERE email = ?",
    args: [adres],
  });

  if (wynik.rows.length === 0) {
    await pasuje(haslo, HASLO_ATRAPA); // wyrównanie czasu — patrz komentarz wyżej
    return null;
  }

  const w = wynik.rows[0] as unknown as {
    id: number;
    email: string;
    haslo: string;
    zablokowany_do: string | null;
    nieudane_proby: number;
  };

  if (w.zablokowany_do && w.zablokowany_do > terazISO()) {
    return null;
  }

  if (await pasuje(haslo, w.haslo)) {
    if (w.nieudane_proby > 0) {
      await db.execute({
        sql: "UPDATE uzytkownicy SET nieudane_proby = 0, zablokowany_do = NULL WHERE id = ?",
        args: [w.id],
      });
    }
    return { id: Number(w.id), email: String(w.email) };
  }

  const proby = Number(w.nieudane_proby) + 1;
  await db.execute({
    sql: "UPDATE uzytkownicy SET nieudane_proby = ?, zablokowany_do = ? WHERE id = ?",
    args: [
      proby,
      proby >= LIMIT_PROB ? zaISO(MINUT_BLOKADY * 60_000) : null,
      w.id,
    ],
  });
  return null;
}

export async function zmienHaslo(
  uzytkownikId: number,
  noweHaslo: string,
): Promise<{ ok: boolean; powod?: string }> {
  if (noweHaslo.length < MIN_DLUGOSC_HASLA) {
    return {
      ok: false,
      powod: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
    };
  }
  await zapewnijSchemat();
  const db = klientZapisu();
  await db.execute({
    sql: "UPDATE uzytkownicy SET haslo = ?, nieudane_proby = 0, zablokowany_do = NULL WHERE id = ?",
    args: [await zahashuj(noweHaslo), uzytkownikId],
  });
  // Zmiana hasła wyrzuca WSZYSTKIE urządzenia. Jeśli ktoś zmienia hasło,
  // bo podejrzewa włamanie, zostawienie cudzej sesji byłoby bezużyteczne.
  await db.execute({
    sql: "DELETE FROM sesje WHERE uzytkownik_id = ?",
    args: [uzytkownikId],
  });
  return { ok: true };
}

// --- sesje -----------------------------------------------------------------

/** Tworzy sesję i zwraca ŻETON — w bazie ląduje wyłącznie jego skrót. */
export async function utworzSesje(uzytkownikId: number): Promise<string> {
  await zapewnijSchemat();
  const token = randomBytes(32).toString("base64url");
  await klientZapisu().execute({
    sql: "INSERT INTO sesje (token_skrot, uzytkownik_id, utworzona, wygasa) VALUES (?, ?, ?, ?)",
    args: [
      skrot(token),
      uzytkownikId,
      terazISO(),
      zaISO(DNI_SESJI * 24 * 60 * 60 * 1000),
    ],
  });
  return token;
}

export async function uzytkownikSesji(token: string): Promise<Uzytkownik | null> {
  if (!token) return null;
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    sql: `SELECT u.id, u.email FROM sesje s
          JOIN uzytkownicy u ON u.id = s.uzytkownik_id
          WHERE s.token_skrot = ? AND s.wygasa > ?`,
    args: [skrot(token), terazISO()],
  });
  if (wynik.rows.length === 0) return null;
  const w = wynik.rows[0] as unknown as { id: number; email: string };
  return { id: Number(w.id), email: String(w.email) };
}

export async function usunSesje(token: string): Promise<void> {
  if (!token) return;
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: "DELETE FROM sesje WHERE token_skrot = ?",
    args: [skrot(token)],
  });
}

// --- reset hasła -----------------------------------------------------------

/**
 * Tworzy żeton resetu. Zwraca null, gdy konta nie ma — ale strona i tak
 * pokazuje ten sam komunikat, żeby formularz nie zdradzał listy adresów.
 */
export async function utworzZetonResetu(email: string): Promise<string | null> {
  await zapewnijSchemat();
  const db = klientZapisu();
  const wynik = await db.execute({
    sql: "SELECT id FROM uzytkownicy WHERE email = ?",
    args: [znormalizujEmail(email)],
  });
  if (wynik.rows.length === 0) return null;

  const uzytkownikId = Number((wynik.rows[0] as unknown as { id: number }).id);
  const token = randomBytes(32).toString("base64url");
  await db.execute({
    sql: "INSERT INTO zetony_resetu (token_skrot, uzytkownik_id, wygasa) VALUES (?, ?, ?)",
    args: [skrot(token), uzytkownikId, zaISO(MINUT_RESETU * 60_000)],
  });
  return token;
}

/** Zużywa żeton i ustawia nowe hasło. Żeton działa RAZ. */
export async function ustawHasloZetonem(
  token: string,
  noweHaslo: string,
): Promise<{ ok: boolean; powod?: string }> {
  await zapewnijSchemat();
  const db = klientZapisu();
  const wynik = await db.execute({
    sql: "SELECT uzytkownik_id FROM zetony_resetu WHERE token_skrot = ? AND uzyty = 0 AND wygasa > ?",
    args: [skrot(token), terazISO()],
  });
  if (wynik.rows.length === 0) {
    return {
      ok: false,
      powod:
        "Ten link do zmiany hasła jest nieaktualny — wygasł albo został już użyty. Poproś o nowy.",
    };
  }
  const uzytkownikId = Number(
    (wynik.rows[0] as unknown as { uzytkownik_id: number }).uzytkownik_id,
  );

  const zmiana = await zmienHaslo(uzytkownikId, noweHaslo);
  if (!zmiana.ok) return zmiana;

  await db.execute({
    sql: "UPDATE zetony_resetu SET uzyty = 1 WHERE token_skrot = ?",
    args: [skrot(token)],
  });
  return { ok: true };
}

// --- reset hasła KODEM, bez poczty -----------------------------------------

/**
 * Kod uprawniający do zmiany hasła bez wysyłania maila.
 *
 * Bierzemy `KOD_RESETU`, a gdy go nie ma — `KOD_REJESTRACJI`. Ten drugi
 * wariant jest świadomym ustępstwem na rzecz wygody: jeden sekret do
 * zapamiętania zamiast dwóch.
 *
 * MA JEDNAK CENĘ I TRZEBA JĄ ZNAĆ. Kod rejestracji staje się wtedy KLUCZEM
 * UNIWERSALNYM do każdego konta w tej instalacji: kto go zna, ustawia dowolne
 * hasło, nie mając dostępu do skrzynki właściciela. Przy reset przez maila
 * przejęcie konta wymaga włamania na pocztę; tutaj wystarczy sam kod.
 * Ustawienie osobnego `KOD_RESETU` rozdziela te dwie role — zalecane, gdy kont
 * jest więcej niż jedno albo gdy kod rejestracji komuś się podało.
 */
export function kodResetu(): string {
  return process.env.KOD_RESETU || process.env.KOD_REJESTRACJI || "";
}

export function resetKodemMozliwy(): boolean {
  return Boolean(kodResetu());
}

/**
 * Porównanie kodów odporne na pomiar czasu.
 *
 * Porównujemy SKRÓTY, nie same kody: `timingSafeEqual` wymaga bufory tej samej
 * długości i rzuca wyjątkiem przy różnych, a sama długość odpowiedzi zdradzałaby
 * długość prawdziwego kodu. Skrót wyrównuje to do 32 bajtów zawsze.
 */
function kodyRowne(podany: string, oczekiwany: string): boolean {
  if (!oczekiwany) return false;
  return timingSafeEqual(
    createHash("sha256").update(podany).digest(),
    createHash("sha256").update(oczekiwany).digest(),
  );
}

/**
 * Ustawia nowe hasło po podaniu adresu i kodu. Zwraca KOD błędu, nie zdanie.
 *
 * NIEISTNIEJĄCE KONTO, KONTO ZABLOKOWANE I ZŁY KOD DAJĄ TEN SAM WYNIK.
 * Rozróżnienie ich powiedziałoby obcemu, które adresy są zarejestrowane
 * i czy trafił w kod — czyli dokładnie to, czego ekran logowania pilnuje
 * od początku.
 */
export async function ustawHasloKodem(
  email: string,
  kod: string,
  noweHaslo: string,
): Promise<{ ok: boolean; powod?: string }> {
  // Długość hasła sprawdzamy PRZED kodem i bez naliczania próby. To pomyłka
  // użytkownika, nie atak — a gdyby szło odwrotnie, komunikat „za krótkie"
  // pojawiałby się wyłącznie po trafieniu kodu i tym samym by go potwierdzał.
  if (noweHaslo.length < MIN_DLUGOSC_HASLA) return { ok: false, powod: "krotkie" };

  const oczekiwany = kodResetu();
  if (!oczekiwany) return { ok: false, powod: "wylaczone" };

  await zapewnijSchemat();
  const db = klientZapisu();
  const wynik = await db.execute({
    sql: "SELECT id, zablokowany_do, nieudane_proby FROM uzytkownicy WHERE email = ?",
    args: [znormalizujEmail(email)],
  });

  if (wynik.rows.length === 0) {
    kodyRowne(kod, oczekiwany); // wyrównanie czasu, wynik celowo pomijany
    return { ok: false, powod: "dane" };
  }

  const w = wynik.rows[0] as unknown as {
    id: number;
    zablokowany_do: string | null;
    nieudane_proby: number;
  };

  if (w.zablokowany_do && w.zablokowany_do > terazISO()) {
    return { ok: false, powod: "dane" };
  }

  if (!kodyRowne(kod, oczekiwany)) {
    // TA SAMA PULA PRÓB CO PRZY LOGOWANIU, i to jest istotne: gdyby reset
    // miał własny licznik, byłby furtką omijającą blokadę po nieudanych
    // logowaniach — wystarczyłoby zgadywać kod zamiast hasła.
    const proby = Number(w.nieudane_proby) + 1;
    await db.execute({
      sql: "UPDATE uzytkownicy SET nieudane_proby = ?, zablokowany_do = ? WHERE id = ?",
      args: [
        proby,
        proby >= LIMIT_PROB ? zaISO(MINUT_BLOKADY * 60_000) : null,
        w.id,
      ],
    });
    return { ok: false, powod: "dane" };
  }

  // zmienHaslo zeruje licznik prób i kasuje WSZYSTKIE sesje — więc udany
  // reset wylogowuje też ewentualnego intruza, który już siedział w koncie.
  const zmiana = await zmienHaslo(Number(w.id), noweHaslo);
  return zmiana.ok ? { ok: true } : { ok: false, powod: "krotkie" };
}

/** Sprzątanie wygasłych wierszy. Wołane przy okazji logowania — bez crona. */
export async function posprzataj(): Promise<void> {
  await zapewnijSchemat();
  const db = klientZapisu();
  const teraz = terazISO();
  await db.execute({ sql: "DELETE FROM sesje WHERE wygasa < ?", args: [teraz] });
  await db.execute({
    sql: "DELETE FROM zetony_resetu WHERE wygasa < ?",
    args: [teraz],
  });
}
