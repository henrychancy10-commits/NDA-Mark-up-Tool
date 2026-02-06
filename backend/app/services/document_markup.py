"""
Core document markup engine.

Generates Word documents with simulated track changes:
- Deletions: red text with strikethrough
- Insertions: blue text with underline
- Comments: added as Word comments with rationale

Uses python-docx for all Word document manipulation.
"""

import copy
import re
from datetime import datetime
from typing import Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsmap
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_COLOR_INDEX


# Standard deletion color (red) and insertion color (blue)
DELETION_COLOR = RGBColor(0xFF, 0x00, 0x00)
INSERTION_COLOR = RGBColor(0x00, 0x00, 0xFF)
COMMENT_AUTHOR = "NDA Markup Tool"


class Change:
    """Represents a single markup change to apply to the document."""

    def __init__(
        self,
        change_type: str,
        original_text: str,
        new_text: str = "",
        rationale: str = "",
        section: str = "",
        priority: str = "medium",
    ):
        """
        Args:
            change_type: 'deletion', 'insertion', 'replacement', or 'comment_only'
            original_text: text to find in the document (for deletion/replacement)
            new_text: replacement or inserted text
            rationale: explanation for the change
            section: which section/clause this belongs to
            priority: 'critical', 'high', 'medium', 'low'
        """
        self.change_type = change_type
        self.original_text = original_text
        self.new_text = new_text
        self.rationale = rationale
        self.section = section
        self.priority = priority
        self.applied = False


class DocumentMarkupEngine:
    """
    Engine for applying markup changes to Word documents.

    Produces .docx files with visual track changes:
    - Strikethrough + red for deletions
    - Underline + blue for insertions
    - Word comments for rationale
    """

    def __init__(self):
        self._comment_id = 0

    def apply_markup(
        self,
        source_path: str,
        changes: list[Change],
        output_path: str,
        author: str = COMMENT_AUTHOR,
    ) -> dict:
        """
        Apply a list of changes to a Word document and save the result.

        Args:
            source_path: path to the original .docx file
            changes: list of Change objects to apply
            output_path: where to save the marked-up .docx
            author: author name for comments

        Returns:
            dict with statistics about applied changes
        """
        doc = Document(source_path)
        self._comment_id = 0
        self._ensure_comments_part(doc)

        stats = {
            "total_changes": len(changes),
            "applied": 0,
            "failed": 0,
            "by_type": {"deletion": 0, "insertion": 0, "replacement": 0, "comment_only": 0},
        }

        for change in changes:
            success = self._apply_single_change(doc, change, author)
            if success:
                stats["applied"] += 1
                stats["by_type"][change.change_type] = (
                    stats["by_type"].get(change.change_type, 0) + 1
                )
                change.applied = True
            else:
                stats["failed"] += 1

        doc.save(output_path)
        return stats

    def _apply_single_change(
        self, doc: Document, change: Change, author: str
    ) -> bool:
        """Apply one change to the document. Returns True if successful."""
        if change.change_type == "deletion":
            return self._apply_deletion(doc, change, author)
        elif change.change_type == "insertion":
            return self._apply_insertion(doc, change, author)
        elif change.change_type == "replacement":
            return self._apply_replacement(doc, change, author)
        elif change.change_type == "comment_only":
            return self._apply_comment_only(doc, change, author)
        return False

    def _apply_deletion(
        self, doc: Document, change: Change, author: str
    ) -> bool:
        """Mark text as deleted (red strikethrough)."""
        return self._find_and_mark_text(
            doc,
            change.original_text,
            mark_type="delete",
            rationale=change.rationale,
            author=author,
        )

    def _apply_insertion(
        self, doc: Document, change: Change, author: str
    ) -> bool:
        """Insert new text (blue underline) after the anchor text."""
        return self._find_and_mark_text(
            doc,
            change.original_text,
            mark_type="insert_after",
            new_text=change.new_text,
            rationale=change.rationale,
            author=author,
        )

    def _apply_replacement(
        self, doc: Document, change: Change, author: str
    ) -> bool:
        """Replace text: strikethrough original (red) + insert new (blue underline)."""
        return self._find_and_mark_text(
            doc,
            change.original_text,
            mark_type="replace",
            new_text=change.new_text,
            rationale=change.rationale,
            author=author,
        )

    def _apply_comment_only(
        self, doc: Document, change: Change, author: str
    ) -> bool:
        """Add a comment to existing text without changing it."""
        return self._find_and_mark_text(
            doc,
            change.original_text,
            mark_type="comment",
            rationale=change.rationale,
            author=author,
        )

    def _find_and_mark_text(
        self,
        doc: Document,
        search_text: str,
        mark_type: str,
        new_text: str = "",
        rationale: str = "",
        author: str = COMMENT_AUTHOR,
    ) -> bool:
        """
        Find text across paragraphs (including across runs) and apply markup.

        This is the core text-finding logic. It handles the fact that
        python-docx splits text into runs at formatting boundaries, so
        a search phrase may span multiple runs.
        """
        # Normalize whitespace for matching
        normalized_search = _normalize_whitespace(search_text)

        # Search through all paragraphs in body, tables, headers, footers
        for paragraph in self._all_paragraphs(doc):
            if self._process_paragraph(
                doc, paragraph, normalized_search, mark_type, new_text, rationale, author
            ):
                return True

        return False

    def _process_paragraph(
        self,
        doc: Document,
        paragraph,
        search_text: str,
        mark_type: str,
        new_text: str,
        rationale: str,
        author: str,
    ) -> bool:
        """
        Try to find and mark text within a single paragraph.
        Handles text that spans multiple runs.
        """
        # Build a map of (char_index -> (run_index, offset_in_run))
        full_text = ""
        char_map = []  # For each char in full_text, store (run_idx, char_idx_in_run)

        for run_idx, run in enumerate(paragraph.runs):
            for char_idx, char in enumerate(run.text):
                char_map.append((run_idx, char_idx))
                full_text += char

        normalized_full = _normalize_whitespace(full_text)

        # Try to find the search text
        match_start = normalized_full.lower().find(search_text.lower())
        if match_start == -1:
            return False

        match_end = match_start + len(search_text)

        # Map normalized positions back to original positions
        orig_positions = _map_normalized_to_original(full_text, match_start, match_end)
        if orig_positions is None:
            return False

        orig_start, orig_end = orig_positions

        # Now we know which characters in the original text to modify
        # Get the run ranges
        if orig_start >= len(char_map) or orig_end > len(char_map):
            return False

        start_run_idx, start_char_idx = char_map[orig_start]
        end_run_idx, end_char_idx = char_map[orig_end - 1]

        if mark_type == "delete":
            self._mark_runs_deleted(paragraph, char_map, orig_start, orig_end)
            if rationale:
                self._add_comment_to_paragraph(doc, paragraph, rationale, author)

        elif mark_type == "insert_after":
            # Insert new text run after the anchor text
            insert_run = self._insert_run_after(
                paragraph, end_run_idx, new_text
            )
            _format_insertion(insert_run)
            if rationale:
                self._add_comment_to_paragraph(doc, paragraph, rationale, author)

        elif mark_type == "replace":
            # Mark original as deleted
            self._mark_runs_deleted(paragraph, char_map, orig_start, orig_end)
            # Insert replacement after
            insert_run = self._insert_run_after(
                paragraph, end_run_idx, new_text
            )
            _format_insertion(insert_run)
            if rationale:
                self._add_comment_to_paragraph(doc, paragraph, rationale, author)

        elif mark_type == "comment":
            if rationale:
                self._add_comment_to_paragraph(doc, paragraph, rationale, author)

        return True

    def _mark_runs_deleted(self, paragraph, char_map, orig_start, orig_end):
        """
        Apply deletion formatting (red + strikethrough) to characters
        at positions orig_start..orig_end in the paragraph.

        This splits runs as needed so only the matched text gets formatted.
        """
        # Collect which runs are affected and at what offsets
        affected_runs = {}  # run_idx -> (first_char_in_run, last_char_in_run)
        for pos in range(orig_start, orig_end):
            run_idx, char_in_run = char_map[pos]
            if run_idx not in affected_runs:
                affected_runs[run_idx] = (char_in_run, char_in_run)
            else:
                existing_start, _ = affected_runs[run_idx]
                affected_runs[run_idx] = (existing_start, char_in_run)

        # Process runs in reverse order to preserve indices
        for run_idx in sorted(affected_runs.keys(), reverse=True):
            run = paragraph.runs[run_idx]
            first_char, last_char = affected_runs[run_idx]
            run_text = run.text

            # Check if we need to split the run
            if first_char == 0 and last_char == len(run_text) - 1:
                # Entire run is deleted
                _format_deletion(run)
            else:
                # Need to split the run
                self._split_and_format_deletion(
                    paragraph, run_idx, first_char, last_char
                )

    def _split_and_format_deletion(
        self, paragraph, run_idx: int, first_char: int, last_char: int
    ):
        """
        Split a run into up to 3 parts: before, deleted, after.
        Only the 'deleted' part gets strikethrough+red formatting.
        """
        run = paragraph.runs[run_idx]
        text = run.text
        original_rpr = copy.deepcopy(run._r.get_or_add_rPr())

        before_text = text[:first_char]
        deleted_text = text[first_char : last_char + 1]
        after_text = text[last_char + 1 :]

        # Modify the current run to be just the deleted portion
        run.text = deleted_text
        _format_deletion(run)

        # Insert 'after' text as a new run right after this one
        if after_text:
            after_run = OxmlElement("w:r")
            after_rpr = copy.deepcopy(original_rpr)
            after_run.append(after_rpr)
            after_t = OxmlElement("w:t")
            after_t.text = after_text
            if after_text.startswith(" ") or after_text.endswith(" "):
                after_t.set(qn("xml:space"), "preserve")
            after_run.append(after_t)
            run._r.addnext(after_run)

        # Insert 'before' text as a new run right before this one
        if before_text:
            before_run = OxmlElement("w:r")
            before_rpr = copy.deepcopy(original_rpr)
            before_run.append(before_rpr)
            before_t = OxmlElement("w:t")
            before_t.text = before_text
            if before_text.startswith(" ") or before_text.endswith(" "):
                before_t.set(qn("xml:space"), "preserve")
            before_run.append(before_t)
            run._r.addprevious(before_run)

    def _insert_run_after(self, paragraph, after_run_idx: int, text: str):
        """Insert a new run with given text after the specified run index."""
        runs = paragraph.runs
        if after_run_idx < len(runs):
            ref_run = runs[after_run_idx]
            # Clone the formatting from the reference run
            new_r = OxmlElement("w:r")
            new_rpr = OxmlElement("w:rPr")
            new_r.append(new_rpr)
            new_t = OxmlElement("w:t")
            new_t.text = text
            if text.startswith(" ") or text.endswith(" "):
                new_t.set(qn("xml:space"), "preserve")
            new_r.append(new_t)
            ref_run._r.addnext(new_r)

            # Return a wrapper we can format
            return _RunWrapper(new_r)
        else:
            # Append to end of paragraph
            run = paragraph.add_run(text)
            return run

    def _all_paragraphs(self, doc: Document):
        """Yield all paragraphs in the document: body, tables, headers, footers."""
        # Body paragraphs
        for paragraph in doc.paragraphs:
            yield paragraph

        # Table cells
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        yield paragraph

        # Headers and footers
        for section in doc.sections:
            if section.header:
                for paragraph in section.header.paragraphs:
                    yield paragraph
            if section.footer:
                for paragraph in section.footer.paragraphs:
                    yield paragraph

    def _ensure_comments_part(self, doc: Document):
        """Ensure the document has a comments part for adding Word comments."""
        # We'll add comments via direct XML manipulation
        pass

    def _add_comment_to_paragraph(
        self, doc: Document, paragraph, text: str, author: str
    ):
        """
        Add a Word comment to the given paragraph.

        This creates actual Word comments that appear in the comments pane
        in Microsoft Word.
        """
        self._comment_id += 1
        comment_id = str(self._comment_id)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:00Z")

        # Ensure Comments part exists in the document
        comments_part = self._get_or_create_comments_part(doc)

        # Create the comment element
        comment_el = OxmlElement("w:comment")
        comment_el.set(qn("w:id"), comment_id)
        comment_el.set(qn("w:author"), author)
        comment_el.set(qn("w:date"), now)
        comment_el.set(qn("w:initials"), "NMT")

        # Add comment text as a paragraph inside the comment
        comment_para = OxmlElement("w:p")
        comment_run = OxmlElement("w:r")
        comment_text = OxmlElement("w:t")
        comment_text.text = text
        comment_run.append(comment_text)
        comment_para.append(comment_run)
        comment_el.append(comment_para)

        comments_part.append(comment_el)

        # Add comment range start/end markers in the paragraph
        p_element = paragraph._p

        # commentRangeStart at beginning of paragraph
        range_start = OxmlElement("w:commentRangeStart")
        range_start.set(qn("w:id"), comment_id)
        p_element.insert(0, range_start)

        # commentRangeEnd at end of paragraph
        range_end = OxmlElement("w:commentRangeEnd")
        range_end.set(qn("w:id"), comment_id)
        p_element.append(range_end)

        # commentReference run at end of paragraph
        ref_run = OxmlElement("w:r")
        ref_rpr = OxmlElement("w:rPr")
        ref_style = OxmlElement("w:rStyle")
        ref_style.set(qn("w:val"), "CommentReference")
        ref_rpr.append(ref_style)
        ref_run.append(ref_rpr)
        comment_ref = OxmlElement("w:commentReference")
        comment_ref.set(qn("w:id"), comment_id)
        ref_run.append(comment_ref)
        p_element.append(ref_run)

    def _get_or_create_comments_part(self, doc: Document):
        """
        Get or create the w:comments element in the document's comments part.
        """
        # Check if we already cached it
        if hasattr(doc, "_nda_comments_element"):
            return doc._nda_comments_element

        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from docx.opc.part import Part
        from docx.opc.packuri import PackURI
        import lxml.etree as etree

        # Look for existing comments part
        doc_part = doc.part
        comments_part_found = None

        for rel in doc_part.rels.values():
            if "comments" in rel.reltype:
                comments_part_found = rel.target_part
                break

        if comments_part_found is not None:
            # Parse existing comments XML
            comments_element = etree.fromstring(comments_part_found.blob)
            doc._nda_comments_element = comments_element
            doc._nda_comments_part = comments_part_found
            return comments_element

        # Create new comments part
        comments_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:comments xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"'
            ' xmlns:mo="http://schemas.microsoft.com/office/mac/office/2008/main"'
            ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
            ' xmlns:mv="urn:schemas-microsoft-com:mac:vml"'
            ' xmlns:o="urn:schemas-microsoft-com:office:office"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            ' xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
            ' xmlns:v="urn:schemas-microsoft-com:vml"'
            ' xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"'
            ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
            ' xmlns:w10="urn:schemas-microsoft-com:office:word"'
            ' xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            ' xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'
            ' xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"'
            ' xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"'
            ' xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"'
            ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
            " mc:Ignorable=\"w14 wp14\">"
            "</w:comments>"
        )

        comments_part = Part(
            PackURI("/word/comments.xml"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
            comments_xml.encode("utf-8"),
            doc_part.package,
        )

        doc_part.relate_to(
            comments_part,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
        )

        comments_element = etree.fromstring(comments_part.blob)

        # We need to update the part's blob when saving, so we'll monkey-patch
        doc._nda_comments_element = comments_element
        doc._nda_comments_part = comments_part

        # Override save to update comments
        original_save = doc.save

        def patched_save(path_or_stream):
            # Update the comments part blob before saving
            if hasattr(doc, "_nda_comments_part") and hasattr(
                doc, "_nda_comments_element"
            ):
                doc._nda_comments_part._blob = etree.tostring(
                    doc._nda_comments_element, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            original_save(path_or_stream)

        doc.save = patched_save

        return comments_element


class _RunWrapper:
    """Minimal wrapper around a w:r XML element to match python-docx Run interface."""

    def __init__(self, r_element):
        self._r = r_element

    @property
    def font(self):
        return _FontWrapper(self._r)


class _FontWrapper:
    """Minimal font wrapper for direct XML manipulation."""

    def __init__(self, r_element):
        self._r = r_element
        self._rpr = r_element.find(qn("w:rPr"))
        if self._rpr is None:
            self._rpr = OxmlElement("w:rPr")
            r_element.insert(0, self._rpr)

    @property
    def color(self):
        return self

    @color.setter
    def color(self, _):
        pass

    def _set_rgb(self, rgb_color):
        color_el = self._rpr.find(qn("w:color"))
        if color_el is None:
            color_el = OxmlElement("w:color")
            self._rpr.append(color_el)
        color_el.set(qn("w:val"), str(rgb_color))

    @property
    def rgb(self):
        return None

    @rgb.setter
    def rgb(self, value):
        self._set_rgb(value)

    @property
    def strike(self):
        return self._rpr.find(qn("w:strike")) is not None

    @strike.setter
    def strike(self, value):
        existing = self._rpr.find(qn("w:strike"))
        if value and existing is None:
            self._rpr.append(OxmlElement("w:strike"))
        elif not value and existing is not None:
            self._rpr.remove(existing)

    @property
    def underline(self):
        return None

    @underline.setter
    def underline(self, value):
        u_el = self._rpr.find(qn("w:u"))
        if value and u_el is None:
            u_el = OxmlElement("w:u")
            u_el.set(qn("w:val"), "single")
            self._rpr.append(u_el)
        elif not value and u_el is not None:
            self._rpr.remove(u_el)


def _format_deletion(run):
    """Apply deletion formatting: red color + strikethrough."""
    run.font.color.rgb = DELETION_COLOR
    run.font.strike = True


def _format_insertion(run):
    """Apply insertion formatting: blue color + underline."""
    if isinstance(run, _RunWrapper):
        run.font.color.rgb = INSERTION_COLOR
        run.font.underline = True
    else:
        run.font.color.rgb = INSERTION_COLOR
        run.font.underline = True


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into single spaces."""
    return re.sub(r"\s+", " ", text.strip())


def _map_normalized_to_original(
    original_text: str, norm_start: int, norm_end: int
) -> Optional[tuple[int, int]]:
    """
    Map character positions from normalized text back to original text.

    When we normalize whitespace for matching, we need to map the match
    positions back to the original text's character positions.
    """
    # Build mapping: normalized_index -> original_index
    norm_to_orig = []
    in_whitespace = False
    norm_idx = 0

    # Skip leading whitespace
    orig_start_offset = 0
    for ch in original_text:
        if ch in " \t\n\r":
            orig_start_offset += 1
        else:
            break

    for orig_idx in range(orig_start_offset, len(original_text)):
        ch = original_text[orig_idx]
        if ch in " \t\n\r":
            if not in_whitespace:
                norm_to_orig.append(orig_idx)
                norm_idx += 1
                in_whitespace = True
        else:
            norm_to_orig.append(orig_idx)
            norm_idx += 1
            in_whitespace = False

    if norm_start >= len(norm_to_orig) or norm_end > len(norm_to_orig):
        return None

    orig_start = norm_to_orig[norm_start]
    orig_end = norm_to_orig[norm_end - 1] + 1

    return (orig_start, orig_end)


def extract_document_text(doc_path: str) -> str:
    """Extract all text from a Word document, preserving paragraph structure."""
    doc = Document(doc_path)
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also extract from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if text:
                        paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_document_structure(doc_path: str) -> list[dict]:
    """
    Extract document structure with paragraph indices, styles, and text.
    This helps Claude understand the document layout for precise changes.
    """
    doc = Document(doc_path)
    structure = []

    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text:
            structure.append(
                {
                    "index": idx,
                    "style": para.style.name if para.style else "Normal",
                    "text": text,
                    "is_heading": para.style.name.startswith("Heading")
                    if para.style
                    else False,
                }
            )

    return structure
