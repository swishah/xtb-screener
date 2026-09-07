"use client";

import Link from "next/link";
import { useActionState } from "react";
import { analizuj } from "./akcje";
import { STAN_POCZATKOWY } from "@/lib/transakcje";

/**
 * Formularz wgrywania i wyniki analizy.
 *
 * Komponent kliencki, bo wynik musi wrócić NA TĘ SAMĄ STRONĘ, a nie w adresie
 * — tabela z kilkuset wierszami nie zmieści się w parametrach URL. `useActionState`
 * daje przy tym progresywne ulepszanie: bez JavaScriptu przeglądarka wysyła
 * zwykły POST, serwer wykonuje akcję i odsyła stronę z wynikiem.
 *
 * NIE IMPORTUJEMY TU NICZEGO Z `lib/import_transakcji.ts` ani `lib/dane.ts` —
 * to moduły serwerowe (exceljs, klient bazy), których webpack nie spakuje do
 * przeglądarki. TypeScript tego nie łapie; wychodzi dopiero przy `npm run build`.
 */

function lb(w: number | null, cyfry = 2, sufiks = ""): string {
  if (w === null) return "—";
  return `${w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

export default function Formularz() {
  const [stan, wyslij, oczekuje] = useActionState(analizuj, STAN_POCZATKOWY);

  const oszczednosci = stan.wyniki
    .map((w) => w.ileTaniej)
    .filter((w) => Number.isFinite(w));
  const srednia = oszczednosci.length
    ? oszczednosci.reduce((a, b) => a + b, 0) / oszczednosci.length
    : null;
  const gorzejNiz2 = oszczednosci.filter((w) => w < -2).length;

  const rsi = stan.wyniki
    .map((w) => w.rsiWDniuZakupu)
    .filter((w): w is number => w !== null);
  const sredniRsi = rsi.length ? rsi.reduce((a, b) => a + b, 0) / rsi.length : null;
  const wysokieRsi = rsi.filter((w) => w > 50).length;

  const wzrosty = stan.wyniki
    .map((w) => w.niewykorzystanyWzrost)
    .filter((w): w is number => w !== null);
  const sredniWzrost = wzrosty.length
    ? wzrosty.reduce((a, b) => a + b, 0) / wzrosty.length
    : null;

  return (
    <>
      <form action={wyslij} className="card form-transakcje">
        <label className="pole-plik">
          <span>Plik z transakcjami</span>
          <input type="file" name="plik" accept=".xlsx,.xls,.csv,.txt" required />
        </label>

        <label>
          <span>Okno analizy po zakupie</span>
          <select name="okno" defaultValue="90">
            {[30, 60, 90, 180, 365].map((n) => (
              <option key={n} value={n}>
                {n} dni
              </option>
            ))}
          </select>
        </label>

        <label className="pole-przelacznik">
          <span>Tickery w formacie XTB (CSV)</span>
          <input type="checkbox" name="tlumacz" value="1" />
        </label>

        <button type="submit" disabled={oczekuje}>
          {oczekuje ? "Analizuję…" : "Przeanalizuj"}
        </button>
      </form>

      {oczekuje && (
        <p className="drobne">
          Pobieram historię cen dla każdego instrumentu — przy kilkudziesięciu
          spółkach to może potrwać kilkanaście sekund.
        </p>
      )}

      {stan.etap === "blad" && (
        <p className="komunikat-blad">{stan.komunikat}</p>
      )}

      {stan.etap === "gotowe" && (
        <>
          <p className="komunikat-info">
            {stan.zrodloXtb
              ? `Rozpoznano eksport z XTB — wczytano ${stan.wczytanych} zakupów, przeanalizowano ${stan.wyniki.length}.`
              : `Wczytano ${stan.wczytanych} zakupów, przeanalizowano ${stan.wyniki.length}.`}
          </p>

          {stan.przeskalowane.length > 0 && (
            <p className="komunikat-info">
              Ceny przeliczone z waluty głównej na subjednostkę dla:{" "}
              <b>{stan.przeskalowane.join(", ")}</b>. Yahoo notuje te instrumenty
              w pensach, a broker podaje je w funtach — bez tej korekty wyniki
              byłyby zawyżone stukrotnie.
            </p>
          )}

          <div className="stats">
            <div>
              <b>{stan.wyniki.length}</b>
              <span>przeanalizowanych transakcji</span>
            </div>
            <div>
              <b className={srednia !== null && srednia < 0 ? "down" : undefined}>
                {lb(srednia, 2, "%")}
              </b>
              <span>śr. potencjalna oszczędność</span>
            </div>
            <div>
              <b>
                {gorzejNiz2}/{oszczednosci.length}
              </b>
              <span>zakupów &gt;2% przed dołkiem</span>
            </div>
          </div>

          {sredniRsi !== null && (
            <p className="drobne">
              <b>RSI w dniu zakupu:</b> średnio {lb(sredniRsi, 1)}. W{" "}
              {wysokieRsi}/{rsi.length} transakcjach przekraczało 50 —{" "}
              {wysokieRsi > rsi.length / 2
                ? "kupujesz częściej w trakcie odbicia niż w dołku wyprzedania."
                : "kupujesz przeważnie przy niskim RSI, czyli blisko stref wyprzedania."}
            </p>
          )}
          {sredniWzrost !== null && (
            <p className="drobne">
              <b>Sprzedaże:</b> po sprzedaży cena rosła średnio jeszcze o{" "}
              {lb(sredniWzrost, 1, "%")} (maksimum w dostępnej historii) — wysoka
              wartość sugeruje, że sprzedajesz zbyt wcześnie.
            </p>
          )}

          <div className="card" style={{ marginTop: 12 }}>
            <div className="scroll">
              <table className="tab-transakcje">
                <thead>
                  <tr>
                    <th>Spółka</th>
                    <th>Kupno</th>
                    <th className="r">Cena</th>
                    <th className="r">Min. po zakupie</th>
                    <th className="r">Ile taniej</th>
                    <th className="r">RSI</th>
                    <th className="r">Od szczytu</th>
                    <th className="r">Sprzedaż</th>
                    <th className="r">Wzrost po</th>
                  </tr>
                </thead>
                <tbody>
                  {stan.wyniki.map((w, i) => (
                    <tr key={`${w.ticker}-${w.dataZakupu}-${i}`}>
                      <td className="t">
                        <Link
                          className="ticker-link"
                          href={`/spolka/${encodeURIComponent(w.ticker)}`}
                        >
                          {w.ticker}
                          <small>{w.instrument}</small>
                        </Link>
                      </td>
                      <td className="drobna-kom">{w.dataZakupu}</td>
                      <td className="r n">{lb(w.cenaZakupu)}</td>
                      <td className="r n">
                        {lb(w.minPoZakupie)}
                        <small className="drobna-kom"> {w.dataMinimum}</small>
                      </td>
                      <td className={w.ileTaniej < 0 ? "r n down" : "r n"}>
                        {lb(w.ileTaniej, 2, "%")}
                      </td>
                      <td className="r n">{lb(w.rsiWDniuZakupu, 1)}</td>
                      <td className="r n">{lb(w.odSzczytuWDniuZakupu, 1, "%")}</td>
                      <td className="r n">{lb(w.cenaSprzedazy)}</td>
                      <td className="r n">{lb(w.niewykorzystanyWzrost, 2, "%")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {stan.nieudane.length > 0 && (
            <details className="listy-ustawienia">
              <summary>
                Nie udało się przeanalizować {stan.nieudane.length} pozycji
              </summary>
              <ul className="drobne">
                {stan.nieudane.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </details>
          )}

          {stan.mapa.length > 0 && (
            <details className="listy-ustawienia">
              <summary>
                Jak przetłumaczyłem tickery ({stan.mapa.length} instrumentów)
              </summary>
              <p className="drobne">
                XTB oznacza instrumenty sufiksem KRAJU (<code>ALE.PL</code>),
                a Yahoo — sufiksem GIEŁDY (<code>ALE.WA</code>), więc bez
                tłumaczenia nie dałoby się pobrać żadnych cen.
              </p>
              <div className="scroll">
                <table className="tab-mapa">
                  <thead>
                    <tr>
                      <th>XTB</th>
                      <th>Yahoo</th>
                      <th>Instrument</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stan.mapa.map((m) => (
                      <tr key={m.xtb}>
                        <td className="t">{m.xtb}</td>
                        <td className="t">{m.yahoo}</td>
                        <td className="drobna-kom">{m.instrument}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <p className="drobne">
            To analiza historyczna „po fakcie”, nie porada inwestycyjna —
            pokazuje wzorce w Twoich dotychczasowych decyzjach. Trafienie
            w dokładny dołek jest z definicji niemożliwe; celem jest wychwycenie
            systematycznych tendencji, nie ocena pojedynczych transakcji.
            Okno analizy: {stan.oknoDni} dni po zakupie.
          </p>
        </>
      )}
    </>
  );
}
