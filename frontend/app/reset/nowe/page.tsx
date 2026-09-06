import Link from "next/link";
import { redirect } from "next/navigation";
import { ustawNoweHaslo } from "../../logowanie/akcje";
import { MIN_DLUGOSC_HASLA } from "@/lib/konta";

export const dynamic = "force-dynamic";

const BLEDY: Record<string, string> = {
  rozne: "Podane hasła nie są takie same.",
  krotkie: `Hasło musi mieć co najmniej ${MIN_DLUGOSC_HASLA} znaków.`,
};

export default async function NoweHaslo({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const token = jeden("token") ?? "";
  if (!token) redirect("/reset?blad=zeton");

  const blad = BLEDY[jeden("blad") ?? ""];

  return (
    <main className="wrap-logowanie">
      <div className="karta-logowania">
        <h1>Ustaw nowe hasło</h1>
        <p className="podtytul">
          Po zapisaniu wylogujemy wszystkie urządzenia — na każdym trzeba będzie
          zalogować się nowym hasłem.
        </p>

        {blad && <p className="komunikat-blad">{blad}</p>}

        <form action={ustawNoweHaslo}>
          <input type="hidden" name="token" value={token} />
          <label>
            <span>Nowe hasło (min. {MIN_DLUGOSC_HASLA} znaków)</span>
            <input
              type="password"
              name="haslo"
              autoComplete="new-password"
              minLength={MIN_DLUGOSC_HASLA}
              required
              autoFocus
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
          <button type="submit">Zapisz hasło</button>
        </form>

        <div className="pod-formularzem">
          <Link href="/logowanie">← Wróć do logowania</Link>
        </div>
      </div>
    </main>
  );
}
