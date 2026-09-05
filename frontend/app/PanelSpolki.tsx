import Link from "next/link";
import Profil from "./spolka/Profil";
import { liczba, type Instrument } from "@/lib/filtry";
import type { News } from "@/lib/newsy";

/**
 * Panel boczny z profilem wybranej spółki.
 *
 * Wyciągnięty ze Screenera, żeby ten sam panel działał w każdym module
 * z listą spółek. Bez tego każdy kolejny moduł kopiowałby nagłówek, przycisk
 * zamknięcia i wywołanie profilu — i po trzech modułach rozjechałyby się
 * między sobą.
 */
export default function PanelSpolki({
  spolka,
  wszystkie,
  newsy,
  adresZamkniecia,
}: {
  spolka: Instrument;
  wszystkie: Instrument[];
  newsy: News[];
  adresZamkniecia: string;
}) {
  const cena = liczba(spolka.Cena);
  const zmiana = liczba(spolka["Zmiana ceny (1Y%)"]);
  const ticker = String(spolka.Ticker);

  return (
    <aside className="panel-spolki">
      <div className="panel-spolki-naglowek">
        <div>
          <h2>{ticker}</h2>
          <p className="spolka-nazwa">
            {String(spolka.Nazwa ?? "")}
            {spolka.Sektor ? ` · ${String(spolka.Sektor)}` : ""}
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
        <Link className="panel-zamknij" href={adresZamkniecia} aria-label="Zamknij panel">
          ✕
        </Link>
      </div>

      <Profil spolka={spolka} wszystkie={wszystkie} newsy={newsy} kompaktowy />

      <Link className="link" href={`/spolka/${encodeURIComponent(ticker)}`}>
        Otwórz na pełnej stronie →
      </Link>
    </aside>
  );
}
