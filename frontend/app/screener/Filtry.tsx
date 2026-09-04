"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { SORTOWANIA, type Filtry } from "@/lib/filtry";

/**
 * Panel filtrów. Stan trzymamy W ADRESIE URL, nie w komponencie — dzięki temu
 * przefiltrowany widok da się zapisać w zakładkach, odświeżyć albo wysłać
 * sobie na telefon, a przycisk „wstecz" działa tak, jak człowiek się spodziewa.
 *
 * Samo filtrowanie robi serwer (patrz lib/dane.ts). Migawka waży ~1,9 MB, więc
 * przesyłanie jej do przeglądarki tylko po to, żeby filtrować na miejscu,
 * byłoby okrutne dla telefonu w zasięgu komórkowym.
 */
export default function PanelFiltrow({
  wartosci,
  rynki,
  sektory,
  liczbaWynikow,
  liczbaWszystkich,
}: {
  wartosci: Filtry;
  rynki: string[];
  sektory: string[];
  liczbaWynikow: number;
  liczbaWszystkich: number;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [oczekuje, startTransition] = useTransition();
  const [szukaj, setSzukaj] = useState(wartosci.szukaj);
  const pierwszyRender = useRef(true);

  function ustaw(zmiany: Record<string, string>) {
    const nowe = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(zmiany)) {
      if (v === "") nowe.delete(k);
      else nowe.set(k, v);
    }
    startTransition(() => {
      router.replace(`/screener?${nowe.toString()}`, { scroll: false });
    });
  }

  // Wyszukiwarka z opóźnieniem: bez tego każda litera oznaczałaby osobne
  // zapytanie do serwera.
  useEffect(() => {
    if (pierwszyRender.current) {
      pierwszyRender.current = false;
      return;
    }
    const t = setTimeout(() => ustaw({ szukaj }), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [szukaj]);

  const czyste =
    wartosci.typ === "stock" &&
    !wartosci.rynek &&
    !wartosci.sektor &&
    wartosci.minScore === 0 &&
    wartosci.maxAth === 0 &&
    wartosci.maxFlag === 10 &&
    !wartosci.szukaj;

  return (
    <div className="filtry">
      <div className="filtry-siatka">
        <label>
          <span>Szukaj</span>
          <input
            type="search"
            value={szukaj}
            onChange={(e) => setSzukaj(e.target.value)}
            placeholder="ticker lub nazwa"
          />
        </label>

        <label>
          <span>Typ</span>
          <select value={wartosci.typ} onChange={(e) => ustaw({ typ: e.target.value })}>
            <option value="stock">Akcje</option>
            <option value="etf">ETF-y</option>
            <option value="">Wszystko</option>
          </select>
        </label>

        <label>
          <span>Rynek</span>
          <select value={wartosci.rynek} onChange={(e) => ustaw({ rynek: e.target.value })}>
            <option value="">Wszystkie</option>
            {rynki.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Sektor</span>
          <select value={wartosci.sektor} onChange={(e) => ustaw({ sektor: e.target.value })}>
            <option value="">Wszystkie</option>
            {sektory.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Min. Buy Score</span>
          <select
            value={String(wartosci.minScore)}
            onChange={(e) => ustaw({ minScore: e.target.value })}
          >
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
              <option key={n} value={n}>
                {n === 0 ? "bez ograniczeń" : `${n} i więcej`}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Spadek od ATH</span>
          <select
            value={String(wartosci.maxAth)}
            onChange={(e) => ustaw({ maxAth: e.target.value })}
          >
            <option value="0">bez ograniczeń</option>
            {[-10, -20, -30, -40, -50, -60, -70].map((n) => (
              <option key={n} value={n}>
                co najmniej {Math.abs(n)}%
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Maks. flag</span>
          <select
            value={String(wartosci.maxFlag)}
            onChange={(e) => ustaw({ maxFlag: e.target.value })}
          >
            {[0, 1, 2, 3, 4, 5, 10].map((n) => (
              <option key={n} value={n}>
                {n === 10 ? "bez ograniczeń" : n === 0 ? "zero flag" : `do ${n}`}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Sortuj wg</span>
          <select value={wartosci.sortuj} onChange={(e) => ustaw({ sortuj: e.target.value })}>
            {SORTOWANIA.map((s) => (
              <option key={s.klucz} value={s.klucz}>
                {s.etykieta}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="filtry-stopka">
        <span className={oczekuje ? "liczy" : undefined}>
          {oczekuje
            ? "Filtruję…"
            : `${liczbaWynikow.toLocaleString("pl-PL")} z ${liczbaWszystkich.toLocaleString("pl-PL")}`}
        </span>
        {!czyste && (
          <button onClick={() => router.replace("/screener", { scroll: false })}>
            Wyczyść filtry
          </button>
        )}
      </div>
    </div>
  );
}
