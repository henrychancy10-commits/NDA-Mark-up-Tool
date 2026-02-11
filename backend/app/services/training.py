"""
Training diff engine.

Compares a clean NDA (.docx) with its negotiated version (.docx or .pdf)
to extract the patterns of changes that were made during negotiation.
Uses Claude to analyze the differences and produce structured patterns.
"""

import json
import os
import re
from difflib import SequenceMatcher
from typing import Optional

from app.services.guideline_parser import parse_guidelines
from app.services.document_markup import extract_document_text


class DiffResult:
    """A single difference found between two document versions."""

    def __init__(
        self,
        diff_type: str,
        original_text: str = "",
        negotiated_text: str = "",
        context_before: str = "",
        context_after: str = "",
    ):
        self.diff_type = diff_type  # 'added', 'removed', 'changed'
        self.original_text = original_text
        self.negotiated_text = negotiated_text
        self.context_before = context_before
        self.context_after = context_after


class TrainingPattern:
    """A reusable pattern learned from training examples."""

    def __init__(
        self,
        pattern_type: str,
        description: str,
        original_pattern: str,
        replacement_pattern: str = "",
        clause_type: str = "",
        frequency: int = 1,
        examples: Optional[list[dict]] = None,
    ):
        self.pattern_type = pattern_type  # 'always_remove', 'always_replace', 'always_add', 'conditional'
        self.description = description
        self.original_pattern = original_pattern
        self.replacement_pattern = replacement_pattern
        self.clause_type = clause_type
        self.frequency = frequency
        self.examples = examples or []


def extract_text_from_file(file_path: str) -> str:
    """Extract text from .docx or .pdf file."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return extract_document_text(file_path)
    elif ext == ".pdf":
        return parse_guidelines(file_path)  # Uses the PDF parser
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def compute_diffs(original_text: str, negotiated_text: str) -> list[DiffResult]:
    """
    Compare original and negotiated text to find differences.
    Uses paragraph-level diffing for meaningful results.
    """
    # Split into paragraphs
    orig_paragraphs = [p.strip() for p in original_text.split("\n") if p.strip()]
    neg_paragraphs = [p.strip() for p in negotiated_text.split("\n") if p.strip()]

    matcher = SequenceMatcher(None, orig_paragraphs, neg_paragraphs)
    diffs = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue

        # Get surrounding context
        context_before = orig_paragraphs[max(0, i1 - 1)] if i1 > 0 else ""
        context_after = orig_paragraphs[min(len(orig_paragraphs) - 1, i2)] if i2 < len(orig_paragraphs) else ""

        if op == "delete":
            # Text was removed in negotiated version
            for idx in range(i1, i2):
                diffs.append(DiffResult(
                    diff_type="removed",
                    original_text=orig_paragraphs[idx],
                    context_before=context_before,
                    context_after=context_after,
                ))
        elif op == "insert":
            # Text was added in negotiated version
            for idx in range(j1, j2):
                diffs.append(DiffResult(
                    diff_type="added",
                    negotiated_text=neg_paragraphs[idx],
                    context_before=context_before,
                    context_after=context_after,
                ))
        elif op == "replace":
            # Text was changed
            orig_block = "\n".join(orig_paragraphs[i1:i2])
            neg_block = "\n".join(neg_paragraphs[j1:j2])

            # Try finer-grained word-level diff within the block
            word_diffs = _word_level_diffs(orig_block, neg_block)
            if word_diffs:
                for wd in word_diffs:
                    wd.context_before = context_before
                    wd.context_after = context_after
                    diffs.append(wd)
            else:
                diffs.append(DiffResult(
                    diff_type="changed",
                    original_text=orig_block,
                    negotiated_text=neg_block,
                    context_before=context_before,
                    context_after=context_after,
                ))

    return diffs


def _word_level_diffs(original: str, negotiated: str) -> list[DiffResult]:
    """Perform word-level diffing for finer granularity."""
    orig_words = original.split()
    neg_words = negotiated.split()

    matcher = SequenceMatcher(None, orig_words, neg_words)
    diffs = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue

        orig_chunk = " ".join(orig_words[i1:i2])
        neg_chunk = " ".join(neg_words[j1:j2])

        # Get word-level context
        ctx_before = " ".join(orig_words[max(0, i1 - 5):i1])
        ctx_after = " ".join(orig_words[i2:min(len(orig_words), i2 + 5)])

        if op == "delete":
            diffs.append(DiffResult(
                diff_type="removed",
                original_text=orig_chunk,
                context_before=ctx_before,
                context_after=ctx_after,
            ))
        elif op == "insert":
            diffs.append(DiffResult(
                diff_type="added",
                negotiated_text=neg_chunk,
                context_before=ctx_before,
                context_after=ctx_after,
            ))
        elif op == "replace":
            diffs.append(DiffResult(
                diff_type="changed",
                original_text=orig_chunk,
                negotiated_text=neg_chunk,
                context_before=ctx_before,
                context_after=ctx_after,
            ))

    return diffs


def diffs_to_json(diffs: list[DiffResult]) -> list[dict]:
    """Convert diff results to JSON-serializable format."""
    return [
        {
            "diff_type": d.diff_type,
            "original_text": d.original_text,
            "negotiated_text": d.negotiated_text,
            "context_before": d.context_before,
            "context_after": d.context_after,
        }
        for d in diffs
    ]


def analyze_training_pair(
    original_path: str,
    negotiated_path: str,
    notes: str = "",
) -> dict:
    """
    Analyze a training pair (clean NDA + negotiated version).

    Returns a dict with:
    - diffs: list of differences found
    - summary: statistics about the changes
    - original_text: extracted text from original
    - negotiated_text: extracted text from negotiated version
    """
    original_text = extract_text_from_file(original_path)
    negotiated_text = extract_text_from_file(negotiated_path)

    diffs = compute_diffs(original_text, negotiated_text)

    summary = {
        "total_diffs": len(diffs),
        "added": sum(1 for d in diffs if d.diff_type == "added"),
        "removed": sum(1 for d in diffs if d.diff_type == "removed"),
        "changed": sum(1 for d in diffs if d.diff_type == "changed"),
    }

    return {
        "diffs": diffs_to_json(diffs),
        "summary": summary,
        "original_text": original_text,
        "negotiated_text": negotiated_text,
    }


def extract_patterns_from_examples(
    examples: list[dict],
) -> list[dict]:
    """
    Analyze multiple training examples to find recurring patterns.

    Each example should have 'diffs' (list of diff dicts).
    Returns patterns that appear across multiple examples.
    """
    # Collect all diffs with normalized text
    all_changes = []
    for ex in examples:
        for diff in ex.get("diffs", []):
            all_changes.append({
                "type": diff["diff_type"],
                "original": _normalize_for_pattern(diff.get("original_text", "")),
                "replacement": _normalize_for_pattern(diff.get("negotiated_text", "")),
                "raw_original": diff.get("original_text", ""),
                "raw_replacement": diff.get("negotiated_text", ""),
            })

    # Group similar changes together
    patterns = []
    seen = set()

    for i, change in enumerate(all_changes):
        if i in seen:
            continue

        similar = [change]
        seen.add(i)

        for j, other in enumerate(all_changes):
            if j in seen or j <= i:
                continue
            if _changes_are_similar(change, other):
                similar.append(other)
                seen.add(j)

        # Create a pattern from the group
        if len(similar) >= 1:
            pattern = _create_pattern(similar)
            patterns.append(pattern)

    # Sort by frequency (most common first)
    patterns.sort(key=lambda p: p["frequency"], reverse=True)

    return patterns


def _normalize_for_pattern(text: str) -> str:
    """Normalize text for pattern matching."""
    text = re.sub(r"\s+", " ", text.strip().lower())
    # Remove specific numbers/dates that vary
    text = re.sub(r"\b\d+\b", "NUM", text)
    return text


def _changes_are_similar(a: dict, b: dict) -> bool:
    """Check if two changes are similar enough to form a pattern."""
    if a["type"] != b["type"]:
        return False

    # Use sequence matching for similarity
    if a["original"] and b["original"]:
        ratio = SequenceMatcher(None, a["original"], b["original"]).ratio()
        if ratio > 0.7:
            return True

    if a["replacement"] and b["replacement"]:
        ratio = SequenceMatcher(None, a["replacement"], b["replacement"]).ratio()
        if ratio > 0.7:
            return True

    return False


def _create_pattern(similar_changes: list[dict]) -> dict:
    """Create a pattern from a group of similar changes."""
    change = similar_changes[0]

    if change["type"] == "removed":
        pattern_type = "always_remove"
        description = f"Remove: \"{change['raw_original'][:80]}...\""  if len(change['raw_original']) > 80 else f"Remove: \"{change['raw_original']}\""
    elif change["type"] == "added":
        pattern_type = "always_add"
        description = f"Add: \"{change['raw_replacement'][:80]}...\"" if len(change['raw_replacement']) > 80 else f"Add: \"{change['raw_replacement']}\""
    else:
        pattern_type = "always_replace"
        orig_short = change['raw_original'][:50] + "..." if len(change['raw_original']) > 50 else change['raw_original']
        repl_short = change['raw_replacement'][:50] + "..." if len(change['raw_replacement']) > 50 else change['raw_replacement']
        description = f"Replace \"{orig_short}\" with \"{repl_short}\""

    return {
        "pattern_type": pattern_type,
        "description": description,
        "original_pattern": change["raw_original"],
        "replacement_pattern": change["raw_replacement"],
        "frequency": len(similar_changes),
        "examples": [
            {"original": c["raw_original"], "replacement": c["raw_replacement"]}
            for c in similar_changes[:3]  # Keep up to 3 examples
        ],
    }


def build_training_context(patterns: list[dict], max_patterns: int = 20) -> str:
    """
    Build a text block that can be injected into the Claude prompt
    to teach it the negotiation patterns from training data.
    """
    if not patterns:
        return ""

    lines = [
        "## Learned Negotiation Patterns (from training examples)",
        "",
        "The following patterns were learned from previously negotiated NDAs.",
        "Apply these patterns where the NDA contains similar language:",
        "",
    ]

    for i, pattern in enumerate(patterns[:max_patterns]):
        freq_note = f" (seen {pattern['frequency']}x)" if pattern["frequency"] > 1 else ""
        lines.append(f"### Pattern {i + 1}{freq_note}")
        lines.append(f"Type: {pattern['pattern_type']}")
        lines.append(f"Description: {pattern['description']}")

        if pattern["original_pattern"]:
            lines.append(f"Original: \"{pattern['original_pattern'][:200]}\"")
        if pattern["replacement_pattern"]:
            lines.append(f"Replacement: \"{pattern['replacement_pattern'][:200]}\"")

        if pattern.get("examples") and len(pattern["examples"]) > 1:
            lines.append("Additional examples:")
            for ex in pattern["examples"][1:]:
                if ex.get("original"):
                    lines.append(f"  - Original: \"{ex['original'][:100]}\"")
                if ex.get("replacement"):
                    lines.append(f"  - Replacement: \"{ex['replacement'][:100]}\"")

        lines.append("")

    return "\n".join(lines)
