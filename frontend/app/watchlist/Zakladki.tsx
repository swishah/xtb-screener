import Link from "next/link";
import { nowaLista, skasujListe, zmienNazwe } from "./akcje";
import { LIMIT_LIST, MAKS_NAZWA, type Lista } from "@/lib/obserwowane";

/**
 * Przełączanie i zarządzanie listami.
 *
 * Zakładki to zwykłe ODNOŚNIKI (`?lista=<id>`), a nie przyciski ze stanem —
 * dzięki temu każdą listę da się zapisać w zakładkach przeglądarki i wysłać
 * linkiem, a komponent zostaje serwerowy.
 *
 * Zmiana nazwy i kasowanie siedzą pod jednym `<details>`, a nie na wierzchu:
 * to czynności rzadkie, a przycisk „usuń listę" obok zakładek zapraszałby do
 * przypadkowego kliknięcia.
 */
export default function Zakladki({
  listy,
  aktywna,
  powrot,
}: {
  listy: Lista[];
  aktywna: number;
  powrot: string;
}) {
  const biezaca = listy.find((l) => l.id === aktywna);

  return (
    <div className="listy-pasek">
      <nav className="listy-zakladki" aria-label="Twoje listy">
        {listy.map((l) => (
          <Link
            key={l.id}
            href={`/watchlist?lista=${l.id}`}
            className={l.id === aktywna ? "zakladka aktywna" : "zakladka"}
            aria-current={l.id === aktywna ? "page" : undefined}
          >
            {l.nazwa}
            <span className="zakladka-ile">{l.ile}</span>
          </Link>
        ))}
      </nav>

      <details className="listy-ustawienia">
        <summary>Zarządzaj listami</summary>

        <div className="listy-formularze">
          {listy.length < LIMIT_LIST && (
            <form action={nowaLista}>
              <input type="hidden" name="powrot" value={powrot} />
              <label>
                <span>Nowa lista</span>
                <input
                  type="text"
                  name="nazwa"
                  maxLength={MAKS_NAZWA}
                  placeholder="np. Dywidendowe"
                  required
                />
              </label>
              <button type="submit">Utwórz</button>
            </form>
          )}

          {biezaca && (
            <form action={zmienNazwe}>
              <input type="hidden" name="lista" value={biezaca.id} />
              <input type="hidden" name="powrot" value={powrot} />
              <label>
                <span>Nazwa tej listy</span>
                <input
                  type="text"
                  name="nazwa"
                  maxLength={MAKS_NAZWA}
                  defaultValue={biezaca.nazwa}
                  required
                />
              </label>
              <button type="submit">Zmień</button>
            </form>
          )}

          {biezaca && listy.length > 1 && (
            <form action={skasujListe} className="form-usun-liste">
              <input type="hidden" name="lista" value={biezaca.id} />
              <input type="hidden" name="powrot" value={powrot} />
              <button type="submit" className="btn-usun">
                Usuń listę „{biezaca.nazwa}”
              </button>
              <span className="drobne">
                {biezaca.ile > 0
                  ? `Najpierw opróżnij listę — jest na niej ${biezaca.ile} ${
                      biezaca.ile === 1 ? "spółka" : "spółek"
                    }. Bez potwierdzenia w oknie jedno kliknięcie kasowałoby je razem z notatkami.`
                  : "Lista jest pusta, więc można ją skasować."}
              </span>
            </form>
          )}
        </div>
      </details>
    </div>
  );
}
