# Marketing Insights

A collection of **agentic AI projects** for marketing automation and agent-driven insights. Each project demonstrates a different aspect of using AI agents — built on Google Cloud — to generate personalized content, optimize campaigns, and drive data-informed marketing decisions.

## Projects

| Project | Description | Agent Framework | Models | Data Layer | Key Capabilities |
|---------|-------------|-----------------|--------|------------|-------------------|
| [**rewe-agent**](./rewe-agent/) | Personalized SEO blog generation for REWE grocery retail. Produces blog posts with AI images and semantically-matched product recommendations from a 10K+ catalog. | [Google ADK](https://adk.dev/) | Gemini 3.1 Pro, Gemini 3 Flash, Gemini 3.1 Flash Image | BigQuery, VECTOR_SEARCH, `text-embedding-004` | Customer 360 personalization · SEO keyword generation · Category-diverse vector search · AI image generation · Dietary safety validation · Cross-session memory |

## Repository Structure

```
marketing-insights/
├── rewe-agent/          # REWE Marketing Agent (ADK + Agent Engine)
├── main.py              # Shared entry point
├── pyproject.toml       # Root project config
└── README.md            # This file
```

## Getting Started

Each project has its own README with setup instructions. Navigate to the project directory and follow the Quick Start guide:

```bash
cd rewe-agent
agents-cli install
agents-cli playground
```

## Tech Stack

All projects in this repository share a common foundation on **Google Cloud**:

- **Agent Frameworks** — [Google ADK](https://adk.dev/), Vertex AI Agent Engine
- **LLMs** — Gemini model family (Pro, Flash, Image)
- **Data** — BigQuery, BigQuery ML, VECTOR_SEARCH
- **Deployment** — Vertex AI Reasoning Engine, Cloud Run
- **Evaluation** — Vertex AI Gen AI Evaluation SDK
- **Observability** — Cloud Trace, Cloud Logging
