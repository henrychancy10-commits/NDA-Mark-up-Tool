"""
Flask API routes for the NDA Markup Tool.
"""

import json
import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app.models.database import (
    create_document,
    create_guideline,
    create_project,
    create_training_example,
    delete_training_example,
    get_changes,
    get_document,
    get_guidelines_for_project,
    get_markup_result,
    get_project,
    get_training_example,
    get_training_patterns,
    list_documents,
    list_projects,
    list_training_examples,
    save_changes,
    save_markup_result,
    save_training_patterns,
    toggle_training_pattern,
    update_change_status,
    update_document_status,
    update_training_example,
)
from app.services.claude_analyzer import ClaudeAnalyzer
from app.services.document_markup import (
    Change,
    DocumentMarkupEngine,
    extract_document_structure,
    extract_document_text,
)
from app.services.guideline_parser import parse_guidelines
from app.services.training import (
    analyze_training_pair,
    build_training_context,
    extract_patterns_from_examples,
)

api = Blueprint("api", __name__, url_prefix="/api")


def _build_summary(changes: list, doc_text: str) -> dict:
    """Build a summary report from change objects (no API key needed)."""
    stats = {"total": len(changes), "by_type": {}, "by_priority": {}, "applied": 0, "failed": 0}
    for c in changes:
        ct = c.change_type if hasattr(c, "change_type") else c.get("change_type", "")
        pr = c.priority if hasattr(c, "priority") else c.get("priority", "medium")
        ap = c.applied if hasattr(c, "applied") else c.get("applied", False)
        stats["by_type"][ct] = stats["by_type"].get(ct, 0) + 1
        stats["by_priority"][pr] = stats["by_priority"].get(pr, 0) + 1
        if ap:
            stats["applied"] += 1
        else:
            stats["failed"] += 1

    change_log = []
    for c in changes:
        if hasattr(c, "change_type"):
            change_log.append({
                "type": c.change_type, "section": c.section,
                "original": c.original_text, "new": c.new_text,
                "rationale": c.rationale, "priority": c.priority, "applied": c.applied,
            })
        else:
            change_log.append(c)

    return {"statistics": stats, "change_log": change_log}

ALLOWED_DOC_EXTENSIONS = {".docx"}
ALLOWED_GUIDELINE_EXTENSIONS = {".docx", ".doc", ".pdf", ".txt"}
ALLOWED_TRAINING_EXTENSIONS = {".docx", ".pdf"}


def _allowed_file(filename: str, allowed: set) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed


def _unique_filename(filename: str) -> str:
    name, ext = os.path.splitext(secure_filename(filename))
    return f"{name}_{uuid.uuid4().hex[:8]}{ext}"


# --- Project endpoints ---


@api.route("/projects", methods=["GET"])
def api_list_projects():
    projects = list_projects()
    return jsonify(projects)


@api.route("/projects", methods=["POST"])
def api_create_project():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Project name is required"}), 400
    project_id = create_project(data["name"], data.get("description", ""))
    project = get_project(project_id)
    return jsonify(project), 201


@api.route("/projects/<int:project_id>", methods=["GET"])
def api_get_project(project_id):
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    project["documents"] = list_documents(project_id)
    project["guidelines"] = get_guidelines_for_project(project_id)
    project["training_examples"] = list_training_examples(project_id)
    project["training_patterns"] = get_training_patterns(project_id)
    return jsonify(project)


# --- Guidelines endpoints ---


@api.route("/projects/<int:project_id>/guidelines", methods=["POST"])
def api_upload_guidelines(project_id):
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename, ALLOWED_GUIDELINE_EXTENSIONS):
        return (
            jsonify(
                {
                    "error": f"Unsupported file type. Allowed: {', '.join(ALLOWED_GUIDELINE_EXTENSIONS)}"
                }
            ),
            400,
        )

    filename = _unique_filename(file.filename)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Parse guidelines text
    try:
        content_text = parse_guidelines(filepath)
    except Exception as e:
        return jsonify({"error": f"Failed to parse guidelines: {str(e)}"}), 400

    gid = create_guideline(project_id, file.filename, filepath, content_text)

    return jsonify({"id": gid, "filename": file.filename, "status": "uploaded"}), 201


# --- Document endpoints ---


@api.route("/projects/<int:project_id>/documents", methods=["POST"])
def api_upload_document(project_id):
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename, ALLOWED_DOC_EXTENSIONS):
        return jsonify({"error": "Only .docx files are supported for NDA documents"}), 400

    mode = request.form.get("mode", "balanced")
    if mode not in ("full", "critical", "balanced"):
        mode = "balanced"

    filename = _unique_filename(file.filename)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    doc_id = create_document(project_id, file.filename, filepath, mode)

    return (
        jsonify(
            {
                "id": doc_id,
                "filename": file.filename,
                "status": "uploaded",
                "mode": mode,
            }
        ),
        201,
    )


@api.route("/documents/<int:doc_id>", methods=["GET"])
def api_get_document(doc_id):
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    doc["changes"] = get_changes(doc_id)
    result = get_markup_result(doc_id)
    if result:
        doc["markup_result"] = {
            "output_path": result["output_path"],
            "summary": result.get("summary", {}),
            "stats": result.get("stats", {}),
        }
    return jsonify(doc)


# --- Analysis endpoint ---


@api.route("/documents/<int:doc_id>/analyze", methods=["POST"])
def api_analyze_document(doc_id):
    """Run Claude analysis on a document against its project's guidelines."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    project_id = doc["project_id"]
    guidelines = get_guidelines_for_project(project_id)
    if not guidelines:
        return jsonify({"error": "No guidelines uploaded for this project"}), 400

    update_document_status(doc_id, "analyzing")

    try:
        # Extract document text and structure
        doc_text = extract_document_text(doc["original_path"])
        doc_structure = extract_document_structure(doc["original_path"])

        # Combine all guidelines
        all_guidelines = "\n\n---\n\n".join(
            g["content_text"] for g in guidelines if g.get("content_text")
        )

        # Include training patterns if available
        patterns = get_training_patterns(project_id)
        if patterns:
            pattern_dicts = [
                {
                    "pattern_type": p["pattern_type"],
                    "description": p["description"],
                    "original_pattern": p["original_pattern"],
                    "replacement_pattern": p["replacement_pattern"],
                    "frequency": p["frequency"],
                    "examples": p.get("examples", []),
                }
                for p in patterns
            ]
            training_context = build_training_context(pattern_dicts)
            all_guidelines = all_guidelines + "\n\n" + training_context

        # Analyze with Claude
        analyzer = ClaudeAnalyzer()
        changes = analyzer.analyze_nda(
            document_text=doc_text,
            guidelines_text=all_guidelines,
            mode=doc["markup_mode"],
            document_structure=doc_structure,
        )

        # Save changes to DB
        changes_data = [
            {
                "change_type": c.change_type,
                "original_text": c.original_text,
                "new_text": c.new_text,
                "rationale": c.rationale,
                "section": c.section,
                "priority": c.priority,
                "status": "pending",
                "applied": 0,
            }
            for c in changes
        ]
        save_changes(doc_id, changes_data)

        update_document_status(doc_id, "analyzed")

        return jsonify(
            {
                "status": "analyzed",
                "changes_count": len(changes),
                "changes": changes_data,
            }
        )

    except Exception as e:
        update_document_status(doc_id, "error")
        return jsonify({"error": str(e)}), 500


# --- Change review endpoints ---


@api.route("/changes/<int:change_id>/approve", methods=["POST"])
def api_approve_change(change_id):
    update_change_status(change_id, "approved")
    return jsonify({"status": "approved"})


@api.route("/changes/<int:change_id>/reject", methods=["POST"])
def api_reject_change(change_id):
    update_change_status(change_id, "rejected")
    return jsonify({"status": "rejected"})


@api.route("/documents/<int:doc_id>/changes/approve-all", methods=["POST"])
def api_approve_all_changes(doc_id):
    changes = get_changes(doc_id)
    for c in changes:
        if c["status"] == "pending":
            update_change_status(c["id"], "approved")
    return jsonify({"status": "all_approved", "count": len(changes)})


# --- Generate markup endpoint ---


@api.route("/documents/<int:doc_id>/generate", methods=["POST"])
def api_generate_markup(doc_id):
    """Generate the marked-up Word document with approved changes."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    changes_data = get_changes(doc_id)
    approved_changes = [c for c in changes_data if c["status"] == "approved"]

    if not approved_changes:
        return jsonify({"error": "No approved changes to apply"}), 400

    update_document_status(doc_id, "generating")

    try:
        # Convert DB records to Change objects
        changes = [
            Change(
                change_type=c["change_type"],
                original_text=c["original_text"],
                new_text=c["new_text"] or "",
                rationale=c["rationale"] or "",
                section=c["section"] or "",
                priority=c["priority"] or "medium",
            )
            for c in approved_changes
        ]

        # Generate output path
        output_dir = current_app.config["OUTPUT_FOLDER"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"marked_up_{doc_id}_{timestamp}.docx"
        output_path = os.path.join(output_dir, output_filename)

        # Apply markup
        engine = DocumentMarkupEngine()
        stats = engine.apply_markup(
            source_path=doc["original_path"],
            changes=changes,
            output_path=output_path,
        )

        # Generate summary (doesn't need API key - just a local computation)
        doc_text = extract_document_text(doc["original_path"])
        summary = _build_summary(changes, doc_text)

        # Save result to DB
        save_markup_result(doc_id, output_path, summary, stats)
        update_document_status(doc_id, "completed", output_path)

        return jsonify(
            {
                "status": "completed",
                "output_path": output_path,
                "stats": stats,
                "summary": summary,
            }
        )

    except Exception as e:
        update_document_status(doc_id, "error")
        return jsonify({"error": str(e)}), 500


# --- Download endpoint ---


@api.route("/documents/<int:doc_id>/download", methods=["GET"])
def api_download_markup(doc_id):
    """Download the marked-up Word document."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    if not doc.get("markup_path") or not os.path.exists(doc["markup_path"]):
        return jsonify({"error": "Markup document not yet generated"}), 404

    return send_file(
        doc["markup_path"],
        as_attachment=True,
        download_name=f"marked_up_{doc['filename']}",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- Quick markup endpoint (all-in-one for simple use) ---


@api.route("/quick-markup", methods=["POST"])
def api_quick_markup():
    """
    All-in-one endpoint: upload NDA + guidelines, analyze, and generate markup.
    Returns the marked-up document directly.
    """
    if "nda" not in request.files:
        return jsonify({"error": "NDA file is required"}), 400
    if "guidelines" not in request.files:
        return jsonify({"error": "Guidelines file is required"}), 400

    nda_file = request.files["nda"]
    guidelines_file = request.files["guidelines"]
    mode = request.form.get("mode", "balanced")

    if not _allowed_file(nda_file.filename, ALLOWED_DOC_EXTENSIONS):
        return jsonify({"error": "NDA must be a .docx file"}), 400
    if not _allowed_file(guidelines_file.filename, ALLOWED_GUIDELINE_EXTENSIONS):
        return jsonify({"error": "Unsupported guidelines format"}), 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    output_dir = current_app.config["OUTPUT_FOLDER"]

    # Save uploads
    nda_filename = _unique_filename(nda_file.filename)
    nda_path = os.path.join(upload_dir, nda_filename)
    nda_file.save(nda_path)

    guidelines_filename = _unique_filename(guidelines_file.filename)
    guidelines_path = os.path.join(upload_dir, guidelines_filename)
    guidelines_file.save(guidelines_path)

    try:
        # Parse guidelines
        guidelines_text = parse_guidelines(guidelines_path)

        # Extract NDA text and structure
        doc_text = extract_document_text(nda_path)
        doc_structure = extract_document_structure(nda_path)

        # Analyze with Claude
        analyzer = ClaudeAnalyzer()
        changes = analyzer.analyze_nda(
            document_text=doc_text,
            guidelines_text=guidelines_text,
            mode=mode,
            document_structure=doc_structure,
        )

        # Generate output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"marked_up_{timestamp}.docx"
        output_path = os.path.join(output_dir, output_filename)

        engine = DocumentMarkupEngine()
        stats = engine.apply_markup(
            source_path=nda_path,
            changes=changes,
            output_path=output_path,
        )

        summary = _build_summary(changes, doc_text)

        return jsonify(
            {
                "status": "completed",
                "stats": stats,
                "summary": summary,
                "download_url": f"/api/download/{output_filename}",
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/download/<filename>", methods=["GET"])
def api_download_file(filename):
    """Download a generated file by filename."""
    output_dir = current_app.config["OUTPUT_FOLDER"]
    filepath = os.path.join(output_dir, secure_filename(filename))
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_file(
        filepath,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- Training endpoints ---


@api.route("/projects/<int:project_id>/training", methods=["GET"])
def api_list_training(project_id):
    """List all training examples and patterns for a project."""
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    examples = list_training_examples(project_id)
    patterns = get_training_patterns(project_id)
    return jsonify({"examples": examples, "patterns": patterns})


@api.route("/projects/<int:project_id>/training/upload", methods=["POST"])
def api_upload_training_pair(project_id):
    """
    Upload a training pair: clean NDA (.docx) + negotiated version (.docx or .pdf).
    Both files can be uploaded together, or the negotiated version can be added later.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    if "original" not in request.files:
        return jsonify({"error": "Original NDA file is required"}), 400

    original_file = request.files["original"]
    if not original_file.filename:
        return jsonify({"error": "No original file selected"}), 400

    if not _allowed_file(original_file.filename, ALLOWED_DOC_EXTENSIONS):
        return jsonify({"error": "Original NDA must be a .docx file"}), 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    name = request.form.get("name", original_file.filename)
    notes = request.form.get("notes", "")

    # Save original
    orig_filename = _unique_filename(original_file.filename)
    orig_path = os.path.join(upload_dir, orig_filename)
    original_file.save(orig_path)

    neg_filename = ""
    neg_path = ""

    # Save negotiated if provided
    if "negotiated" in request.files:
        neg_file = request.files["negotiated"]
        if neg_file.filename and _allowed_file(neg_file.filename, ALLOWED_TRAINING_EXTENSIONS):
            neg_filename = _unique_filename(neg_file.filename)
            neg_path = os.path.join(upload_dir, neg_filename)
            neg_file.save(neg_path)

    example_id = create_training_example(
        project_id=project_id,
        name=name,
        original_filename=original_file.filename,
        original_path=orig_path,
        negotiated_filename=neg_file.filename if neg_path else "",
        negotiated_path=neg_path,
        notes=notes,
    )

    # If both files provided, immediately compute diffs
    result = {"id": example_id, "status": "uploaded"}
    if neg_path:
        try:
            analysis = analyze_training_pair(orig_path, neg_path, notes)
            update_training_example(
                example_id,
                diffs_json=json.dumps(analysis["diffs"]),
                summary_json=json.dumps(analysis["summary"]),
                status="analyzed",
            )
            result["status"] = "analyzed"
            result["summary"] = analysis["summary"]
            result["diffs_count"] = len(analysis["diffs"])
        except Exception as e:
            update_training_example(example_id, status="error")
            result["status"] = "error"
            result["error"] = str(e)

    return jsonify(result), 201


@api.route("/training/<int:example_id>/negotiated", methods=["POST"])
def api_upload_negotiated(example_id):
    """Upload/replace the negotiated version for an existing training example."""
    example = get_training_example(example_id)
    if not example:
        return jsonify({"error": "Training example not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not _allowed_file(file.filename, ALLOWED_TRAINING_EXTENSIONS):
        return jsonify({"error": "File must be .docx or .pdf"}), 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    filename = _unique_filename(file.filename)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Compute diffs
    try:
        analysis = analyze_training_pair(
            example["original_path"], filepath, example.get("notes", "")
        )
        update_training_example(
            example_id,
            negotiated_filename=file.filename,
            negotiated_path=filepath,
            diffs_json=json.dumps(analysis["diffs"]),
            summary_json=json.dumps(analysis["summary"]),
            status="analyzed",
        )
        return jsonify({
            "status": "analyzed",
            "summary": analysis["summary"],
            "diffs_count": len(analysis["diffs"]),
        })
    except Exception as e:
        update_training_example(example_id, status="error")
        return jsonify({"error": str(e)}), 500


@api.route("/training/<int:example_id>", methods=["GET"])
def api_get_training_example(example_id):
    """Get a training example with its diffs."""
    example = get_training_example(example_id)
    if not example:
        return jsonify({"error": "Training example not found"}), 404
    return jsonify(example)


@api.route("/training/<int:example_id>", methods=["DELETE"])
def api_delete_training_example(example_id):
    """Delete a training example."""
    example = get_training_example(example_id)
    if not example:
        return jsonify({"error": "Training example not found"}), 404
    delete_training_example(example_id)
    return jsonify({"status": "deleted"})


@api.route("/projects/<int:project_id>/training/extract-patterns", methods=["POST"])
def api_extract_patterns(project_id):
    """
    Extract reusable patterns from all analyzed training examples in a project.
    This is the "learn" step that consolidates examples into patterns.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    examples = list_training_examples(project_id)
    analyzed = [e for e in examples if e.get("status") == "analyzed" and e.get("diffs")]

    if not analyzed:
        return jsonify({"error": "No analyzed training examples found. Upload and analyze pairs first."}), 400

    # Extract patterns across all examples
    example_data = [{"diffs": e["diffs"]} for e in analyzed]
    patterns = extract_patterns_from_examples(example_data)

    # Save patterns to DB
    save_training_patterns(project_id, patterns)

    return jsonify({
        "status": "extracted",
        "patterns_count": len(patterns),
        "patterns": patterns,
        "from_examples": len(analyzed),
    })


@api.route("/training/patterns/<int:pattern_id>/toggle", methods=["POST"])
def api_toggle_pattern(pattern_id):
    """Enable or disable a training pattern."""
    data = request.get_json() or {}
    active = data.get("active", True)
    toggle_training_pattern(pattern_id, active)
    return jsonify({"status": "updated", "active": active})
