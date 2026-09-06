"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { FiltryDywidend } from "@/lib/dywidendy";

/**
 * Ustawienia modułu Dywidendy — wszystkie w adresie URL, tak jak w Screenerze
 * i w module „Tanie vs sektor”. Dzięki temu ulubione kryteria da się zapisać
 * w zakładkach przeglądarki i wysłać komuś linkiem.
 */
export default function Suwaki({
  filtry,
  znalezionych,
}: {
  filtry: FiltryDywidend;
  znalezionych: number;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [oczekuje, startTransition] = useTransition();

  function ustaw(klucz: string, wartosc: string) {
    const nowe = new URLSearchParams(params.toString());
    nowe.set(klucz, wartosc);
    startTransition(() => {
      router.replace(`/dywidendy?${nowe.toString()}`, { scroll: false });
    });
  }

  return (
    <div className="filtry">
      <div className="filtry-siatka">
        <label>
          <span>Min. stopa dywidendy</span>
          <select
            value={String(filtry.minStopa)}
            onChange={(e) => ustaw("minStopa", e.target.value)}
          >
            {[0, 2, 3, 4, 5, 6, 8, 10].map((n) => (
              <option key={n} value={n}>
                {n === 0 ? "dowolna" : `${n}% i więcej`}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Maks. zmiana ceny w rok</span>
          <select
            value={String(filtry.maksZmiana1Y)}
            onChange={(e) => ustaw("maksZmiana1Y", e.target.value)}
          >
            {[-20, -10, 0, 5, 15, 30, 100].map((n) => (
              <option key={n} value={n}>
                {n > 0 ? `+${n}%` : `${n}%`} i mniej
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Maks. payout ratio</span>
          <select
            value={String(filtry.maksPayout)}
            onChange={(e) => ustaw("maksPayout", e.target.value)}
          >
            {[50, 60, 80, 100, 200].map((n) => (
              <option key={n} value={n}>
                {n}%
              </option>
            ))}
          </select>
        </label>

        <label className="pole-przelacznik">
          <span>Tylko przed tegoroczną wypłatą</span>
          <input
            type="checkbox"
            checked={filtry.tylkoPrzedSezonem}
            onChange={(e) =>
              ustaw("przedSezonem", e.target.checked ? "1" : "0")
            }
          />
        </label>
      </div>

      <div className="filtry-stopka">
        <span className={oczekuje ? "liczy" : undefined}>
          {oczekuje
            ? "Liczę…"
            : `${znalezionych.toLocaleString("pl-PL")} spółek spełnia kryteria`}
        </span>
      </div>
    </div>
  );
}
