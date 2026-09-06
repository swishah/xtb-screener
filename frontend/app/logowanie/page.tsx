import Link from "next/link";
import { redirect } from "next/navigation";
import { zaloguj } from "./akcje";
import { rejestracjaOtwarta } from "@/lib/konta";
import { zalogowany } from "@/lib/sesja";

export const dynamic = "force-dynamic";

/**
 * Komunikaty trzymamy TUTAJ, a w adresie chodzą tylko krótkie kody. Adres da
 * się dowolnie spreparować, więc wyświetlanie jego zawartości wprost robiłoby
 * ze strony logowania tablicę ogłoszeniową dla obcych.
 */
const BLEDY: Record<string, string> = {
  dane: "Nieprawidłowy adres e-mail lub hasło.",
  puste: "Podaj adres e-mail i hasło.",
};

const INFO: Record<string, string> = {
  wylogowano: "Wylogowano. Do zobaczenia.",
  haslo: "Hasło zmienione. Zaloguj się nowym.",
};

export default async function Logowanie({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (await zalogowany()) redirect("/");

  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const blad = BLEDY[jeden("blad") ?? ""];
  const info = INFO[jeden("info") ?? ""];

  return (
    <main className="wrap-logowanie">
      <div className="karta-logowania">
        <h1>XTB Screener</h1>
        <p className="podtytul">Zaloguj się, żeby zobaczyć swoje dane.</p>

        {blad && <p className="komunikat-blad">{blad}</p>}
        {info && <p className="komunikat-info">{info}</p>}

        <form action={zaloguj}>
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
            <span>Hasło</span>
            <input
              type="password"
              name="haslo"
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit">Zaloguj</button>
        </form>

        <div className="pod-formularzem">
          <Link href="/reset">Nie pamiętam hasła</Link>
          {rejestracjaOtwarta() && <Link href="/rejestracja">Załóż konto</Link>}
        </div>
      </div>
    </main>
  );
}
