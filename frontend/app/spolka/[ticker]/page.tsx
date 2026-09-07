import Link from "next/link";
import { notFound } from "next/navigation";
import Pasek from "../../Pasek";
import Profil from "../Profil";
import WykresPelny from "../WykresPelny";
import { historiaCeny, migawkaBezpieczna } from "@/lib/dane";
import { liczba } from "@/lib/filtry";
import { newsySpolki } from "@/lib/newsy";
import { symbolTradingView } from "@/lib/tradingview";
import { wymagajZalogowania } from "@/lib/sesja";
import { alarmySpolki } from "@/lib/alarmy";
import { czyObserwuje } from "@/lib/obserwowane";
import UstawAlarm from "../../alarmy/UstawAlarm";
import ListaAlarmow from "../../alarmy/Lista";
import {
  obserwujZProfilu as obserwuj,
  przestanObserwowac,
} from "../../watchlist/akcje";

export const dynamic = "force-dynamic";

/** Krótkie kody z adresu na zdania — patrz uzasadnienie w akcjach logowania. */
/**
 * Komunikaty watchlisty. Sukces widać po samym przycisku („★ Obserwujesz”),
 * więc wyświetlamy wyłącznie te kody, które niosą coś nowego.
 */
const KOMUNIKATY_WATCHLISTY: Record<string, string> = {
  limit: "Osiągnięto limit obserwowanych spółek na koncie.",
  nieznany: "Nie znam takiego tickera.",
  duplikat: "Ta spółka już jest na Twojej watchliście.",
};

/** Krótkie kody z adresu na zdania — patrz uzasadnienie w akcjach logowania. */
const KOMUNIKATY_ALARMU: Record<string, string> = {
  dodany: "Alarm ustawiony. Sprawdzi go najbliższy skan.",
  duplikat: "Taki alarm już istnieje — ten sam próg w tę samą stronę.",
  limit: "Osiągnięto limit alarmów na koncie.",
  cena: "Cena alarmu musi być liczbą większą od zera.",
  "brak-tickera": "Nie wiadomo, której spółki dotyczy alarm.",
};

export default async function StronaSpolki({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // Cała aplikacja jest za logowaniem — publiczne są tylko
  // ekrany logowania, rejestracji i resetu hasła.
  const uzytkownik = await wymagajZalogowania();

  const { ticker } = await params;
  const q = await searchParams;
  const pokazWykres = (Array.isArray(q.wykres) ? q.wykres[0] : q.wykres) === "1";
  const szukany = decodeURIComponent(ticker).toUpperCase();

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();
  const spolka = instrumenty.find(
    (i) => String(i.Ticker ?? "").toUpperCase() === szukany,
  );

  if (!spolka && !blad) notFound();

  // Newsy pobieramy dopiero po znalezieniu spółki — nie ma sensu odpytywać
  // Yahoo o ticker, którego nie ma w migawce.
  const newsy = spolka
    ? await newsySpolki(String(spolka.Ticker), String(spolka.Nazwa ?? ""))
    : [];

  const cena = spolka ? liczba(spolka.Cena) : null;
  const zmiana = spolka ? liczba(spolka["Zmiana ceny (1Y%)"]) : null;

  // Alarmy i ścieżkę ceny pobieramy tylko dla znalezionej spółki i tylko
  // wtedy, gdy jest z czego rysować wykres.
  const alarmy = spolka ? await alarmySpolki(uzytkownik.id, szukany) : [];
  const punkty = spolka && cena !== null ? await historiaCeny(szukany) : [];
  const komunikatAlarmu = Array.isArray(q.alarm) ? q.alarm[0] : q.alarm;
  const obserwowana = spolka
    ? await czyObserwuje(uzytkownik.id, String(spolka.Ticker))
    : false;

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      {blad && (
        <div className="alert">
          <b>Nie udało się wczytać danych.</b>
          <div style={{ marginTop: 8, fontSize: "0.78rem", opacity: 0.75 }}>{blad}</div>
        </div>
      )}

      {spolka && (
        <>
          <div className="spolka-naglowek">
            <div>
              <h2>{String(spolka.Ticker)}</h2>
              <p className="spolka-nazwa">
                {String(spolka.Nazwa ?? "")}
                {spolka.Sektor ? ` · ${String(spolka.Sektor)}` : ""}
                {spolka.Rynek ? ` · ${String(spolka.Rynek)}` : ""}
              </p>
            </div>
            <div className="spolka-cena">
              {cena !== null && (
                <strong>
                  {cena.toLocaleString("pl-PL", { maximumFractionDigits: 2 })}{" "}
                  <span className="brak">{String(spolka.Waluta ?? "")}</span>
                </strong>
              )}
              {zmiana !== null && (
                <span className={zmiana < 0 ? "down" : "up"}>
                  {zmiana > 0 ? "+" : ""}
                  {zmiana.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}% / rok
                </span>
              )}
            </div>
            <div className="spolka-akcje">
              <Link className="btn-wykres-duzy" href={`?wykres=1`}>
                Pokaż wykres
              </Link>
              {/* Zwykły formularz z akcją serwerową — działa bez JavaScriptu,
                  tak samo jak alarmy. Adres powrotu to ta sama strona. */}
              <form action={obserwowana ? przestanObserwowac : obserwuj}>
                <input
                  type="hidden"
                  name="ticker"
                  value={String(spolka.Ticker)}
                />
                <input
                  type="hidden"
                  name="powrot"
                  value={`/spolka/${encodeURIComponent(String(spolka.Ticker))}`}
                />
                <button
                  type="submit"
                  className={obserwowana ? "btn-obserwuj wl-tak" : "btn-obserwuj"}
                  title={
                    obserwowana
                      ? "Usuń z watchlisty"
                      : "Dodaj do watchlisty"
                  }
                >
                  {obserwowana ? "★ Obserwujesz" : "☆ Obserwuj"}
                </button>
              </form>
              <Link className="link" href="/screener">
                ← Wróć do screenera
              </Link>
            </div>
          </div>

          {(() => {
            const kod = Array.isArray(q.wl) ? q.wl[0] : q.wl;
            const tresc = kod ? KOMUNIKATY_WATCHLISTY[kod] : null;
            return tresc ? <p className="komunikat-blad">{tresc}</p> : null;
          })()}

          <section className="card sekcja-alarmy" id="alarmy">
            <div className="cardhead">
              <h2>Alarm cenowy</h2>
              <em>przeciągnij linię albo wpisz cenę</em>
            </div>

            {komunikatAlarmu && (
              <p
                className={
                  komunikatAlarmu === "dodany"
                    ? "komunikat-info"
                    : "komunikat-blad"
                }
              >
                {KOMUNIKATY_ALARMU[komunikatAlarmu] ?? "Nie udało się zapisać alarmu."}
              </p>
            )}

            {cena !== null ? (
              <UstawAlarm
                ticker={String(spolka.Ticker)}
                nazwa={String(spolka.Nazwa ?? "")}
                cena={cena}
                min52={liczba(spolka["52-tyg. minimum"])}
                max52={liczba(spolka["52-tyg. maksimum"])}
                waluta={String(spolka.Waluta ?? "")}
                punkty={punkty}
                progiIstniejace={alarmy
                  .filter((a) => !a.wyzwolony)
                  .map((a) => a.cena)}
                powrot={`/spolka/${encodeURIComponent(String(spolka.Ticker))}`}
              />
            ) : (
              <p className="pusto">
                Bez ceny z migawki nie ma na czym postawić alarmu.
              </p>
            )}

            {alarmy.length > 0 && (
              <ListaAlarmow
                alarmy={alarmy}
                powrot={`/spolka/${encodeURIComponent(String(spolka.Ticker))}`}
                pokazTicker={false}
              />
            )}
          </section>

          <Profil spolka={spolka} wszystkie={instrumenty} newsy={newsy} />
        </>
      )}

      {spolka && pokazWykres && (
        <WykresPelny
          ticker={String(spolka.Ticker)}
          nazwa={String(spolka.Nazwa ?? "")}
          symbol={symbolTradingView(String(spolka.Ticker ?? ""))}
          adresZamkniecia={`/spolka/${encodeURIComponent(String(spolka.Ticker))}`}
          cena={cena}
          waluta={String(spolka.Waluta ?? "")}
          powrot={`/spolka/${encodeURIComponent(String(spolka.Ticker))}?wykres=1`}
        />
      )}

      <footer>
        Dane z migawki {data}. Oceny „dobrze / przeciętnie / słabo” porównują
        wskaźnik z medianą jego sektora albo z progami wypisanymi pod pytajnikiem
        — to opis liczby, nie rekomendacja. Narzędzie do przeglądu, nie porada
        inwestycyjna.
      </footer>
    </main>
  );
}
