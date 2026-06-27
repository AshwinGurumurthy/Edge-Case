#!/usr/bin/env python3
"""
Testing scenario generator agent using LangGraph.

Reads an app description (or a scanner `ScanContext`), optionally researches
failure patterns via web search, and outputs structured testing scenarios.

Backend selection mirrors the scanner so the pipeline runs with or without keys:
  - ANTHROPIC_API_KEY set  -> Claude Haiku (web search enabled if TAVILY_API_KEY).
  - otherwise               -> local Ollama (no web search).
  - force with SCENARIO_BACKEND=anthropic|ollama.
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Annotated

import requests
from dotenv import load_dotenv
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

load_dotenv()

ANTHROPIC_MODEL = os.getenv("SCENARIO_ANTHROPIC_MODEL", "claude-haiku-4-5")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite4:micro")

SYSTEM_PROMPT = """You are a senior QA engineer and testing strategist. Your job is to:
1. Analyze an app's description, features, and user workflows
2. Use web search to research what similar applications commonly fail at — look for known failure patterns, common bugs, security vulnerabilities, UX pitfalls, and edge cases reported in the wild
3. Synthesize your research into a comprehensive, structured set of testing scenarios

When searching, look for:
- "[app type] common bugs" or "[app type] known issues"
- "[app type] security vulnerabilities"
- "[app type] edge cases"
- "[app type] user complaints" or "[app type] failure modes"
- Relevant CVEs, post-mortems, or developer forums discussing similar apps

Your final output must be a structured markdown document with:
- Functional testing scenarios
- Edge cases
- Security/auth scenarios (if applicable)
- Performance/load scenarios (if applicable)
- Expected outcomes for each scenario

Be specific and actionable — other automated agents will execute these tests."""

USER_PROMPT = (
    "Here is the app description:\n\n{desc}\n\n"
    "Research what applications like this commonly fail at, then generate "
    "a comprehensive set of testing scenarios, expected outputs, and edge cases. "
    "Format everything as a clean markdown document."
)


def select_backend() -> str:
    forced = os.getenv("SCENARIO_BACKEND", "").strip().lower()
    if forced in ("anthropic", "ollama"):
        return forced
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama"


def _has_tavily() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


class State(TypedDict):
    messages: Annotated[list, add_messages]


def _msg_text(msg) -> str:
    """Normalize an LLM message's content (str or list of blocks) to text."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _run_anthropic(app_description: str) -> str:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.graph import END, START, StateGraph

    use_search = _has_tavily()
    model = ChatAnthropic(model=ANTHROPIC_MODEL)
    tools = []
    if use_search:
        from langchain_tavily import TavilySearch
        from langgraph.prebuilt import ToolNode, tools_condition

        tools = [TavilySearch(max_results=5)]
        model = model.bind_tools(tools)
    else:
        print("[scenario] TAVILY_API_KEY not set — generating without web search.", file=sys.stderr)

    def agent_node(state: State):
        return {"messages": [model.invoke(state["messages"])]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_edge(START, "agent")
    if use_search:
        graph_builder.add_node("tools", ToolNode(tools))
        graph_builder.add_conditional_edges("agent", tools_condition)
        graph_builder.add_edge("tools", "agent")
    else:
        graph_builder.add_edge("agent", END)
    graph = graph_builder.compile()

    initial_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(desc=app_description)),
    ]

    print("[scenario] Starting (anthropic)...", file=sys.stderr)
    last_text = ""
    for event in graph.stream(
        {"messages": initial_messages},
        config={"recursion_limit": 25},
        stream_mode="updates",
    ):
        for node_name, update in event.items():
            for msg in update.get("messages", []):
                if node_name == "agent":
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            print(f"[scenario] Searching: {tc.get('args', {}).get('query', '')}", file=sys.stderr)
                    else:
                        text = _msg_text(msg)
                        if text.strip():
                            last_text = text
                elif node_name == "tools":
                    print("[scenario] Got search results", file=sys.stderr)

    if not last_text:
        raise RuntimeError("scenario agent produced no final message")
    return last_text


def _run_ollama(app_description: str) -> str:
    print("[scenario] Starting (ollama, no web search)...", file=sys.stderr)
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(desc=app_description)},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=600)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama request to {OLLAMA_HOST} failed ({exc}). Is `ollama serve` "
            f"running and is model '{OLLAMA_MODEL}' pulled?"
        ) from exc
    content = resp.json().get("message", {}).get("content", "")
    if not content.strip():
        raise RuntimeError("Ollama returned an empty response")
    return content


def run_agent(app_description: str) -> str:
    backend = select_backend()
    if backend == "anthropic":
        return _run_anthropic(app_description)
    return _run_ollama(app_description)


def scenario_node(state: dict) -> dict:
    """LangGraph node — consumes scan_context, produces scenario_output."""
    scan_context = state.get("scan_context")
    if scan_context is None:
        raise ValueError("scenario_node requires scan_context in state")
    app_description = scan_context.as_prompt_context()
    scenarios = run_agent(app_description)
    return {"scenario_output": scenarios}


def read_app_description(path: str) -> str:
    content = Path(path).read_text(encoding="utf-8")
    if not content.strip():
        print(f"Error: {path} is empty.", file=sys.stderr)
        sys.exit(1)
    return content


def build_output(scenarios: str, input_path: str) -> str:
    app_name = Path(input_path).stem.replace("-", " ").replace("_", " ").title()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Testing Scenarios — {app_name}

> Generated: {timestamp}
> Source: `{input_path}`

---

{scenarios}
"""


def main():
    parser = argparse.ArgumentParser(
        description="Generate testing scenarios for an app from its description."
    )
    parser.add_argument("input", help="Path to the .md file describing the app")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .md file path (default: <input-stem>-scenarios.md)",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or str(
        Path(input_path).with_name(Path(input_path).stem + "-scenarios.md")
    )

    app_description = read_app_description(input_path)
    scenarios = run_agent(app_description)
    output = build_output(scenarios, input_path)

    Path(output_path).write_text(output, encoding="utf-8")
    print(f"\nScenarios written to: {output_path}", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
