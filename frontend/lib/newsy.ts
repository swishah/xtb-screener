/**
 * Newsy spółki — pobierane NA ŻĄDANIE, przy otwarciu profilu.
 *
 * Nie ma ich w migawce i nie będzie: skan przechodzi ~1300 instrumentów, więc
 * każde dodatkowe zapytanie na spółkę wydłużyłoby go nieproporcjonalnie. To ta
 * sama zasada, którą stosuje appka Streamlit — dane „na żądanie” siedzą za
 * kliknięciem.
 *
 * OGRANICZENIE, KTÓRE TRZEBA ZNAĆ: Yahoo ma newsy praktycznie wyłącznie dla
 * spółek amerykańskich. Sprawdzone na tej bazie — dla AAPL i NKE wraca 10 z 10
 * trafień, dla ALE.WA, CDR.WA, REP.MC i ZAL.DE zero. Co gorsza, użyty endpoint
 * to WYSZUKIWARKA TEKSTOWA: zapytanie o „ALE.WA” zwracało artykuły o firmie
 * Allstate. Dlatego filtrujemy po relatedTickers i wolimy pokazać „brak
 * newsów” niż cudze — zobaczenie newsa o innej spółce pod nazwą Allegro jest
 * gorsze niż brak newsa.
 */
export type News = {
  tytul: string;
  wydawca: string;
  link: string;
  czas: number;
};

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36";

const DNI = 31;

export async function newsySpolki(ticker: string): Promise<News[]> {
  const t = String(ticker || "").trim();
  if (!t) return [];

  const url =
    "https://query1.finance.yahoo.com/v1/finance/search" +
    `?q=${encodeURIComponent(t)}&newsCount=20&quotesCount=0`;

  try {
    const odp = await fetch(url, {
      headers: { "User-Agent": UA },
      // Newsy zmieniają się w ciągu dnia, ale nie co minutę.
      next: { revalidate: 1800 },
    });
    if (!odp.ok) return [];

    const dane = (await odp.json()) as {
      news?: {
        title?: string;
        publisher?: string;
        link?: string;
        providerPublishTime?: number;
        relatedTickers?: string[];
      }[];
    };

    const granica = Date.now() / 1000 - DNI * 24 * 3600;
    const szukany = t.toUpperCase();

    return (dane.news ?? [])
      .filter((n) =>
        (n.relatedTickers ?? []).some((rt) => String(rt).toUpperCase() === szukany),
      )
      .filter((n) => (n.providerPublishTime ?? 0) >= granica)
      .map((n) => ({
        tytul: String(n.title ?? ""),
        wydawca: String(n.publisher ?? ""),
        link: String(n.link ?? ""),
        czas: Number(n.providerPublishTime ?? 0),
      }))
      .filter((n) => n.tytul && n.link)
      .sort((a, b) => b.czas - a.czas)
      .slice(0, 8);
  } catch {
    // Brak sieci albo zmiana formatu odpowiedzi nie może wywalić profilu.
    return [];
  }
}
