"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

/**
 * Dwa ustawienia modułu, oba w adresie URL — tak jak filtry Screenera.
 * Ulubione kryteria da się przez to zapisać w zakładkach.
 */
export default function Suwaki({
  minSpolek,
  maksRoznica,
  znalezionych,
}: {
  minSpolek: number;
  maksRoznica: number;
  znalezionych: number;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [oczekuje, startTransition] = useTransition();

  function ustaw(klucz: string, wartosc: string) {
    const nowe = new URLSearchParams(params.toString());
    nowe.set(klucz, wartosc);
    // Wybrana spółka zostaje — zmiana progu nie ma zamykać otwartego profilu.
    startTransition(() => {
      router.replace(`/tanie?${nowe.toString()}`, { scroll: false });
    });
  }

  return (
    <div className="filtry">
      <div className="filtry-siatka">
        <label>
          <span>Min. spółek w sektorze</span>
          <select
            value={String(minSpolek)}
            onChange={(e) => ustaw("minSpolek", e.target.value)}
          >
            {[2, 3, 5, 8, 10, 15, 20].map((n) => (
              <option key={n} value={n}>
                {n} i więcej
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Taniej od mediany o co najmniej</span>
          <select
            value={String(maksRoznica)}
            onChange={(e) => ustaw("maksRoznica", e.target.value)}
          >
            {[-10, -20, -30, -40, -50, -60, -70, -80].map((n) => (
              <option key={n} value={n}>
                {Math.abs(n)}%
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="filtry-stopka">
        <span className={oczekuje ? "liczy" : undefined}>
          {oczekuje ? "Liczę…" : `${znalezionych.toLocaleString("pl-PL")} spółek spełnia kryteria`}
        </span>
      </div>
    </div>
  );
}
