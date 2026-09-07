import { dodaj } from "./akcje";
import type { Instrument } from "@/lib/filtry";

/**
 * Dodawanie spółki do obserwowanych.
 *
 * Pole tickera to zwykły `input` z podpowiedziami z `datalist`, a nie lista
 * rozwijana z 1346 pozycjami: przeglądarka filtruje podpowiedzi w trakcie
 * pisania sama, bez JavaScriptu, a wpisanie tickera z pamięci jest szybsze
 * niż przewijanie. Poprawność i tak sprawdza serwer — akcja odrzuca ticker,
 * którego nie ma w migawce, żeby literówka nie tworzyła martwego wiersza.
 */
export default function DodajSpolke({
  instrumenty,
  powrot,
  listaId,
}: {
  instrumenty: Instrument[];
  powrot: string;
  listaId: number;
}) {
  return (
    <form action={dodaj} className="form-dodaj-obserwowana">
      <input type="hidden" name="powrot" value={powrot} />
      <input type="hidden" name="lista" value={listaId} />

      <label>
        <span>Spółka lub ETF</span>
        <input
          type="text"
          name="ticker"
          list="lista-instrumentow"
          placeholder="np. AAPL"
          required
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label className="rozciagnij">
        <span>Notatka (opcjonalnie)</span>
        <input
          type="text"
          name="notatka"
          placeholder="np. czekam na wyniki Q3"
          autoComplete="off"
        />
      </label>

      <button type="submit">Dodaj</button>

      <datalist id="lista-instrumentow">
        {instrumenty.map((i) => (
          <option key={String(i.Ticker)} value={String(i.Ticker)}>
            {String(i.Nazwa ?? "")}
          </option>
        ))}
      </datalist>
    </form>
  );
}
