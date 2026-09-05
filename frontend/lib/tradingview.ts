/**
 * Zamiana tickera Yahoo na symbol TradingView.
 *
 * Lustro _SUFFIX_TRADINGVIEW z core/scanner.py. Yahoo używa sufiksu giełdy po
 * kropce (ALE.WA), TradingView prefiksu giełdy przed dwukropkiem (GPW:ALE).
 *
 * Zero importów z Node.
 */
const GIELDY: Record<string, string> = {
  WA: "GPW",
  DE: "XETR",
  PA: "EURONEXT",
  AS: "EURONEXT",
  LS: "EURONEXT",
  BR: "EURONEXT",
  MC: "BME",
  ST: "OMXSTO",
  OL: "OSL",
  CO: "OMXCOP",
  HE: "OMXHEX",
  MI: "MIL",
  VI: "VIE",
  L: "LSE",
  SW: "SIX",
  PR: "PSECZ",
};

/**
 * Zwraca symbol w formacie TradingView. Dla tickerów amerykańskich (bez
 * sufiksu) oddajemy sam symbol — TradingView sam znajdzie giełdę, bo NASDAQ
 * i NYSE trzeba by rozróżniać, a tej informacji w migawce nie ma.
 */
export function symbolTradingView(ticker: string): string {
  const t = String(ticker || "").trim().toUpperCase();
  if (!t) return "";
  if (!t.includes(".")) return t;

  const [baza, sufiks] = t.split(".");
  const gielda = GIELDY[sufiks];
  return gielda ? `${gielda}:${baza}` : baza;
}
