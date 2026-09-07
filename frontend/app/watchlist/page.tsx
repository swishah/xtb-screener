import Link from "next/link";
import Pasek from "../Pasek";
import DodajSpolke from "./Dodaj";
import Korelacje from "./Korelacje";
import ListaObserwowanych from "./Lista";
import Zakladki from "./Zakladki";
import { przenies } from "./akcje";
import { historiaCeny, migawkaBezpieczna } from "@/lib/dane";
import type { Instrument } from "@/lib/filtry";
import { macierzKorelacji, MAKS_SPOLEK, type Szereg } from "@/lib/korelacje";
import {
  LIMIT_OBSERWOWANYCH,
  listyUzytkownika,
  obserwowaneZListy,
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
      ? `Skopiowano ${ile} ${ile === 1 ? "spółkę" : "spółek"} ze starej watchlisty.`
      : "Nie było czego kopiować — wszystko już masz na tej liście.";
  }
  const slownik: Record<string, string> = {
    dodany: "Dodano do listy.",
    usuniety: "Usunięto z listy.",
    notatka: "Zapisano notatkę.",
    przeniesiona: "Przeniesiono na wybraną listę.",
    jestJuzTam: "Ta spółka jest już na liście docelowej.",
    duplikat: "Ta spółka już jest na tej liście.",
    limit: `Masz już maksymalną liczbę obserwowanych spółek (${LIMIT_OBSERWOWANYCH}).`,
    nieznany: "Nie znam takiego tickera — wybierz spółkę z podpowiedzi.",
    brakTickera: "Nie podano tickera.",
    "lista-dodana": "Utworzono nową listę.",
    "lista-nazwa": "Zmieniono nazwę listy.",
    "lista-usunieta": "Usunięto listę.",
    "lista-duplikat": "Masz już listę o takiej nazwie.",
    "lista-pustaNazwa": "Nazwa listy nie może być pusta.",
    "lista-limit": "Osiągnięto maksymalną liczbę list.",
    "lista-ostatnia": "To Twoja jedyna lista — nie da się jej usunąć.",
    "lista-niepusta":
      "Najpierw opróżnij listę. Kasowanie razem z zawartością wymagałoby potwierdzenia, którego bez JavaScriptu nie ma.",
  };
  return slownik[kod] ?? null;
}

const BLEDY = new Set([
  "duplikat",
  "limit",
  "nieznany",
  "brakTickera",
  "jestJuzTam",
  "lista-duplikat",
  "lista-pustaNazwa",
  "lista-limit",
  "lista-ostatnia",
  "lista-niepusta",
]);

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
  const listy = await listyUzytkownika(uzytkownik.id);

  // Wybrana lista z adresu; przy śmieciach albo cudzym id wracamy na pierwszą.
  const zadana = Number(jeden("lista"));
  const aktywna = listy.some((l) => l.id === zadana) ? zadana : listy[0].id;
  const powrot = `/watchlist?lista=${aktywna}`;

  const pozycje = await obserwowaneZListy(uzytkownik.id, aktywna);
  const dane = new Map<string, Instrument>(
    instrumenty.map((i) => [String(i.Ticker), i]),
  );

  // Stara, wspólna watchlist ze Streamlita. Pytamy o nią tylko po to, żeby
  // pokazać przycisk — i tylko wtedy, gdy jest w niej coś, czego na TEJ
  // liście jeszcze nie ma.
  const stare = await staraWatchlista();
  const doPrzeniesienia = stare.filter(
    (s) => !pozycje.some((p) => p.ticker === s.ticker),
  ).length;

  const bezDanych = pozycje.filter((p) => !dane.has(p.ticker)).length;
  const kod = jeden("wl");
  const info = komunikat(kod);
  const lacznie = listy.reduce((s, l) => s + l.ile, 0);

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
        <h2 style={{ fontSize: "1.15rem" }}>Watchlisty</h2>
        <em>
          {listy.length} {listy.length === 1 ? "lista" : "listy"} · {lacznie}{" "}
          {lacznie === 1 ? "spółka" : "spółek"} łącznie
        </em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      {info && (
        <p className={kod && BLEDY.has(kod) ? "komunikat-blad" : "komunikat-info"}>
          {info}
        </p>
      )}

      <Zakladki listy={listy} aktywna={aktywna} powrot={powrot} />

      {doPrzeniesienia > 0 && (
        <form action={przenies} className="card pasek-przeniesienia">
          <input type="hidden" name="powrot" value={powrot} />
          <input type="hidden" name="lista" value={aktywna} />
          <span>
            W starej, wspólnej watchliście ze Streamlita jest{" "}
            <b>{doPrzeniesienia}</b>{" "}
            {doPrzeniesienia === 1 ? "spółka" : "spółek"}, których nie ma na tej
            liście. Stara lista pozostanie nietknięta — kopiujemy, nie
            przenosimy.
          </span>
          <button type="submit">Skopiuj na tę listę</button>
        </form>
      )}

      <div className="card" style={{ marginTop: 12, padding: "14px 20px" }}>
        <DodajSpolke
          instrumenty={instrumenty}
          powrot={powrot}
          listaId={aktywna}
        />
      </div>

      <div className="card" style={{ marginTop: 12, padding: "4px 20px 12px" }}>
        <ListaObserwowanych
          pozycje={pozycje}
          dane={dane}
          powrot={powrot}
          listaId={aktywna}
          listy={listy}
        />
        {bezDanych > 0 && (
          <p className="drobne">
            {bezDanych}{" "}
            {bezDanych === 1 ? "spółka nie ma danych" : "spółek nie ma danych"}{" "}
            w najnowszej migawce (np. dodane po ostatnim skanie albo usunięte
            z uniwersum) — liczby pojawią się po kolejnym skanie.
          </p>
        )}
      </div>

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Korelacje</h2>
        <em>czy ta lista to nie jeden zakład w kilku opakowaniach</em>
        {pozycje.length >= 2 && !chceKorelacje && (
          <Link className="link" href={`${powrot}&korelacje=1`}>
            Policz →
          </Link>
        )}
        {chceKorelacje && (
          <Link className="link" href={powrot}>
            Ukryj
          </Link>
        )}
      </div>

      <div className="card" style={{ marginTop: 12, padding: "12px 20px" }}>
        {chceKorelacje || pozycje.length < 2 ? (
          <Korelacje macierz={macierz} pominieto={pominieto} />
        ) : (
          <p className="pusto">
            Kliknij „Policz”, żeby sprawdzić, czy spółki z tej listy nie
            poruszają się razem. Liczone na żądanie, bo wymaga sięgnięcia po
            historię cen każdej z nich.
          </p>
        )}
      </div>

      <footer>
        Listy są przypisane do Twojego konta — każdy użytkownik ma swoje. Ta
        sama spółka może być na kilku listach naraz, z osobną notatką na każdej;
        „Dywidendowe” i „Kupione” to dwa różne powody obserwowania. Dane liczbowe
        pochodzą z najnowszej migawki ({data}) i zmieniają się po każdym skanie;
        notatki są Twoje i nic ich nie nadpisuje. Limit: {LIMIT_OBSERWOWANYCH}{" "}
        spółek łącznie na konto. Alarm cenowy ustawisz na profilu spółki.
      </footer>
    </main>
  );
}
