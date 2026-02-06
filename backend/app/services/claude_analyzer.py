"""
Claude API integration for NDA analysis.

Sends the NDA text and markup guidelines to Claude, which returns
structured JSON describing the changes to make.
"""

import json
import os
from typing import Optional

import anthropic

from app.services.document_markup import Change


SYSTEM_PROMPT = """You are an expert legal document reviewer specializing in Non-Disclosure Agreements (NDAs).
Your task is to analyze an NDA document against provided markup guidelines and produce specific, actionable changes.

You must return a JSON array of changes. Each change must have:
- "change_type": one of "deletion", "insertion", "replacement", "comment_only"
- "original_text": the EXACT text from the document to find (must match verbatim for deletion/replacement/comment_only). For insertion, this is the anchor text AFTER which the new text will be inserted.
- "new_text": the replacement or new text (required for insertion and replacement, empty for deletion)
- "rationale": brief explanation of why this change is needed
- "section": which section/clause this belongs to
- "priority": one of "critical", "high", "medium", "low"

CRITICAL RULES:
1. The "original_text" MUST be an exact substring of the document text. Copy it character-for-character.
2. Include enough surrounding text to make each match unique (at least 20-30 characters when possible).
3. Do NOT modify boilerplate section headers or numbering unless the guidelines specifically require it.
4. For replacements, the new_text should contain ONLY the replacement, not the original.
5. Order changes by their position in the document (top to bottom).
6. Prioritize changes based on legal risk: terms that expose the receiving party to unlimited liability or overly broad obligations are "critical".

Return ONLY the JSON array, no other text or markdown formatting."""


MODE_INSTRUCTIONS = {
    "full": """Apply ALL recommended changes from the guidelines, including:
- Critical legal protections
- Standard market adjustments
- Style and clarity improvements
- Nice-to-have suggestions""",
    "critical": """Apply ONLY critical and high-priority changes:
- Terms that create unacceptable legal risk
- Missing essential protections
- Overly broad or one-sided obligations
Do NOT include style changes, minor clarifications, or nice-to-have improvements.""",
    "balanced": """Apply critical and high-priority changes, plus important medium-priority ones:
- All critical legal protections
- Standard market adjustments
- Important clarifications
Skip purely stylistic changes and minor nice-to-have items.""",
}


class ClaudeAnalyzer:
    """Analyzes NDA documents using Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed directly"
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_nda(
        self,
        document_text: str,
        guidelines_text: str,
        mode: str = "balanced",
        document_structure: Optional[list[dict]] = None,
    ) -> list[Change]:
        """
        Analyze an NDA against guidelines and return a list of Change objects.

        Args:
            document_text: full text of the NDA
            guidelines_text: markup guidelines/rules
            mode: 'full', 'critical', or 'balanced'
            document_structure: optional structure info for better location finding

        Returns:
            list of Change objects to apply
        """
        mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["balanced"])

        # Build the user prompt
        user_prompt = self._build_prompt(
            document_text, guidelines_text, mode_instruction, document_structure
        )

        # Handle large documents by chunking if needed
        if len(user_prompt) > 150000:
            return self._analyze_chunked(
                document_text, guidelines_text, mode_instruction, document_structure
            )

        return self._call_claude(user_prompt)

    def _build_prompt(
        self,
        document_text: str,
        guidelines_text: str,
        mode_instruction: str,
        document_structure: Optional[list[dict]] = None,
    ) -> str:
        prompt = f"""## Markup Mode
{mode_instruction}

## Markup Guidelines
{guidelines_text}

## NDA Document to Review
{document_text}"""

        if document_structure:
            structure_summary = "\n".join(
                f"[Para {s['index']}] ({s['style']}): {s['text'][:100]}..."
                if len(s["text"]) > 100
                else f"[Para {s['index']}] ({s['style']}): {s['text']}"
                for s in document_structure
            )
            prompt += f"""

## Document Structure (for reference)
{structure_summary}"""

        prompt += """

## Instructions
Analyze the NDA against the markup guidelines. Return a JSON array of changes.
Remember: "original_text" must be an EXACT match of text in the document.
Return ONLY the JSON array."""

        return prompt

    def _call_claude(self, user_prompt: str) -> list[Change]:
        """Make the API call to Claude and parse the response."""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if response_text.startswith("```"):
            # Strip markdown code block
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        changes_data = json.loads(response_text)

        changes = []
        for item in changes_data:
            change = Change(
                change_type=item.get("change_type", "comment_only"),
                original_text=item.get("original_text", ""),
                new_text=item.get("new_text", ""),
                rationale=item.get("rationale", ""),
                section=item.get("section", ""),
                priority=item.get("priority", "medium"),
            )
            changes.append(change)

        return changes

    def _analyze_chunked(
        self,
        document_text: str,
        guidelines_text: str,
        mode_instruction: str,
        document_structure: Optional[list[dict]] = None,
    ) -> list[Change]:
        """
        For large documents, split into sections and analyze each chunk.
        Merge results at the end.
        """
        # Split document into roughly equal chunks at paragraph boundaries
        paragraphs = document_text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0
        max_chunk_size = 40000  # characters per chunk

        for para in paragraphs:
            if current_length + len(para) > max_chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = len(para)
            else:
                current_chunk.append(para)
                current_length += len(para)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        all_changes = []
        for i, chunk in enumerate(chunks):
            chunk_prompt = self._build_prompt(
                f"[Document chunk {i + 1} of {len(chunks)}]\n\n{chunk}",
                guidelines_text,
                mode_instruction,
            )
            try:
                changes = self._call_claude(chunk_prompt)
                all_changes.extend(changes)
            except Exception as e:
                print(f"Warning: Failed to analyze chunk {i + 1}: {e}")

        return all_changes

    def generate_summary(
        self, changes: list[Change], document_text: str
    ) -> dict:
        """
        Generate a summary report of the changes made.

        Returns a dict with:
        - executive_summary: high-level overview
        - changes_by_priority: grouped changes
        - risk_areas: identified risk areas
        - statistics: counts and categories
        """
        stats = {
            "total": len(changes),
            "by_type": {},
            "by_priority": {},
            "applied": sum(1 for c in changes if c.applied),
            "failed": sum(1 for c in changes if not c.applied),
        }

        for change in changes:
            stats["by_type"][change.change_type] = (
                stats["by_type"].get(change.change_type, 0) + 1
            )
            stats["by_priority"][change.priority] = (
                stats["by_priority"].get(change.priority, 0) + 1
            )

        changes_by_priority = {}
        for change in changes:
            if change.priority not in changes_by_priority:
                changes_by_priority[change.priority] = []
            changes_by_priority[change.priority].append(
                {
                    "type": change.change_type,
                    "section": change.section,
                    "rationale": change.rationale,
                    "original": change.original_text[:100] + "..."
                    if len(change.original_text) > 100
                    else change.original_text,
                    "new": change.new_text[:100] + "..."
                    if len(change.new_text) > 100
                    else change.new_text,
                    "applied": change.applied,
                }
            )

        return {
            "statistics": stats,
            "changes_by_priority": changes_by_priority,
            "change_log": [
                {
                    "type": c.change_type,
                    "section": c.section,
                    "original": c.original_text,
                    "new": c.new_text,
                    "rationale": c.rationale,
                    "priority": c.priority,
                    "applied": c.applied,
                }
                for c in changes
            ],
        }
