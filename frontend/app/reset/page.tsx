import Link from "next/link";
import { poprosOReset } from "../logowanie/akcje";
import { pocztaSkonfigurowana } from "@/lib/poczta";

export const dynamic = "force-dynamic";

const BLEDY: Record<string, string> = {
  puste: "Podaj adres e-mail.",
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
            <p className="podtytul">
              Podaj adres, na który założone jest konto. Wyślemy link do
              ustawienia nowego hasła.
            </p>

            {blad && <p className="komunikat-blad">{blad}</p>}
            {!pocztaSkonfigurowana() && !blad && (
              <p className="komunikat-blad">
                Uwaga: wysyłka poczty nie jest jeszcze skonfigurowana, więc ten
                formularz nic nie wyśle. Brakuje EMAIL_SMTP_HOST, EMAIL_FROM
                albo EMAIL_PASSWORD w ustawieniach wdrożenia.
              </p>
            )}

            <form action={poprosOReset}>
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
              <button type="submit">Wyślij link</button>
            </form>
          </>
        )}

        <div className="pod-formularzem">
          <Link href="/logowanie">← Wróć do logowania</Link>
        </div>
      </div>
    </main>
  );
}
