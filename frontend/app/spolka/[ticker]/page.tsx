import Link from "next/link";
import { notFound } from "next/navigation";
import Pasek from "../../Pasek";
import Profil from "../Profil";
import { migawkaBezpieczna } from "@/lib/dane";
import { liczba } from "@/lib/filtry";
import { newsySpolki } from "@/lib/newsy";

export const dynamic = "force-dynamic";

export default async function StronaSpolki({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
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
            <Link className="link" href="/screener">
              ← Wróć do screenera
            </Link>
          </div>

          <Profil spolka={spolka} wszystkie={instrumenty} newsy={newsy} />
        </>
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
