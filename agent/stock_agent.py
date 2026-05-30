"""Stock research agent (web-search powered).

Scans the watch-list in ``config.STOCKS`` and, for each ticker, researches recent
news, the latest earnings report, key finance metrics, and similar companies.
Then it recommends the top-N stocks worth researching further.

Reliable fan-out design: each ticker is researched in its own focused,
web-search-only agent run, in parallel — a single combined run tends to truncate
after the first couple of tickers.
"""

from __future__ import annotations

import asyncio

from agents import Agent, Runner, WebSearchTool

import config
from garmin.config import GarminConfig  # noqa: F401  (triggers .env load)

_SPOTLIGHT_INSTRUCTIONS = """\
You are an equity research analyst. You research ONE stock and write a concise
spotlight for it. You MUST use the web_search tool — do not answer from memory.
Run a few targeted searches: recent news, the latest earnings report, key
financial metrics, and close peers/competitors.

ABSOLUTE RULES ON SOURCES:
- Every link MUST be a real URL that web_search actually returned. Copy it verbatim.
- NEVER use placeholder links (no example.com, no "https://...", no made-up URLs).
  If you found no real source for a point, omit the link and write "(no source found)".
- Never fabricate prices, metrics, earnings, or news. Write "could not verify" if
  you cannot confirm something.

OUTPUT — return ONLY this Markdown block (no preamble, no other sections):

### <TICKER> — <company name>
1. **News:** one sentence on the most recent, interesting development. ([source](REAL_URL))
2. **Earnings:** one-line summary of the latest reported quarter (revenue, EPS, surprise). ([source](REAL_URL))
3. **Metrics:** the key figures you verified (e.g. P/E, revenue growth, margins, guidance).
4. **Similar companies:** 1-2 peers and a few words why.

Use the real URLs from web_search in place of REAL_URL.
"""

_RECOMMEND_INSTRUCTIONS = """\
You are an equity strategist. You are given several researched stock spotlights.
Based ONLY on the information in them (catalysts, momentum, earnings strength,
valuation, news), recommend the {n} stocks most worth researching FURTHER.

You may recommend tickers from the spotlights or close peers mentioned within
them — but do not introduce facts that aren't supported by the spotlights.

OUTPUT — return ONLY Markdown starting with the heading:

## 🏆 Top {n} Stocks to Research Further
1. **<TICKER>** — one or two sentences on why it's worth a deeper look.
2. ...
(through {n})

End with exactly: "These are informational observations, not personalized financial advice."
"""


def build_stock_agent() -> Agent:
    """A single-stock research agent (web-search only)."""
    return Agent(
        name="Equity Research Analyst",
        instructions=_SPOTLIGHT_INSTRUCTIONS,
        model=config.MODEL,
        tools=[WebSearchTool(search_context_size="high")],
    )


def _recommend_agent() -> Agent:
    return Agent(
        name="Equity Strategist",
        instructions=_RECOMMEND_INSTRUCTIONS.format(n=config.TOP_STOCKS_TO_RECOMMEND),
        model=config.MODEL,
    )


async def _research_all(tickers: list[str]) -> list[str]:
    agent = build_stock_agent()
    sem = asyncio.Semaphore(config.RESEARCH_CONCURRENCY)

    async def one(ticker: str) -> str:
        prompt = (
            f"Research and write the spotlight for the stock with ticker {ticker}. "
            "Find the most recent news, latest earnings, key metrics, and peers."
        )
        async with sem:
            try:
                res = await Runner.run(agent, prompt, max_turns=12)
                return res.final_output.strip()
            except Exception as exc:  # noqa: BLE001
                return f"### {ticker}\n_Research unavailable: {exc}_"

    return await asyncio.gather(*(one(t) for t in tickers))


async def _recommend(spotlights: str) -> str:
    try:
        res = await Runner.run(_recommend_agent(), spotlights, max_turns=2)
        return res.final_output.strip()
    except Exception:  # noqa: BLE001
        return (f"## 🏆 Top {config.TOP_STOCKS_TO_RECOMMEND} Stocks to Research Further\n"
                "- See the spotlights above.\n\n"
                "These are informational observations, not personalized financial advice.")


async def _build_report_async(tickers: list[str]) -> str:
    blocks = await _research_all(tickers)
    spotlights = "\n\n".join(blocks)
    recommendations = await _recommend(spotlights)
    return f"## 🔎 Stock Spotlights\n\n{spotlights}\n\n{recommendations}"


def generate_stock_report(tickers: list[str] | None = None) -> str:
    """Research the watch-list and return the Markdown briefing + top-N picks."""
    tickers = tickers or config.STOCKS
    if not tickers:
        return "## 🔎 Stock Spotlights\n\n_No stocks configured in config.STOCKS._"
    return asyncio.run(_build_report_async(tickers))
