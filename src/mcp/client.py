"""MCP control-plane client (stub).

In WARROOM the **MCP server** is the control plane: it exposes tools that mutate
the running infrastructure -- stop/restart containers, inject latency through a
Toxiproxy, and generate load. The Context subtree's ``context_mcp`` agent talks
to this control plane to learn *what failure levers exist* and *what the current
infra state is*, so the rest of the system reasons about reality, not guesses.

This module is a faithful **stub**: it returns a realistic tool catalog and a
mock infra snapshot so the architecture runs without a live MCP server. To go
live, replace the bodies of ``list_tools`` / ``snapshot`` with real JSON-RPC /
HTTP calls to your MCP server (e.g. http://127.0.0.1:9100).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class MCPTool:
    name: str
    description: str
    args: dict


# A representative WARROOM control-plane tool catalog.
_DEFAULT_TOOLS = [
    MCPTool("db.stop", "Stop the Postgres container (simulate DB outage)", {"grace_s": 0}),
    MCPTool("db.start", "Restart the Postgres container", {}),
    MCPTool("net.inject_latency", "Add latency via Toxiproxy", {"ms": 0, "jitter_ms": 0}),
    MCPTool("net.clear", "Remove all injected network faults", {}),
    MCPTool("load.flood", "Generate a request flood against an endpoint", {"rps": 0, "seconds": 0}),
    MCPTool("svc.health", "Probe service + dependency health", {}),
]


class MCPClient:
    """Thin client over the MCP control plane. Stubbed by default."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("MCP_BASE_URL", "http://127.0.0.1:9100")

    def list_tools(self) -> list[MCPTool]:
        """Return the available failure-injection / probe tools."""
        # TODO(live): GET {base_url}/tools and parse into MCPTool list.
        return list(_DEFAULT_TOOLS)

    def snapshot(self) -> dict:
        """Return a mock real-time infra snapshot (what a drill would observe)."""
        # TODO(live): GET {base_url}/state
        return {
            "services": {"app": "degraded", "postgres": "down"},
            "success_rate": 0.41,
            "error_count": 137,
            "p95_latency_ms": 4200,
            "first_failure_at": "T+0.8s",
            "active_faults": ["db.stop"],
        }

    def as_context(self) -> str:
        """Render tools + snapshot as text for the context_mcp agent's prompt."""
        tools = "\n".join(f"- {t.name}: {t.description}" for t in self.list_tools())
        return (
            "MCP CONTROL-PLANE TOOLS (failure levers available):\n"
            f"{tools}\n\n"
            "CURRENT INFRA SNAPSHOT (from the last/active drill):\n"
            f"{json.dumps(self.snapshot(), indent=2)}"
        )
