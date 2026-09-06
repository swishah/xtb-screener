import Link from "next/link";
import { redirect } from "next/navigation";
import { zarejestruj } from "../logowanie/akcje";
import { MIN_DLUGOSC_HASLA, rejestracjaOtwarta } from "@/lib/konta";
import { zalogowany } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const BLEDY: Record<string, string> = {
  zamknieta: "Rejestracja jest wyłączona.",
  kod: "Nieprawidłowy kod rejestracji.",
  rozne: "Podane hasła nie są takie same.",
  istnieje: "Konto z tym adresem już istnieje.",
  email: "To nie wygląda na poprawny adres e-mail.",
  haslo: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
};

export default async function Rejestracja({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (await zalogowany()) redirect("/");

  const q = await searchParams;
  const surowy = q.blad;
  const blad = BLEDY[(Array.isArray(surowy) ? surowy[0] : surowy) ?? ""];

  if (!rejestracjaOtwarta()) {
    return (
      <main className="wrap-logowanie">
        <div className="karta-logowania">
          <h1>Rejestracja wyłączona</h1>
          <p className="podtytul">
            Zakładanie kont jest domyślnie zamknięte — to narzędzie osobiste,
            nie serwis. Żeby je otworzyć, ustaw zmienną{" "}
            <code>KOD_REJESTRACJI</code> w ustawieniach wdrożenia; wtedy konto
            założy tylko ktoś, kto zna ten kod.
          </p>
          <div className="pod-formularzem">
            <Link href="/logowanie">← Wróć do logowania</Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="wrap-logowanie">
      <div className="karta-logowania">
        <h1>Załóż konto</h1>
        <p className="podtytul">
          Potrzebny jest kod rejestracji — ten sam, który ustawiłeś w zmiennej{" "}
          <code>KOD_REJESTRACJI</code>.
        </p>

        {blad && <p className="komunikat-blad">{blad}</p>}

        <form action={zarejestruj}>
          <label>
            <span>Kod rejestracji</span>
            <input type="password" name="kod" required autoFocus />
          </label>
          <label>
            <span>Adres e-mail</span>
            <input type="email" name="email" autoComplete="username" required />
          </label>
          <label>
            <span>Hasło (min. {MIN_DLUGOSC_HASLA} znaków)</span>
            <input
              type="password"
              name="haslo"
              autoComplete="new-password"
              minLength={MIN_DLUGOSC_HASLA}
              required
            />
          </label>
          <label>
            <span>Powtórz hasło</span>
            <input
              type="password"
              name="powtorz"
              autoComplete="new-password"
              minLength={MIN_DLUGOSC_HASLA}
              required
            />
          </label>
          <button type="submit">Załóż konto</button>
        </form>

        <div className="pod-formularzem">
          <Link href="/logowanie">← Wróć do logowania</Link>
        </div>
      </div>
    </main>
  );
}
