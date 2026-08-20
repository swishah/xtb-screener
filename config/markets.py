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
MWIG40_MAP = {"11B.WA": "11 bit studios", "1AT.WA": "Atal", "ABS.WA": "Asseco BS", "APR.WA": "Auto Partner", "ASB.WA": "ASBIS", "BFT.WA": "Benefit Systems", "CAR.WA": "Inter Cars", "CIG.WA": "CI Games", "CLN.WA": "Celon Pharma", "COG.WA": "Cognor", "DAT.WA": "DataWalk", "DIA.WA": "Diagnostyka", "DOM.WA": "Dom Development", "EAT.WA": "AmRest", "ENP.WA": "Enea", "EUR.WA": "Eurocash", "GPP.WA": "Grupa Pracuj", "GRN.WA": "Grenevia", "GTC.WA": "GTC", "HUU.WA": "Huuuge", "ING.WA": "ING BSK", "TXT.WA": "Text S.A.", "MIL.WA": "Millennium", "MBR.WA": "Mo-BRUK", "NEU.WA": "Neuca", "PLW.WA": "PlayWay", "RVU.WA": "Revuele", "SEL.WA": "Selena FM", "STP.WA": "Stalproduct", "TEN.WA": "Ten Square Games", "TPE.WA": "Tauron", "VRG.WA": "VRG", "WPL.WA": "Wirtualna Polska", "XTB.WA": "XTB", "GPW.WA": "GPW", "SNK.WA": "Sanok", "AST.WA": "Asseco POL", "ATC.WA": "Arctic Paper"}
DAX_MAP = {"ADS.DE": "Adidas", "AIR.DE": "Airbus", "ALV.DE": "Allianz", "BAS.DE": "BASF", "BAYN.DE": "Bayer", "BEI.DE": "Beiersdorf", "BMW.DE": "BMW", "BNR.DE": "Brenntag", "CBK.DE": "Commerzbank", "CON.DE": "Continental", "1COV.DE": "Covestro", "DTG.DE": "Daimler Truck", "DBK.DE": "Deutsche Bank", "DB1.DE": "Deutsche Börse", "DPW.DE": "DHL Group", "DTE.DE": "Deutsche Telekom", "EOAN.DE": "E.ON", "FRE.DE": "Fresenius", "HNR1.DE": "Hannover Re", "HEI.DE": "Heidelberg Materials", "HEN3.DE": "Henkel", "IFX.DE": "Infineon", "MBG.DE": "Mercedes-Benz", "MRK.DE": "Merck", "MTX.DE": "MTU Aero Engines", "MUV2.DE": "Munich Re", "P911.DE": "Porsche AG", "PAH3.DE": "Porsche SE", "QIA.DE": "Qiagen", "RHM.DE": "Rheinmetall", "RWE.DE": "RWE", "SAP.DE": "SAP", "SRT3.DE": "Sartorius", "SIE.DE": "Siemens", "ENR.DE": "Siemens Energy", "SHL.DE": "Siemens Healthineers", "SY1.DE": "Symrise", "VOW3.DE": "Volkswagen", "VNA.DE": "Vonovia", "ZAL.DE": "Zalando"}
CAC40_MAP = {"AC.PA": "Accor", "AI.PA": "Air Liquide", "AIR.PA": "Airbus", "MT.AS": "ArcelorMittal", "CS.PA": "AXA", "BNP.PA": "BNP Paribas", "EN.PA": "Bouygues", "CAP.PA": "Capgemini", "CA.PA": "Carrefour", "ACA.PA": "Crédit Agricole", "BN.PA": "Danone", "DSY.PA": "Dassault Systèmes", "EDEN.PA": "Edenred", "ENGI.PA": "Engie", "EL.PA": "EssilorLuxottica", "ERF.PA": "Eurofins Scientific", "RMS.PA": "Hermès", "KER.PA": "Kering", "LR.PA": "Legrand", "OR.PA": "L'Oréal", "MC.PA": "LVMH", "ML.PA": "Michelin", "ORP.PA": "Orange", "PRV.PA": "Pernod Ricard", "PUB.PA": "Publicis Groupe", "RNO.PA": "Renault", "SAF.PA": "Safran", "SGO.PA": "Saint-Gobain", "SAN.PA": "Sanofi", "SU.PA": "Schneider Electric", "GLE.PA": "Société Générale", "STLAP.PA": "Stellantis", "STMPA.PA": "STMicroelectronics", "TEP.PA": "Teleperformance", "HO.PA": "Thales", "TTE.PA": "TotalEnergies", "URW.AS": "Unibail-Rodamco-Westfield", "VIE.PA": "Veolia", "DG.PA": "Vinci", "VIV.PA": "Vivendi"}
FTSE_MAP = {"SHEL.L": "Shell", "AZN.L": "AstraZeneca", "HSBA.L": "HSBC", "ULVR.L": "Unilever", "BP.L": "BP", "GSK.L": "GSK", "DGE.L": "Diageo", "REL.L": "RELX", "BATS.L": "British American Tobacco", "GLEN.L": "Glencore", "RIO.L": "Rio Tinto", "BA.L": "BAE Systems", "CPG.L": "Compass Group", "LSEG.L": "LSEG", "NWG.L": "NatWest Group", "BARC.L": "Barclays", "STAN.L": "Standard Chartered", "NG.L": "National Grid", "AHT.L": "Ashtead", "TSCO.L": "Tesco", "LLOY.L": "Lloyds", "PRU.L": "Prudential", "AV.L": "Aviva", "SSE.L": "SSE", "LGEN.L": "Legal & General", "RTO.L": "Rentokil", "NXT.L": "Next", "WPP.L": "WPP", "VOD.L": "Vodafone", "RR.L": "Rolls-Royce", "EZJ.L": "easyJet", "IAG.L": "IAG"}
IBEX_MAP = {"ANA.MC": "Acciona", "ACX.MC": "Acerinox", "ACS.MC": "ACS", "AENA.MC": "Aena", "AMS.MC": "Amadeus", "BKT.MC": "Bankinter", "BBVA.MC": "BBVA", "CABK.MC": "CaixaBank", "CLNX.MC": "Cellnex", "ENG.MC": "Enagás", "ELE.MC": "Endesa", "FER.MC": "Ferrovial", "FDR.MC": "Fluidra", "GRF.MC": "Grifols", "IAG.MC": "IAG", "IBE.MC": "Iberdrola", "ITX.MC": "Inditex", "IDR.MC": "Indra", "COL.MC": "Inmobiliaria Colonial", "LOG.MC": "Logista", "MAP.MC": "Mapfre", "MEL.MC": "Meliá Hotels", "MRL.MC": "Merlin Properties", "NTGY.MC": "Naturgy", "RED.MC": "Redeia", "REP.MC": "Repsol", "ROVI.MC": "Rovi", "SAB.MC": "Sabadell", "SAN.MC": "Banco Santander", "SCYR.MC": "Sacyr", "TEF.MC": "Telefónica", "UNI.MC": "Unicaja"}
OMX_MAP = {"ABB.ST": "ABB", "ALFA.ST": "Alfa Laval", "ASSA-B.ST": "ASSA ABLOY", "ATCO-A.ST": "Atlas Copco A", "ATCO-B.ST": "Atlas Copco B", "AZN.ST": "AstraZeneca", "BOL.ST": "Boliden", "ELUX-B.ST": "Electrolux", "ERIC-B.ST": "Ericsson", "ESSITY-B.ST": "Essity", "EVO.ST": "Evolution", "GETI-B.ST": "Getinge", "HEXA-B.ST": "Hexagon", "HM-B.ST": "H&M", "INVE-B.ST": "Investor B", "KINV-B.ST": "Kinnevik", "NDA-SE.ST": "Nordea", "SAND.ST": "Sandvik", "SCA-B.ST": "SCA", "SEB-A.ST": "SEB", "SHB-A.ST": "Handelsbanken", "SKA-B.ST": "Skanska", "SKF-B.ST": "SKF", "STE-R.ST": "Stora Enso", "SWED-A.ST": "Swedbank", "SWMA.ST": "Swedish Match", "TEL2-B.ST": "Tele2", "TELIA.ST": "Telia", "VOLV-B.ST": "Volvo B"}
OBX_MAP = {"EQNR.OL": "Equinor", "DNB.OL": "DNB Bank", "AKBP.OL": "Aker BP", "TEL.OL": "Telenor", "NHY.OL": "Norsk Hydro", "MOWI.OL": "Mowi", "YAR.OL": "Yara International", "ORK.OL": "Orkla", "SUBC.OL": "Subsea 7", "TOM.OL": "Tomra Systems", "STB.OL": "Storebrand", "SALM.OL": "SalMar", "GJFS.OL": "Gjensidige", "AKER.OL": "Aker", "SCHA.OL": "Schibsted A", "FRO.OL": "Frontline", "TGS.OL": "TGS", "BAKKA.OL": "Bakkafrost", "LSG.OL": "Lerøy Seafood", "KOG.OL": "Kongsberg Gruppen", "NOD.OL": "Nordic Semiconductor", "NEL.OL": "Nel", "VAR.OL": "Vår Energi", "MPCC.OL": "MPC Container Ships"}

# ---------------------------------------------------------------------------
# ETF-y — rozszerzona lista UCITS ETF-ów notowanych na giełdach europejskich.
# Im bardziej niszowa kategoria (tematyczne, sektorowe, obligacyjne), tym
# WIĘKSZA szansa, że dokładny ticker/sufiks Yahoo Finance się nie zgadza —
# silnik po prostu pominie taki wpis i zaloguje go jako pominięty, więc nic
# się nie wysypie, ale po pierwszym skanie warto zerknąć w log i wyczyścić
# nietrafione pozycje. Zweryfikuj też dostępność każdego w samej XTB.
# ---------------------------------------------------------------------------
ETF_MAP = {
    # --- Szeroki rynek: świat / USA / Europa / EM (najwyższa pewność tickerów) ---
    "CSPX.L": "iShares Core S&P 500 UCITS ETF (Acc)",
    "SXR8.DE": "iShares Core S&P 500 UCITS ETF (DE, Acc)",
    "VUAA.L": "Vanguard S&P 500 UCITS ETF (Acc)",
    "VUSA.L": "Vanguard S&P 500 UCITS ETF (Dist)",
    "SPY5.L": "SPDR S&P 500 UCITS ETF",
    "IUSA.AS": "iShares Core S&P 500 UCITS ETF (EUR)",
    "IWDA.AS": "iShares Core MSCI World UCITS ETF (Acc)",
    "EUNL.DE": "iShares Core MSCI World UCITS ETF (DE, Acc)",
    "SWDA.L": "iShares Core MSCI World UCITS ETF (L)",
    "VWCE.DE": "Vanguard FTSE All-World UCITS ETF (Acc)",
    "VWRL.L": "Vanguard FTSE All-World UCITS ETF (Dist)",
    "XDWD.DE": "Xtrackers MSCI World UCITS ETF (Acc)",
    "LCWD.L": "Lyxor Core MSCI World UCITS ETF",
    "SPPW.DE": "SPDR MSCI World UCITS ETF",
    "SSAC.L": "iShares MSCI ACWI UCITS ETF (Acc)",
    "VFEM.L": "Vanguard FTSE Emerging Markets UCITS ETF",
    "EIMI.L": "iShares Core MSCI EM IMI UCITS ETF (Acc)",
    "IEEM.L": "iShares MSCI EM UCITS ETF",
    "XMME.DE": "Xtrackers MSCI Emerging Markets Swap UCITS ETF",
    "IUSN.DE": "iShares MSCI World Small Cap UCITS ETF",
    "WSML.L": "iShares MSCI World Small Cap UCITS ETF (L)",
    "VJPN.L": "Vanguard FTSE Japan UCITS ETF",
    "IJPN.L": "iShares Core MSCI Japan IMI UCITS ETF",
    "VEUR.L": "Vanguard FTSE Developed Europe UCITS ETF",
    "EXSA.DE": "iShares STOXX Europe 600 UCITS ETF",
    "ISF.L": "iShares Core FTSE 100 UCITS ETF",
    "DAXEX.DE": "iShares Core DAX UCITS ETF",
    "CAC.PA": "Amundi CAC 40 UCITS ETF",

    # --- USA: styl, waga równa, Nasdaq ---
    "XDEW.DE": "Xtrackers S&P 500 Equal Weight UCITS ETF",
    "EWSX.DE": "iShares S&P 500 Equal Weight UCITS ETF",
    "XDNA.DE": "Xtrackers Nasdaq 100 UCITS ETF",
    "EQQQ.L": "Invesco EQQQ Nasdaq-100 UCITS ETF",
    "CNDX.L": "iShares Nasdaq 100 UCITS ETF",
    "CSNDX.SW": "iShares Nasdaq 100 UCITS ETF (SW)",

    # --- Sektory S&P 500 (iShares) ---
    "QDVE.DE": "iShares S&P 500 Information Technology Sector UCITS ETF",
    "IUIT.L": "iShares S&P 500 Information Technology Sector UCITS ETF (L)",
    "IUHC.L": "iShares S&P 500 Health Care Sector UCITS ETF",
    "IUFS.L": "iShares S&P 500 Financials Sector UCITS ETF",
    "IUCM.L": "iShares S&P 500 Consumer Discretionary Sector UCITS ETF",
    "IUES.L": "iShares S&P 500 Energy Sector UCITS ETF",
    "IUUS.L": "iShares S&P 500 Utilities Sector UCITS ETF",

    # --- Sektory MSCI World (Xtrackers) — niższa pewność dokładnego sufiksu ---
    "XDWT.DE": "Xtrackers MSCI World Information Technology UCITS ETF",
    "XDWH.DE": "Xtrackers MSCI World Health Care UCITS ETF",
    "XDWF.DE": "Xtrackers MSCI World Financials UCITS ETF",
    "XDWC.DE": "Xtrackers MSCI World Consumer Discretionary UCITS ETF",
    "XDWS.DE": "Xtrackers MSCI World Consumer Staples UCITS ETF",
    "XDWU.DE": "Xtrackers MSCI World Utilities UCITS ETF",
    "XDWY.DE": "Xtrackers MSCI World Energy UCITS ETF",
    "XDWM.DE": "Xtrackers MSCI World Materials UCITS ETF",
    "XDWI.DE": "Xtrackers MSCI World Industrials UCITS ETF",

    # --- Tematyczne / technologiczne (niższa pewność, sprawdź po skanie) ---
    "SEMI.L": "iShares MSCI Global Semiconductors UCITS ETF",
    "XAIX.DE": "Xtrackers Artificial Intelligence & Big Data UCITS ETF",
    "RBOT.L": "iShares Automation & Robotics UCITS ETF",
    "ECAR.L": "iShares Electric Vehicles and Driving Technology UCITS ETF",
    "WCBR.L": "iShares Digital Security UCITS ETF",
    "BKCH.L": "iShares Blockchain Technology UCITS ETF",

    # --- Czysta energia / ESG ---
    "INRG.L": "iShares Global Clean Energy UCITS ETF",

    # --- Dywidendy / value ---
    "VHYL.L": "Vanguard FTSE All-World High Dividend Yield UCITS ETF",
    "TDIV.AS": "VanEck Morningstar Developed Markets Dividend Leaders ETF",
    "ZPRV.DE": "SPDR MSCI USA Small Cap Value Weighted UCITS ETF",

    # --- Nieruchomości (REIT) ---
    "IWDP.L": "iShares Developed Markets Property Yield UCITS ETF",
    "IPRP.L": "iShares European Property Yield UCITS ETF",

    # --- Metale szlachetne / surowce ---
    "IGLN.L": "iShares Physical Gold ETC",
    "SGLN.L": "Invesco Physical Gold ETC",
    "PHAU.L": "WisdomTree Physical Gold",
    "SSLN.L": "iShares Physical Silver ETC",
    "ICOM.L": "iShares Diversified Commodity Swap UCITS ETF",

    # --- Obligacje ---
    "IEAG.L": "iShares Core Euro Aggregate Bond UCITS ETF",
    "VAGF.L": "Vanguard Global Aggregate Bond UCITS ETF (EUR Hedged, Acc)",
}

# sWIG80 — pełny, aktualny skład (sierpień 2026).
SWIG80_MAP_RAW = {
    "11B.WA": "11 bit studios", "1AT.WA": "Atal", "ABS.WA": "Asseco Business Solutions", "AGO.WA": "Agora",
    "AMB.WA": "Ambra", "AMC.WA": "Amica", "ANR.WA": "Answear.com", "APT.WA": "Apator", "ARH.WA": "Archicom",
    "ARL.WA": "Arlen", "AST.WA": "Astarta Holding", "ATC.WA": "Arctic Paper", "ATR.WA": "Atrem",
    "BCX.WA": "Bioceltix", "BIO.WA": "Bioton", "BLO.WA": "Bloober Team", "BMC.WA": "Bumech",
    "BOS.WA": "Bank Ochrony Środowiska", "BRS.WA": "Boryszew", "CIG.WA": "CI Games", "CLN.WA": "Celon Pharma",
    "CMP.WA": "Comp", "COG.WA": "Cognor", "CRJ.WA": "Creepy Jar", "CRQ.WA": "Creotech Quantum",
    "CTX.WA": "Captor Therapeutics", "DAD.WA": "Dadelo", "DAT.WA": "DataWalk", "DCR.WA": "Decora",
    "DIG.WA": "Digital Network", "ECH.WA": "Echo Investment", "ELT.WA": "Elektrotim", "ENT.WA": "Enter Air",
    "ERB.WA": "Erbud", "EUR.WA": "Eurocash", "FRO.WA": "Ferro", "FTE.WA": "Fabryki Mebli Forte",
    "GRX.WA": "GreenX Metals", "HUG.WA": "Huuuge", "ICE.WA": "Medinice", "IMC.WA": "Industrial Milk Company",
    "KGN.WA": "Kogeneracja", "LWB.WA": "Bogdanka", "MCI.WA": "MCI Capital", "MDG.WA": "Medicalgorithmics",
    "MLG.WA": "MLP Group", "MNC.WA": "Mennica Polska", "MRC.WA": "Mercator Medical", "MSZ.WA": "Mostostal Zabrze",
    "OND.WA": "Onde", "OPN.WA": "Oponeo.pl", "PCR.WA": "PCC Rokita", "PLW.WA": "PlayWay",
    "QRS.WA": "Quercus TFI", "REX.WA": "Rex Concepts", "ROB.WA": "Robyg", "RVU.WA": "Ryvu Therapeutics",
    "SCP.WA": "Scope Fluidics", "SCW.WA": "Scanway", "SEL.WA": "Selena FM", "SGN.WA": "Sygnity",
    "SKA.WA": "Śnieżka", "SLV.WA": "Selvita", "SNK.WA": "Sanok Rubber", "STP.WA": "Stalprodukt",
    "STX.WA": "Stalexport Autostrady", "SVE.WA": "Synthaverse", "TAR.WA": "Tarczyński", "TOA.WA": "Toya",
    "TOR.WA": "Torpol", "UNI.WA": "Unibep", "UNT.WA": "Unimot", "VGO.WA": "Vigo Photonics",
    "VOT.WA": "Votum", "VRG.WA": "VRG (Vistula)", "WLT.WA": "Wielton", "WTN.WA": "Wittchen",
    "WWL.WA": "Wawel", "ZEP.WA": "ZE PAK", "ZRE.WA": "Zremb-Chojnice",
}
# sWIG80 rebalansuje się kwartalnie i część spółek bywa jednocześnie "na liście
# rezerwowej" w WIG20/mWIG40 z powodu ręcznie utrzymywanych map wyżej — usuwamy
# duplikaty, żeby nie skanować tej samej spółki dwa razy.
SWIG80_MAP = {t: n for t, n in SWIG80_MAP_RAW.items() if t not in WIG20_MAP and t not in MWIG40_MAP}

# FTSE MIB (Włochy, Borsa Italiana) — stan na sierpień 2026. Kilka spółek jest
# formalnie zarejestrowanych w Holandii, ale notowanych głównie w Mediolanie
# (Stellantis, Ferrari, Campari, STMicroelectronics, Iveco Group) — ich sufiks
# Yahoo Finance bywa niejednoznaczny, warto zweryfikować przy pierwszym skanie.
FTSEMIB_MAP = {
    "A2A.MI": "A2A", "AMP.MI": "Amplifon", "AVIO.MI": "Avio", "AZM.MI": "Azimut",
    "BMED.MI": "Banca Mediolanum", "BMPS.MI": "Banca Monte dei Paschi di Siena", "BAMI.MI": "Banco BPM",
    "BPE.MI": "BPER Banca", "BC.MI": "Brunello Cucinelli", "BZU.MI": "Buzzi",
    "CPR.MI": "Campari (Davide Campari-Milano)", "DIA.MI": "DiaSorin", "ENEL.MI": "Enel", "ENI.MI": "Eni",
    "RACE.MI": "Ferrari", "FCT.MI": "Fincantieri", "FBK.MI": "FinecoBank", "G.MI": "Generali",
    "HER.MI": "Hera", "ISP.MI": "Intesa Sanpaolo", "IP.MI": "Interpump Group", "INW.MI": "Inwit",
    "IG.MI": "Italgas", "IVG.MI": "Iveco Group", "LDO.MI": "Leonardo", "LTMC.MI": "Lottomatica Group",
    "MB.MI": "Mediobanca", "MONC.MI": "Moncler", "NEXI.MI": "Nexi", "PST.MI": "Poste Italiane",
    "PRY.MI": "Prysmian", "REC.MI": "Recordati", "SPM.MI": "Saipem", "SRG.MI": "Snam",
    "STLAM.MI": "Stellantis", "STM.MI": "STMicroelectronics", "TIT.MI": "Telecom Italia", "TEN.MI": "Tenaris",
    "TRN.MI": "Terna", "UCG.MI": "UniCredit", "UNI.MI": "Unipol",
}

# ATX (Austria, Wiener Börse) — ok. 20 głównych spółek, stan orientacyjny
# sierpień 2026, zweryfikuj przy pierwszym skanie (kilka tickerów może się
# różnić w zależności od klasy akcji).
ATX_MAP = {
    "EBS.VI": "Erste Group Bank", "OMV.VI": "OMV", "VER.VI": "Verbund", "VOE.VI": "voestalpine",
    "RBI.VI": "Raiffeisen Bank International", "WIE.VI": "Wienerberger", "ANDR.VI": "Andritz",
    "EVN.VI": "EVN", "VIG.VI": "Vienna Insurance Group", "UQA.VI": "Uniqa Insurance",
    "TKA.VI": "Telekom Austria", "MMK.VI": "Mayr-Melnhof Karton", "IIA.VI": "Immofinanz",
    "CAI.VI": "CA Immobilien Anlagen", "ATS.VI": "AT&S", "SBO.VI": "Schoeller-Bleckmann Oilfield Equipment",
    "LNZ.VI": "Lenzing", "POST.VI": "Österreichische Post", "FLU.VI": "Flughafen Wien", "POS.VI": "PORR",
}

# PSI (Portugalia, Euronext Lisbon) — ok. 16 głównych spółek, stan orientacyjny
# sierpień 2026, zweryfikuj przy pierwszym skanie.
PSI_MAP = {
    "EDP.LS": "EDP - Energias de Portugal", "EDPR.LS": "EDP Renováveis", "GALP.LS": "Galp Energia",
    "JMT.LS": "Jerónimo Martins", "NOS.LS": "NOS", "RENE.LS": "REN - Redes Energéticas Nacionais",
    "SON.LS": "Sonae", "CTT.LS": "CTT - Correios de Portugal", "EGL.LS": "Mota-Engil",
    "SEM.LS": "Semapa", "NVG.LS": "Navigator Company", "COR.LS": "Corticeira Amorim",
    "BCP.LS": "Banco Comercial Português (Millennium bcp)", "IPR.LS": "Impresa", "ALTR.LS": "Altri",
    "IBS.LS": "Ibersol",
}

# Pojedyncze, ważne spółki UK spoza FTSE 100 (np. FTSE 250) — dopisywane
# ręcznie na żądanie, żeby nie mieszać ich z czystą listą "FTSE 100".
UK_EXTRA_MAP = {
    "WIZZ.L": "Wizz Air Holdings",
}

# Tickery ręcznie potwierdzone przez Ciebie jako dostępne na koncie XTB.
# Zostaw pustą listę, żeby na starcie nie filtrować niczego — a docelowo
# uzupełniaj w miarę weryfikacji w platformie.
VERIFIED_TICKERS: set[str] = set()

STOCK_GROUPS = {
    "Polska (WIG20+mWIG40)": {**WIG20_MAP, **MWIG40_MAP},
    "Polska (sWIG80)": SWIG80_MAP,
    "Niemcy (DAX)": DAX_MAP,
    "Francja (CAC 40)": CAC40_MAP,
    "UK (FTSE 100)": FTSE_MAP,
    "UK (dodatkowe spoza FTSE 100)": UK_EXTRA_MAP,
    "Hiszpania (IBEX 35)": IBEX_MAP,
    "Szwecja (OMX 30)": OMX_MAP,
    "Norwegia (OBX)": OBX_MAP,
    "Włochy (FTSE MIB)": FTSEMIB_MAP,
    "Austria (ATX)": ATX_MAP,
    "Portugalia (PSI)": PSI_MAP,
    # S&P 500 i S&P 400 (MidCap) są pobierane dynamicznie w core/scanner.py
    # (get_sp500_map / get_sp400_map), bo ich składy zmieniają się w czasie.
}
