import Link from "next/link";
import { wyloguj, zmienWlasneHaslo } from "../logowanie/akcje";
import { MIN_DLUGOSC_HASLA } from "@/lib/konta";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const BLEDY: Record<string, string> = {
  stare: "Obecne hasło jest nieprawidłowe.",
  rozne: "Nowe hasła nie są takie same.",
  krotkie: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
};

/**
 * Konto — celowo minimalne. Adres, zmiana hasła, wylogowanie. Reszta ustawień
 * dojdzie wtedy, gdy będzie czym je wypełnić (alarmy, powiadomienia).
 */
export default async function Konto({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const uzytkownik = await wymagajZalogowania();
  const q = await searchParams;
  const surowy = q.blad;
  const blad = BLEDY[(Array.isArray(surowy) ? surowy[0] : surowy) ?? ""];

  return (
    <main className="wrap">
      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Konto</h2>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <div className="card" style={{ marginTop: 12, padding: 20 }}>
        <p style={{ margin: 0 }}>
          Zalogowany jako <b>{uzytkownik.email}</b>
        </p>
        <form action={wyloguj} style={{ marginTop: 14 }}>
          <button type="submit" className="btn-wtorny">
            Wyloguj się
          </button>
        </form>
      </div>

      <div className="card" style={{ marginTop: 12, padding: 20 }}>
        <h3 style={{ margin: "0 0 4px", fontSize: "1rem" }}>Zmiana hasła</h3>
        <p className="brak" style={{ margin: "0 0 14px", fontSize: "0.85rem" }}>
          Po zmianie wylogują się wszystkie urządzenia — także to.
        </p>

        {blad && <p className="komunikat-blad">{blad}</p>}

        <form action={zmienWlasneHaslo} className="formularz-konta">
          <label>
            <span>Obecne hasło</span>
            <input
              type="password"
              name="stare"
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            <span>Nowe hasło (min. {MIN_DLUGOSC_HASLA} znaków)</span>
            <input
              type="password"
              name="nowe"
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
          <button type="submit">Zmień hasło</button>
        </form>
      </div>
    </main>
  );
}
