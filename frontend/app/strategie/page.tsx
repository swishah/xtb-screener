import Link from "next/link";
import Pasek from "../Pasek";
import TabelaStrategii from "./TabelaStrategii";
import { migawkaBezpieczna } from "@/lib/dane";
import { liczba, porownajRemis } from "@/lib/filtry";
import { STRATEGIE, znajdzStrategie } from "@/lib/strategie";

export const dynamic = "force-dynamic";

const ILE = 30;

export default async function Strategie({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const wybrany = Array.isArray(q.s) ? q.s[0] : q.s;
  const strategia = znajdzStrategie(wybrany);

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();

  // Spółka bez policzonego wyniku nie ma czego szukać w rankingu — inaczej
  // wypełniałaby koniec listy zerami i sugerowała, że została oceniona.
  const ranking = instrumenty
    .filter((i) => i.Typ === "stock" && liczba(i[strategia.kolumnaScore]) !== null)
    .sort((a, b) => {
      const roznica =
        (liczba(b[strategia.kolumnaScore]) ?? 0) -
        (liczba(a[strategia.kolumnaScore]) ?? 0);
      // Wyniki strategii są całkowite i niskie, więc na szczycie remisuje
      // kilkanaście spółek naraz. Bez jawnej reguły czołówka byłaby losowa
      // i zmieniałaby się między odświeżeniami — patrz porownajRemis().
      return roznica !== 0 ? roznica : porownajRemis(a, b);
    });

  const czolo = ranking.slice(0, ILE);
  const najlepszyWynik = liczba(czolo[0]?.[strategia.kolumnaScore]) ?? 0;

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      {blad && (
        <div className="alert">
          <b>Nie udało się wczytać danych.</b>
          <div style={{ marginTop: 8, fontSize: "0.78rem", opacity: 0.75 }}>{blad}</div>
        </div>
      )}

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Strategie</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      {/* Wybór strategii zwykłymi odnośnikami, nie przyciskami: adres URL
          jednoznacznie opisuje widok, więc da się go zapisać i wysłać. */}
      <nav className="wybor">
        {STRATEGIE.map((s) => (
          <Link
            key={s.klucz}
            href={`/strategie?s=${s.klucz}`}
            className={`wybor-poz${s.klucz === strategia.klucz ? " aktywna" : ""}`}
            aria-current={s.klucz === strategia.klucz ? "page" : undefined}
          >
            {s.nazwa}
          </Link>
        ))}
      </nav>

      <p className="opis-strategii">{strategia.opis}</p>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="cardhead">
          <h2>Ranking</h2>
          <em>
            {ranking.length.toLocaleString("pl-PL")} ocenionych spółek · najwyższy
            wynik {najlepszyWynik} / {strategia.maks}
          </em>
        </div>
        <TabelaStrategii wiersze={czolo} strategia={strategia} />
      </div>

      <footer>
        Pokazane pierwsze {ILE} pozycji rankingu. Wyniki liczone podczas
        codziennego skanu — kolumny w tabeli to wskaźniki, na których opiera się
        wybrana strategia, żeby było widać, skąd wziął się wynik. Maksimum wyznaczone
        empirycznie, nie szacunkowo.
      </footer>
    </main>
  );
}
