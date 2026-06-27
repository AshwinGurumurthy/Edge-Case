"""Shared graph state and the structured context the scanner produces.

`ScanContext` is the contract between the scanner and every downstream agent.
Each field answers one of the questions the scanner is responsible for:

  a. what the code is trying to do        -> purpose
  b. the end-to-end workflow              -> end_to_end_workflow
  c. target industry                      -> target_industry
  d. target audience interest             -> target_audience
  e. features                             -> features
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


class Feature(BaseModel):
    """A concrete capability the codebase implements."""

    name: str = Field(description="Short feature name, e.g. 'CSV export'.")
    description: str = Field(
        description="What the feature does, in one or two sentences."
    )
    evidence: str = Field(
        description="File path(s) or signal this was inferred from, e.g. 'src/export.py'."
    )


class WorkflowStep(BaseModel):
    """One ordered stage of the end-to-end flow."""

    step: str = Field(description="Short label for this stage, e.g. 'Ingest request'.")
    detail: str = Field(
        description="What happens at this stage and which components are involved."
    )


class ScanContext(BaseModel):
    """Structured understanding of a scanned codebase.

    This is the artifact the scanner writes to graph state for downstream agents.
    Keep it JSON-schema-friendly: plain strings, lists, and nested models only
    (no numeric/length constraints — structured outputs don't enforce those).
    """

    purpose: str = Field(
        description="What the code is trying to do — the core problem it solves, in 2-4 sentences."
    )
    end_to_end_workflow: list[WorkflowStep] = Field(
        default_factory=list,
        description="The end-to-end flow from input/trigger to output, in order.",
    )
    target_industry: list[str] = Field(
        default_factory=list,
        description="Industries/verticals this targets (e.g. fintech, healthcare). Empty if unclear.",
    )
    target_audience: list[str] = Field(
        default_factory=list,
        description="Who uses it and what they care about (e.g. 'backend engineers needing X'). Empty if unclear.",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="Concrete capabilities the codebase implements.",
    )
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Languages, frameworks, key libraries, datastores, and infra detected.",
    )
    entry_points: list[str] = Field(
        default_factory=list,
        description="Primary entry points (CLI command, server start, main file, API routes).",
    )
    summary: str = Field(
        description="One-paragraph executive summary tying everything together."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Inferences made under uncertainty and anything that could not be determined.",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Overall confidence in this analysis given the available signal."
    )

    def as_prompt_context(self) -> str:
        """Render the context as a markdown block downstream agents can drop
        directly into their own prompts."""

        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {i}" for i in items) if items else "- (none determined)"

        workflow = (
            "\n".join(
                f"{n}. **{s.step}** — {s.detail}"
                for n, s in enumerate(self.end_to_end_workflow, 1)
            )
            or "- (not determined)"
        )
        features = (
            "\n".join(
                f"- **{f.name}** — {f.description} _(evidence: {f.evidence})_"
                for f in self.features
            )
            or "- (none determined)"
        )

        return (
            f"# Codebase Context (confidence: {self.confidence})\n\n"
            f"## Purpose\n{self.purpose}\n\n"
            f"## End-to-end workflow\n{workflow}\n\n"
            f"## Target industry\n{bullets(self.target_industry)}\n\n"
            f"## Target audience\n{bullets(self.target_audience)}\n\n"
            f"## Features\n{features}\n\n"
            f"## Tech stack\n{bullets(self.tech_stack)}\n\n"
            f"## Entry points\n{bullets(self.entry_points)}\n\n"
            f"## Summary\n{self.summary}\n\n"
            f"## Assumptions & gaps\n{bullets(self.assumptions)}\n"
        )


class GraphState(TypedDict, total=False):
    """Shared LangGraph state.

    Downstream agents read `scan_context`. They should treat `scan_error` as a
    signal that the scan did not complete and branch accordingly.
    """

    # Inputs
    target: str          # local directory path OR git repository URL
    max_chars: int       # optional cap on collected source sent to the model
    output_md: str       # optional path to write the rendered context as a .md file

    # Outputs produced by the scanner node
    scan_context: ScanContext            # the context future agents consume
    scan_meta: dict[str, Any]            # collection stats (files scanned, truncation, root)
    scan_error: str                      # populated only if the scan failed
