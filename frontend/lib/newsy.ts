/**
 * Newsy spółki — kanał RSS Google News, pobierany NA ŻĄDANIE przy otwarciu
 * profilu.
 *
 * DLACZEGO NIE YAHOO: pierwsza wersja korzystała z wyszukiwarki Yahoo i miała
 * newsy praktycznie wyłącznie dla spółek amerykańskich. Sprawdzone na tym
 * uniwersum: AAPL i NKE po 10 trafień na 10, ALE.WA / CDR.WA / REP.MC / ZAL.DE
 * po zero. A ponieważ był to zwykły serwis wyszukiwania tekstu, zapytanie
 * o „ALE.WA” zwracało artykuły o firmie Allstate. Ponad 40% instrumentów w tej
 * bazie to spółki spoza USA, więc źródło było bezużyteczne tam, gdzie najbardziej
 * potrzebne.
 *
 * Google News działa dla każdego rynku i oddaje wyniki w LOKALNYM JĘZYKU —
 * polskie spółki po polsku, niemieckie po niemiecku. Zmierzone na tej bazie:
 * po ~100 pozycji dla Dino, Allegro, CD Projekt, Zalando, Repsol i Wizz Air.
 * Nie wymaga klucza API ani konta, co ma znaczenie przy projekcie, który ma
 * działać latami bez opieki.
 *
 * TRZY RZECZY, KTÓRE MUSZĄ TU BYĆ — każda wynika z pomiaru, nie z ostrożności:
 *
 * 1. `when:31d` w zapytaniu. Bez tego dla Ambry 99 ze 100 wyników było starszych
 *    niż miesiąc.
 * 2. Odcięcie końcówek prawnych z nazwy („S.A.”, „Inc.”, „Holdings Plc”).
 *    Wyszukiwanie pełnej nazwy rejestrowej gubi większość artykułów, bo prasa
 *    jej nie używa.
 * 3. Filtr po tytule. Nazwy bywają wieloznaczne — „Ambra” to również marka
 *    perfum, więc zapytanie zwracało artykuły o kosmetykach. Te artykuły nie
 *    mają nazwy spółki w tytule, więc wymaganie jej obecności odsiewa je
 *    w całości: z 5 wyników zostaje 1 właściwy.
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

/**
 * Sufiks tickera Yahoo → język i kraj wydania Google News. Bez tego niemiecka
 * spółka dostawałaby anglojęzyczne omówienia zamiast prasy z własnego rynku.
 * Mapowanie po sufiksie, a nie po kolumnie „Rynek”, bo sufiks jest jednoznaczny,
 * a nazwy rynków w migawce bywają niespójne („UK”, „UK (FTSE 100)”, „Niemcy”,
 * „Niemcy (DAX)”).
 */
const REGIONY: Record<string, { hl: string; gl: string }> = {
  WA: { hl: "pl", gl: "PL" },
  DE: { hl: "de", gl: "DE" },
  VI: { hl: "de", gl: "AT" },
  SW: { hl: "de", gl: "CH" },
  PA: { hl: "fr", gl: "FR" },
  AS: { hl: "nl", gl: "NL" },
  BR: { hl: "nl", gl: "BE" },
  LS: { hl: "pt", gl: "PT" },
  MC: { hl: "es", gl: "ES" },
  MI: { hl: "it", gl: "IT" },
  ST: { hl: "sv", gl: "SE" },
  OL: { hl: "no", gl: "NO" },
  CO: { hl: "da", gl: "DK" },
  HE: { hl: "fi", gl: "FI" },
  PR: { hl: "cs", gl: "CZ" },
  L: { hl: "en", gl: "GB" },
};

function region(ticker: string): { hl: string; gl: string } {
  const czesci = String(ticker || "").toUpperCase().split(".");
  if (czesci.length < 2) return { hl: "en", gl: "US" };
  return REGIONY[czesci[1]] ?? { hl: "en", gl: "US" };
}

/** Formy prawne, których prasa nie używa, a które psują wyszukiwanie. */
const KONCOWKI_PRAWNE =
  /\b(S\.?A\.?|Inc\.?|Incorporated|Corporation|Corp\.?|PLC|N\.?V\.?|AG|SE|ASA|AB|Oyj|Group|Holdings?|Company|Co\.?|Ltd\.?|S\.p\.A\.|SpA|SAB|CV)\b/gi;

export function rdzenNazwy(nazwa: string): string {
  return String(nazwa || "")
    .replace(KONCOWKI_PRAWNE, "")
    .replace(/[,.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Czy tytuł faktycznie dotyczy tej spółki. */
function dotyczySpolki(tytul: string, nazwa: string): boolean {
  const t = tytul.toLowerCase();
  const r = rdzenNazwy(nazwa).toLowerCase();
  if (!r) return false;
  if (t.includes(r)) return true;
  // Prasa skraca nazwy wielowyrazowe („CD Projekt RED” → „CD Projekt”),
  // więc dopuszczamy dopasowanie po pierwszym znaczącym słowie.
  const pierwsze = r.split(" ").find((s) => s.length >= 4);
  return pierwsze ? t.includes(pierwsze) : false;
}

/**
 * Treść znacznika. `[^>]*` w otwarciu jest konieczne — wydawca przychodzi jako
 * `<source url="...">`, więc wzorzec bez atrybutów nigdy go nie znajdował
 * i tytuły zostawały sklejone z nazwą serwisu.
 */
function tekstZnacznika(blok: string, znacznik: string): string {
  const m = blok.match(
    new RegExp(`<${znacznik}[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${znacznik}>`),
  );
  return m ? m[1].trim() : "";
}

function odkoduj(s: string): string {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

export async function newsySpolki(ticker: string, nazwa: string): Promise<News[]> {
  const rdzen = rdzenNazwy(nazwa) || String(ticker || "").split(".")[0];
  if (!rdzen) return [];

  const { hl, gl } = region(ticker);
  const zapytanie = `"${rdzen}" when:31d`;
  const url =
    "https://news.google.com/rss/search" +
    `?q=${encodeURIComponent(zapytanie)}&hl=${hl}&gl=${gl}&ceid=${gl}:${hl}`;

  try {
    const odp = await fetch(url, {
      headers: { "User-Agent": UA },
      // Newsy zmieniają się w ciągu dnia, ale nie co minutę.
      next: { revalidate: 1800 },
    });
    if (!odp.ok) return [];
    const xml = await odp.text();

    const pozycje = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].map((m) => {
      const blok = m[1];
      let tytul = odkoduj(tekstZnacznika(blok, "title"));
      // Wydawcę bierzemy ze znacznika <source>, a nie z rozcinania tytułu po
      // ostatnim myślniku. Rozcinanie myliło się tam, gdzie sam nagłówek
      // zawiera myślnik: „DNP (+1.53%) - Dino Polska SA” dawało wydawcę
      // „Dino Polska SA”, czyli nazwę spółki zamiast serwisu.
      const wydawca = odkoduj(tekstZnacznika(blok, "source"));
      // Google News dokleja wydawcę na koniec tytułu, czasem DWUKROTNIE
      // („… - boerse.de - boerse.de”), więc obcinamy w pętli.
      if (wydawca) {
        const ogon = ` - ${wydawca}`;
        while (tytul.endsWith(ogon)) tytul = tytul.slice(0, -ogon.length).trim();
      }
      const data = Date.parse(tekstZnacznika(blok, "pubDate"));
      return {
        tytul,
        wydawca,
        link: odkoduj(tekstZnacznika(blok, "link")),
        czas: Number.isFinite(data) ? Math.floor(data / 1000) : 0,
      };
    });

    const widziane = new Set<string>();
    return pozycje
      .filter((n) => n.tytul && n.link && n.czas > 0)
      .filter((n) => dotyczySpolki(n.tytul, nazwa))
      .filter((n) => {
        const klucz = n.tytul.toLowerCase();
        if (widziane.has(klucz)) return false;
        widziane.add(klucz);
        return true;
      })
      .sort((a, b) => b.czas - a.czas)
      .slice(0, 10);
  } catch {
    // Brak sieci albo zmiana formatu kanału nie może wywalić profilu.
    return [];
  }
}
