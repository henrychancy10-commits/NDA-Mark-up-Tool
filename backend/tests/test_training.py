"""
Tests for the training diff engine and training API endpoints.
"""

import io
import json
import os
import sys

from docx import Document

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.create_app import create_app
from app.services.training import (
    compute_diffs,
    extract_patterns_from_examples,
    build_training_context,
    diffs_to_json,
)


def _make_nda_bytes(paragraphs):
    """Create a .docx from a list of paragraph strings."""
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def test_compute_diffs_basic():
    """Test that basic diffs are found between original and negotiated text."""
    original = "This Agreement shall last for five (5) years.\n\nThe Receiving Party shall not disclose."
    negotiated = "This Agreement shall last for two (2) years.\n\nThe Receiving Party shall not disclose."

    diffs = compute_diffs(original, negotiated)
    assert len(diffs) > 0

    # Should find the term change
    found = False
    for d in diffs:
        if "five" in d.original_text or "two" in d.negotiated_text:
            found = True
    assert found, "Should detect the term length change"
    print("PASS: test_compute_diffs_basic")


def test_compute_diffs_addition():
    """Test detecting added text."""
    original = "Clause A.\n\nClause C."
    negotiated = "Clause A.\n\nClause B (new).\n\nClause C."

    diffs = compute_diffs(original, negotiated)
    added = [d for d in diffs if d.diff_type == "added"]
    assert len(added) > 0, "Should detect added clause"
    print("PASS: test_compute_diffs_addition")


def test_compute_diffs_removal():
    """Test detecting removed text."""
    original = "Clause A.\n\nClause B.\n\nClause C."
    negotiated = "Clause A.\n\nClause C."

    diffs = compute_diffs(original, negotiated)
    removed = [d for d in diffs if d.diff_type == "removed"]
    assert len(removed) > 0, "Should detect removed clause"
    print("PASS: test_compute_diffs_removal")


def test_extract_patterns():
    """Test pattern extraction from multiple examples."""
    examples = [
        {
            "diffs": [
                {"diff_type": "changed", "original_text": "five (5) years", "negotiated_text": "two (2) years", "context_before": "", "context_after": ""},
                {"diff_type": "removed", "original_text": "including but not limited to", "negotiated_text": "", "context_before": "", "context_after": ""},
            ]
        },
        {
            "diffs": [
                {"diff_type": "changed", "original_text": "five (5) years", "negotiated_text": "two (2) years", "context_before": "", "context_after": ""},
                {"diff_type": "removed", "original_text": "including but not limited to", "negotiated_text": "", "context_before": "", "context_after": ""},
            ]
        },
    ]

    patterns = extract_patterns_from_examples(examples)
    assert len(patterns) > 0

    # Patterns seen in both examples should have frequency >= 2
    high_freq = [p for p in patterns if p["frequency"] >= 2]
    assert len(high_freq) >= 1, "Should find recurring patterns"
    print("PASS: test_extract_patterns")


def test_build_training_context():
    """Test that training context is built properly for Claude prompt."""
    patterns = [
        {
            "pattern_type": "always_replace",
            "description": "Replace five years with two years",
            "original_pattern": "five (5) years",
            "replacement_pattern": "two (2) years",
            "frequency": 3,
            "examples": [],
        },
        {
            "pattern_type": "always_remove",
            "description": "Remove catch-all language",
            "original_pattern": "including but not limited to",
            "replacement_pattern": "",
            "frequency": 2,
            "examples": [],
        },
    ]

    context = build_training_context(patterns)
    assert "Learned Negotiation Patterns" in context
    assert "five (5) years" in context
    assert "including but not limited to" in context
    assert "seen 3x" in context
    print("PASS: test_build_training_context")


def test_training_api_full_flow():
    """Test the full training API: upload pair, analyze, extract patterns."""
    app = create_app()

    # Create two NDA versions
    original_paras = [
        "NON-DISCLOSURE AGREEMENT",
        "This Agreement shall remain in effect for a period of five (5) years.",
        "Confidential Information means any and all information, including but not limited to trade secrets.",
        "This Agreement shall be governed by the laws of the State of Delaware.",
    ]
    negotiated_paras = [
        "NON-DISCLOSURE AGREEMENT",
        "This Agreement shall remain in effect for a period of two (2) years.",
        "Confidential Information means any and all information relating to trade secrets.",
        "This Agreement shall be governed by the laws of the State of California.",
    ]

    with app.test_client() as client:
        # Create project
        r = client.post("/api/projects", json={"name": "Training Test"})
        assert r.status_code == 201
        project_id = r.get_json()["id"]

        # Upload training pair
        orig_bytes = _make_nda_bytes(original_paras)
        neg_bytes = _make_nda_bytes(negotiated_paras)

        r = client.post(
            f"/api/projects/{project_id}/training/upload",
            data={
                "original": (orig_bytes, "original.docx"),
                "negotiated": (neg_bytes, "negotiated.docx"),
                "name": "Test NDA Pair",
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 201
        result = r.get_json()
        assert result["status"] == "analyzed"
        assert result["diffs_count"] > 0
        print(f"  Uploaded pair: {result['diffs_count']} diffs found")

        # Upload a second pair (same pattern)
        orig_bytes2 = _make_nda_bytes(original_paras)
        neg_bytes2 = _make_nda_bytes(negotiated_paras)
        r = client.post(
            f"/api/projects/{project_id}/training/upload",
            data={
                "original": (orig_bytes2, "original2.docx"),
                "negotiated": (neg_bytes2, "negotiated2.docx"),
                "name": "Test NDA Pair 2",
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 201

        # List training examples
        r = client.get(f"/api/projects/{project_id}/training")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["examples"]) == 2

        # Extract patterns
        r = client.post(f"/api/projects/{project_id}/training/extract-patterns")
        assert r.status_code == 200
        result = r.get_json()
        assert result["patterns_count"] > 0
        print(f"  Extracted {result['patterns_count']} patterns from {result['from_examples']} examples")

        # Verify patterns are in project data
        r = client.get(f"/api/projects/{project_id}")
        project_data = r.get_json()
        assert len(project_data["training_patterns"]) > 0
        print(f"  Project has {len(project_data['training_patterns'])} active patterns")

        # Toggle a pattern off
        pattern_id = project_data["training_patterns"][0]["id"]
        r = client.post(
            f"/api/training/patterns/{pattern_id}/toggle",
            json={"active": False},
            content_type="application/json",
        )
        assert r.status_code == 200

        # Delete an example
        example_id = data["examples"][0]["id"]
        r = client.delete(f"/api/training/{example_id}")
        assert r.status_code == 200

        r = client.get(f"/api/projects/{project_id}/training")
        assert len(r.get_json()["examples"]) == 1

        print("PASS: test_training_api_full_flow")


def test_upload_original_then_negotiated_later():
    """Test uploading original first, then negotiated separately."""
    app = create_app()

    paras_orig = ["Term: five (5) years."]
    paras_neg = ["Term: two (2) years."]

    with app.test_client() as client:
        client.post("/api/projects", json={"name": "Staged Upload"})

        # Upload only original
        orig_bytes = _make_nda_bytes(paras_orig)
        r = client.post(
            "/api/projects/1/training/upload",
            data={"original": (orig_bytes, "orig.docx"), "name": "Staged"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 201
        result = r.get_json()
        example_id = result["id"]
        assert result["status"] == "uploaded"  # No negotiated yet

        # Upload negotiated separately
        neg_bytes = _make_nda_bytes(paras_neg)
        r = client.post(
            f"/api/training/{example_id}/negotiated",
            data={"file": (neg_bytes, "neg.docx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        result = r.get_json()
        assert result["status"] == "analyzed"
        assert result["diffs_count"] > 0
        print("PASS: test_upload_original_then_negotiated_later")


if __name__ == "__main__":
    test_compute_diffs_basic()
    test_compute_diffs_addition()
    test_compute_diffs_removal()
    test_extract_patterns()
    test_build_training_context()

    # Reset DB for API tests
    import os
    os.environ["DATABASE_PATH"] = "test_training.db"
    if os.path.exists("test_training.db"):
        os.remove("test_training.db")

    test_training_api_full_flow()

    if os.path.exists("test_training.db"):
        os.remove("test_training.db")

    test_upload_original_then_negotiated_later()

    if os.path.exists("test_training.db"):
        os.remove("test_training.db")

    print("\nAll training tests passed!")
