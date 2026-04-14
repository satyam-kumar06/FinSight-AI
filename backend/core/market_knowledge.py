import logging
from typing import List, Dict
from core.embeddings import store_in_collection, get_chroma_client
import os

MARKET_COLLECTION = "market_knowledge"

KNOWLEDGE_BASE = [
    # INDICATORS
    {
        "id": "indicator_nifty50",
        "category": "indicator",
        "name": "Nifty 50",
        "plain_explanation": "The Nifty 50 is India's main stock market index that tracks the performance of the 50 largest and most actively traded companies listed on the National Stock Exchange. It represents about 65% of the total market capitalization of all companies listed on the NSE. Companies in this index come from various sectors like banking, IT, energy, and consumer goods. The index value changes based on the stock prices of these companies, going up when most stocks rise and down when they fall.",
        "why_it_matters": "For regular investors, the Nifty 50 serves as a benchmark to measure how their investment portfolio is performing compared to the overall market. When the Nifty rises, it often indicates positive economic conditions that can benefit most investors' holdings.",
        "historical_example": "During the COVID-19 market crash in March 2020, the Nifty 50 fell by about 40% from its peak, but recovered strongly by the end of 2020, reaching new highs as economic activity resumed."
    },
    {
        "id": "indicator_sp500",
        "category": "indicator",
        "name": "S&P 500",
        "plain_explanation": "The S&P 500 is America's primary stock market index that includes the 500 largest companies listed on stock exchanges in the United States. These companies represent leading businesses across all major industries and account for about 80% of the total value of the U.S. stock market. The index is weighted by market capitalization, meaning larger companies have more influence on the index value. It provides a broad view of how the U.S. economy is performing through corporate earnings and stock performance.",
        "why_it_matters": "Indian investors often watch the S&P 500 because global economic trends and U.S. company performance can influence Indian markets and the rupee value. A strong S&P 500 often signals global economic health that can benefit emerging markets like India.",
        "historical_example": "In the 2008 financial crisis, the S&P 500 lost about 57% of its value from October 2007 to March 2009, but has since recovered and reached new highs, demonstrating the market's long-term upward trend despite major setbacks."
    },
    {
        "id": "indicator_vix",
        "category": "indicator",
        "name": "VIX / India VIX",
        "plain_explanation": "The VIX, also called the fear index, measures how much investors expect stock market volatility over the next 30 days. A high VIX reading suggests investors are worried about potential large price swings, while a low reading indicates calm market conditions. The India VIX works similarly but focuses on expected volatility in the Indian market. These indicators are calculated using options prices on major indices.",
        "why_it_matters": "For regular investors, a rising VIX often signals it's time to be more cautious with investments, while a falling VIX suggests more stable conditions for investing. High volatility periods typically bring more investment risk.",
        "historical_example": "During the early days of the COVID-19 pandemic in March 2020, the VIX spiked to over 80, its highest level since the 2008 crisis, reflecting extreme market fear before gradually declining as conditions stabilized."
    },
    {
        "id": "indicator_pe_ratio",
        "category": "indicator",
        "name": "P/E Ratio",
        "plain_explanation": "The Price-to-Earnings ratio compares a company's stock price to its earnings per share, showing how much investors are willing to pay for each rupee of company profit. A high P/E suggests investors expect strong future growth, while a low P/E might indicate the stock is undervalued or facing challenges. Different industries have different typical P/E ranges based on their growth prospects and risk levels.",
        "why_it_matters": "Regular investors use P/E ratios to identify potentially overvalued or undervalued stocks. Extremely high P/E stocks might be risky if earnings don't grow as expected, while low P/E stocks could offer good buying opportunities.",
        "historical_example": "During the dot-com bubble in 2000, many technology stocks had P/E ratios over 100 as investors paid exorbitant prices for expected future growth, but when earnings didn't materialize, stock prices crashed dramatically."
    },
    {
        "id": "indicator_moving_average",
        "category": "indicator",
        "name": "Moving Average (50-day, 200-day)",
        "plain_explanation": "Moving averages smooth out daily stock price fluctuations by calculating the average price over a specific number of days. The 50-day moving average shows the average price over the last 50 trading days, while the 200-day shows the average over 200 days. When a stock's price crosses above its moving average, it can signal an uptrend, and crossing below can signal a downtrend.",
        "why_it_matters": "For regular investors, moving averages help identify the overall direction of stock price trends rather than getting caught up in daily noise. The 200-day moving average is particularly important as a long-term trend indicator.",
        "historical_example": "In 2018, when the Nifty 50 fell below its 200-day moving average, it signaled a major downtrend that lasted several months before the market recovered above that level."
    },
    {
        "id": "indicator_macd",
        "category": "indicator",
        "name": "MACD",
        "plain_explanation": "MACD, or Moving Average Convergence Divergence, shows the relationship between two moving averages of a stock's price. It consists of the MACD line (difference between 12-day and 26-day exponential moving averages) and a signal line (9-day moving average of the MACD line). When the MACD line crosses above the signal line, it suggests buying momentum, and crossing below suggests selling momentum.",
        "why_it_matters": "Regular investors use MACD to identify changes in a stock's momentum and potential trend reversals. It's particularly useful for timing entries and exits in trending markets.",
        "historical_example": "During the 2020 market recovery, MACD crossovers on the Nifty 50 provided early signals of the strong upward momentum that lasted through 2021."
    },
    {
        "id": "indicator_rsi",
        "category": "indicator",
        "name": "RSI",
        "plain_explanation": "The Relative Strength Index measures the speed and magnitude of price changes on a scale from 0 to 100. Readings above 70 suggest a stock might be overbought and due for a price decline, while readings below 30 suggest it might be oversold and due for a price increase. It's calculated using the average gains and losses over 14 days.",
        "why_it_matters": "For regular investors, RSI helps identify when stocks might be getting too expensive (overbought) or too cheap (oversold), providing potential timing signals for buying or selling.",
        "historical_example": "In early 2022, many technology stocks showed RSI readings above 70 during their peak, followed by significant price declines as the market corrected."
    },
    {
        "id": "indicator_bond_yield",
        "category": "indicator",
        "name": "Bond Yield (10-year G-Sec)",
        "plain_explanation": "The 10-year Government Security yield represents the interest rate the government pays on its 10-year bonds. It serves as a benchmark for all other borrowing costs in the economy. When yields rise, it becomes more expensive for companies and individuals to borrow money, and when yields fall, borrowing becomes cheaper.",
        "why_it_matters": "Regular investors watch bond yields because they influence interest rates on loans, fixed deposits, and can signal economic expectations. Rising yields often pressure stock markets as borrowing costs increase.",
        "historical_example": "In 2018, when the 10-year G-Sec yield rose above 8%, it contributed to a broader market sell-off as investors worried about higher borrowing costs affecting corporate profits."
    },
    {
        "id": "indicator_fii_dii_flow",
        "category": "indicator",
        "name": "FII/DII Flow",
        "plain_explanation": "FII (Foreign Institutional Investor) flow tracks money coming in or going out of Indian markets from overseas investors like mutual funds and pension funds. DII (Domestic Institutional Investor) flow tracks similar activity from Indian institutions. Positive flows indicate buying activity while negative flows indicate selling. These flows are reported weekly and monthly.",
        "why_it_matters": "For regular investors, strong FII buying often supports market rallies, while heavy selling can pressure prices. DII flows show domestic investor confidence in the market.",
        "historical_example": "During the 2020 COVID crisis, FIIs sold heavily in March, contributing to the market crash, but their return in April-May helped fuel the subsequent recovery."
    },
    {
        "id": "indicator_advance_decline",
        "category": "indicator",
        "name": "Advance/Decline Ratio",
        "plain_explanation": "The Advance/Decline ratio compares the number of stocks that closed higher (advancing) versus those that closed lower (declining) on a given day. A ratio above 1 means more stocks rose than fell, indicating broad market strength, while below 1 suggests weakness. It's calculated by dividing the number of advancing stocks by declining stocks.",
        "why_it_matters": "Regular investors use this ratio to gauge whether market movements are broad-based or concentrated in a few stocks. A high advance/decline ratio during a market decline suggests the downturn might be short-lived.",
        "historical_example": "In the 2008 crisis, the advance/decline ratio on the NSE stayed low for months, confirming the broad-based nature of the market decline."
    },
    # EVENTS
    {
        "id": "event_rbi_repo_rate",
        "category": "event",
        "name": "RBI Repo Rate Decision",
        "plain_explanation": "The RBI's repo rate is the interest rate at which banks can borrow money from the central bank for short periods. When the RBI changes this rate, it affects the cost of borrowing throughout the economy. A rate cut makes loans cheaper, encouraging spending and investment, while a rate hike makes borrowing more expensive to control inflation.",
        "why_it_matters": "For regular investors, repo rate changes directly impact fixed deposit rates, home loan EMIs, and stock market sentiment. Rate cuts often boost stock prices while rate hikes can pressure them.",
        "historical_example": "In May 2020, the RBI cut repo rates by 40 basis points to 4% to combat COVID-19 economic impact, which helped revive stock markets and made borrowing cheaper for consumers."
    },
    {
        "id": "event_us_fed_rate",
        "category": "event",
        "name": "US Fed Rate Decision",
        "plain_explanation": "The US Federal Reserve's interest rate decisions affect global liquidity and risk appetite. When the Fed raises rates, it can attract investment dollars to the US, strengthening the dollar and potentially hurting emerging markets. When rates are cut, money flows to higher-yielding markets like India.",
        "why_it_matters": "Indian investors feel the impact through rupee value changes and FII investment flows. Fed rate hikes often pressure Indian markets and the rupee, while cuts bring relief.",
        "historical_example": "In December 2015, when the Fed raised rates for the first time in nearly a decade, emerging markets including India saw significant outflows and rupee depreciation."
    },
    {
        "id": "event_cpi_inflation",
        "category": "event",
        "name": "CPI Inflation Data",
        "plain_explanation": "CPI measures changes in the prices of everyday goods and services that consumers buy. It tracks inflation by comparing current prices to prices from a year ago. High inflation means money buys less, while low inflation suggests stable purchasing power. The RBI uses CPI data to decide on interest rate changes.",
        "why_it_matters": "For regular investors, high inflation erodes investment returns and can lead to higher interest rates that pressure stock markets. It also affects the real value of savings and fixed income investments.",
        "historical_example": "In 2013, CPI inflation peaked at 11.2%, leading the RBI to raise rates aggressively, which contributed to a slowdown in economic growth and market performance."
    },
    {
        "id": "event_quarterly_earnings",
        "category": "event",
        "name": "Quarterly Earnings Season",
        "plain_explanation": "Every three months, companies release their financial results showing profits, revenues, and business performance. This period is called earnings season and typically lasts 6-8 weeks. Investors compare actual results to expectations, and stock prices move based on whether companies beat, meet, or miss analyst forecasts.",
        "why_it_matters": "Regular investors should be cautious during earnings season as stock prices can be volatile. Positive surprises often lead to price increases, while disappointments cause declines.",
        "historical_example": "In Q1 2020 earnings season, many companies reported COVID-19 impacts, leading to significant stock price declines, but Q3 2020 showed recovery with better-than-expected results driving rallies."
    },
    {
        "id": "event_union_budget",
        "category": "event",
        "name": "Union Budget",
        "plain_explanation": "The annual Union Budget outlines the government's income, spending plans, and economic policies for the coming year. It includes tax changes, sector-specific allocations, and infrastructure spending plans. The budget speech by the Finance Minister explains these plans and their expected economic impact.",
        "why_it_matters": "For regular investors, budget announcements can create opportunities in favored sectors while challenging others. Tax changes directly affect personal finances and investment decisions.",
        "historical_example": "In Budget 2021, increased infrastructure spending boosted construction and related stocks, while changes in capital gains tax affected long-term investment strategies."
    },
    {
        "id": "event_fii_flow_events",
        "category": "event",
        "name": "FII Outflow/Inflow Events",
        "plain_explanation": "FII flows represent money moving in or out of Indian markets by foreign investors. Large outflows occur when foreign investors sell Indian assets, often due to global events or local concerns. Inflows happen when they buy more Indian investments. These flows are tracked daily and can be influenced by global economic conditions, interest rate differentials, and market sentiment.",
        "why_it_matters": "Regular investors experience the impact through market volatility and rupee fluctuations. Heavy outflows can depress stock prices, while inflows support market rallies.",
        "historical_example": "In August 2013, during the 'taper tantrum' when the US Fed signaled rate hikes, FIIs pulled out $4 billion in one month, causing the rupee to depreciate 15% and markets to fall sharply."
    },
    {
        "id": "event_crude_oil_shock",
        "category": "event",
        "name": "Crude Oil Price Shock",
        "plain_explanation": "Crude oil price shocks occur when oil prices change dramatically due to supply disruptions, demand changes, or geopolitical events. High oil prices increase import costs for India, which imports most of its oil needs. This affects inflation, the current account deficit, and rupee value.",
        "why_it_matters": "For regular investors, oil shocks impact transportation, energy, and inflation-sensitive sectors. High oil prices can hurt airline and consumer goods stocks while benefiting energy companies.",
        "historical_example": "In 2008, oil prices peaked at $147 per barrel, contributing to high inflation and a severe economic slowdown in India, with the Sensex falling over 50% that year."
    },
    {
        "id": "event_currency_depreciation",
        "category": "event",
        "name": "Currency Depreciation (INR/USD)",
        "plain_explanation": "Currency depreciation means the rupee loses value against the US dollar, making imports more expensive and exports cheaper. This happens due to factors like trade deficits, interest rate differentials, or global events. A weaker rupee increases the cost of imported goods but helps exporters compete internationally.",
        "why_it_matters": "Regular investors see impact through higher prices for imported goods and potential benefits for IT and export-oriented companies. Currency moves also affect returns on foreign investments.",
        "historical_example": "In 2018, the rupee depreciated from 63 to 74 against the dollar due to rising oil prices and trade tensions, increasing import costs and contributing to higher inflation."
    },
    {
        "id": "event_geopolitical_events",
        "category": "event",
        "name": "Geopolitical Events",
        "plain_explanation": "Geopolitical events include international conflicts, trade wars, elections, or diplomatic tensions that affect global markets. These events create uncertainty and can lead investors to move money to safer assets. In India, such events often affect oil prices, currency stability, and foreign investment flows.",
        "why_it_matters": "For regular investors, geopolitical uncertainty typically leads to market volatility and risk-off sentiment, with investors favoring gold and government bonds over stocks.",
        "historical_example": "During the Russia-Ukraine conflict in 2022, oil prices spiked and global markets fell, with Indian markets dropping 5-10% before recovering as the situation stabilized."
    },
    {
        "id": "event_credit_rating_change",
        "category": "event",
        "name": "Credit Rating Change",
        "plain_explanation": "Credit rating agencies like S&P, Moody's, and Fitch assess country's creditworthiness and assign ratings. A rating upgrade improves investor confidence and can lower borrowing costs, while a downgrade increases costs and may trigger FII outflows. India's rating affects how international investors view the country's economic stability.",
        "why_it_matters": "Regular investors feel the impact through changes in government bond yields and FII investment patterns. Rating changes can influence market sentiment and currency stability.",
        "historical_example": "In 2012, when S&P downgraded India's rating from stable to negative, it led to FII outflows and rupee depreciation, though the market impact was relatively contained."
    },
    # INSTRUMENTS
    {
        "id": "instrument_equity_shares",
        "category": "instrument",
        "name": "Equity Shares (Stocks)",
        "plain_explanation": "Equity shares represent ownership in a company, giving shareholders a claim on the company's profits and assets. When you buy shares, you become a part-owner and can receive dividends if the company distributes profits. Stock prices change based on company performance, economic conditions, and investor sentiment. Different types of shares exist, including preference shares with fixed dividends.",
        "why_it_matters": "For regular investors, stocks offer potential for long-term wealth creation through capital appreciation and dividends, but come with the risk of losing money if the company performs poorly.",
        "historical_example": "Reliance Industries shares, which cost about ₹100 in 1990, have grown to over ₹2,500 by 2023, creating significant wealth for long-term investors despite market volatility."
    },
    {
        "id": "instrument_government_bonds",
        "category": "instrument",
        "name": "Government Bonds (G-Secs)",
        "plain_explanation": "Government bonds are debt instruments issued by the central government to borrow money for public spending. They pay regular interest and return the principal amount at maturity. G-Secs are considered the safest investment as they're backed by the government. Different maturities exist, from short-term (1-3 years) to long-term (10-30 years).",
        "why_it_matters": "Regular investors use government bonds for stable income and capital preservation, especially during market uncertainty. They serve as a benchmark for other interest rates in the economy.",
        "historical_example": "During the 2008 crisis, investors flocked to government bonds, driving yields down and providing safe haven returns while stock markets crashed."
    },
    {
        "id": "instrument_corporate_bonds",
        "category": "instrument",
        "name": "Corporate Bonds / Debentures",
        "plain_explanation": "Corporate bonds are debt instruments issued by companies to raise capital for business expansion. They pay fixed or floating interest rates and return principal at maturity. Debentures are unsecured bonds backed only by the company's creditworthiness. Bond ratings from agencies indicate the risk level, with AAA being the safest and lower ratings carrying higher risk.",
        "why_it_matters": "For regular investors, corporate bonds offer higher interest rates than government bonds but come with credit risk if the company defaults. They're suitable for income-focused investors willing to accept some risk.",
        "historical_example": "In 2019, when IL&FS defaulted on its bonds, investors lost significant amounts, highlighting the credit risk in corporate bonds despite their attractive yields."
    },
    {
        "id": "instrument_etfs",
        "category": "instrument",
        "name": "ETFs (Exchange Traded Funds)",
        "plain_explanation": "ETFs are investment funds that hold a collection of assets like stocks or bonds and are traded on stock exchanges like individual shares. They provide diversification by investing in multiple companies or sectors at once. Index ETFs track market indices, while thematic ETFs focus on specific sectors or strategies. ETF prices change throughout the trading day based on supply and demand.",
        "why_it_matters": "Regular investors use ETFs for easy diversification and lower costs compared to mutual funds. They're ideal for beginners wanting exposure to broad markets without picking individual stocks.",
        "historical_example": "The Nifty 50 ETF has grown significantly since its launch in 2010, providing investors with returns closely tracking the index while offering liquidity and low costs."
    },
    {
        "id": "instrument_index_mutual_funds",
        "category": "instrument",
        "name": "Index Mutual Funds",
        "plain_explanation": "Index mutual funds are investment pools that aim to replicate the performance of a specific market index like the Nifty 50 or Sensex. They buy the same stocks in the same proportions as the index. Unlike actively managed funds, they don't try to beat the market but match its performance. Investors buy and sell units at the end of each trading day at the net asset value (NAV).",
        "why_it_matters": "For regular investors, index funds offer low-cost, diversified exposure to the market with consistent long-term returns. They're suitable for passive investors who believe in market efficiency.",
        "historical_example": "Since 2000, index funds tracking the S&P 500 have delivered average annual returns of about 10%, outperforming most actively managed funds over long periods."
    },
    {
        "id": "instrument_active_mutual_funds",
        "category": "instrument",
        "name": "Active Mutual Funds",
        "plain_explanation": "Active mutual funds are professionally managed investment pools where fund managers select stocks, bonds, or other assets to try to outperform the market. They charge higher fees for the expertise and research involved. Fund performance depends on the manager's skill in timing markets and picking winners. Different categories exist like equity savings, balanced advantage, and sector-specific funds.",
        "why_it_matters": "Regular investors choose active funds hoping for higher returns than market indices, but they must be willing to pay higher fees and accept that most funds underperform their benchmarks over time.",
        "historical_example": "During the 2020 market crash, some active fund managers successfully reduced exposure to falling stocks, protecting investor capital better than passive index funds."
    },
    {
        "id": "instrument_futures_options",
        "category": "instrument",
        "name": "Futures and Options (Derivatives)",
        "plain_explanation": "Futures and options are derivative contracts that derive their value from underlying assets like stocks or indices. Futures obligate buyers and sellers to buy/sell the asset at a predetermined price on a future date. Options give the right (but not obligation) to buy (call) or sell (put) at a set price. These instruments are used for hedging risk or speculation.",
        "why_it_matters": "For regular investors, derivatives offer ways to hedge existing positions or potentially amplify returns, but they carry high risk of losses and are not suitable for beginners due to their complexity.",
        "historical_example": "In 2008, the collapse of derivative markets contributed to the global financial crisis, with losses running into trillions of dollars worldwide."
    },
    {
        "id": "instrument_reits",
        "category": "instrument",
        "name": "REITs (Real Estate Investment Trusts)",
        "plain_explanation": "REITs are companies that own, operate, or finance income-generating real estate like office buildings, malls, and apartments. They must distribute at least 90% of their taxable income as dividends to investors. REITs provide exposure to real estate without the hassle of direct property ownership. They trade on stock exchanges like regular shares.",
        "why_it_matters": "Regular investors use REITs for regular income through dividends and potential property value appreciation, offering an alternative to direct real estate investment with better liquidity.",
        "historical_example": "Indian REITs launched in 2019 have provided investors with double-digit dividend yields, making them attractive during periods of low interest rates."
    },
    {
        "id": "instrument_gold_etfs",
        "category": "instrument",
        "name": "Gold ETFs and Sovereign Gold Bonds",
        "plain_explanation": "Gold ETFs are investment funds that hold physical gold and are traded on stock exchanges. They provide an easy way to invest in gold without storing physical metal. Sovereign Gold Bonds are government-backed schemes where investors can buy gold bonds that pay interest and are redeemable in gold or cash. Both offer protection against inflation and currency fluctuations.",
        "why_it_matters": "For regular investors, gold investments serve as a hedge against economic uncertainty, inflation, and currency depreciation, though they don't provide regular income like dividends.",
        "historical_example": "During the COVID-19 crisis in 2020, gold prices rose 25%, providing strong returns for investors seeking safety amid market turmoil."
    },
    {
        "id": "instrument_fixed_deposits",
        "category": "instrument",
        "name": "Fixed Deposits (comparison context)",
        "plain_explanation": "Fixed deposits are savings accounts offered by banks where you deposit money for a fixed period (typically 1-5 years) and earn a guaranteed interest rate. The interest is compounded and paid at maturity or periodically. They're insured by the government up to certain limits and offer complete capital protection.",
        "why_it_matters": "Regular investors use FDs for risk-free returns and emergency funds, though inflation often erodes their real returns. They serve as a benchmark for comparing returns from riskier investments.",
        "historical_example": "During high inflation periods like 2013-2014, FD rates reached 9-10%, but have since fallen to 5-6% as interest rates declined, reducing their attractiveness compared to stocks."
    }
]

def initialize_market_knowledge():
    client = get_chroma_client()
    collection = client.get_or_create_collection(MARKET_COLLECTION)
    
    # Check if already loaded
    count = collection.count()
    if count > 0:
        logging.info(f"Market knowledge already loaded ({count} entries)")
        return
    
    # Build texts and metadatas
    texts = []
    metadatas = []
    
    for entry in KNOWLEDGE_BASE:
        text = f"{entry['name']}\n{entry['plain_explanation']}\nWhy it matters: {entry['why_it_matters']}\nHistorical example: {entry['historical_example']}"
        texts.append(text)
        metadatas.append({
            "id": entry["id"],
            "category": entry["category"],
            "name": entry["name"]
        })
    
    # Store in collection
    store_in_collection(texts, metadatas, MARKET_COLLECTION, "market")
    
    logging.info(f"Market knowledge base loaded: {len(texts)} entries")
