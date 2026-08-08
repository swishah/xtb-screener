"""
Uniwersum instrumentów.

WAŻNE: XTB nie udostępnia publicznego, niezalogowanego API z pełną listą
notowanych instrumentów (stare xapi.xtb.com/ws.xtb.com zostały wyłączone
w marcu 2025; obecny dostęp do xStation5 wymaga zalogowanego konta demo/real
i osobnej integracji). Dlatego uniwersum poniżej jest budowane na bazie
składu głównych indeksów (WIG20+mWIG40, DAX, CAC40, FTSE100, IBEX35, OMX30,
OBX, S&P500) — to instrumenty, które XTB faktycznie oferuje (XTB reklamuje
dostęp do >1500 akcji i >200 ETF-ów z 16 giełd, w tym GPW, Xetra, NYSE,
Nasdaq, LSE i giełd skandynawskich).

Zanim zaczniesz realnie handlować konkretnym tickerem, zweryfikuj jego
dostępność w samej platformie XTB (wyszukiwarka instrumentów) — ten plik
tego automatycznie nie sprawdza. Możesz oznaczać tickery jako zweryfikowane
w VERIFIED_TICKERS poniżej; ekran screenera pozwala filtrować tylko po nich.
"""

# ---------------------------------------------------------------------------
# AKCJE — mapy indeksów (przeniesione z oryginalnego skryptu użytkownika)
# ---------------------------------------------------------------------------
WIG20_MAP = {"ALE.WA": "Allegro", "ALR.WA": "Alior Bank", "BDX.WA": "Budimex", "BHW.WA": "Bank Handlowy", "CDR.WA": "CD Projekt", "CPS.WA": "Cyfrowy Polsat", "DNP.WA": "Dino Polska", "JSW.WA": "JSW", "KGH.WA": "KGHM", "KRU.WA": "Kruk", "LPP.WA": "LPP", "MBK.WA": "mBank", "OPL.WA": "Orange Polska", "PEO.WA": "Pekao SA", "PGE.WA": "PGE", "PKO.WA": "PKO BP", "PKN.WA": "ORLEN", "PZU.WA": "PZU", "SPL.WA": "Santander BP", "MDV.WA": "Modivo"}
MWIG40_MAP = {"11B.WA": "11 bit studios", "1AT.WA": "Atal", "ABS.WA": "Asseco BS", "APR.WA": "Auto Partner", "ASB.WA": "ASBIS", "BFT.WA": "Benefit Systems", "CAR.WA": "Inter Cars", "CIG.WA": "CI Games", "CLN.WA": "Celon Pharma", "COG.WA": "Cognor", "DAT.WA": "DataWalk", "DOM.WA": "Dom Development", "EAT.WA": "AmRest", "ENP.WA": "Enea", "EUR.WA": "Eurocash", "GPP.WA": "Grupa Pracuj", "GRN.WA": "Grenevia", "GTC.WA": "GTC", "HUU.WA": "Huuuge", "ING.WA": "ING BSK", "TXT.WA": "Text S.A.", "MIL.WA": "Millennium", "MBR.WA": "Mo-BRUK", "NEU.WA": "Neuca", "PLW.WA": "PlayWay", "RVU.WA": "Revuele", "SEL.WA": "Selena FM", "STP.WA": "Stalproduct", "TEN.WA": "Ten Square Games", "TPE.WA": "Tauron", "VRG.WA": "VRG", "WPL.WA": "Wirtualna Polska", "XTB.WA": "XTB", "GPW.WA": "GPW", "SNK.WA": "Sanok", "AST.WA": "Asseco POL", "ATC.WA": "Arctic Paper"}
DAX_MAP = {"ADS.DE": "Adidas", "AIR.DE": "Airbus", "ALV.DE": "Allianz", "BAS.DE": "BASF", "BAYN.DE": "Bayer", "BEI.DE": "Beiersdorf", "BMW.DE": "BMW", "BNR.DE": "Brenntag", "CBK.DE": "Commerzbank", "CON.DE": "Continental", "1COV.DE": "Covestro", "DTG.DE": "Daimler Truck", "DBK.DE": "Deutsche Bank", "DB1.DE": "Deutsche Börse", "DPW.DE": "DHL Group", "DTE.DE": "Deutsche Telekom", "EOAN.DE": "E.ON", "FRE.DE": "Fresenius", "HNR1.DE": "Hannover Re", "HEI.DE": "Heidelberg Materials", "HEN3.DE": "Henkel", "IFX.DE": "Infineon", "MBG.DE": "Mercedes-Benz", "MRK.DE": "Merck", "MTX.DE": "MTU Aero Engines", "MUV2.DE": "Munich Re", "P911.DE": "Porsche AG", "PAH3.DE": "Porsche SE", "QIA.DE": "Qiagen", "RHM.DE": "Rheinmetall", "RWE.DE": "RWE", "SAP.DE": "SAP", "SRT3.DE": "Sartorius", "SIE.DE": "Siemens", "ENR.DE": "Siemens Energy", "SHL.DE": "Siemens Healthineers", "SY1.DE": "Symrise", "VOW3.DE": "Volkswagen", "VNA.DE": "Vonovia", "ZAL.DE": "Zalando"}
CAC40_MAP = {"AC.PA": "Accor", "AI.PA": "Air Liquide", "AIR.PA": "Airbus", "MT.AS": "ArcelorMittal", "CS.PA": "AXA", "BNP.PA": "BNP Paribas", "EN.PA": "Bouygues", "CAP.PA": "Capgemini", "CA.PA": "Carrefour", "ACA.PA": "Crédit Agricole", "BN.PA": "Danone", "DSY.PA": "Dassault Systèmes", "EDEN.PA": "Edenred", "ENGI.PA": "Engie", "EL.PA": "EssilorLuxottica", "ERF.PA": "Eurofins Scientific", "RMS.PA": "Hermès", "KER.PA": "Kering", "LR.PA": "Legrand", "OR.PA": "L'Oréal", "MC.PA": "LVMH", "ML.PA": "Michelin", "ORP.PA": "Orange", "PRV.PA": "Pernod Ricard", "PUB.PA": "Publicis Groupe", "RNO.PA": "Renault", "SAF.PA": "Safran", "SGO.PA": "Saint-Gobain", "SAN.PA": "Sanofi", "SU.PA": "Schneider Electric", "GLE.PA": "Société Générale", "STLAP.PA": "Stellantis", "STMPA.PA": "STMicroelectronics", "TEP.PA": "Teleperformance", "HO.PA": "Thales", "TTE.PA": "TotalEnergies", "URW.AS": "Unibail-Rodamco-Westfield", "VIE.PA": "Veolia", "DG.PA": "Vinci", "VIV.PA": "Vivendi"}
FTSE_MAP = {"SHEL.L": "Shell", "AZN.L": "AstraZeneca", "HSBA.L": "HSBC", "ULVR.L": "Unilever", "BP.L": "BP", "GSK.L": "GSK", "DGE.L": "Diageo", "REL.L": "RELX", "BATS.L": "British American Tobacco", "GLEN.L": "Glencore", "RIO.L": "Rio Tinto", "BA.L": "BAE Systems", "CPG.L": "Compass Group", "LSEG.L": "LSEG", "NWG.L": "NatWest Group", "BARC.L": "Barclays", "STAN.L": "Standard Chartered", "NG.L": "National Grid", "AHT.L": "Ashtead", "TSCO.L": "Tesco", "LLOY.L": "Lloyds", "PRU.L": "Prudential", "AV.L": "Aviva", "SSE.L": "SSE", "LGEN.L": "Legal & General", "RTO.L": "Rentokil", "NXT.L": "Next", "WPP.L": "WPP", "VOD.L": "Vodafone", "RR.L": "Rolls-Royce", "EZJ.L": "easyJet", "IAG.L": "IAG"}
IBEX_MAP = {"ANA.MC": "Acciona", "ACX.MC": "Acerinox", "ACS.MC": "ACS", "AENA.MC": "Aena", "AMS.MC": "Amadeus", "BKT.MC": "Bankinter", "BBVA.MC": "BBVA", "CABK.MC": "CaixaBank", "CLNX.MC": "Cellnex", "ENG.MC": "Enagás", "ELE.MC": "Endesa", "FER.MC": "Ferrovial", "FDR.MC": "Fluidra", "GRF.MC": "Grifols", "IAG.MC": "IAG", "IBE.MC": "Iberdrola", "ITX.MC": "Inditex", "IDR.MC": "Indra", "COL.MC": "Inmobiliaria Colonial", "LOG.MC": "Logista", "MAP.MC": "Mapfre", "MEL.MC": "Meliá Hotels", "MRL.MC": "Merlin Properties", "NTGY.MC": "Naturgy", "RED.MC": "Redeia", "REP.MC": "Repsol", "ROVI.MC": "Rovi", "SAB.MC": "Sabadell", "SAN.MC": "Banco Santander", "SCYR.MC": "Sacyr", "TEF.MC": "Telefónica", "UNI.MC": "Unicaja"}
OMX_MAP = {"ABB.ST": "ABB", "ALFA.ST": "Alfa Laval", "ASSA-B.ST": "ASSA ABLOY", "ATCO-A.ST": "Atlas Copco A", "ATCO-B.ST": "Atlas Copco B", "AZN.ST": "AstraZeneca", "BOL.ST": "Boliden", "ELUX-B.ST": "Electrolux", "ERIC-B.ST": "Ericsson", "ESSITY-B.ST": "Essity", "EVO.ST": "Evolution", "GETI-B.ST": "Getinge", "HEXA-B.ST": "Hexagon", "HM-B.ST": "H&M", "INVE-B.ST": "Investor B", "KINV-B.ST": "Kinnevik", "NDA-SE.ST": "Nordea", "SAND.ST": "Sandvik", "SCA-B.ST": "SCA", "SEB-A.ST": "SEB", "SHB-A.ST": "Handelsbanken", "SKA-B.ST": "Skanska", "SKF-B.ST": "SKF", "STE-R.ST": "Stora Enso", "SWED-A.ST": "Swedbank", "SWMA.ST": "Swedish Match", "TEL2-B.ST": "Tele2", "TELIA.ST": "Telia", "VOLV-B.ST": "Volvo B"}
OBX_MAP = {"EQNR.OL": "Equinor", "DNB.OL": "DNB Bank", "AKBP.OL": "Aker BP", "TEL.OL": "Telenor", "NHY.OL": "Norsk Hydro", "MOWI.OL": "Mowi", "YAR.OL": "Yara International", "ORK.OL": "Orkla", "SUBC.OL": "Subsea 7", "TOM.OL": "Tomra Systems", "STB.OL": "Storebrand", "SALM.OL": "SalMar", "GJFS.OL": "Gjensidige", "AKER.OL": "Aker", "SCHA.OL": "Schibsted A", "FRO.OL": "Frontline", "TGS.OL": "TGS", "BAKKA.OL": "Bakkafrost", "LSG.OL": "Lerøy Seafood", "KOG.OL": "Kongsberg Gruppen", "NOD.OL": "Nordic Semiconductor", "NEL.OL": "Nel", "VAR.OL": "Vår Energi", "MPCC.OL": "MPC Container Ships"}

# ---------------------------------------------------------------------------
# ETF-y — popularne UCITS ETF-y notowane na giełdach europejskich, typowo
# oferowane przez brokerów z ofertą "akcje+ETF" pokroju XTB. Zweryfikuj
# dostępność każdego w platformie przed poleganiem na nim.
# ---------------------------------------------------------------------------
ETF_MAP = {
    "CSPX.L": "iShares Core S&P 500 UCITS ETF (Acc)",
    "SXR8.DE": "iShares Core S&P 500 UCITS ETF (DE, Acc)",
    "VUSA.L": "Vanguard S&P 500 UCITS ETF (Dist)",
    "IWDA.AS": "iShares Core MSCI World UCITS ETF (Acc)",
    "EUNL.DE": "iShares Core MSCI World UCITS ETF (DE, Acc)",
    "VWCE.DE": "Vanguard FTSE All-World UCITS ETF (Acc)",
    "VFEM.L": "Vanguard FTSE Emerging Markets UCITS ETF",
    "EIMI.L": "iShares Core MSCI EM IMI UCITS ETF (Acc)",
    "XDWD.DE": "Xtrackers MSCI World UCITS ETF (Acc)",
    "IUSN.DE": "iShares MSCI World Small Cap UCITS ETF",
    "EXSA.DE": "iShares STOXX Europe 600 UCITS ETF",
    "VEUR.L": "Vanguard FTSE Developed Europe UCITS ETF",
    "XDEW.DE": "Xtrackers S&P 500 Equal Weight UCITS ETF",
    "QDVE.DE": "iShares S&P 500 Information Technology Sector UCITS ETF",
    "IUIT.L": "iShares S&P 500 Information Technology Sector UCITS ETF",
    "IGLN.L": "iShares Physical Gold ETC",
    "SGLN.L": "Invesco Physical Gold ETC",
    "EQQQ.L": "Invesco EQQQ Nasdaq-100 UCITS ETF",
    "XDNA.DE": "Xtrackers Nasdaq 100 UCITS ETF",
    "LCWD.L": "Lyxor Core MSCI World UCITS ETF",
    "SPPW.DE": "SPDR MSCI World UCITS ETF",
    "SPY5.L": "SPDR S&P 500 UCITS ETF",
    "ISF.L": "iShares Core FTSE 100 UCITS ETF",
    "DAXEX.DE": "iShares Core DAX UCITS ETF",
    "CSNDX.SW": "iShares Nasdaq 100 UCITS ETF",
    "VHYL.L": "Vanguard FTSE All-World High Dividend Yield UCITS ETF",
    "TDIV.AS": "VanEck Morningstar Developed Markets Dividend Leaders ETF",
    "IUSA.AS": "iShares Core S&P 500 UCITS ETF (EUR)",
    "XAIX.DE": "Xtrackers Artificial Intelligence & Big Data UCITS ETF",
    "SEMI.L": "iShares MSCI Global Semiconductors UCITS ETF",
}

# Tickery ręcznie potwierdzone przez Ciebie jako dostępne na koncie XTB.
# Zostaw pustą listę, żeby na starcie nie filtrować niczego — a docelowo
# uzupełniaj w miarę weryfikacji w platformie.
VERIFIED_TICKERS: set[str] = set()

STOCK_GROUPS = {
    "Polska (WIG20+mWIG40)": {**WIG20_MAP, **MWIG40_MAP},
    "Niemcy (DAX)": DAX_MAP,
    "Francja (CAC 40)": CAC40_MAP,
    "UK (FTSE 100)": FTSE_MAP,
    "Hiszpania (IBEX 35)": IBEX_MAP,
    "Szwecja (OMX 30)": OMX_MAP,
    "Norwegia (OBX)": OBX_MAP,
    # S&P 500 jest budowany dynamicznie w core/scanner.py (get_sp500_map),
    # bo lista >500 tickerów zmienia się w czasie.
}
