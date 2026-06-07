from __future__ import annotations

import io
from typing import Any

from fpdf import FPDF

from .models import ParentState


def _clean_text(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(15, 23, 42)
        self.cell(0, 12, "ResearchSwarm Institutional Report", ln=True, align="C")
        self.ln(6)

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(31, 41, 55)
        self.cell(0, 8, title, ln=True)
        self.ln(2)

    def section_body(self, text: str) -> None:
        self.set_font("Helvetica", "", 11)
        self.set_text_color(31, 41, 55)
        self.multi_cell(0, 6, _clean_text(text))
        self.ln(4)

    def bullet_list(self, items: list[str]) -> None:
        self.set_font("Helvetica", "", 11)
        self.set_text_color(31, 41, 55)
        for item in items:
            # Use ASCII dash to avoid latin-1 encoding errors for non-ASCII bullets
            self.multi_cell(0, 6, f"- {_clean_text(item)}")
        self.ln(3)


def _build_agent_status_lines(state: ParentState) -> list[str]:
    statuses = state.get("agent_statuses", {})
    failures = state.get("agent_failures", [])
    lines: list[str] = []

    for agent_name in ["web", "domain", "financial", "legal"]:
        status = statuses.get(agent_name, "pending")
        description = {
            "pending": "Skipped or not needed",
            "success": "Complete",
            "partial": "Partial result — some task issues",
            "failed": "Failed or unavailable",
        }.get(status, str(status))
        lines.append(f"{agent_name.capitalize()}: {description}")

    if failures:
        lines.append("")
        lines.append("Agent failures:")
        for failure in failures:
            lines.append(f"- {failure}")

    return lines


def _build_task_section(state: ParentState) -> list[str]:
    sections: list[str] = []
    for label, key in [
        ("Web tasks", "web_tasks"),
        ("Domain tasks", "domain_tasks"),
        ("Financial tasks", "financial_tasks"),
        ("Legal tasks", "legal_tasks"),
    ]:
        tasks = state.get(key, [])
        if tasks:
            sections.append(f"{label}:")
            for task in tasks:
                sections.append(f"- {task}")
            sections.append("")
    return sections


def _build_research_sections(state: ParentState) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for label, key in [
        ("Web Research", "web_result"),
        ("Domain Knowledge", "domain_result"),
        ("Financial Analysis", "financial_result"),
        ("Legal Review", "legal_result"),
    ]:
        text = state.get(key, "")
        if text:
            sections.append((label, text))
    return sections


def build_report_pdf(state: ParentState) -> io.BytesIO:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(55, 65, 81)
    pdf.cell(0, 8, f"Query: {_clean_text(state['query'])}", ln=True)
    pdf.ln(4)

    pdf.section_title("Executive Summary")
    pdf.section_body(state.get("validated_answer", "No synthesized answer available."))
    pdf.bullet_list([
        f"Confidence: {state.get('confidence', 'low').upper()}",
        f"Validated: {'Yes' if state.get('is_valid', False) else 'No'}",
        f"Orchestrator plan length: {len(state.get('orchestrator_plan', '') or '')} characters",
    ])

    pdf.add_page()
    pdf.section_title("Pipeline Summary")
    pdf.section_body("This report is generated from the multi-agent pipeline output, including the orchestrator plan, research results, critique, and final validation summary.")
    pdf.bullet_list(_build_agent_status_lines(state))

    pdf.section_title("Orchestrator Plan")
    pdf.section_body(state.get("orchestrator_plan", "No orchestrator plan was generated."))
    task_lines = _build_task_section(state)
    if task_lines:
        for line in task_lines:
            if line.startswith("-"):
                pdf.multi_cell(0, 6, _clean_text(line))
            else:
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6, _clean_text(line))
        pdf.ln(4)
    else:
        pdf.section_body("No tasks were generated for specialists.")

    research_sections = _build_research_sections(state)
    for title, content in research_sections:
        pdf.section_title(title)
        pdf.section_body(content)

    pdf.section_title("Devil's Advocate Critique")
    pdf.section_body(state.get("devils_critique", "No critique available."))

    pdf.section_title("Final Validation")
    pdf.section_body(
        f"Confidence: {state.get('confidence', 'low').upper()}\n"
        f"Validated answer available: {'Yes' if state.get('validated_answer') else 'No'}\n"
        f"Answer:\n{state.get('validated_answer', 'No answer generated.')}",
    )

    buffer = io.BytesIO()
    buffer.write(pdf.output(dest="S").encode("latin-1", "replace"))
    buffer.seek(0)
    return buffer
