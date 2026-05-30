"""Weekly AI & tech research agent (web-search powered).

Researches the most significant AI / LLM / data-engineering / GPU-serving /
startup developments from the last 7 days and returns a concise, scannable
Markdown briefing with source links.
"""

from __future__ import annotations

from datetime import date

from agents import Agent, Runner, WebSearchTool

import config
from garmin.config import GarminConfig  # noqa: F401  (triggers .env load)


def _topics_block() -> str:
    """Render the configured topics (config.TECH_TOPICS) into the instructions."""
    lines = []
    for i, topic in enumerate(config.TECH_TOPICS, 1):
        sources = ", ".join(topic.get("sources", []))
        lines.append(f"{i}. {topic['title']} — {topic['focus']}")
        if sources:
            lines.append(f"   Example sources (go beyond these): {sources}.")
    return "\n".join(lines)


def _output_format_block() -> str:
    """The exact section headings the briefing must use (from config.TECH_TOPICS)."""
    parts = []
    for topic in config.TECH_TOPICS:
        parts.append(f"## {topic['title']}\n1. ...\n2. ...")
    return "\n\n".join(parts)


def _instructions() -> str:
    return f"""\
You are an elite AI and Tech research weekly analyst. You search the web for and
research the most significant tech engineering updates from the past 7 days, then
summarize them shortly for a senior engineering leader.

CRITICAL DIRECTION: The technologies, companies, and libraries listed under each
topic are JUST EXAMPLES to show scope. Do NOT restrict yourself to them. Your main
value is discovering novel frameworks, unexpected inventions, and cutting-edge
subtopics an expert engineering lead might not already know about.

Use the web_search tool aggressively — run several searches per topic, prefer
primary/official sources, and only report items genuinely from the LAST 7 DAYS.
Never invent items or links; every bullet must cite a real source URL you found.

Research these topics:

{_topics_block()}

OUTPUT FORMAT — return GitHub-flavored Markdown ONLY (no HTML, no preamble, no
closing remarks). Use exactly these section headings, in this order:

{_output_format_block()}

Rules:
- Each bullet = a number, then a MAXIMUM of ONE clear, technical, impact-driven
  sentence, then EXACTLY ONE inline Markdown source link (the best primary
  source) in parentheses — never duplicate the same link.
- 3-5 bullets per topic. Bold company names, libraries, and new terms.
- Before concluding a topic is quiet, run more specific searches. Only state
  nothing was found if focused searches truly return nothing from the last 7 days.
- Keep it highly technical, concise, and scannable. No fluff.
"""


def build_tech_agent() -> Agent:
    return Agent(
        name="Weekly Tech Analyst",
        instructions=_instructions(),
        model=config.MODEL,
        tools=[WebSearchTool(search_context_size="high")],
    )


def generate_tech_report(today: date | None = None) -> str:
    """Run the tech research agent and return the Markdown briefing."""
    today = today or date.today()
    agent = build_tech_agent()
    prompt = (
        f"You are running on {today.strftime('%A, %B %d, %Y')}. Research and "
        "summarize the most significant tech engineering updates from the past 7 "
        "days across all the topics. Follow the output format exactly."
    )
    result = Runner.run_sync(agent, prompt, max_turns=24)
    return result.final_output
