import Link from "next/link";
import Pasek from "../Pasek";
import DodajSpolke from "./Dodaj";
import Korelacje from "./Korelacje";
import ListaObserwowanych from "./Lista";
import { przenies } from "./akcje";
import { historiaCeny, migawkaBezpieczna } from "@/lib/dane";
import type { Instrument } from "@/lib/filtry";
import { macierzKorelacji, MAKS_SPOLEK, type Szereg } from "@/lib/korelacje";
import {
  LIMIT_OBSERWOWANYCH,
  obserwowaneUzytkownika,
  staraWatchlista,
} from "@/lib/obserwowane";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

/** Krótkie kody z adresu na zdania. Nigdy nie wyświetlamy treści z URL wprost. */
function komunikat(kod: string | undefined): string | null {
  if (!kod) return null;
  if (kod.startsWith("przeniesiono-")) {
    const ile = Number(kod.slice("przeniesiono-".length));
    if (!Number.isFinite(ile)) return null;
    return ile > 0
      ? `Przeniesiono ${ile} ${ile === 1 ? "spółkę" : "spółek"} ze starej watchlisty.`
      : "Nie było czego przenosić — wszystko już masz na liście.";
  }
  const slownik: Record<string, string> = {
    dodany: "Dodano do obserwowanych.",
    usuniety: "Usunięto z obserwowanych.",
    notatka: "Zapisano notatkę.",
    duplikat: "Ta spółka już jest na Twojej liście.",
    limit: `Masz już maksymalną liczbę obserwowanych (${LIMIT_OBSERWOWANYCH}).`,
    nieznany: "Nie znam takiego tickera — wybierz spółkę z podpowiedzi.",
    brakTickera: "Nie podano tickera.",
  };
  return slownik[kod] ?? null;
}

export default async function Watchlist({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const uzytkownik = await wymagajZalogowania();
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const { instrumenty, data, tryb } = await migawkaBezpieczna();
  const pozycje = await obserwowaneUzytkownika(uzytkownik.id);
  const dane = new Map<string, Instrument>(
    instrumenty.map((i) => [String(i.Ticker), i]),
  );

  // Stara, wspólna watchlist ze Streamlita. Pytamy o nią tylko po to, żeby
  // pokazać przycisk przeniesienia — i tylko wtedy, gdy jest w niej coś,
  // czego użytkownik jeszcze nie ma.
  const stare = await staraWatchlista();
  const doPrzeniesienia = stare.filter(
    (s) => !pozycje.some((p) => p.ticker === s.ticker),
  ).length;

  const bezDanych = pozycje.filter((p) => !dane.has(p.ticker)).length;
  const kod = jeden("wl");
  const info = komunikat(kod);
  const toBlad = kod
    ? ["duplikat", "limit", "nieznany", "brakTickera"].includes(kod)
    : false;

  // Korelacje liczymy WYŁĄCZNIE na żądanie — to jedno zapytanie do bazy
  // na każdą obserwowaną spółkę.
  const chceKorelacje = jeden("korelacje") === "1";
  let macierz = null;
  let pominieto = 0;
  if (chceKorelacje && pozycje.length >= 2) {
    const wybrane = pozycje.slice(0, MAKS_SPOLEK);
    pominieto = pozycje.length - wybrane.length;
    const szeregi: Szereg[] = await Promise.all(
      wybrane.map(async (p) => ({
        ticker: p.ticker,
        punkty: await historiaCeny(p.ticker, 400),
      })),
    );
    macierz = macierzKorelacji(szeregi);
  }

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Watchlist</h2>
        <em>
          {pozycje.length}{" "}
          {pozycje.length === 1 ? "obserwowana spółka" : "obserwowanych"}
        </em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      {info && (
        <p className={toBlad ? "komunikat-blad" : "komunikat-info"}>{info}</p>
      )}

      {doPrzeniesienia > 0 && (
        <form action={przenies} className="card pasek-przeniesienia">
          <input type="hidden" name="powrot" value="/watchlist" />
          <span>
            W starej, wspólnej watchliście ze Streamlita jest{" "}
            <b>{doPrzeniesienia}</b>{" "}
            {doPrzeniesienia === 1 ? "spółka" : "spółek"}, których nie masz na
            swojej liście. Stara lista pozostanie nietknięta — kopiujemy, nie
            przenosimy.
          </span>
          <button type="submit">Skopiuj na moje konto</button>
        </form>
      )}

      <div className="card" style={{ marginTop: 12, padding: "14px 20px" }}>
        <DodajSpolke instrumenty={instrumenty} powrot="/watchlist" />
      </div>

      <div className="card" style={{ marginTop: 12, padding: "4px 20px 12px" }}>
        <ListaObserwowanych
          pozycje={pozycje}
          dane={dane}
          powrot="/watchlist"
        />
        {bezDanych > 0 && (
          <p className="drobne">
            {bezDanych}{" "}
            {bezDanych === 1
              ? "spółka nie ma danych"
              : "spółek nie ma danych"}{" "}
            w najnowszej migawce (np. dodane po ostatnim skanie albo usunięte
            z uniwersum) — liczby pojawią się po kolejnym skanie.
          </p>
        )}
      </div>

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Korelacje</h2>
        <em>czy to nie jest jeden zakład w kilku opakowaniach</em>
        {pozycje.length >= 2 && !chceKorelacje && (
          <Link className="link" href="/watchlist?korelacje=1">
            Policz →
          </Link>
        )}
        {chceKorelacje && (
          <Link className="link" href="/watchlist">
            Ukryj
          </Link>
        )}
      </div>

      <div className="card" style={{ marginTop: 12, padding: "12px 20px" }}>
        {chceKorelacje || pozycje.length < 2 ? (
          <Korelacje macierz={macierz} pominieto={pominieto} />
        ) : (
          <p className="pusto">
            Kliknij „Policz”, żeby sprawdzić, czy obserwowane spółki nie
            poruszają się razem. Liczone na żądanie, bo wymaga sięgnięcia po
            historię cen każdej z nich.
          </p>
        )}
      </div>

      <footer>
        Watchlist jest przypisana do Twojego konta — każdy użytkownik ma swoją.
        Dane liczbowe pochodzą z najnowszej migawki ({data}), więc zmieniają
        się po każdym skanie; notatki są Twoje i nic ich nie nadpisuje. Limit
        na konto: {LIMIT_OBSERWOWANYCH} spółek. Alarm cenowy na obserwowaną
        spółkę ustawisz na jej profilu.
      </footer>
    </main>
  );
}
