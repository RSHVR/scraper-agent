#!/usr/bin/env python3
"""OSINT research script - find comprehensive information about a person."""

import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import argparse
from src.agents.agentic_scraper import AgenticScraper

# ============================================================================
# CONFIGURATION - Edit these for your search
# ============================================================================

TARGET = {
    "name": "John Doe",  # Target's full name
    "known_usernames": ["johndoe", "jdoe123"],  # Known handles/usernames
    "known_employers": ["Acme Corp"],  # Current or past employers
    "known_schools": [],  # e.g., ["University of Toronto", "MIT"]
    "location": "",  # Optional location hint
    "notes": "",  # Any other hints
}

PROVIDER = "cohere"  # "claude", "cohere", "ollama", "huggingface"
MAX_ITERATIONS = 100

# ============================================================================
# RESEARCH PROMPT - Instructs agent to track findings and be exhaustive
# ============================================================================

RESEARCH_SYSTEM_PROMPT = """You are an OSINT research agent gathering comprehensive information about a person.

## CRITICAL: Track Your Findings
After EACH tool result, mentally maintain a running list of:
- CONFIRMED FACTS: Name, location, employer, job title, education, skills, contact info
- PROFILE URLs: All social/professional profiles found
- USERNAME PATTERNS: Common handles discovered
- STILL NEEDED: Information gaps to fill

## Identity Correlation
When you find a profile, confirm it's the right person by checking:
- Consistent username patterns across platforms
- Same employer/location/job title mentioned
- Bio text similarities
- Cross-references (LinkedIn mentions GitHub, etc.)

Once you're CONFIDENT a profile belongs to the target, mark it as CONFIRMED and extract FULL content.

## Research Strategy
1. Start with broad name search
2. When you find usernames, search for those specifically
3. When you find employers, search "person + employer"
4. For each CONFIRMED profile, use render_with_browser and extract ALL content
5. Don't stop at URLs - extract actual information (job history, skills, projects, contact info)

## IMPORTANT: Use Hybrid/Parallel Searches
You can call multiple tools in parallel - USE THIS to be efficient:
- Search multiple platforms at once: "username site:github.com", "username site:linkedin.com", "username site:twitter.com"
- Render multiple confirmed URLs in parallel with render_with_browser
- Extract content from multiple pages simultaneously

Example efficient search pattern:
- Call web_search("username github"), web_search("username linkedin"), web_search("username twitter") IN PARALLEL
- Then render_with_browser all confirmed URLs IN PARALLEL
- Then extract_content from all pages IN PARALLEL

## Exhaustive Platform Coverage - CHECK EVERY SINGLE ONE:
You MUST search for the target on ALL of these platforms. Do not skip any:
- LinkedIn, GitHub, Twitter/X, Facebook, Instagram
- Reddit, Discord, Telegram, Snapchat
- YouTube, TikTok, Twitch
- Medium, Substack, Dev.to, Hashnode
- Stack Overflow, HuggingFace, Kaggle
- Devpost, Product Hunt, AngelList
- Spotify, SoundCloud, Apple Music
- Steam, PlayStation Network, Xbox Live
- PayPal.me, Venmo, Cash App
- Gravatar, Gravatar, About.me, Linktree
- ZoomInfo, RocketReach, Apollo.io
- University/college/polytechnic websites, Google Scholar, ResearchGate

## Document Searches:
- Search "name filetype:pdf resume" to find resume PDFs
- Search "name filetype:pdf CV" for CVs
- Look for public Google Docs, Notion pages, or portfolio PDFs

## When to Stop
Only call save_result when you have:
1. Searched multiple query variations (name, usernames, employer combinations)
2. Rendered and extracted content from ALL confirmed profiles
3. Compiled a comprehensive profile with all available information

Do NOT stop just because you found some URLs. Extract the actual content."""

# ============================================================================
# GOAL TEMPLATE
# ============================================================================

def build_goal(target: dict) -> str:
    """Build the research goal from target config."""

    usernames = ", ".join(f'"{u}"' for u in target.get("known_usernames", []))
    employers = ", ".join(target.get("known_employers", []))
    schools = ", ".join(target.get("known_schools", []))

    return f'''Find comprehensive information about {target["name"]} online.

## Search Queries to Try:
- "{target["name"]}"
{f'- Known usernames: {usernames}' if usernames else ''}
{f'- Employer searches: "{target["name"]} {employers}"' if employers else ''}
{f'- School searches: "{target["name"]} {schools}"' if schools else ''}
{f'- Location hint: {target.get("location", "unknown")}' if target.get("location") else ''}
- Document search: "{target["name"]} filetype:pdf resume"
- Document search: "{target["name"]} filetype:pdf CV"
- Academic search: "{target["name"]} site:edu" or "{target["name"]} university OR college OR polytechnic"

## Platforms to Check:
1. LinkedIn - FULL profile (experience, education, skills, certifications)
2. GitHub - repositories, contributions, README files
3. Personal website - ALL pages (projects, about, blog, contact, resume)
4. Medium/Substack - blog posts
5. Devpost - hackathon projects
6. Twitter/X
7. YouTube
8. Stack Overflow
9. HuggingFace
10. Gravatar
11. Twine
12. ZoomInfo
13. RocketReach (rocketreach.co)
14. Reddit
15. Telegram
16. Snapchat
17. Spotify
18. PayPal.me
19. SoundCloud
20. Discord
21. Steam
22. PlayStation Network (PSN)
23. University/college/polytechnic websites (student directory, research, course projects)
24. News articles, podcasts, conference talks

## Document Searches:
- Search for PDFs: "{target["name"]} filetype:pdf resume"
- Search for CVs: "{target["name"]} filetype:pdf CV"
- Search for documents: "{target["name"]} filetype:doc OR filetype:docx"

## Instructions:
- For each CONFIRMED profile, use render_with_browser() to get full content
- Use extract_content() to pull structured data (not just raw HTML)
- Look for: email, phone, job history, education, skills, projects, social links
- Cross-reference information across platforms to confirm identity
- Do NOT stop early - exhaust all sources before compiling final report

{f'Additional context: {target.get("notes")}' if target.get("notes") else ''}'''


# ============================================================================
# MAIN
# ============================================================================

async def main(target: dict, provider: str, max_iterations: int):
    session_id = target["name"].lower().replace(" ", "-") + "-research"

    agent = AgenticScraper(
        session_id=session_id,
        provider=provider,
        max_iterations=max_iterations
    )

    # Override the system prompt for research mode
    from langgraph.prebuilt import create_react_agent
    def research_build(tools):
        from src.agents.agentic_scraper import logger
        logger.info("Using RESEARCH system prompt")
        return create_react_agent(
            model=agent.llm,
            tools=tools,
            prompt=RESEARCH_SYSTEM_PROMPT
        )
    agent._build_agent = research_build

    async def on_message(msg):
        msg_type = msg.get('type')
        iteration = msg.get('iteration', 0)
        if msg_type == 'tool_call':
            print(f"[{iteration}] 🔧 {msg.get('tool_name')}: {str(msg.get('tool_input', {}))[:100]}")
        elif msg_type == 'tool_result':
            data = msg.get('data', {})
            if isinstance(data, dict):
                preview = data.get('raw', str(data))[:150] if 'raw' in data else str(data)[:150]
            else:
                preview = str(data)[:150]
            print(f"[{iteration}] ✅ {preview}")
        elif msg_type == 'thought':
            text = msg.get('text', '')[:200]
            if text.strip() and len(text) > 30:
                print(f"[{iteration}] 💭 {text}")

    goal = build_goal(target)
    print(f"🔍 Researching: {target['name']}")
    print(f"📡 Provider: {provider}")
    print(f"🔄 Max iterations: {max_iterations}")
    print("=" * 70)

    result = await agent.run(goal=goal, on_message=on_message)

    print(f"\n{'='*70}")
    print(f"Status: {result.status}")
    print(f"Iterations: {result.iterations}")
    print(f"Cost: ${result.metrics.total_cost_usd:.4f}")
    print(f"{'='*70}")

    if result.data:
        import json
        print(f"\nData:\n{json.dumps(result.data, indent=2)[:3000]}")

    if result.message:
        print(f"\nFinal Report:\n{result.message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OSINT research on a person")
    parser.add_argument("--name", help="Target name")
    parser.add_argument("--usernames", help="Known usernames (comma-separated)")
    parser.add_argument("--employers", help="Known employers (comma-separated)")
    parser.add_argument("--schools", help="Known schools/universities (comma-separated)")
    parser.add_argument("--location", help="Location hint")
    parser.add_argument("--provider", default=PROVIDER, help="LLM provider")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    args = parser.parse_args()

    if args.name:
        TARGET["name"] = args.name
    if args.usernames:
        TARGET["known_usernames"] = [u.strip() for u in args.usernames.split(",")]
    if args.employers:
        TARGET["known_employers"] = [e.strip() for e in args.employers.split(",")]
    if args.schools:
        TARGET["known_schools"] = [s.strip() for s in args.schools.split(",")]
    if args.location:
        TARGET["location"] = args.location

    asyncio.run(main(TARGET, args.provider, args.max_iterations))
