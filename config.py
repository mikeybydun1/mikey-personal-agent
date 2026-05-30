"""Central configuration for the Mikey Agent.

This is the single place to tune the agent's behavior and content. **Secrets**
(API keys, passwords) live in the gitignored ``.env`` file — never here. Anything
you might want to edit (the model, look-back windows, the tech-research topics
and their sources, and the stock watch-list) lives here.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=False)

# --------------------------------------------------------------------------- #
# Model — used by every agent. Override with OPENAI_MODEL in .env if desired.
# --------------------------------------------------------------------------- #
MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Parallelism for per-item web-search agents (stock research fan-out).
RESEARCH_CONCURRENCY: int = 4


# --------------------------------------------------------------------------- #
# Garmin health report — look-back windows (in days)
# --------------------------------------------------------------------------- #
GARMIN_RUNNING_DAYS: int = 30
GARMIN_SLEEP_DAYS: int = 14
GARMIN_GENERAL_DAYS: int = 14


# --------------------------------------------------------------------------- #
# Weekly tech briefing — topics the analyst researches.
# Edit / add topics freely. Each topic becomes one section of the briefing.
#   title:   the section heading shown in the email
#   focus:   what the analyst should look for
#   sources: example sources to check (the analyst is told to go beyond these)
# --------------------------------------------------------------------------- #
TECH_TOPICS: list[dict] = [
    {
        "title": "🤖 Agent Frameworks & LLMs",
        "focus": (
            "AI models, AI agents, agentic coding, foundational LLM research, core "
            "ecosystem releases (Anthropic, OpenAI, DeepSeek, Google, Meta, Mistral, "
            "Hugging Face, LangChain), and emerging open-source projects / dev tools."
        ),
        "sources": [
            "Anthropic News", "OpenAI Research", "Google Research Blog",
            "NVIDIA Blog", "Hugging Face Blog", "LangChain Blog",
        ],
    },
    {
        "title": "🛢️ Data Engineering",
        "focus": (
            "stream/batch ecosystems and lakehouse tech: Apache Iceberg, Flink, "
            "Spark, Kafka, Polars, DuckDB, Databricks. New features and major releases."
        ),
        "sources": [
            "Apache Flink Blog", "Databricks Blog", "Polars Blog",
            "Confluent Blog", "Netflix Tech Blog", "GitHub Trending",
        ],
    },
    {
        "title": "🚀 Startup Ecosystem & Exits",
        "focus": (
            "acquisitions, mergers, major funding rounds, scale milestones, new "
            "product launches. Strong weight on Israeli high-tech and cybersecurity, "
            "plus global AI / B2B SaaS / cyber / deep tech."
        ),
        "sources": ["CTech (Calcalist)", "Globes English", "TechCrunch", "VC portfolios"],
    },
    {
        "title": "⚡ GPU Optimization & Serving",
        "focus": (
            "hardware/runtime optimizations: torch.compile & kernel fusion, "
            "quantization (FP8, INT4, AWQ), TensorRT-LLM, Triton kernels, vLLM / "
            "SGLang serving, and low-level acceleration libraries."
        ),
        "sources": [
            "PyTorch Blog", "NVIDIA Developer Blog", "vLLM releases",
            "hardware engineering research papers",
        ],
    },
]


# --------------------------------------------------------------------------- #
# Stock research — the watch-list the stock agent scans every run.
# Use the ticker symbols (e.g. Vertiv = VRT, Arista = ANET). Edit freely.
# --------------------------------------------------------------------------- #
STOCKS: list[str] = ["META", "AMZN", "NVDA", "VRT", "ANET", "PLTR", "MSFT"]

# How many stocks the agent should recommend researching further.
TOP_STOCKS_TO_RECOMMEND: int = 5
