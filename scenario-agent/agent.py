#!/usr/bin/env python3
"""
Testing scenario generator agent using LangGraph.
Reads an app description .md file, researches failure patterns via web search,
and outputs structured testing scenarios to a .md file.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

load_dotenv()

MODEL = "claude-haiku-4-5"

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


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_graph():
    tools = [TavilySearch(max_results=5)]
    model = ChatAnthropic(model=MODEL).bind_tools(tools)

    def agent_node(state: State):
        return {"messages": [model.invoke(state["messages"])]}

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_agent(app_description: str) -> str:
    graph = build_graph()

    initial_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Here is the app description:\n\n{app_description}\n\n"
            "Research what applications like this commonly fail at, then generate "
            "a comprehensive set of testing scenarios, expected outputs, and edge cases. "
            "Format everything as a clean markdown document."
        ),
    ]

    print("[agent] Starting...", file=sys.stderr)
    last_message = None

    for event in graph.stream(
        {"messages": initial_messages},
        config={"recursion_limit": 25},
        stream_mode="updates",
    ):
        for node_name, update in event.items():
            messages = update.get("messages", [])
            for msg in messages:
                if node_name == "agent":
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            query = tc.get("args", {}).get("query", "")
                            print(f"[agent] Searching: {query}", file=sys.stderr)
                    elif hasattr(msg, "content") and msg.content:
                        print("[agent] Generating scenarios...", file=sys.stderr)
                        last_message = msg
                elif node_name == "tools":
                    print(f"[tools] Got search results", file=sys.stderr)

    return last_message.content


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
