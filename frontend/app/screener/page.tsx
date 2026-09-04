import Link from "next/link";
import Pasek from "../Pasek";
import Tabela from "../Tabela";
import { liczba, migawkaBezpieczna } from "@/lib/dane";

export const dynamic = "force-dynamic";

/**
 * Screener — pierwszy przeniesiony moduł.
 *
 * Na razie bez filtrów: pokazuje akcje posortowane wg Buy Score, ograniczone
 * do 100 pozycji. Filtry przychodzą w kolejnym kroku; ta strona ma najpierw
 * udowodnić, że wzorzec działa na prawdziwych danych.
 */
export default async function Screener() {
  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();

  const akcje = instrumenty
    .filter((i) => i.Typ === "stock")
    .sort((a, b) => (liczba(b["Buy Score"]) ?? -1) - (liczba(a["Buy Score"]) ?? -1))
    .slice(0, 100);

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      {blad && (
        <div className="alert">
          <b>Nie udało się wczytać danych.</b>
          <div style={{ marginTop: 8, fontSize: "0.78rem", opacity: 0.75 }}>
            {blad}
          </div>
        </div>
      )}

      <div className="card">
        <div className="cardhead">
          <h2>Screener</h2>
          <em>
            {akcje.length} z {instrumenty.filter((i) => i.Typ === "stock").length} akcji,
            wg Buy Score
          </em>
          <Link className="link" href="/">
            ← Wróć na pulpit
          </Link>
        </div>
        <Tabela wiersze={akcje} />
      </div>

      <footer>
        Lista skrócona do 100 pozycji o najwyższym Buy Score. Filtrowanie po
        rynku, sektorze i wskaźnikach — w kolejnym kroku.
      </footer>
    </main>
  );
}
