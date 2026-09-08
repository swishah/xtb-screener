import Link from "next/link";
import { poprosOReset, resetujKodem } from "../logowanie/akcje";
import { MIN_DLUGOSC_HASLA, resetKodemMozliwy } from "@/lib/konta";
import { pocztaSkonfigurowana } from "@/lib/poczta";

export const dynamic = "force-dynamic";

/**
 * Odzyskanie hasła. Dwie drogi, obie opcjonalne.
 *
 * KODEM (gdy ustawiony KOD_RESETU albo KOD_REJESTRACJI) — jeden formularz,
 * bez poczty. MAILEM (gdy skonfigurowany SMTP) — link ważny godzinę.
 * Gdy żadna nie jest dostępna, mówimy to wprost zamiast pokazywać formularz,
 * który z założenia nic nie zrobi.
 */

const BLEDY: Record<string, string> = {
  puste: "Wypełnij wszystkie pola.",
  rozne: "Hasła nie są takie same.",
  krotkie: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
  // Jeden komunikat na trzy różne przyczyny — patrz komentarz przy
  // ustawHasloKodem w lib/konta.ts.
  dane: "Nie udało się zmienić hasła. Sprawdź adres i kod.",
  wylaczone:
    "Zmiana hasła kodem nie jest włączona. Trzeba ustawić KOD_RESETU albo " +
    "KOD_REJESTRACJI w ustawieniach wdrożenia.",
  zeton: "Link do zmiany hasła wygasł albo został już użyty. Poproś o nowy.",
  poczta:
    "Wysyłka poczty nie jest skonfigurowana, więc nie mam jak wysłać linku. " +
    "Trzeba ustawić EMAIL_SMTP_HOST, EMAIL_FROM i EMAIL_PASSWORD.",
};

export default async function Reset({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const blad = BLEDY[jeden("blad") ?? ""];
  const wyslano = jeden("info") === "wyslano";

  const kodem = resetKodemMozliwy();
  const mailem = pocztaSkonfigurowana();

  return (
    <main className="wrap-logowanie">
      <div className="karta-logowania">
        <h1>Nie pamiętam hasła</h1>

        {wyslano ? (
          <>
            {/* Ten sam komunikat niezależnie od tego, czy konto istnieje —
                inaczej formularz zdradzałby, które adresy są zarejestrowane. */}
            <p className="komunikat-info">
              Jeśli konto o tym adresie istnieje, wysłaliśmy na nie link do
              zmiany hasła. Link działa przez godzinę i tylko raz.
            </p>
            <p className="podtytul">
              Nie ma wiadomości? Sprawdź folder ze spamem.
            </p>
          </>
        ) : (
          <>
            {blad && <p className="komunikat-blad">{blad}</p>}

            {!kodem && !mailem && (
              <p className="komunikat-blad">
                Odzyskiwanie hasła nie jest włączone — brakuje i kodu
                (<code>KOD_RESETU</code> albo <code>KOD_REJESTRACJI</code>),
                i konfiguracji poczty. Hasło da się wtedy ustawić wyłącznie
                skryptem <code>scripts/ustaw_haslo.py</code> z komputera
                z dostępem do bazy.
              </p>
            )}

            {kodem && (
              <>
                <p className="podtytul">
                  Podaj adres konta i kod, którym zakładasz konta. Ustawisz
                  nowe hasło od razu, bez maila.
                </p>

                <form action={resetujKodem}>
                  <label>
                    <span>Adres e-mail</span>
                    <input
                      type="email"
                      name="email"
                      autoComplete="username"
                      required
                      autoFocus
                    />
                  </label>
                  <label>
                    <span>Kod</span>
                    <input type="password" name="kod" required />
                  </label>
                  <label>
                    <span>Nowe hasło (min. {MIN_DLUGOSC_HASLA} znaków)</span>
                    <input
                      type="password"
                      name="haslo"
                      autoComplete="new-password"
                      minLength={MIN_DLUGOSC_HASLA}
                      required
                    />
                  </label>
                  <label>
                    <span>Powtórz nowe hasło</span>
                    <input
                      type="password"
                      name="powtorz"
                      autoComplete="new-password"
                      minLength={MIN_DLUGOSC_HASLA}
                      required
                    />
                  </label>
                  <button type="submit">Ustaw nowe hasło</button>
                </form>

                <p className="drobne" style={{ marginTop: 12 }}>
                  Po zmianie hasła wszystkie urządzenia zostają wylogowane —
                  także to, z którego ktoś mógł korzystać bez Twojej wiedzy.
                </p>
              </>
            )}

            {kodem && mailem && <hr className="rozdzielacz" />}

            {mailem && (
              <>
                <p className="podtytul">
                  {kodem
                    ? "Albo poproś o link na maila — działa godzinę i tylko raz."
                    : "Podaj adres, na który założone jest konto. Wyślemy link do ustawienia nowego hasła."}
                </p>
                <form action={poprosOReset}>
                  <label>
                    <span>Adres e-mail</span>
                    <input
                      type="email"
                      name="email"
                      autoComplete="username"
                      required
                    />
                  </label>
                  <button type="submit">Wyślij link</button>
                </form>
              </>
            )}
          </>
        )}

        <div className="pod-formularzem">
          <Link href="/logowanie">← Wróć do logowania</Link>
        </div>
      </div>
    </main>
  );
}
