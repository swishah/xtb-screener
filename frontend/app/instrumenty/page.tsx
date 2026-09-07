import Link from "next/link";
import Pasek from "../Pasek";
import { dodaj, sprawdz, usun } from "./akcje";
import { migawkaBezpieczna } from "@/lib/dane";
import {
  LIMIT_WLASNYCH,
  TYPY,
  wlasneInstrumenty,
} from "@/lib/instrumenty";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

export default async function Instrumenty({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await wymagajZalogowania();

  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const { data, tryb, instrumenty } = await migawkaBezpieczna();
  const wlasne = await wlasneInstrumenty();

  const wynik = jeden("wynik");
  const tk = jeden("t") ?? "";

  // Znaleziony instrument opisujemy parametrami adresu, a nie stanem serwera:
  // strona zostaje bezstanowa, a wynik sprawdzenia da się odświeżyć i wysłać.
  const znaleziony =
    wynik === "znaleziony"
      ? {
          ticker: tk,
          nazwa: jeden("n") ?? tk,
          cena: jeden("c") ?? "",
          waluta: jeden("w") ?? "",
          typ: jeden("typ") ?? "stock",
          gielda: jeden("g") ?? "",
          poprawionyZ: jeden("z") ?? "",
        }
      : null;

  const KOMUNIKATY: Record<string, string> = {
    pusty: "Nie podano tickera.",
    wbudowany: `${tk} jest już skanowany — nie trzeba go dopisywać.`,
    brak: `Yahoo Finance nie zwraca notowań dla „${tk}”. Sprawdź pisownię i sufiks giełdy: polskie spółki mają .WA, niemieckie .DE, amerykańskie żadnego.`,
    dodany: `Dodano ${tk}. Pojawi się w tabelach po najbliższym skanie — wcześniej nie ma dla niego żadnych danych.`,
    usuniety: `Usunięto ${tk}. Od następnego skanu nie będzie pobierany; dotychczasowe migawki zostają nietknięte.`,
    duplikat: `${tk} jest już na liście.`,
    limit: `Osiągnięto limit ${LIMIT_WLASNYCH} własnych instrumentów.`,
    blad: "Nie udało się zapisać. Spróbuj ponownie.",
  };
  const komunikat = wynik && wynik !== "znaleziony" ? KOMUNIKATY[wynik] : null;
  const toBlad = ["pusty", "brak", "duplikat", "limit", "blad"].includes(
    wynik ?? "",
  );

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Własne instrumenty</h2>
        <em>
          {wlasne.length} z {LIMIT_WLASNYCH}
        </em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Dopisz instrument, którego nie ma w uniwersum. Trafi do skanu razem
        z resztą przy najbliższym uruchomieniu i od tego momentu będzie widoczny
        we wszystkich modułach. Uniwersum wbudowane to składy głównych indeksów
        plus około 69 ETF-ów — XTB oferuje ich blisko 1900, więc zawsze będzie
        czego dokładać.
      </p>

      {komunikat && (
        <p className={toBlad ? "komunikat-blad" : "komunikat-info"}>{komunikat}</p>
      )}

      <form action={sprawdz} className="card form-instrument">
        <label>
          <span>Ticker w formacie Yahoo Finance</span>
          <input
            type="text"
            name="ticker"
            placeholder="np. ALE.WA, AAPL, SXR8.DE"
            required
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <button type="submit">Sprawdź</button>
        <span className="drobne">
          Wklejasz ticker z XTB (np. <code>ALE.PL</code>)? Sam go poprawię.
        </span>
      </form>

      {znaleziony && (
        <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
          {znaleziony.poprawionyZ && (
            <p className="komunikat-info">
              Ticker <b>{znaleziony.poprawionyZ}</b> wygląda na format XTB —
              poprawiłem go na <b>{znaleziony.ticker}</b>, bo tego oczekuje Yahoo
              Finance.
            </p>
          )}

          <h3 className="naglowek-sekcji">
            {znaleziony.ticker} — {znaleziony.nazwa}
          </h3>
          <p className="drobne" style={{ marginTop: 0 }}>
            Ostatnia cena: <b>{znaleziony.cena} {znaleziony.waluta}</b> · rozpoznany
            typ: <b>{TYPY[znaleziony.typ] ?? znaleziony.typ}</b>
            {znaleziony.gielda ? ` · giełda: ${znaleziony.gielda}` : ""}
          </p>

          {znaleziony.typ === "index" && (
            <p className="komunikat-blad">
              To indeks, nie spółka — nie ma bilansu ani zysków, więc wskaźniki
              fundamentalne (C/Z, ROE, marże) zostaną puste. Techniczne (RSI,
              średnie, dystans od szczytu) będą liczone normalnie.
            </p>
          )}

          <form action={dodaj} className="form-instrument" style={{ marginTop: 8 }}>
            <input type="hidden" name="ticker" value={znaleziony.ticker} />
            <input type="hidden" name="nazwa" value={znaleziony.nazwa} />
            <label>
              <span>Typ w uniwersum</span>
              <select name="typ" defaultValue={znaleziony.typ}>
                {Object.entries(TYPY).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Dodaj do uniwersum</button>
            <span className="drobne">
              Rozpoznany automatycznie z danych Yahoo — popraw, jeśli się myli.
            </span>
          </form>
        </div>
      )}

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Dopisane instrumenty</h2>
        <em>skanowane codziennie razem z uniwersum wbudowanym</em>
      </div>

      <div className="card" style={{ marginTop: 12, padding: "4px 20px 12px" }}>
        {wlasne.length === 0 ? (
          <p className="pusto">
            Jeszcze nic nie dopisałeś. Wpisz ticker powyżej i kliknij „Sprawdź”.
          </p>
        ) : (
          <div className="scroll">
            <table className="tab-instrumenty">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Nazwa</th>
                  <th>Typ</th>
                  <th>Dodano</th>
                  <th className="r">W migawce</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {wlasne.map((i) => {
                  const jest = instrumenty.some(
                    (x) => String(x.Ticker ?? "").toUpperCase() === i.ticker,
                  );
                  return (
                    <tr key={i.ticker}>
                      <td className="t">
                        {jest ? (
                          <Link
                            className="ticker-link"
                            href={`/spolka/${encodeURIComponent(i.ticker)}`}
                          >
                            {i.ticker}
                          </Link>
                        ) : (
                          i.ticker
                        )}
                      </td>
                      <td className="drobna-kom">{i.nazwa}</td>
                      <td className="drobna-kom">{TYPY[i.typ] ?? i.typ}</td>
                      <td className="drobna-kom">{i.dodano}</td>
                      <td className="r">
                        {jest ? (
                          <span className="ocena lepiej">jest</span>
                        ) : (
                          <span className="ocena brak-oceny">po skanie</span>
                        )}
                      </td>
                      <td className="r">
                        <form action={usun}>
                          <input type="hidden" name="ticker" value={i.ticker} />
                          <button type="submit" className="btn-usun">
                            Usuń
                          </button>
                        </form>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <footer>
        Lista jest <b>wspólna dla całej instalacji</b>, nie osobna dla każdego
        konta — skan jest jeden, więc „moje uniwersum” nie miałoby jak istnieć
        oddzielnie. Kolumna „W migawce” mówi, czy instrument zdążył już wejść do
        danych: świeżo dopisany pojawi się dopiero po najbliższym skanie.
        Usunięcie wpisu nie kasuje zebranych już migawek.
      </footer>
    </main>
  );
}
