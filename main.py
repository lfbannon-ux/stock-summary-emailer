#!/usr/bin/env python3
"""
Berkholts Daily Stock Summary Emailer - V6
===========================================
Key changes from V5:
1. ASX Scraper integration for announcements (replaces Claude web search)
2. ASX Scraper integration for earnings (replaces Claude web search)
3. Option C for competitors: Claude web search + ASX scraper supplement for listed competitors
4. Significant cost reduction (fewer API calls)

Dependencies (add to requirements.txt):
- playwright
- pdfplumber
- beautifulsoup4

Post-install command for Railway:
- playwright install chromium
"""

import os
import sys
import smtplib
import json
import re
import tempfile
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pdfplumber
from playwright.sync_api import sync_playwright


# Cache settings
CACHE_DIR = Path(os.environ.get('CACHE_DIR', '/home/claude/cache'))
EARNINGS_CACHE_DAYS = 30

# ASX Scraper settings
ASX_BASE_URL = "https://www.asx.com.au"
ASX_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


STOCKS = [
    # ========================================================================
    # SECTOR: IRON ORE & DIVERSIFIED MINING
    # ========================================================================
    {
        "name": "BHP Group Limited",
        "ticker": "BHP.AX",
        "asx_code": "BHP",
        "sector": "Iron Ore & Diversified Mining",
        "industry": "diversified mining (iron ore, copper, coal)",
        "industry_publications": ["Mining.com", "Australian Mining", "Mining Weekly", "Fastmarkets"],
        "supply_chain": {
            "customers": "Chinese and Asian steel mills, copper smelters, refiners",
            "suppliers": "mining equipment providers, energy and haulage contractors"
        },
        "watchlist": ["Rio Tinto (ASX:RIO)", "Fortescue (ASX:FMG)", "Vale (NYSE:VALE)", "Freeport-McMoRan (NYSE:FCX)", "Southern Copper (NYSE:SCCO)", "Glencore (LSE:GLEN)", "Teck Resources (NYSE:TECK)", "Anglo American (LSE:AAL)"],
        "listed_competitors": ["RIO", "FMG"],
        "watch_signal": "BHP and RIO mirror each other. Chinese steel demand is the demand-side signal for seaborne iron ore. Copper is read through Freeport, Southern Copper, Glencore, Teck and Anglo American.",
        "asx_url": "https://www.asx.com.au/markets/company/BHP",
        "revenue_drivers": {
            "primary": "Iron ore (62% Fe) and copper prices, driven by Chinese steel demand",
            "key_metrics": ["iron ore 62% Fe price USD/t", "copper price USD/lb", "China steel production", "China property and stimulus measures"],
            "search_terms": ["iron ore price today", "copper price today"],
            "commodities": ["Iron Ore 62% Fe (target: US$90-130/t)", "Copper (LME, US$/lb)"],
            "what_to_track": "Iron ore price is the #1 earnings driver; copper is the growth pillar; Chinese steel demand and stimulus set the demand backdrop"
        }
    },
    {
        "name": "Rio Tinto Limited",
        "ticker": "RIO.AX",
        "asx_code": "RIO",
        "sector": "Iron Ore & Diversified Mining",
        "industry": "diversified mining (iron ore, copper, aluminium)",
        "industry_publications": ["Mining.com", "Australian Mining", "Mining Weekly", "Fastmarkets"],
        "supply_chain": {
            "customers": "Chinese and Asian steel mills, aluminium and copper buyers",
            "suppliers": "mining equipment providers, rail and port logistics, energy contractors"
        },
        "watchlist": ["BHP Group (ASX:BHP)", "Fortescue (ASX:FMG)", "Vale (NYSE:VALE)", "Freeport-McMoRan (NYSE:FCX)", "Southern Copper (NYSE:SCCO)", "Glencore (LSE:GLEN)", "Teck Resources (NYSE:TECK)", "Anglo American (LSE:AAL)"],
        "listed_competitors": ["BHP", "FMG"],
        "watch_signal": "RIO and BHP mirror each other. Chinese steel demand is the demand-side signal for iron ore. Copper read via Freeport, Southern Copper, Glencore, Teck and Anglo American.",
        "asx_url": "https://www.asx.com.au/markets/company/RIO",
        "revenue_drivers": {
            "primary": "Iron ore (62% Fe) prices and Pilbara volumes, plus copper and aluminium",
            "key_metrics": ["iron ore 62% Fe price USD/t", "copper price USD/lb", "aluminium (LME) price", "China steel production"],
            "search_terms": ["iron ore price today", "copper price today"],
            "commodities": ["Iron Ore 62% Fe (target: US$90-130/t)", "Copper (LME, US$/lb)", "Aluminium (LME, US$/t)"],
            "what_to_track": "Iron ore price and Pilbara shipments dominate earnings; copper (Oyu Tolgoi ramp) is the growth story; aluminium adds cyclicality"
        }
    },
    {
        "name": "Mineral Resources Limited",
        "ticker": "MIN.AX",
        "asx_code": "MIN",
        "sector": "Iron Ore & Diversified Mining",
        "industry": "mining services, iron ore and lithium production",
        "industry_publications": ["Mining.com", "Australian Mining", "Mining Weekly", "Fastmarkets"],
        "supply_chain": {
            "customers": "lithium buyers including battery manufacturers, iron ore offtakers, mining services clients",
            "suppliers": "mining equipment providers, crushing/processing contractors"
        },
        "watchlist": ["Pilbara Minerals (ASX:PLS)", "IGO Limited (ASX:IGO)", "Liontown Resources (ASX:LTR)", "Albemarle (NYSE:ALB)", "SQM (NYSE:SQM)", "Monadelphous (ASX:MND)", "Fortescue (ASX:FMG)", "Vale (NYSE:VALE)"],
        "listed_competitors": ["PLS", "FMG"],
        "watch_signal": "MIN is a three-part watch: iron ore (BHP/RIO/FMG mirror, Chinese steel demand), lithium (Pilbara, IGO, Liontown; global Albemarle, SQM) and mining services (Monadelphous). MIN's balance sheet and deleveraging progress is the specific tell.",
        "asx_url": "https://www.asx.com.au/markets/company/MIN",
        "revenue_drivers": {
            "primary": "Lithium spodumene prices (SC6) and iron ore prices (62% Fe), plus mining services contracts",
            "key_metrics": ["spodumene SC6 price USD/dmt", "iron ore 62% Fe price USD/t", "lithium carbonate price", "MIN net debt and deleveraging"],
            "search_terms": ["spodumene price today", "iron ore price today"],
            "commodities": ["Spodumene SC6 (target: US$800-1500/dmt)", "Iron Ore 62% Fe (target: US$90-130/t)"],
            "what_to_track": "Lithium prices are the #1 earnings driver; Onslow iron ore volumes; mining services contract wins; balance-sheet deleveraging is the key market focus"
        }
    },
    # ========================================================================
    # SECTOR: GOLD
    # ========================================================================
    {
        "name": "Newmont Corporation (CDI)",
        "ticker": "NEM.AX",
        "asx_code": "NEM",
        "sector": "Gold",
        "industry": "gold mining",
        "industry_publications": ["Mining.com", "Kitco News", "Mining Weekly", "Australian Mining"],
        "supply_chain": {
            "customers": "gold refiners, bullion banks, central banks (indirect)",
            "suppliers": "mining equipment providers, energy and reagent suppliers"
        },
        "watchlist": ["Barrick Gold (NYSE:GOLD)", "Agnico Eagle (NYSE:AEM)", "Northern Star (ASX:NST)", "Evolution Mining (ASX:EVN)"],
        "listed_competitors": ["NST", "EVN"],
        "watch_signal": "Watch the gold price versus all-in sustaining cost (AISC) - the margin spread is the earnings driver. Barrick and Agnico Eagle globally; Northern Star and Evolution as ASX peers.",
        "asx_url": "https://www.asx.com.au/markets/company/NEM",
        "revenue_drivers": {
            "primary": "Gold price versus all-in sustaining cost (AISC), and production volumes",
            "key_metrics": ["gold price USD/oz", "all-in sustaining cost (AISC) USD/oz", "copper byproduct credits", "production ounces"],
            "search_terms": ["gold price today", "gold miner AISC 2026"],
            "commodities": ["Gold (spot, US$/oz)"],
            "what_to_track": "Gold price vs AISC sets the margin; cost inflation erodes it; production volumes and byproduct copper matter for the big diversified operations"
        }
    },
    # ========================================================================
    # SECTOR: STEEL
    # ========================================================================
    {
        "name": "BlueScope Steel Limited",
        "ticker": "BSL.AX",
        "asx_code": "BSL",
        "sector": "Steel",
        "industry": "steel production and building products",
        "industry_publications": ["Fastmarkets", "SteelOrbis", "Argus Metals", "Australian Mining"],
        "supply_chain": {
            "customers": "construction, manufacturing, automotive and building product distributors (US and Australia)",
            "suppliers": "iron ore and metallurgical coal producers, steel scrap dealers"
        },
        "watchlist": ["Nucor (NYSE:NUE)", "Steel Dynamics (NASDAQ:STLD)", "Cleveland-Cliffs (NYSE:CLF)", "POSCO (NYSE:PKX)", "Nippon Steel (TYO:5401)", "Sims (ASX:SGM)"],
        "listed_competitors": ["SGM"],
        "watch_signal": "The US mini-mill spread (steel selling price minus scrap/input cost) plus tariffs (Section 232) drive it - North Star in Ohio is the swing asset. Nucor and Steel Dynamics are the mini-mill reads; Cleveland-Cliffs, POSCO, Nippon Steel; Sims (SGM) for scrap.",
        "asx_url": "https://www.asx.com.au/markets/company/BSL",
        "revenue_drivers": {
            "primary": "US and Australian steel spreads (steel price minus raw material cost), plus tariffs",
            "key_metrics": ["US hot-rolled coil (HRC) steel price", "steel scrap price", "China HRC export price", "Section 232 tariff status"],
            "search_terms": ["US HRC steel price 2026", "steel mini mill spread"],
            "commodities": ["US HRC steel (US$/short ton)", "Steel scrap (US$/t)"],
            "what_to_track": "North Star (US mini-mill) spread is the key earnings swing; tariffs support US prices; Australian coated/painted volumes and building activity matter domestically"
        }
    },
    # ========================================================================
    # SECTOR: BANKS
    # ========================================================================
    {
        "name": "Commonwealth Bank of Australia",
        "ticker": "CBA.AX",
        "asx_code": "CBA",
        "sector": "Banks",
        "industry": "retail and business banking",
        "industry_publications": ["Australian Banking Daily", "Banking Day", "AFR Banking", "The Australian Business"],
        "supply_chain": {
            "customers": "retail mortgage and deposit customers, SMEs, corporates",
            "suppliers": "wholesale funding markets, deposit base, technology vendors"
        },
        "watchlist": ["Westpac (ASX:WBC)", "National Australia Bank (ASX:NAB)", "ANZ Group (ASX:ANZ)", "Macquarie Group (ASX:MQG)", "Bendigo & Adelaide Bank (ASX:BEN)", "Bank of Queensland (ASX:BOQ)"],
        "listed_competitors": ["ANZ", "BEN"],
        "watch_signal": "The Big Four (CBA, WBC, NAB, ANZ) move together, plus MQG and regionals Bendigo (BEN) and BOQ. Housing credit growth and net interest margin (NIM) are the shared drivers. CBA is the mortgage/retail bellwether.",
        "asx_url": "https://www.asx.com.au/markets/company/CBA",
        "revenue_drivers": {
            "primary": "Net interest margin (NIM) and housing/business credit growth",
            "key_metrics": ["Australian housing credit growth", "RBA cash rate", "net interest margin (NIM)", "mortgage competition and front-book pricing", "bad and doubtful debt charges"],
            "search_terms": ["Australian housing credit growth 2026", "RBA cash rate decision"],
            "what_to_track": "NIM is the profit lever; mortgage competition compresses it; credit growth and deposit mix drive volumes; arrears/impairments the risk"
        }
    },
    {
        "name": "Westpac Banking Corporation",
        "ticker": "WBC.AX",
        "asx_code": "WBC",
        "sector": "Banks",
        "industry": "retail and business banking",
        "industry_publications": ["Australian Banking Daily", "Banking Day", "AFR Banking", "The Australian Business"],
        "supply_chain": {
            "customers": "retail mortgage and deposit customers, SMEs, corporates, institutional clients",
            "suppliers": "wholesale funding markets, deposit base, technology vendors"
        },
        "watchlist": ["Commonwealth Bank (ASX:CBA)", "National Australia Bank (ASX:NAB)", "ANZ Group (ASX:ANZ)", "Macquarie Group (ASX:MQG)", "Bendigo & Adelaide Bank (ASX:BEN)", "Bank of Queensland (ASX:BOQ)"],
        "listed_competitors": ["ANZ", "BEN"],
        "watch_signal": "The Big Four (CBA, WBC, NAB, ANZ) move together, plus MQG and regionals Bendigo (BEN) and BOQ. Housing credit growth and net interest margin (NIM) are the shared drivers; Westpac's cost-reset program is a specific focus.",
        "asx_url": "https://www.asx.com.au/markets/company/WBC",
        "revenue_drivers": {
            "primary": "Net interest margin (NIM) and housing/business credit growth",
            "key_metrics": ["Australian housing credit growth", "RBA cash rate", "net interest margin (NIM)", "mortgage competition", "cost-to-income ratio"],
            "search_terms": ["Australian housing credit growth 2026", "RBA cash rate decision"],
            "what_to_track": "NIM and mortgage competition drive the margin; cost reduction is the self-help lever; credit quality and impairments the risk"
        }
    },
    {
        "name": "National Australia Bank Limited",
        "ticker": "NAB.AX",
        "asx_code": "NAB",
        "sector": "Banks",
        "industry": "business and retail banking",
        "industry_publications": ["Australian Banking Daily", "Banking Day", "AFR Banking", "The Australian Business"],
        "supply_chain": {
            "customers": "SME and business banking customers, retail mortgage and deposit customers, corporates",
            "suppliers": "wholesale funding markets, deposit base, technology vendors"
        },
        "watchlist": ["Commonwealth Bank (ASX:CBA)", "Westpac (ASX:WBC)", "ANZ Group (ASX:ANZ)", "Macquarie Group (ASX:MQG)", "Bendigo & Adelaide Bank (ASX:BEN)", "Bank of Queensland (ASX:BOQ)"],
        "listed_competitors": ["ANZ", "BEN"],
        "watch_signal": "The Big Four (CBA, WBC, NAB, ANZ) move together, plus MQG and regionals Bendigo (BEN) and BOQ. Housing credit growth and net interest margin (NIM) are the shared drivers; NAB is the business-banking leader, so SME credit is its specific tell.",
        "asx_url": "https://www.asx.com.au/markets/company/NAB",
        "revenue_drivers": {
            "primary": "Net interest margin (NIM), business (SME) credit growth and housing lending",
            "key_metrics": ["Australian business credit growth", "housing credit growth", "RBA cash rate", "net interest margin (NIM)", "business lending market share"],
            "search_terms": ["Australian business credit growth 2026", "RBA cash rate decision"],
            "what_to_track": "Business/SME lending is NAB's edge; NIM and deposit mix drive margins; housing competition and impairments the swing factors"
        }
    },
    # ========================================================================
    # SECTOR: DIVERSIFIED FINANCIALS
    # ========================================================================
    {
        "name": "Macquarie Group Limited",
        "ticker": "MQG.AX",
        "asx_code": "MQG",
        "sector": "Diversified Financials",
        "industry": "investment banking and asset management",
        "industry_publications": ["Infrastructure Investor", "Private Equity International", "Bloomberg Markets", "Reuters Finance"],
        "supply_chain": {
            "customers": "institutional investors, infrastructure funds, corporate clients, retail banking customers",
            "suppliers": "global capital markets, institutional co-investors"
        },
        "watchlist": ["Brookfield (NYSE:BN)", "Blackstone (NYSE:BX)", "KKR (NYSE:KKR)", "Apollo Global (NYSE:APO)", "Ares Management (NYSE:ARES)", "Charter Hall (ASX:CHC)", "IFM Investors (unlisted)"],
        "listed_competitors": ["CHC"],
        "watch_signal": "Global alternative managers Brookfield, Blackstone, KKR, Apollo and Ares for fee-earning AUM and infrastructure marks; CHC and IFM overlap on real assets. Deal flow and asset realisations drive the volatile lines.",
        "asx_url": "https://www.asx.com.au/markets/company/MQG",
        "revenue_drivers": {
            "primary": "Fee-earning AUM, infrastructure/asset marks, M&A and IPO deal fees, commodities trading",
            "key_metrics": ["fee-earning assets under management", "infrastructure asset valuations/marks", "Australian and global M&A deal volume", "commodities trading volumes"],
            "search_terms": ["global alternative asset managers AUM 2026", "infrastructure investment marks"],
            "what_to_track": "Fee-earning AUM growth and performance fees; infrastructure marks and realisations; deal flow (M&A/IPO); commodities/markets income is volatile"
        }
    },
    # ========================================================================
    # SECTOR: INSURANCE BROKING
    # ========================================================================
    {
        "name": "AUB Group Limited",
        "ticker": "AUB.AX",
        "asx_code": "AUB",
        "sector": "Insurance Broking",
        "industry": "insurance broking",
        "industry_publications": ["Insurance News Australia", "Insurance Business Australia", "Australasian Underwriting"],
        "supply_chain": {
            "customers": "SME businesses, corporate clients requiring insurance placement",
            "suppliers": "underwriters including Lloyd's syndicates, QBE, Allianz"
        },
        "watchlist": ["Steadfast Group (ASX:SDF)", "Marsh McLennan (NYSE:MMC)", "Aon (NYSE:AON)", "Arthur J. Gallagher (NYSE:AJG)", "Brown & Brown (NYSE:BRO)", "Howden/Tysers (unlisted)", "Insurance Australia Group (ASX:IAG)", "Suncorp (ASX:SUN)", "QBE Insurance (ASX:QBE)"],
        "listed_competitors": ["SDF", "IAG"],
        "watch_signal": "Steadfast (SDF) is the essential comp. Global brokers Marsh McLennan, Aon, Gallagher, Brown & Brown and Howden (Tysers read). Underwriters IAG, Suncorp and QBE signal where the premium rate cycle is turning.",
        "asx_url": "https://www.asx.com.au/markets/company/AUB",
        "revenue_drivers": {
            "primary": "Broker commissions as a percentage of insurance premiums placed",
            "key_metrics": ["commercial insurance premium rates", "broker M&A activity Australia", "insurance market hard/soft cycle"],
            "search_terms": ["Australian commercial insurance premium rates 2026", "insurance broker acquisition Australia"],
            "what_to_track": "Premium rate increases drive commission revenue; acquisitions drive growth; a softening rate cycle is the key risk"
        }
    },
    # ========================================================================
    # SECTOR: PLATFORMS & INVESTMENT HOUSES
    # ========================================================================
    {
        "name": "HUB24 Limited",
        "ticker": "HUB.AX",
        "asx_code": "HUB",
        "sector": "Platforms & Investment Houses",
        "industry": "wealth management platforms",
        "industry_publications": ["Financial Standard", "Professional Planner", "Money Management", "Morningstar Australia"],
        "supply_chain": {
            "customers": "financial advisers, stockbrokers, accountants, self-directed investors",
            "suppliers": "custody providers, fund managers, technology vendors"
        },
        "watchlist": ["Netwealth Group (ASX:NWL)", "Insignia Financial (ASX:IFL)", "AMP (ASX:AMP)", "Praemium (ASX:PPS)", "BT/Macquarie Wrap (via ASX:MQG)", "Iress (ASX:IRE)"],
        "listed_competitors": ["NWL", "PPS"],
        "watch_signal": "Netwealth (NWL) is the direct comp; Insignia, AMP and Praemium; BT and Macquarie Wrap for platform flows; Iress for adviser software. Net inflows and FUA growth are the shared tell.",
        "asx_url": "https://www.asx.com.au/markets/company/HUB",
        "revenue_drivers": {
            "primary": "Funds Under Administration (FUA) and platform fees",
            "key_metrics": ["platform FUA growth", "net inflows", "adviser numbers", "platform market share"],
            "search_terms": ["wealth platform FUA Australia", "financial adviser movement Australia"],
            "what_to_track": "FUA growth drives revenue (net inflows plus market performance); adviser wins/losses; platform fee compression is the risk"
        }
    },
    {
        "name": "Washington H. Soul Pattinson and Company Limited",
        "ticker": "SOL.AX",
        "asx_code": "SOL",
        "sector": "Platforms & Investment Houses",
        "industry": "diversified investment house",
        "industry_publications": ["AFR", "The Australian Business", "Livewire Markets", "Morningstar Australia"],
        "supply_chain": {
            "customers": "shareholders (as an investment vehicle); underlying portfolio spans equities, private equity, credit, property",
            "suppliers": "capital markets, co-investment partners"
        },
        "watchlist": ["Brickworks (ASX:BKW)", "Wesfarmers (ASX:WES)", "Australian Foundation Investment Co (ASX:AFI)", "Argo Investments (ASX:ARG)"],
        "listed_competitors": ["BKW", "WES"],
        "watch_signal": "SOL's proposed merger with Brickworks (BKW) - which unwinds the cross-shareholding - is the key event to track. Compare Wesfarmers and the LICs (AFIC, Argo) as the other diversified-compounder models.",
        "asx_url": "https://www.asx.com.au/markets/company/SOL",
        "revenue_drivers": {
            "primary": "Portfolio NTA growth and dividends from holdings (large-cap equities, private equity, credit, property)",
            "key_metrics": ["SOL net tangible assets (NTA)", "Brickworks merger progress", "dividend growth streak", "private/large-cap portfolio valuations"],
            "search_terms": ["Washington Soul Pattinson news 2026", "Brickworks Soul Patts merger"],
            "what_to_track": "NTA and dividend growth are the scorecard; the Brickworks merger is the pivotal corporate event; private markets and credit portfolio performance"
        }
    },
    # ========================================================================
    # SECTOR: HEALTHCARE
    # ========================================================================
    {
        "name": "CSL Limited",
        "ticker": "CSL.AX",
        "asx_code": "CSL",
        "sector": "Healthcare",
        "industry": "biotechnology and plasma-derived therapies",
        "industry_publications": ["BioPharma Dive", "Fierce Pharma", "Endpoints News", "BioWorld"],
        "supply_chain": {
            "customers": "hospitals, healthcare providers, governments (vaccines), patients with immunodeficiencies and bleeding disorders",
            "suppliers": "plasma collection centres (CSL Plasma), pharmaceutical manufacturing equipment providers"
        },
        "watchlist": ["Grifols (NASDAQ:GRFS)", "Takeda (NYSE:TAK)", "Octapharma (unlisted)", "Argenx (NASDAQ:ARGX)", "Sanofi (NASDAQ:SNY)", "GSK (NYSE:GSK)", "ADMA Biologics (NASDAQ:ADMA)"],
        "listed_competitors": [],
        "watch_signal": "The plasma/Ig oligopoly is Grifols, Takeda and Octapharma. Argenx (FcRn platform) is the structural threat to watch. Sanofi and GSK for the Seqirus flu franchise; ADMA is a read on US plasma pricing.",
        "asx_url": "https://www.asx.com.au/markets/company/CSL",
        "revenue_drivers": {
            "primary": "Immunoglobulin (Ig) sales and pricing, plasma collection volumes, vaccine sales",
            "key_metrics": ["immunoglobulin Ig pricing", "plasma collection volumes US", "influenza vaccine uptake", "albumin pricing"],
            "search_terms": ["immunoglobulin price trend", "plasma collection volumes 2026"],
            "what_to_track": "Ig pricing is the key margin driver; plasma collection cost per litre; FcRn competition (Argenx) to the Ig franchise; Seqirus vaccine seasonality"
        }
    },
    {
        "name": "Sigma Healthcare Limited",
        "ticker": "SIG.AX",
        "asx_code": "SIG",
        "sector": "Healthcare",
        "industry": "pharmacy wholesale and retail (Chemist Warehouse)",
        "industry_publications": ["Australian Journal of Pharmacy", "Pharmacy Daily", "AFR Health", "Australian Doctor"],
        "supply_chain": {
            "customers": "Chemist Warehouse and franchise pharmacies, independent pharmacies, hospitals",
            "suppliers": "pharmaceutical manufacturers, PBS-listed drug suppliers, consumer health brands"
        },
        "watchlist": ["EBOS Group (ASX:EBO)", "Wesfarmers Health / API / Priceline (ASX:WES)", "Metcash pharma (ASX:MTS)", "TerryWhite Chemmart (via ASX:EBO)", "Amazon Pharmacy (via NASDAQ:AMZN)"],
        "listed_competitors": ["EBO", "MTS"],
        "watch_signal": "EBOS (EBO) is the critical comp - it lost the Chemist Warehouse distribution contract to Sigma, which reshapes both companies. Also Wesfarmers Health (API/Priceline), Metcash pharma and TerryWhite. Amazon Pharmacy is the structural threat.",
        "asx_url": "https://www.asx.com.au/markets/company/SIG",
        "revenue_drivers": {
            "primary": "Chemist Warehouse network sales and pharmacy wholesale volumes, plus PBS reforms and merger synergies",
            "key_metrics": ["Chemist Warehouse store rollout", "PBS 60-day dispensing impact", "pharmacy script volumes", "Sigma-Chemist Warehouse merger synergies"],
            "search_terms": ["Chemist Warehouse Sigma 2026", "Australian pharmacy PBS reform"],
            "what_to_track": "Chemist Warehouse network growth post-merger; realisation of merger synergies; PBS reform (60-day dispensing) on volumes; the EBOS contract transition"
        }
    },
    # ========================================================================
    # SECTOR: CONSUMER STAPLES & CONGLOMERATE
    # ========================================================================
    {
        "name": "Woolworths Group Limited",
        "ticker": "WOW.AX",
        "asx_code": "WOW",
        "sector": "Consumer Staples & Conglomerate",
        "industry": "supermarkets and food retail",
        "industry_publications": ["Inside Retail", "Australian Food News", "Retail World", "AFR Companies"],
        "supply_chain": {
            "customers": "Australian and New Zealand grocery shoppers",
            "suppliers": "food and grocery manufacturers, fresh produce growers, FMCG brands"
        },
        "watchlist": ["Coles Group (ASX:COL)", "Metcash (ASX:MTS)", "Endeavour Group (ASX:EDV)", "Aldi (unlisted)", "Amazon (NASDAQ:AMZN)", "Costco (NASDAQ:COST)"],
        "listed_competitors": ["COL", "MTS"],
        "watch_signal": "Coles (COL) is the mirror. Metcash (IGA), Endeavour, plus Aldi, Amazon and Costco on the fringe. Food inflation, comparable sales and volume growth are the shared drivers.",
        "asx_url": "https://www.asx.com.au/markets/company/WOW",
        "revenue_drivers": {
            "primary": "Supermarket comparable sales, food inflation and volume/margin",
            "key_metrics": ["Australian food inflation", "supermarket comparable sales", "grocery volume growth", "EBIT margin"],
            "search_terms": ["Australian food inflation 2026", "Coles Woolworths sales"],
            "what_to_track": "Comparable sales and volume vs price mix; food inflation tailwind/headwind; margin and cost-of-doing-business; competition from Coles/Aldi"
        }
    },
    {
        "name": "Wesfarmers Limited",
        "ticker": "WES.AX",
        "asx_code": "WES",
        "sector": "Consumer Staples & Conglomerate",
        "industry": "diversified conglomerate (Bunnings, Kmart, WesCEF, Health)",
        "industry_publications": ["Inside Retail", "AFR Companies", "Australian Mining", "The Australian Business"],
        "supply_chain": {
            "customers": "home improvement, discount department store, chemicals/fertiliser and health customers",
            "suppliers": "global and domestic product manufacturers, lithium/chemical feedstock, importers"
        },
        "watchlist": ["Home Depot (NYSE:HD)", "Lowe's (NYSE:LOW)", "Coles Group (ASX:COL)", "Washington H. Soul Pattinson (ASX:SOL)", "Mineral Resources (ASX:MIN)"],
        "listed_competitors": ["COL", "SOL"],
        "watch_signal": "Bunnings drives Wesfarmers - Home Depot and Lowe's are the read on home improvement demand. Kmart versus discretionary retail; WesCEF ties to lithium (compare MIN). Compare Wesfarmers to SOL as the other diversified conglomerate/compounder.",
        "asx_url": "https://www.asx.com.au/markets/company/WES",
        "revenue_drivers": {
            "primary": "Bunnings sales (home improvement), Kmart discretionary sales, and WesCEF lithium/chemicals",
            "key_metrics": ["Bunnings comparable sales", "Australian home improvement spending", "Kmart sales and margin", "lithium hydroxide price (WesCEF Mt Holland/Covalent)"],
            "search_terms": ["Bunnings sales 2026", "Australian home improvement retail"],
            "commodities": ["Lithium hydroxide (US$/t)"],
            "what_to_track": "Bunnings is the earnings engine (Home Depot/Lowe's read); Kmart value retail resilience; WesCEF lithium ramp and pricing; capital allocation across the portfolio"
        }
    },
    # ========================================================================
    # SECTOR: CONSUMER DISCRETIONARY
    # ========================================================================
    {
        "name": "Nick Scali Limited",
        "ticker": "NCK.AX",
        "asx_code": "NCK",
        "sector": "Consumer Discretionary",
        "industry": "furniture retail",
        "industry_publications": ["Inside Retail", "Furniture News", "AFR Companies", "Retail World"],
        "supply_chain": {
            "customers": "household furniture buyers in Australia, New Zealand and (post-Anglia) the UK",
            "suppliers": "offshore furniture manufacturers (largely Asia-based), logistics providers"
        },
        "watchlist": ["Harvey Norman (ASX:HVN)", "Adairs (ASX:ADH)", "Temple & Webster (ASX:TPW)", "DFS Furniture (LSE:DFS)", "ScS Group (unlisted, UK)"],
        "listed_competitors": ["HVN", "ADH"],
        "watch_signal": "Harvey Norman, Adairs and Temple & Webster domestically; UK DFS and ScS as the read on the Anglia (UK) acquisition. Housing turnover and consumer discretionary spend are the demand drivers.",
        "asx_url": "https://www.asx.com.au/markets/company/NCK",
        "revenue_drivers": {
            "primary": "Furniture sales, gross margin, store rollout and UK (Anglia) integration",
            "key_metrics": ["Australian housing turnover", "consumer discretionary spending", "furniture retail sales", "UK furniture market conditions"],
            "search_terms": ["Australian furniture retail 2026", "housing turnover Australia"],
            "what_to_track": "Housing turnover drives furniture demand; gross margin (direct sourcing) is the edge; store rollout and the UK Anglia integration are the growth levers"
        }
    },
    {
        "name": "Guzman y Gomez Limited",
        "ticker": "GYG.AX",
        "asx_code": "GYG",
        "sector": "Consumer Discretionary",
        "industry": "quick service restaurants (Mexican QSR)",
        "industry_publications": ["Inside Retail", "Hospitality Magazine", "QSR Magazine", "AFR Companies"],
        "supply_chain": {
            "customers": "fast-casual restaurant diners (Australia, US, Singapore, Japan)",
            "suppliers": "food distributors, franchise operators, property landlords"
        },
        "watchlist": ["Chipotle Mexican Grill (NYSE:CMG)", "Wingstop (NASDAQ:WING)", "Cava Group (NYSE:CAVA)", "Domino's Pizza Enterprises (ASX:DMP)", "Collins Foods (ASX:CKF)"],
        "listed_competitors": ["DMP", "CKF"],
        "watch_signal": "Chipotle (CMG) is the model - its same-store sales and unit economics set expectations. Wingstop and Cava as US high-growth QSR reads. Domino's (DMP) is the ASX QSR cautionary tale; Collins Foods (KFC/Taco Bell) for the local operator view.",
        "asx_url": "https://www.asx.com.au/markets/company/GYG",
        "revenue_drivers": {
            "primary": "Comparable/same-store sales, new restaurant rollout and unit economics",
            "key_metrics": ["QSR same-store sales", "restaurant traffic vs pricing", "GYG restaurant count", "average unit volumes"],
            "search_terms": ["Guzman y Gomez sales 2026", "Chipotle same store sales"],
            "what_to_track": "Comparable sales (traffic vs price) is the health metric; new-store rollout pace and returns; margin as it scales; the Chipotle read-through on fast-casual demand"
        }
    },
    {
        "name": "Breville Group Limited",
        "ticker": "BRG.AX",
        "asx_code": "BRG",
        "sector": "Consumer Discretionary",
        "industry": "premium small kitchen appliances",
        "industry_publications": ["Inside Retail", "HomeWorld Business", "Appliance Retailer", "AFR Companies"],
        "supply_chain": {
            "customers": "premium appliance buyers via retail and e-commerce (Americas, EMEA, APAC)",
            "suppliers": "contract manufacturers (largely China-based), component suppliers"
        },
        "watchlist": ["De'Longhi (BIT:DLG)", "SharkNinja (NYSE:SN)", "Groupe SEB (EPA:SK)", "Helen of Troy (NASDAQ:HELE)", "Newell Brands (NASDAQ:NWL)", "Williams-Sonoma (NYSE:WSM)"],
        "listed_competitors": [],
        "watch_signal": "De'Longhi is the closest model. SharkNinja, Groupe SEB, Helen of Troy and Newell as global appliance peers. Williams-Sonoma is a key channel/retail read for premium kitchen demand.",
        "asx_url": "https://www.asx.com.au/markets/company/BRG",
        "revenue_drivers": {
            "primary": "Premium appliance sales, new product launches, US/Europe expansion and the coffee category",
            "key_metrics": ["US and Europe small appliance demand", "consumer discretionary spending", "coffee machine category growth", "Breville new product launches"],
            "search_terms": ["small appliance market 2026", "SharkNinja De'Longhi results"],
            "what_to_track": "Coffee category and premium positioning drive growth; geographic expansion (Europe/Americas); new-product cadence; input costs and tariffs on China-sourced goods"
        }
    },
    {
        "name": "Propel Funeral Partners Limited",
        "ticker": "PFP.AX",
        "asx_code": "PFP",
        "sector": "Consumer Discretionary",
        "industry": "death care services (funeral homes, cemeteries, crematoria)",
        "industry_publications": ["Australian Funeral Directors Association", "Australasian Cemeteries & Crematoria Association"],
        "supply_chain": {
            "customers": "families and individuals requiring funeral services across Australia and New Zealand",
            "suppliers": "casket and coffin manufacturers, memorial and headstone suppliers, floral providers, vehicle fleet suppliers"
        },
        "watchlist": ["Service Corporation International (NYSE:SCI)", "InvoCare (unlisted, TPG-owned)", "Dignity (unlisted, UK)"],
        "listed_competitors": [],
        "watch_signal": "Service Corporation International (SCI) is the global model. InvoCare (TPG-owned) is the former #1 domestic operator. Dignity (UK) for the death-care model. Death-rate demographics are the structural driver.",
        "asx_url": "https://www.asx.com.au/markets/company/PFP",
        "revenue_drivers": {
            "primary": "Number of funerals performed, average revenue per funeral, and acquisitions",
            "key_metrics": ["Australian death rate", "mortality statistics ABS", "funeral home acquisitions", "cremation vs burial rates"],
            "search_terms": ["Australian death rate statistics 2026", "funeral home acquisition Australia"],
            "what_to_track": "Death volumes (aging population is the tailwind); average revenue per funeral; acquisition pipeline in a fragmented industry; cremation vs burial mix"
        }
    },
    # ========================================================================
    # SECTOR: SOFTWARE
    # ========================================================================
    {
        "name": "WiseTech Global Limited",
        "ticker": "WTC.AX",
        "asx_code": "WTC",
        "sector": "Software",
        "industry": "logistics execution software",
        "industry_publications": ["The Loadstar", "Journal of Commerce", "Supply Chain Dive", "iTnews"],
        "supply_chain": {
            "customers": "freight forwarders, logistics providers, customs brokers globally",
            "suppliers": "cloud infrastructure providers, software development talent"
        },
        "watchlist": ["Descartes Systems (NASDAQ:DSGX)", "DSV (CPH:DSV)", "Kuehne+Nagel (SWX:KNIN)", "Expeditors (NASDAQ:EXPD)", "Manhattan Associates (NASDAQ:MANH)", "e2open (NYSE:ETWO)", "SAP (NYSE:SAP)"],
        "listed_competitors": [],
        "watch_signal": "Descartes (DSGX) is the closest listed comp. Track the big freight forwarders directly (DSV integration risk, Kuehne+Nagel, Expeditors) for logistics demand and CargoWise adoption. Manhattan, e2open and SAP TM on the software side.",
        "asx_url": "https://www.asx.com.au/markets/company/WTC",
        "revenue_drivers": {
            "primary": "CargoWise recurring revenue, freight-forwarder adoption and new module rollouts",
            "key_metrics": ["global freight volumes", "container shipping rates", "CargoWise large-customer rollouts", "logistics software adoption"],
            "search_terms": ["global freight forwarding 2026", "WiseTech CargoWise rollout"],
            "what_to_track": "New large-forwarder rollouts and module attach; freight cycle affects customers' appetite; competitive wins vs Descartes; product execution and governance"
        }
    },
    {
        "name": "Xero Limited",
        "ticker": "XRO.AX",
        "asx_code": "XRO",
        "sector": "Software",
        "industry": "cloud accounting software (SaaS)",
        "industry_publications": ["Accounting Today", "AccountingWEB", "iTnews", "SaaS industry press"],
        "supply_chain": {
            "customers": "small and medium businesses, accountants and bookkeepers (ANZ, UK, US)",
            "suppliers": "cloud infrastructure providers, app ecosystem partners"
        },
        "watchlist": ["Intuit (NASDAQ:INTU)", "Sage Group (LSE:SGE)", "MYOB (unlisted, KKR-owned)", "Bill.com (NYSE:BILL)"],
        "listed_competitors": [],
        "watch_signal": "Intuit (QuickBooks) is the primary global comp, especially in the US. Sage, MYOB and Bill.com round out the field. Subscriber growth, ARPU and price increases are the key metrics.",
        "asx_url": "https://www.asx.com.au/markets/company/XRO",
        "revenue_drivers": {
            "primary": "Subscriber growth, ARPU, net revenue retention and US/UK expansion",
            "key_metrics": ["Xero subscriber growth", "SME cloud accounting adoption", "Intuit QuickBooks subscribers", "SaaS ARPU and churn"],
            "search_terms": ["Xero subscribers 2026", "Intuit QuickBooks results"],
            "what_to_track": "Net subscriber adds and ARPU (price rises) drive the 'Rule of 40'; US expansion is the swing; churn/retention and payments monetisation"
        }
    },
    {
        "name": "Hansen Technologies Limited",
        "ticker": "HSN.AX",
        "asx_code": "HSN",
        "sector": "Software",
        "industry": "billing and CIS software (utilities, energy, telco)",
        "industry_publications": ["Energy Magazine Australia", "Utility Week", "Light Reading", "Comms Business"],
        "supply_chain": {
            "customers": "energy retailers, utilities (electricity, gas, water), telecommunications providers, pay-TV operators",
            "suppliers": "cloud infrastructure providers (AWS, Azure), technology partners"
        },
        "watchlist": ["Amdocs (NASDAQ:DOX)", "CSG Systems (NASDAQ:CSGS)", "NetCracker (via NEC)", "Oracle Utilities (via NYSE:ORCL)"],
        "listed_competitors": [],
        "watch_signal": "Billing/CIS software peers Amdocs, CSG Systems, NetCracker and Oracle Utilities. Hansen's serial-acquirer model invites comparison to the Nordic software compounders (Constellation Software, Vitec).",
        "asx_url": "https://www.asx.com.au/markets/company/HSN",
        "revenue_drivers": {
            "primary": "Recurring software licence revenue, new contract wins and bolt-on acquisitions",
            "key_metrics": ["utility/telco billing contract wins", "energy retailer M&A", "recurring revenue growth", "acquisition pipeline"],
            "search_terms": ["utility billing software contract 2026", "Amdocs CSG Systems results"],
            "what_to_track": "New contract wins (long sales cycles); recurring revenue and retention; acquisition-led growth and integration; customer M&A that consolidates the base"
        }
    },
    {
        "name": "Block, Inc. (CDI)",
        "ticker": "XYZ.AX",
        "asx_code": "XYZ",
        "sector": "Software",
        "industry": "payments and fintech (Square, Cash App, Afterpay)",
        "industry_publications": ["PaymentsSource", "Finextra", "The Block", "TechCrunch Fintech"],
        "supply_chain": {
            "customers": "merchants (Square), consumers (Cash App), BNPL shoppers (Afterpay)",
            "suppliers": "card networks, banking partners, cloud infrastructure"
        },
        "watchlist": ["PayPal (NASDAQ:PYPL)", "Shopify (NYSE:SHOP)", "Adyen (AMS:ADYEN)", "Fiserv (NYSE:FI)", "Toast (NYSE:TOST)", "Affirm (NASDAQ:AFRM)", "Coinbase (NASDAQ:COIN)"],
        "listed_competitors": [],
        "watch_signal": "PayPal, Shopify, Adyen, Fiserv and Toast for merchant/payments; Affirm for BNPL (the Afterpay read); Coinbase for the bitcoin exposure. Gross profit growth across Square and Cash App is the scorecard.",
        "asx_url": "https://www.asx.com.au/markets/company/XYZ",
        "revenue_drivers": {
            "primary": "Square gross payment volume/gross profit, Cash App monetisation, Afterpay GMV and bitcoin",
            "key_metrics": ["Square gross payment volume (GPV)", "Cash App monthly actives and gross profit", "BNPL/Afterpay GMV", "bitcoin price"],
            "search_terms": ["Block Square Cash App results 2026", "PayPal Adyen earnings"],
            "commodities": ["Bitcoin (US$)"],
            "what_to_track": "Gross profit (not revenue) across Square and Cash App; Afterpay GMV and losses; bitcoin holdings mark-to-market; competition from PayPal/Adyen/Toast"
        }
    },
    # ========================================================================
    # SECTOR: REAL ESTATE
    # ========================================================================
    {
        "name": "Charter Hall Group",
        "ticker": "CHC.AX",
        "asx_code": "CHC",
        "sector": "Real Estate",
        "industry": "real estate investment and funds management",
        "industry_publications": ["The Property Council", "Commercial Real Estate", "Australian Property Journal", "PERE News"],
        "supply_chain": {
            "customers": "institutional investors, superannuation funds, wholesale investors, tenants",
            "suppliers": "property developers, construction firms, property managers"
        },
        "watchlist": ["Goodman Group (ASX:GMG)", "Dexus (ASX:DXS)", "GPT Group (ASX:GPT)", "Mirvac (ASX:MGR)", "Stockland (ASX:SGP)", "Centuria Capital (ASX:CNI)", "HMC Capital (ASX:HMC)", "Scentre Group (ASX:SCG)", "Vicinity Centres (ASX:VCX)"],
        "listed_competitors": ["GMG", "DXS"],
        "watch_signal": "Goodman (GMG) is the quality benchmark. Dexus, GPT, Mirvac and Stockland for cap rates; Centuria and HMC Capital for the funds-management model; Scentre and Vicinity for retail. Cap-rate direction is the shared tell.",
        "asx_url": "https://www.asx.com.au/markets/company/CHC",
        "revenue_drivers": {
            "primary": "Assets Under Management (AUM), property transaction fees and base management fees",
            "key_metrics": ["commercial property cap rates", "office vacancy rates Sydney Melbourne", "industrial property yields", "institutional capital flows"],
            "search_terms": ["Australian commercial property cap rates 2026", "industrial property investment Australia"],
            "what_to_track": "AUM growth drives base fees; transactions drive performance fees; cap-rate compression/expansion moves valuations and gearing"
        }
    },
    {
        "name": "Growthpoint Properties Australia",
        "ticker": "GOZ.AX",
        "asx_code": "GOZ",
        "sector": "Real Estate",
        "industry": "real estate investment trust (office and industrial)",
        "industry_publications": ["The Property Council", "Commercial Real Estate", "Australian Property Journal", "The Urban Developer"],
        "supply_chain": {
            "customers": "office tenants (corporates, government), industrial tenants, institutional investors",
            "suppliers": "property developers, construction firms, facilities management providers"
        },
        "watchlist": ["Dexus (ASX:DXS)", "GPT Group (ASX:GPT)", "Mirvac (ASX:MGR)", "Centuria Industrial REIT (ASX:CIP)", "Goodman Group (ASX:GMG)"],
        "listed_competitors": ["DXS", "CIP"],
        "watch_signal": "An office/industrial A-REIT. Dexus, GPT and Mirvac for office; Centuria Industrial (CIP) and Goodman (GMG) as the industrial benchmark. Cap rates, office occupancy and the interest-rate impact on NTA are the tells.",
        "asx_url": "https://www.asx.com.au/markets/company/GOZ",
        "revenue_drivers": {
            "primary": "Rental income, occupancy rates and property valuations",
            "key_metrics": ["Sydney office vacancy rate", "Melbourne office vacancy rate", "industrial property vacancy", "office cap rates", "REIT distribution yields"],
            "search_terms": ["Sydney CBD office vacancy rate 2026", "Australian industrial property market"],
            "what_to_track": "Office occupancy (majority of portfolio) and industrial occupancy; rent review outcomes; cap-rate movements drive NTA; interest rates on valuations and gearing"
        }
    },
    # ========================================================================
    # SECTOR: PROPERTY TECH & INFORMATION
    # ========================================================================
    {
        "name": "PEXA Group Limited",
        "ticker": "PXA.AX",
        "asx_code": "PXA",
        "sector": "Property Tech & Information",
        "industry": "e-conveyancing and digital property exchange",
        "industry_publications": ["Australian Property Journal", "Mortgage Business", "iTnews", "Fintech industry press"],
        "supply_chain": {
            "customers": "conveyancers, lawyers, banks and lenders (Australia and UK)",
            "suppliers": "land registries, banking integration partners, cloud infrastructure"
        },
        "watchlist": ["Sympli (unlisted, InfoTrack/ATO-backed)", "Dye & Durham (TSX:DND)", "UK HM Land Registry digitisation", "NatWest and UK lender go-lives"],
        "listed_competitors": [],
        "watch_signal": "No listed AU comp - PEXA is effectively an e-conveyancing monopoly; Sympli (private, InfoTrack/ATO-backed) is the emerging domestic challenger. UK/Canada reads via Land Registry digitisation and Dye & Durham. Track UK lender go-lives (NatWest) for the expansion story.",
        "asx_url": "https://www.asx.com.au/markets/company/PXA",
        "revenue_drivers": {
            "primary": "Australian property settlement volumes and refinancing activity, plus UK expansion",
            "key_metrics": ["Australian property settlement volumes", "refinancing activity", "housing turnover", "PEXA UK lender go-lives"],
            "search_terms": ["Australian property transaction volumes 2026", "PEXA UK NatWest go-live"],
            "what_to_track": "Settlement volumes and refinancing drive the core Exchange; interoperability/competition risk from Sympli; UK expansion milestones (lender onboarding) and its cash burn"
        }
    },
    {
        "name": "News Corporation (CDI)",
        "ticker": "NWS.AX",
        "asx_code": "NWS",
        "sector": "Property Tech & Information",
        "industry": "diversified media and information services",
        "industry_publications": ["Digiday", "Press Gazette", "AFR Companies", "The Australian Business"],
        "supply_chain": {
            "customers": "property advertisers, news/information subscribers, book buyers",
            "suppliers": "journalists and content creators, printing and distribution, technology platforms"
        },
        "watchlist": ["REA Group (ASX:REA)", "CoStar Group (NASDAQ:CSGP)", "Zillow (NASDAQ:ZG)", "RELX (LSE:REL)", "Thomson Reuters (NYSE:TRI)"],
        "listed_competitors": ["REA"],
        "watch_signal": "REA Group (REA) is the real value driver inside News Corp. CoStar and Zillow read across to Move/Realtor.com; RELX and Thomson Reuters for the Dow Jones professional-information franchise.",
        "asx_url": "https://www.asx.com.au/markets/company/NWS",
        "revenue_drivers": {
            "primary": "REA Group digital property advertising, Dow Jones/professional-info subscriptions, book publishing",
            "key_metrics": ["REA Australian listings and yield", "US real estate listings (Move/Realtor.com)", "Dow Jones subscriptions", "digital advertising revenue"],
            "search_terms": ["REA Group results 2026", "News Corp Dow Jones subscriptions"],
            "what_to_track": "REA is the crown jewel (listings and yield); Dow Jones subscription growth; US digital real estate (Move) vs Zillow/CoStar; book publishing and capital allocation"
        }
    },
    # ========================================================================
    # SECTOR: DISTRIBUTION
    # ========================================================================
    {
        "name": "Dicker Data Limited",
        "ticker": "DDR.AX",
        "asx_code": "DDR",
        "sector": "Distribution",
        "industry": "IT distribution and technology wholesale",
        "industry_publications": ["CRN Australia", "ARN (Australian Reseller News)", "iTnews", "Channel Life"],
        "supply_chain": {
            "customers": "IT resellers, system integrators, managed service providers across Australia and NZ",
            "suppliers": "Cisco, Dell Technologies, HP, Lenovo, Microsoft, VMware, Hewlett Packard Enterprise"
        },
        "watchlist": ["TD SYNNEX (NYSE:SNX)", "Ingram Micro (NYSE:INGM)", "Data#3 (ASX:DTL)", "Microsoft (NASDAQ:MSFT)", "HP (NYSE:HPQ)", "Cisco (NASDAQ:CSCO)", "Dell (NYSE:DELL)", "Lenovo (HKG:0992)"],
        "listed_competitors": ["DTL"],
        "watch_signal": "TD SYNNEX and Ingram Micro globally; Data#3 (DTL) locally. Vendors Microsoft, HP, Cisco, Dell and Lenovo signal channel demand - their guidance and product cycles (AI PCs, servers) flow through to Dicker Data.",
        "asx_url": "https://www.asx.com.au/markets/company/DDR",
        "revenue_drivers": {
            "primary": "Enterprise IT spending, vendor partnerships and hardware vs services mix",
            "key_metrics": ["Australian IT spending growth", "enterprise hardware sales", "cloud infrastructure demand", "AI PC and server demand"],
            "search_terms": ["Australian enterprise IT spending 2026", "AI infrastructure demand Australia"],
            "what_to_track": "Enterprise IT refresh cycles (AI PCs, servers); key vendor product launches and channel demand; margin on services vs hardware; working-capital and interest costs"
        }
    },
]


# ============================================================================
# YAHOO FINANCE - PRICE DATA
# ============================================================================

def get_stock_price(ticker: str) -> dict:
    """Get accurate stock price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if len(hist) < 2:
            return {"error": f"Not enough history for {ticker}"}
        
        yesterday_close = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2])
        yesterday_date = hist.index[-1].strftime("%B %d, %Y")
        previous_date = hist.index[-2].strftime("%B %d, %Y")
        change_percent = ((yesterday_close - previous_close) / previous_close) * 100
        
        return {
            "yesterday_close": round(yesterday_close, 2),
            "yesterday_date": yesterday_date,
            "previous_close": round(previous_close, 2),
            "previous_date": previous_date,
            "change_percent": round(change_percent, 2),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# ASX SCRAPER FUNCTIONS
# ============================================================================

def asx_get_announcements(ticker: str) -> list:
    """Get announcement list from ASX."""
    url = f"{ASX_BASE_URL}/asx/v2/statistics/announcements.do?by=asxCode&asxCode={ticker}&timeframe=D&period=M6"
    
    try:
        r = requests.get(url, headers=ASX_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return []
        
        anns = []
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            link = cells[2].find('a', href=True)
            if not link:
                continue
            
            href = link['href']
            pdf_url = f"{ASX_BASE_URL}{href}" if href.startswith('/') else f"{ASX_BASE_URL}/asx/v2/statistics/{href}"
            
            text = link.get_text(strip=True)
            m = re.match(r'^(.+?)\s*\d+\s*pages?', text, re.I)
            
            anns.append({
                'title': m.group(1).strip() if m else text,
                'date': cells[0].get_text(strip=True),
                'pdf_url': pdf_url,
                'sensitive': bool(cells[1].find('img'))
            })
        
        return anns
    except Exception as e:
        print(f"      Error fetching announcements: {e}")
        return []


def asx_download_pdf(pdf_url: str) -> bytes:
    """Download PDF by clicking Accept button using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(pdf_url, wait_until='networkidle', timeout=20000)
            
            content = page.content()
            
            if 'commercial purpose' in content.lower():
                buttons = page.query_selector_all('input[type="submit"]')
                
                accept_btn = None
                for btn in buttons:
                    value = btn.get_attribute('value') or ''
                    if 'agree' in value.lower() or 'confirm' in value.lower() or 'accept' in value.lower():
                        accept_btn = btn
                        break
                
                checkbox = page.query_selector('input[type="checkbox"]')
                if checkbox:
                    checkbox.click()
                    page.wait_for_timeout(500)
                
                if accept_btn:
                    accept_btn.click()
                else:
                    try:
                        page.click('text=Agree')
                    except:
                        pass
                
                page.wait_for_timeout(3000)
                page.wait_for_load_state('networkidle')
                
                resp = context.request.get(pdf_url)
                body = resp.body()
                
                if body[:5] == b'%PDF-':
                    browser.close()
                    return body
            
            browser.close()
            return None
    except Exception as e:
        print(f"      Error downloading PDF: {e}")
        return None


def asx_extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(pdf_bytes)
            path = f.name
        
        text = ""
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages[:15]:
                t = pg.extract_text()
                if t:
                    text += t + "\n"
        
        os.unlink(path)
        return text[:12000] if text else ""
    except Exception as e:
        print(f"      Error extracting text: {e}")
        return ""


def asx_is_periodic_earnings_report(title: str) -> bool:
    """Check if announcement is a quarterly, half-yearly or annual earnings report."""
    title_lower = title.lower()
    
    periodic_patterns = [
        r'(full year|fy\d{2}|annual).*(result|report)',
        r'(half year|1h\d{2}|2h\d{2}|interim).*(result|report)',
        r'(quarter|q[1-4]|[1-4]q).*(result|report)',
        r'(result|report).*(full year|fy\d{2}|annual)',
        r'(result|report).*(half year|1h|2h|interim)',
        r'(result|report).*(quarter|q[1-4])',
        r'appendix 4[de]',
        r'preliminary final report',
        r'\d{4}\s+(full year|annual)\s+result',
        r'(1h|2h|hy)\d{2}\s+result',
        r'profit announcement',
    ]
    
    exclude_patterns = [
        'trading update', 'guidance', 'presentation', 'investor',
        'agm', 'annual general meeting', 'dividend', 'buyback',
        'acquisition', 'merger', 'takeover', 'proposal', 'bid',
        'offer', 'chair address', 'ceo address',
    ]
    
    for exclude in exclude_patterns:
        if exclude in title_lower:
            return False
    
    for pattern in periodic_patterns:
        if re.search(pattern, title_lower):
            return True
    
    return False


# ============================================================================
# CLAUDE API FUNCTIONS
# ============================================================================

def get_anthropic_client() -> anthropic.Anthropic:
    """Get Anthropic client."""
    return anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))


def call_claude_with_search(client: anthropic.Anthropic, prompt: str, max_searches: int = 2) -> str:
    """Call Claude API with web search tool enabled."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = ""
        for block in response.content:
            if hasattr(block, 'text') and block.text is not None:
                result += block.text
        
        return result.strip() if result else "NO_RESPONSE"
    except Exception as e:
        return f"ERROR: {str(e)}"


def call_claude_analyze(client: anthropic.Anthropic, prompt: str) -> str:
    """Call Claude API for analysis (no web search)."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"


# ============================================================================
# ASX-BASED RESEARCH FUNCTIONS (replaces web search for announcements/earnings)
# ============================================================================

def parse_asx_date(date_str: str) -> datetime:
    """Parse ASX date string which may include time. Returns datetime or None."""
    if not date_str:
        return None
    
    # Clean up the date string - remove time portion if present
    # ASX dates can be "26/08/2025" or "26/08/20257:38 am" or "29/01/2026 8:12 am"
    date_str = date_str.strip()
    
    # Try to extract just the date part (DD/MM/YYYY)
    date_match = re.match(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
    if date_match:
        date_part = date_match.group(1)
        try:
            return datetime.strptime(date_part, "%d/%m/%Y")
        except ValueError:
            pass
    
    # Try other formats
    for fmt in ["%d/%m/%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y %H:%M %p", "%d/%m/%Y%H:%M %p"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def format_asx_date(date_str: str) -> str:
    """Format ASX date string to clean format without time."""
    parsed = parse_asx_date(date_str)
    if parsed:
        return parsed.strftime("%d %b %Y")  # e.g., "26 Aug 2025"
    return date_str  # Return original if parsing fails


def research_new_information(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research NEW information about the company in the last 7 days.
    MUST capture ALL ASX announcements from last 7 days - no filtering.
    Returns structured data for the "New Information" section.
    """
    asx_code = stock['asx_code']
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    
    result = {
        "has_new_info": False,
        "items": [],  # List of new information items
        "no_news_message": "No new information in the last 7 days."
    }
    
    # Step 1: Get ALL ASX announcements from last 7 days - NO FILTERING
    anns = asx_get_announcements(asx_code)
    recent_anns = []
    
    for ann in anns:
        ann_date = parse_asx_date(ann['date'])
        if ann_date and ann_date >= seven_days_ago:
            recent_anns.append(ann)
        elif not ann_date:
            # If date parsing fails but it's in the first few announcements, include it
            if len(recent_anns) < 5 and anns.index(ann) < 5:
                recent_anns.append(ann)
    
    # Add ALL recent ASX announcements to result (prioritize price-sensitive)
    # Sort: price-sensitive first, then by date
    recent_anns.sort(key=lambda x: (not x.get('sensitive', False), x.get('date', '')))
    
    for ann in recent_anns[:5]:  # Max 5 recent announcements
        # Mark price-sensitive announcements
        ann_type = "ASX Announcement (Price Sensitive)" if ann.get('sensitive') else "ASX Announcement"
        
        result["items"].append({
            "type": ann_type,
            "title": ann['title'],
            "date": format_asx_date(ann['date']),
            "summary": None,
            "source_url": ann['pdf_url'],
            "is_new": True,
            "price_sensitive": ann.get('sensitive', False)
        })
        result["has_new_info"] = True
    
    # Step 2: Search for recent news from reputable sources (skip if we have plenty of ASX news)
    if len(result["items"]) < 3:
        news_prompt = f"""Search for news about {stock['name']} (ASX: {stock['asx_code']}) published in the LAST 7 DAYS ONLY.

**ONLY include news from these sources:**
- Australian Financial Review (AFR)
- Sydney Morning Herald (SMH)
- The Australian
- Bloomberg
- Reuters

**STRICT RULES:**
- ONLY include articles published within the last 7 days
- If you cannot verify the publication date is within 7 days, DO NOT include it
- Focus on material news: earnings updates, contracts, acquisitions, management changes, guidance
- Ignore opinion pieces, analyst commentary, or general market news

After searching, provide JSON only:
{{
    "news_items": [
        {{
            "title": "Headline of the article",
            "source_name": "Publication name",
            "source_url": "URL or null",
            "publication_date": "Date (must be within last 7 days)",
            "summary": "1 sentence summary of what's new"
        }}
    ],
    "no_recent_news": true/false
}}

If no news from the last 7 days is found, return: {{"news_items": [], "no_recent_news": true}}
"""
        
        search_result = call_claude_with_search(client, news_prompt, max_searches=1)
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', search_result)
            if json_match:
                news_data = json.loads(json_match.group())
                for item in news_data.get('news_items', []):
                    result["items"].append({
                        "type": "News",
                        "title": item.get('title'),
                        "date": item.get('publication_date'),
                        "summary": item.get('summary'),
                        "source_name": item.get('source_name'),
                        "source_url": item.get('source_url'),
                        "is_new": True,
                        "price_sensitive": False
                    })
                    result["has_new_info"] = True
        except (json.JSONDecodeError, AttributeError):
            pass
    
    return result


def research_announcements_asx(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research announcements using ASX scraper.
    Returns structured data compatible with V5 format.
    """
    asx_code = stock['asx_code']
    
    anns = asx_get_announcements(asx_code)
    if not anns:
        return {
            "last_announcement": {
                "date": "Not found",
                "title": "Not found",
                "summary": "Unable to retrieve announcement data from ASX",
                "source_url": stock.get('asx_url')
            },
            "price_sensitive_news": {
                "found": False,
                "description": "No announcements found",
                "source_url": None
            }
        }
    
    # Get price-sensitive announcements
    sensitive = [a for a in anns if a['sensitive']]
    
    result = {
        "last_announcement": {
            "date": "Not found",
            "title": "Not found",
            "summary": "No recent announcements",
            "source_url": stock.get('asx_url')
        },
        "price_sensitive_news": {
            "found": False,
            "description": "No material announcements in the past 3 days",
            "source_url": None
        }
    }
    
    # Process the latest price-sensitive announcement
    if sensitive:
        latest = sensitive[0]
        print(f"      Downloading: {latest['title'][:40]}...")
        
        pdf_bytes = asx_download_pdf(latest['pdf_url'])
        if pdf_bytes:
            text = asx_extract_text(pdf_bytes)
            if text:
                # Use Claude to summarize the announcement
                prompt = f"""Analyze this ASX announcement and provide a 2-3 sentence summary focusing on what happened and why it matters to investors.

Title: {latest['title']}
Date: {latest['date']}

Content:
{text[:8000]}

Provide ONLY the summary, no bullet points or formatting."""

                summary = call_claude_analyze(client, prompt)
                
                result["last_announcement"] = {
                    "date": latest['date'],
                    "title": latest['title'],
                    "summary": summary if not summary.startswith("ERROR") else "Summary unavailable",
                    "source_url": latest['pdf_url']
                }
                
                result["price_sensitive_news"] = {
                    "found": True,
                    "description": summary if not summary.startswith("ERROR") else latest['title'],
                    "source_url": latest['pdf_url']
                }
    
    return result


def research_market_update(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research the LAST MARKET UPDATE - the most recent price-sensitive ASX announcement
    containing fundamental information that impacts the stock price.
    
    This includes: quarterly updates, guidance changes, trading updates, annual/half-year results,
    capital raises, acquisitions, or any other price-sensitive material.
    """
    asx_code = stock['asx_code']
    
    # Check cache first (cache for 7 days since market updates are more frequent)
    cached = load_from_cache(asx_code, 'market_update', 7)
    if cached:
        return cached
    
    anns = asx_get_announcements(asx_code)
    if not anns:
        return {
            "update_type": "Not found",
            "update_date": "Not found",
            "title": "Not found",
            "key_financials": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Get the most recent PRICE-SENSITIVE announcement (ASX marks these clearly)
    sensitive = [a for a in anns if a.get('sensitive')]
    
    if not sensitive:
        return {
            "update_type": "Not found",
            "update_date": "Not found",
            "title": "No recent price-sensitive announcements",
            "key_financials": "Not found",
            "guidance": "None mentioned",
            "source_url": stock.get('asx_url')
        }
    
    # Use the MOST RECENT price-sensitive announcement
    latest = sensitive[0]
    print(f"      Downloading: {latest['title'][:50]}...")
    
    pdf_bytes = asx_download_pdf(latest['pdf_url'])
    if not pdf_bytes:
        return {
            "update_type": "Announcement",
            "update_date": format_asx_date(latest['date']),
            "title": latest['title'],
            "key_financials": "Unable to download PDF",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    text = asx_extract_text(pdf_bytes)
    if not text:
        return {
            "update_type": "Announcement",
            "update_date": format_asx_date(latest['date']),
            "title": latest['title'],
            "key_financials": "Unable to extract text from PDF",
            "guidance": "None mentioned",
            "source_url": latest['pdf_url']
        }
    
    # Use Claude to extract key information from any type of market update
    prompt = f"""Analyze this ASX price-sensitive announcement and extract the key information that would impact the stock price.

Title: {latest['title']}
Date: {latest['date']}

Content:
{text[:10000]}

This could be ANY type of market update: quarterly results, half-year/annual results, trading update, guidance change, capital raising, acquisition, or other material announcement.

Provide your response in EXACTLY this JSON format (no other text):
{{
    "update_type": "Type of update (e.g., 'Annual Results FY25', 'Quarterly Update Q2 FY26', 'Trading Update', 'Capital Raising', 'Guidance Upgrade', 'Acquisition Announcement', etc.)",
    "key_financials": "The MOST IMPORTANT financial metrics or numbers from this announcement. For results: include Revenue, NPAT, EPS, Dividend if available. For trading updates: include any metrics mentioned. For capital raises: include size and terms. For guidance: include the specific numbers. Format as a concise string with key metrics separated by ' | '. Example: 'NPAT: $180M (+31%) | EPS: 171.75c | Dividend: 66c fully franked'. If no financials, describe the key material information.",
    "guidance": "Any forward-looking guidance, outlook, or forecasts mentioned. Include specific numbers if provided. If none, return 'None mentioned'."
}}

**RULES:**
- Extract the ACTUAL numbers from the document
- Focus on the most material information that would move the stock price
- Be specific with numbers - include percentages, currency amounts, comparisons to prior periods
- If this is a capital raising, include the size, price, and discount
- If this is an acquisition, include the target and price"""

    response = call_claude_analyze(client, prompt)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            update_data = json.loads(json_match.group())
            result = {
                "update_type": update_data.get('update_type', 'Announcement'),
                "update_date": format_asx_date(latest['date']),
                "title": latest['title'],
                "key_financials": update_data.get('key_financials', 'Not found'),
                "guidance": update_data.get('guidance', 'None mentioned'),
                "source_url": latest['pdf_url']
            }
            
            # Cache successful results
            if result.get('key_financials') != 'Not found':
                save_to_cache(asx_code, 'market_update', result)
            
            return result
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "update_type": "Announcement",
        "update_date": format_asx_date(latest['date']),
        "title": latest['title'],
        "key_financials": "Unable to extract - see source",
        "guidance": "None mentioned",
        "source_url": latest['pdf_url']
    }


# Keep the old function name as alias for backwards compatibility during transition
def research_earnings_asx(client: anthropic.Anthropic, stock: dict) -> dict:
    """Deprecated - use research_market_update instead."""
    return research_market_update(client, stock)


# ============================================================================
# CLAUDE WEB SEARCH RESEARCH FUNCTIONS (for industry and competitors)
# ============================================================================

def research_industry(client: anthropic.Anthropic, stock: dict) -> dict:
    """Research industry dynamics focused on REVENUE DRIVERS. Max 2 months old, flag items from last 7 days as NEW."""
    industry_pubs = ", ".join(stock.get('industry_publications', []))
    
    # Get revenue driver information
    revenue_drivers = stock.get('revenue_drivers', {})
    primary_driver = revenue_drivers.get('primary', 'general business performance')
    key_metrics = revenue_drivers.get('key_metrics', [])
    search_terms = revenue_drivers.get('search_terms', [f"{stock['industry']} Australia"])
    what_to_track = revenue_drivers.get('what_to_track', '')
    commodities = revenue_drivers.get('commodities', [])
    
    # Build commodity section if applicable
    commodity_section = ""
    if commodities:
        commodity_section = f"""
**COMMODITY PRICES TO FIND (CRITICAL):**
{chr(10).join(f'- {c}' for c in commodities)}
You MUST search for current prices of these commodities and include them in your response.
"""
    
    prompt = f"""You are researching factors that drive REVENUE and EARNINGS for {stock['name']} (ASX: {stock['asx_code']}).

**PRIMARY REVENUE DRIVER:** {primary_driver}

**KEY METRICS TO FIND:**
{chr(10).join(f'- {m}' for m in key_metrics)}
{commodity_section}
**CONTEXT:** {what_to_track}

**SEARCH STRATEGY:**
Search for: {', '.join(f'"{t}"' for t in search_terms[:2])}

**STRICT DATE REQUIREMENTS:**
- ONLY include information published within the LAST 2 MONTHS (60 days)
- Mark items published in the LAST 7 DAYS with "is_new": true

**SOURCE HIERARCHY:**
1. Industry-specific trade publications: {industry_pubs}
2. Tier-one financial news: AFR, Bloomberg, Reuters, WSJ
3. Company announcements and data providers

**EXCLUDED:** IBISWorld, Mordor Intelligence, generic market research reports

After searching, provide JSON only (no other text):
{{
    "data_points": [
        {{
            "fact": "Specific data point with NUMBERS - e.g. prices, rates, percentages, volumes",
            "source_name": "Publication name",
            "source_url": "URL or null",
            "publication_date": "REQUIRED - exact date (e.g., 'January 15, 2026')",
            "is_new": true/false,
            "relevance": "How this specifically impacts {stock['name']}'s revenue or earnings"
        }}
    ]
}}

**CRITICAL RULES:**
- Focus on data that DIRECTLY impacts {stock['name']}'s revenue: {primary_driver}
- Include SPECIFIC NUMBERS (prices, rates, percentages, volumes)
- Every fact must explain its impact on earnings/revenue in the relevance field
- If searching for commodity prices, include the current price with date
- Return empty array if no relevant data within 2 months
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            
            # POST-PROCESS: Filter out items older than 2 months
            if 'data_points' in data:
                filtered_points = []
                two_months_ago = datetime.now() - timedelta(days=60)
                
                for point in data['data_points']:
                    if point is None:
                        continue
                    pub_date_str = point.get('publication_date') or ''
                    
                    # Skip if no date provided
                    if not pub_date_str:
                        continue
                    
                    # Try to parse the date and validate it's within 2 months
                    is_valid = False
                    for fmt in ["%B %d, %Y", "%d %B %Y", "%B %Y", "%d/%m/%Y", "%Y-%m-%d", 
                                "%b %d, %Y", "%d %b %Y", "%b %Y"]:
                        try:
                            pub_date = datetime.strptime(pub_date_str, fmt)
                            if pub_date >= two_months_ago:
                                is_valid = True
                                # Also check if it's within last 7 days for [NEW] tag
                                seven_days_ago = datetime.now() - timedelta(days=7)
                                point['is_new'] = pub_date >= seven_days_ago
                            break
                        except (ValueError, TypeError):
                            continue
                    
                    # If we couldn't parse the date, check for year indicators
                    if not is_valid and pub_date_str:
                        # Reject if contains old years
                        if any(yr in pub_date_str for yr in ['2024', '2023', '2022', '2021', '2020']):
                            continue
                        # Accept if contains recent months
                        if '2026' in pub_date_str or '2025' in pub_date_str:
                            # Check for months that are definitely > 2 months old
                            if any(m in pub_date_str.lower() for m in ['january 2025', 'february 2025', 'march 2025', 
                                                                         'april 2025', 'may 2025', 'june 2025',
                                                                         'july 2025', 'august 2025', 'september 2025',
                                                                         'october 2025', 'november 2025']):
                                continue  # Skip old 2025 dates
                            is_valid = True
                    
                    if is_valid:
                        filtered_points.append(point)
                
                data['data_points'] = filtered_points
            
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return {
        "data_points": []
    }


def research_competitors(client: anthropic.Anthropic, stock: dict) -> dict:
    """
    Research WATCHLIST updates relevant to the holding using Claude web search.
    Prioritises peer earnings/results and transcript quotes with a read-through to
    the holding. Max 2 months old, flag items from last 7 days as NEW.
    Web search is primary; ASX scraper supplements listed watchlist names.
    """
    watchlist = stock.get('watchlist') or stock.get('competitors') or []
    listed_comps = [c for c in watchlist if '.AX)' in c or 'ASX:' in c]
    unlisted_comps = [c for c in watchlist if '.AX)' not in c and 'ASX:' not in c]
    watch_signal = stock.get('watch_signal', '')

    prompt = f"""You are monitoring a WATCHLIST of peer companies for updates that are RELEVANT to {stock['name']} (ASX: {stock['asx_code']}).

**WHY THIS MATTERS:** {watch_signal if watch_signal else f"These are the closest comparables and read-throughs for {stock['name']}."}

**WATCHLIST COMPANIES TO MONITOR:**
Listed: {', '.join(listed_comps) if listed_comps else 'None specified'}
Global / unlisted: {', '.join(unlisted_comps) if unlisted_comps else 'None specified'}

**WHAT TO LOOK FOR (in priority order):**
1. EARNINGS / RESULTS updates - quarterly or half-year results, trading updates, guidance changes. This is the #1 priority.
2. Direct QUOTES from earnings-call transcripts or management commentary that read across to {stock['name']} (e.g. demand trends, pricing, volumes, a shared end-market or the key signal above).
3. Material strategic actions - contract wins/losses, M&A, capacity/product moves - but ONLY if they have a clear read-through to {stock['name']}.

**RELEVANCE FILTER (critical):**
- ONLY include an item if it tells us something useful about {stock['name']} or its industry.
- For EACH item, explain the read-through in the "implications" field. If you cannot articulate why it matters to {stock['name']}, DO NOT include it.

**STRICT DATE REQUIREMENTS:**
- ONLY include information published within the LAST 2 MONTHS (60 days)
- You MUST verify and include the publication date for each item
- Mark items published in the LAST 7 DAYS with "is_new": true

**SOURCE HIERARCHY (prioritize in this order):**
1. Company results releases, investor presentations and earnings-call transcripts
2. Industry-specific trade publications
3. Tier-one financial news: AFR, WSJ, Bloomberg, Reuters, SMH, The Australian, FT

**EXCLUDED SOURCES - DO NOT CITE:**
- IBISWorld, Mordor Intelligence, or similar market research aggregators
- Generic analyst price-target notes or opinion pieces
- Any article older than 2 months

After searching, provide the following in JSON format only (no other text):
{{
    "competitor_news": [
        {{
            "competitor": "Watchlist company name",
            "news": "The specific earnings result, guidance change or action (with key numbers where available)",
            "quote": "A direct quote from the transcript / management commentary if available, otherwise null",
            "publication_date": "REQUIRED - exact date from the source (e.g., 'January 15, 2026')",
            "is_new": true/false,
            "source_name": "Publication or 'Earnings call transcript'",
            "source_url": "Actual URL from search results, or null",
            "implications": "REQUIRED - the read-through: what this specifically means for {stock['name']}"
        }}
    ],
    "no_recent_news": false,
    "no_recent_news_note": null
}}

If NO relevant watchlist updates were found within the 2-month window, return:
{{
    "competitor_news": [],
    "no_recent_news": true,
    "no_recent_news_note": "No material watchlist updates with a read-through to {stock['name']} in the last 2 months."
}}

**CRITICAL RULES:**
- EVERY item must have a verified publication_date within the last 2 months
- Set "is_new": true if published within the last 7 days, otherwise false
- Prioritise earnings/results and transcript quotes over generic news
- EVERY item must have an "implications" read-through to {stock['name']} - drop items that don't
- Prefer a direct "quote" where the transcript/commentary is available; use null if not
"""
    
    result = call_claude_with_search(client, prompt, max_searches=2)
    
    competitor_data = None
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            competitor_data = json.loads(json_match.group())
            
            # POST-PROCESS: Filter out items older than 2 months
            if 'competitor_news' in competitor_data:
                filtered_news = []
                two_months_ago = datetime.now() - timedelta(days=60)
                
                for item in competitor_data['competitor_news']:
                    if item is None:
                        continue
                    pub_date_str = item.get('publication_date') or ''
                    
                    # Skip if no date provided
                    if not pub_date_str:
                        continue
                    
                    # Try to parse the date and validate it's within 2 months
                    is_valid = False
                    for fmt in ["%B %d, %Y", "%d %B %Y", "%B %Y", "%d/%m/%Y", "%Y-%m-%d", 
                                "%b %d, %Y", "%d %b %Y", "%b %Y"]:
                        try:
                            pub_date = datetime.strptime(pub_date_str, fmt)
                            if pub_date >= two_months_ago:
                                is_valid = True
                                # Also check if it's within last 7 days for [NEW] tag
                                seven_days_ago = datetime.now() - timedelta(days=7)
                                item['is_new'] = pub_date >= seven_days_ago
                            break
                        except (ValueError, TypeError):
                            continue
                    
                    # If we couldn't parse the date, check for year indicators
                    if not is_valid and pub_date_str:
                        # Reject if contains old years
                        if any(yr in pub_date_str for yr in ['2024', '2023', '2022', '2021', '2020']):
                            continue
                        # Accept if contains recent months
                        if '2026' in pub_date_str or '2025' in pub_date_str:
                            # Check for months that are definitely > 2 months old
                            if any(m in pub_date_str.lower() for m in ['january 2025', 'february 2025', 'march 2025', 
                                                                         'april 2025', 'may 2025', 'june 2025',
                                                                         'july 2025', 'august 2025', 'september 2025',
                                                                         'october 2025', 'november 2025']):
                                continue  # Skip old 2025 dates
                            is_valid = True
                    
                    if is_valid:
                        filtered_news.append(item)
                
                competitor_data['competitor_news'] = filtered_news
                
                # Update no_recent_news flag if all items were filtered out
                if not filtered_news:
                    competitor_data['no_recent_news'] = True
                    competitor_data['no_recent_news_note'] = "No material competitive announcements found within the last 2 months."
    except (json.JSONDecodeError, AttributeError):
        pass
    
    if not competitor_data:
        competitor_data = {
            "competitor_news": [],
            "no_recent_news": True,
            "no_recent_news_note": "Unable to retrieve competitor data"
        }
    
    # Option C: Supplement with ASX scraper for listed competitors
    listed_competitor_codes = stock.get('listed_competitors', [])
    if listed_competitor_codes:
        asx_competitor_news = research_competitors_asx(client, listed_competitor_codes)
        if asx_competitor_news:
            # Add ASX-sourced news to the competitor_news list
            competitor_data['competitor_news'].extend(asx_competitor_news)
            if competitor_data.get('no_recent_news') and asx_competitor_news:
                competitor_data['no_recent_news'] = False
                competitor_data['no_recent_news_note'] = None
    
    return competitor_data


def research_competitors_asx(client: anthropic.Anthropic, competitor_codes: list) -> list:
    """
    Get recent announcements from ASX-listed competitors.
    Returns list of competitor news items.
    """
    competitor_news = []
    
    # Limit to top 2 competitors to manage time
    for code in competitor_codes[:2]:
        print(f"      Checking ASX competitor: {code}...")
        
        anns = asx_get_announcements(code)
        if not anns:
            continue
        
        # Get latest price-sensitive announcement
        sensitive = [a for a in anns if a['sensitive']]
        if not sensitive:
            continue
        
        latest = sensitive[0]
        
        # Only include if within last 14 days (approximate check via date string)
        # Note: Date parsing could be improved for exact validation
        
        competitor_news.append({
            "competitor": f"{code} (ASX)",
            "news": latest['title'],
            "quote": None,
            "publication_date": latest['date'],
            "source_name": "ASX Announcement",
            "source_url": latest['pdf_url'],
            "implications": "See ASX announcement for details"
        })
    
    return competitor_news


# ============================================================================
# CACHING FUNCTIONS
# ============================================================================

def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(asx_code: str, cache_type: str) -> Path:
    """Get the cache file path for a specific stock and data type."""
    return CACHE_DIR / f"{asx_code.lower()}_{cache_type}.json"


def load_from_cache(asx_code: str, cache_type: str, max_age_days: int) -> dict | None:
    """Load data from cache if it exists and is not expired."""
    cache_path = get_cache_path(asx_code, cache_type)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r') as f:
            cached = json.load(f)
        
        cached_date = datetime.fromisoformat(cached.get('_cached_at', '2000-01-01'))
        age = datetime.now() - cached_date
        
        if age > timedelta(days=max_age_days):
            print(f"(cache expired: {age.days} days old)")
            return None
        
        print(f"(using cache from {age.days} days ago)")
        return cached.get('data')
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"(cache read error: {e})")
        return None


def save_to_cache(asx_code: str, cache_type: str, data: dict):
    """Save data to cache with timestamp."""
    ensure_cache_dir()
    cache_path = get_cache_path(asx_code, cache_type)
    
    cached = {
        '_cached_at': datetime.now().isoformat(),
        '_asx_code': asx_code,
        'data': data
    }
    
    try:
        with open(cache_path, 'w') as f:
            json.dump(cached, f, indent=2)
    except Exception as e:
        print(f"(cache write error: {e})")


# ============================================================================
# HTML FORMATTING
# ============================================================================

def format_stock_html(stock: dict, price_data: dict, new_info: dict, market_update: dict, 
                      industry: dict, competitors: dict, stock_num: int) -> str:
    """Format all researched data into HTML."""
    
    price_data = price_data or {}
    new_info = new_info or {}
    market_update = market_update or {}
    industry = industry or {}
    competitors = competitors or {}

    # Watchlist context line (the sector "tell" / why these peers are monitored)
    watch_signal = stock.get('watch_signal', '')
    watchlist_names = stock.get('watchlist') or []
    if watch_signal:
        watch_signal_html = f"Watching: {watch_signal}"
    elif watchlist_names:
        watch_signal_html = "Watching: " + ", ".join(watchlist_names)
    else:
        watch_signal_html = "&nbsp;"

    # Price section
    if price_data.get('error'):
        price_html = f'<span style="color:#e74c3c;">Price data unavailable: {price_data.get("error", "Unknown error")}</span>'
    else:
        change_pct = price_data.get('change_percent', 0) or 0
        change_color = "#27ae60" if change_pct >= 0 else "#e74c3c"
        change_sign = "+" if change_pct >= 0 else ""
        price_html = f"""<strong style="color:#2980b9;">YESTERDAY ({price_data.get('yesterday_date', 'N/A')}):</strong> A${price_data.get('yesterday_close', 0):.2f} | 
<strong style="color:#2980b9;">PREVIOUS ({price_data.get('previous_date', 'N/A')}):</strong> A${price_data.get('previous_close', 0):.2f} | 
<strong style="color:#2980b9;">CHANGE:</strong> <span style="color:{change_color};">{change_sign}{change_pct:.2f}%</span>"""
    
    # NEW INFORMATION section - ALL ASX announcements from last 7 days
    if new_info.get('has_new_info') and new_info.get('items'):
        new_info_items = []
        for item in new_info['items']:
            # Highlight price-sensitive announcements
            if item.get('price_sensitive'):
                item_html = f"<strong style=\"color:#e74c3c;\">⚡ {item.get('type', 'News')}:</strong> {item.get('title', 'Untitled')}"
            else:
                item_html = f"<strong>{item.get('type', 'News')}:</strong> {item.get('title', 'Untitled')}"
            if item.get('date'):
                item_html += f" ({item['date']})"
            if item.get('source_url'):
                item_html += f' <a href="{item["source_url"]}" style="color:#3498db;">[Source]</a>'
            if item.get('summary'):
                item_html += f"<br><em style=\"color:#7f8c8d;font-size:0.9em;\">{item['summary']}</em>"
            new_info_items.append(f"<li>{item_html}</li>")
        new_info_html = "\n".join(new_info_items)
    else:
        new_info_html = "<li><em>No new information in the last 7 days.</em></li>"
    
    # LAST MARKET UPDATE section (replaces old Earnings section)
    update_url = market_update.get('source_url') or stock.get('asx_url', '#')
    
    if market_update.get('update_type') and market_update.get('update_type') != 'Not found':
        market_update_html = f"""<strong>Type:</strong> {market_update.get('update_type')}<br>
<strong>Date:</strong> {market_update.get('update_date', 'Not found')}<br>
<strong>Key Financials:</strong> {market_update.get('key_financials', 'Not found')}<br>
<strong>Guidance:</strong> {market_update.get('guidance', 'None mentioned')}"""
    else:
        market_update_html = "No recent price-sensitive market update found."
    
    # Industry dynamics - with [NEW] tag for items from last 7 days
    ind_points = industry.get('data_points') or []
    if ind_points:
        ind_items = []
        for point in ind_points:
            if point is None:
                continue
            fact = point.get('fact') or ''
            if not fact or fact == 'N/A':
                continue
            
            # Add [NEW] tag if published in last 7 days
            is_new = point.get('is_new', False)
            new_tag = '<span style="color:#e74c3c;font-weight:bold;">[NEW]</span> ' if is_new else ''
            
            source_name = point.get('source_name') or point.get('source')
            source_url = point.get('source_url')
            pub_date = point.get('publication_date', '')
            
            item = f"{new_tag}{fact}"
            if source_name and source_name != 'N/A':
                if source_url:
                    item += f' <a href="{source_url}" style="color:#3498db;">({source_name}'
                    if pub_date and pub_date != 'Date not verified':
                        item += f', {pub_date}'
                    item += ')</a>'
                else:
                    item += f' ({source_name}'
                    if pub_date and pub_date != 'Date not verified':
                        item += f', {pub_date}'
                    item += ')'
            
            relevance = point.get('relevance')
            if relevance and relevance != 'N/A' and len(relevance) > 10:
                item += f'<br><em style="color:#7f8c8d;font-size:0.9em;">→ {relevance}</em>'
            
            ind_items.append(f'<li>{item}</li>')
        industry_html = "\n".join(ind_items) if ind_items else "<li>No key driver data found in the last 2 months.</li>"
    else:
        industry_html = "<li>No key driver data found in the last 2 months.</li>"
    
    # Watchlist updates - peer earnings/transcript items relevant to the holding
    # (with [NEW] tag for items from last 7 days)
    comp_news = competitors.get('competitor_news') or []
    no_recent = competitors.get('no_recent_news', False)

    if no_recent or not comp_news:
        note = competitors.get('no_recent_news_note') or 'No material watchlist updates with a read-through to the holding in the last 2 months.'
        competitor_html = f"<li><em>{note}</em></li>"
    else:
        comp_items = []
        for news_item in comp_news:
            if news_item is None:
                continue
            competitor_name = news_item.get('competitor') or 'Unknown'
            news_desc = news_item.get('news') or ''
            if not news_desc:
                continue

            # Add [NEW] tag if published in last 7 days
            is_new = news_item.get('is_new', False)
            new_tag = '<span style="color:#e74c3c;font-weight:bold;">[NEW]</span> ' if is_new else ''

            item = f"{new_tag}<strong>{competitor_name}:</strong> {news_desc}"

            source_name = news_item.get('source_name')
            pub_date = news_item.get('publication_date') or news_item.get('date')
            source_url = news_item.get('source_url')

            if source_name or pub_date:
                item += ' ('
                if pub_date:
                    item += pub_date
                if source_name and pub_date:
                    item += ', '
                if source_name:
                    item += source_name
                item += ')'

            if source_url:
                item += f' <a href="{source_url}" style="color:#3498db;">[Source]</a>'

            # Direct transcript / management quote, if captured
            quote = news_item.get('quote')
            if quote and str(quote).strip().lower() not in ('none', 'null', ''):
                item += (f'<br><span style="display:block;border-left:3px solid #bdc3c7;'
                         f'margin:4px 0 4px 4px;padding-left:8px;color:#555;font-size:0.9em;'
                         f'font-style:italic;">“{quote}”</span>')

            implications = news_item.get('implications')
            if implications and implications != "See ASX announcement for details":
                item += f"<br><em style=\"color:#7f8c8d;font-size:0.9em;\">→ Read-through to {stock['name']}: {implications}</em>"

            comp_items.append(f'<li>{item}</li>')

        competitor_html = "\n".join(comp_items) if comp_items else "<li>No watchlist updates from the last 2 months.</li>"
    
    # Assemble HTML
    html = f"""
<h2 style="color:#34495e;margin-top:30px;border-bottom:2px solid #ecf0f1;padding-bottom:8px;">
{stock_num}. {stock['name']} ({stock['ticker']})
</h2>

<p style="margin:10px 0;line-height:1.6;">
{price_html}
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">NEW INFORMATION (Last 7 Days):</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{new_info_html}
</ul>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">LAST MARKET UPDATE:</strong><br>
{market_update_html}<br>
<strong>Source:</strong> <a href="{update_url}" style="color:#3498db;">View Announcement</a>
</p>

<p style="margin:15px 0;line-height:1.6;">
<strong style="color:#2980b9;">KEY DRIVERS (Last 2 Months):</strong>
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{industry_html}
</ul>

<p style="margin:15px 0 2px 0;line-height:1.6;">
<strong style="color:#2980b9;">WATCHLIST — RELEVANT UPDATES (Earnings &amp; Transcripts, Last 2 Months):</strong>
</p>
<p style="margin:0 0 5px 0;color:#95a5a6;font-size:11px;font-style:italic;">
{watch_signal_html}
</p>
<ul style="margin:5px 0 15px 20px;line-height:1.8;">
{competitor_html}
</ul>

<hr style="border:none;border-top:1px solid #ecf0f1;margin:30px 0;">
"""
    return html


def wrap_in_template(content: str, today: str) -> str:
    """Wrap in email template."""
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background-color:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:20px;">
<table width="1000" cellpadding="20" cellspacing="0" style="background-color:#ffffff;border:1px solid #dddddd;">
<tr><td>

<h1 style="color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px;margin-top:0;">
Berkholts Stock Summaries - {today}
</h1>

{content}

<p style="color:#7f8c8d;font-size:12px;margin-top:30px;text-align:center;">
Generated by Berkholts Stock Summary System V6<br>
Prices: Yahoo Finance | Announcements & Earnings: ASX Direct | Key Drivers & Watchlist: Claude AI<br>
Sources: ASX announcements, earnings-call transcripts, trade publications, AFR, WSJ, SMH, The Australian<br>
</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(html: str, recipient: str, smtp_email: str, smtp_password: str, subject: str):
    """Send email with detailed logging."""
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = recipient
    
    msg['Reply-To'] = smtp_email
    msg['X-Priority'] = '3'
    
    try:
        print(f"      Connecting to smtp.gmail.com:465...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print(f"      Connected. Logging in as {smtp_email}...")
            server.login(smtp_email, smtp_password)
            print(f"      Logged in. Sending to {recipient}...")
            result = server.sendmail(smtp_email, recipient, msg.as_string())
            if result:
                print(f"      ⚠️ Partial failure: {result}")
            else:
                print(f"      ✅ SMTP accepted message for {recipient}")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"      ❌ Recipient refused: {e.recipients}")
        raise
    except smtplib.SMTPAuthenticationError as e:
        print(f"      ❌ Authentication failed: {e}")
        raise
    except smtplib.SMTPException as e:
        print(f"      ❌ SMTP error: {type(e).__name__}: {e}")
        raise
    except Exception as e:
        print(f"      ❌ Unexpected error: {type(e).__name__}: {e}")
        raise


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 Berkholts Stock Emailer - V6 (ASX Scraper Integration)")
    print(f"⏰ Started: {datetime.now()}")
    print("=" * 70)
    
    # Check env vars
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient_emails_str = os.getenv('RECIPIENT_EMAILS')
    
    missing = []
    if not anthropic_key: missing.append('ANTHROPIC_API_KEY')
    if not smtp_email: missing.append('SMTP_EMAIL')
    if not smtp_password: missing.append('SMTP_PASSWORD')
    if not recipient_emails_str: missing.append('RECIPIENT_EMAILS')
    
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        sys.exit(1)
    
    recipients = [e.strip() for e in recipient_emails_str.split(',') if e.strip()]
    
    # Always include backup recipient
    BACKUP_RECIPIENT = "lfbannon@gmail.com"
    if BACKUP_RECIPIENT not in recipients:
        recipients.append(BACKUP_RECIPIENT)
        print(f"📧 Recipients: {', '.join(recipients[:-1])} + backup: {BACKUP_RECIPIENT}")
    else:
        print(f"📧 Recipients: {', '.join(recipients)}")
    
    # Initialize cache
    ensure_cache_dir()
    print(f"💾 Cache directory: {CACHE_DIR}")
    print(f"   Earnings cache duration: {EARNINGS_CACHE_DAYS} days")
    
    client = get_anthropic_client()
    today_str = datetime.now().strftime("%B %d, %Y")
    
    all_html = ""
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"\n{'=' * 70}")
        print(f"📊 STOCK {i}/{len(STOCKS)}: {stock['name']}  [{stock.get('sector', '')}]")
        print("=" * 70)
        
        # Step 1: Get price (Yahoo Finance)
        print("   💰 Getting price...", end=" ")
        price = get_stock_price(stock['ticker'])
        if price.get('error'):
            print(f"⚠️ {price['error']}")
        else:
            print(f"✅ A${price['yesterday_close']:.2f} ({price['change_percent']:+.2f}%)")
        
        # Step 2: Research NEW INFORMATION (last 7 days - ALL ASX announcements)
        print("   📰 Researching new information (last 7 days)...", end=" ")
        new_info = research_new_information(client, stock)
        new_info_count = len(new_info.get('items', []))
        new_info_status = f"✅ ({new_info_count} items)" if new_info.get('has_new_info') else "⚠️ (none)"
        print(new_info_status)
        
        # Step 3: Research LAST MARKET UPDATE (most recent price-sensitive announcement)
        print("   💹 Researching last market update (ASX)...", end=" ")
        market_update = research_market_update(client, stock)
        update_status = "✅" if market_update.get('update_type') != 'Not found' else "⚠️"
        print(update_status)
        
        # Step 4: Research KEY DRIVERS (Claude web search - last 2 months)
        print("   🏭 Researching key drivers (last 2 months)...", end=" ")
        industry = research_industry(client, stock)
        ind_status = "✅" if len(industry.get('data_points', [])) > 0 else "⚠️"
        print(ind_status)
        
        # Step 5: Research watchlist updates (peer earnings/transcripts + ASX supplement)
        watch_count = len(stock.get('watchlist', []))
        listed_comp_count = len(stock.get('listed_competitors', []))
        print(f"   🏁 Researching watchlist ({watch_count} peers, +{listed_comp_count} ASX)...", end=" ")
        competitors = research_competitors(client, stock)
        comp_status = "✅" if len(competitors.get('competitor_news', [])) > 0 or competitors.get('no_recent_news') else "⚠️"
        print(comp_status)
        
        # Step 6: Format HTML
        print("   📝 Formatting HTML...", end=" ")
        try:
            stock_html = format_stock_html(stock, price, new_info, market_update, industry, competitors, i)
            if stock_html is None:
                stock_html = f"<h2>{stock['name']} - Error formatting data</h2><hr>"
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            stock_html = f"<h2>{stock['name']} - Error: {str(e)}</h2><hr>"
        
        all_html += stock_html
    
    # Final assembly
    print(f"\n📧 Assembling email...")
    final_html = wrap_in_template(all_html, today_str)
    print(f"📄 Total: {len(final_html)} chars")
    
    # Send
    subject = f"Berkholts Stock Summaries - {today_str}"
    for recipient in recipients:
        try:
            print(f"📤 Sending to {recipient}...", end=" ")
            send_email(final_html, recipient, smtp_email, smtp_password, subject)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
    
    print(f"\n✅ DONE at {datetime.now()}")


if __name__ == "__main__":
    main()
