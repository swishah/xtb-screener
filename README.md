# XTB Screener

Screener akcji i ETF-ów pod strategię "duży spadek od ATH, ale biznes wciąż
zdrowy", oparty o dane Yahoo Finance, z historią migawek (backtest) i appką
Streamlit.

## Jak to działa

```
config/markets.py   – uniwersum tickerów (indeksy + ETF-y)
core/scanner.py      – silnik: pobiera dane, liczy wskaźniki i score
core/db.py            – SQLite (data/history.db) — codzienne migawki
scripts/run_daily_scan.py – uruchamiane przez GitHub Actions co dzień
app.py                – appka Streamlit (screener / deep value / backtest)
```

Streamlit Community Cloud ma **ulotny filesystem** (resetuje się przy każdym
redeployu), więc trwałość historii bierze się stąd, że `data/history.db` jest
**commitowane do repo przez GitHub Actions** (`.github/workflows/daily_scan.yml`)
codziennie po sesji. Appka Streamlit tylko *czyta* tę bazę.

## Start lokalny

```bash
pip install -r requirements.txt
python scripts/run_daily_scan.py   # pierwszy skan, zapełnia data/history.db
streamlit run app.py
```

## Deploy

1. Wrzuć repo na GitHub (upewnij się, że `data/history.db` NIE zawiera
   żadnych sekretów — to tylko dane rynkowe).
2. Włącz w repo: Settings → Actions → General → "Read and write permissions"
   dla GITHUB_TOKEN (żeby workflow mógł commitować `history.db`).
3. Uruchom workflow raz ręcznie (zakładka Actions → Daily market scan → Run
   workflow), żeby baza miała pierwszą migawkę.
4. Wejdź na [share.streamlit.io](https://share.streamlit.io), połącz repo,
   wskaż `app.py` jako plik główny → Deploy.

## Ważne zastrzeżenia

- **Uniwersum tickerów** jest budowane ze składów głównych indeksów (WIG,
  DAX, CAC40, FTSE100, IBEX35, OMX30, OBX, S&P500) + ręcznie dobranej listy
  popularnych ETF-ów UCITS. XTB nie ma publicznego API do pobrania pełnej,
  aktualnej listy notowanych instrumentów bez zalogowanego konta (stare
  `xapi.xtb.com`/`ws.xtb.com` przestały działać w marcu 2025). **Zawsze
  zweryfikuj w samej platformie XTB**, czy dany ticker jest faktycznie
  dostępny, zanim złożysz zlecenie — możesz zaznaczać potwierdzone tickery
  w `VERIFIED_TICKERS` w `config/markets.py`.
- To narzędzie do przeglądu/rankingu, nie system transakcyjny i nie porada
  inwestycyjna — decyzje i ich skutki są po Twojej stronie.
- Jeśli kiedyś dodasz webhook/klucz API (np. do powiadomień), trzymaj go w
  `st.secrets` / zmiennych środowiskowych GitHub Actions (Settings → Secrets),
  nigdy w kodzie źródłowym.
