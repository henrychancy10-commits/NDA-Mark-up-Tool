import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getProject,
  getTraining,
  uploadTrainingPair,
  uploadNegotiated,
  deleteTrainingExample,
  extractPatterns,
  togglePattern,
} from "../services/api";

export default function TrainingPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [examples, setExamples] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState(null);
  const [expandedExample, setExpandedExample] = useState(null);

  // Upload form state
  const [pairName, setPairName] = useState("");
  const [notes, setNotes] = useState("");
  const [originalFile, setOriginalFile] = useState(null);
  const [negotiatedFile, setNegotiatedFile] = useState(null);
  const origRef = useRef(null);
  const negRef = useRef(null);

  function loadData() {
    Promise.all([getProject(projectId), getTraining(projectId)])
      .then(([proj, training]) => {
        setProject(proj);
        setExamples(training.examples || []);
        setPatterns(training.patterns || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadData();
  }, [projectId]);

  async function handleUpload(e) {
    e.preventDefault();
    if (!originalFile) return;
    setUploading(true);
    setError(null);
    try {
      await uploadTrainingPair(projectId, originalFile, negotiatedFile, pairName, notes);
      setPairName("");
      setNotes("");
      setOriginalFile(null);
      setNegotiatedFile(null);
      if (origRef.current) origRef.current.value = "";
      if (negRef.current) negRef.current.value = "";
      loadData();
    } catch (err) {
      setError(err.message);
    }
    setUploading(false);
  }

  async function handleUploadNegotiated(exampleId, file) {
    setError(null);
    try {
      await uploadNegotiated(exampleId, file);
      loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(exampleId) {
    if (!confirm("Delete this training example?")) return;
    try {
      await deleteTrainingExample(exampleId);
      loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleExtractPatterns() {
    setExtracting(true);
    setError(null);
    try {
      const result = await extractPatterns(projectId);
      setPatterns(result.patterns || []);
      loadData();
    } catch (err) {
      setError(err.message);
    }
    setExtracting(false);
  }

  async function handleTogglePattern(patternId, active) {
    try {
      await togglePattern(patternId, active);
      setPatterns((prev) =>
        prev.map((p) => (p.id === patternId ? { ...p, active: active ? 1 : 0 } : p))
      );
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-gray-500">Loading...</p>;

  const analyzedCount = examples.filter((e) => e.status === "analyzed").length;

  return (
    <div>
      <button
        onClick={() => navigate(`/projects/${projectId}`)}
        className="text-sm text-blue-600 hover:text-blue-800 mb-4 block"
      >
        &larr; Back to project
      </button>

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Training Mode{project ? `: ${project.name}` : ""}
        </h1>
        <p className="text-gray-500 mt-1">
          Upload pairs of clean NDAs and their fully negotiated versions.
          The tool learns your negotiation patterns to improve future markup.
        </p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Upload form */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Upload Training Pair
        </h2>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name (optional)
            </label>
            <input
              type="text"
              value={pairName}
              onChange={(e) => setPairName(e.target.value)}
              placeholder="e.g., Acme Corp NDA - Jan 2025"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Clean / Original NDA (.docx) *
              </label>
              <input
                ref={origRef}
                type="file"
                accept=".docx"
                onChange={(e) => setOriginalFile(e.target.files[0])}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 file:mr-3 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1 file:text-sm file:text-blue-700"
                required
              />
              <p className="text-xs text-gray-400 mt-1">
                The original NDA before any negotiation
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Negotiated / Final Version (.docx or .pdf)
              </label>
              <input
                ref={negRef}
                type="file"
                accept=".docx,.pdf"
                onChange={(e) => setNegotiatedFile(e.target.files[0])}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 file:mr-3 file:rounded file:border-0 file:bg-green-50 file:px-3 file:py-1 file:text-sm file:text-green-700"
              />
              <p className="text-xs text-gray-400 mt-1">
                The fully negotiated version (can add later)
              </p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any context about this NDA negotiation..."
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={uploading || !originalFile}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
          >
            {uploading ? "Uploading..." : "Upload Training Pair"}
          </button>
        </form>
      </div>

      {/* Training examples list */}
      {examples.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Training Examples ({examples.length})
            </h2>
            {analyzedCount > 0 && (
              <button
                onClick={handleExtractPatterns}
                disabled={extracting}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium"
              >
                {extracting
                  ? "Extracting..."
                  : `Learn Patterns (${analyzedCount} examples)`}
              </button>
            )}
          </div>

          <div className="space-y-3">
            {examples.map((ex) => (
              <div
                key={ex.id}
                className="bg-white border border-gray-200 rounded-lg p-4"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {ex.name || ex.original_filename}
                    </h3>
                    <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                      <span>Original: {ex.original_filename}</span>
                      {ex.negotiated_filename && (
                        <span>Negotiated: {ex.negotiated_filename}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full ${
                        ex.status === "analyzed"
                          ? "bg-green-100 text-green-800"
                          : ex.status === "error"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {ex.status}
                    </span>
                    <button
                      onClick={() => handleDelete(ex.id)}
                      className="text-red-400 hover:text-red-600 text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {/* Upload negotiated if missing */}
                {!ex.negotiated_path && (
                  <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded">
                    <p className="text-sm text-amber-700 mb-2">
                      Upload the negotiated version to analyze differences:
                    </p>
                    <input
                      type="file"
                      accept=".docx,.pdf"
                      onChange={(e) => {
                        if (e.target.files[0]) handleUploadNegotiated(ex.id, e.target.files[0]);
                      }}
                      className="text-sm"
                    />
                  </div>
                )}

                {/* Summary stats */}
                {ex.summary && ex.summary.total_diffs > 0 && (
                  <div className="mt-3">
                    <div className="flex gap-4 text-sm">
                      <span className="text-gray-600">
                        {ex.summary.total_diffs} differences found:
                      </span>
                      {ex.summary.added > 0 && (
                        <span className="text-green-600">+{ex.summary.added} added</span>
                      )}
                      {ex.summary.removed > 0 && (
                        <span className="text-red-600">-{ex.summary.removed} removed</span>
                      )}
                      {ex.summary.changed > 0 && (
                        <span className="text-blue-600">~{ex.summary.changed} changed</span>
                      )}
                    </div>
                    <button
                      onClick={() =>
                        setExpandedExample(expandedExample === ex.id ? null : ex.id)
                      }
                      className="text-sm text-blue-600 hover:text-blue-800 mt-1"
                    >
                      {expandedExample === ex.id ? "Hide diffs" : "Show diffs"}
                    </button>
                  </div>
                )}

                {/* Expanded diffs */}
                {expandedExample === ex.id && ex.diffs && (
                  <div className="mt-3 space-y-2 max-h-96 overflow-y-auto">
                    {ex.diffs.map((diff, idx) => (
                      <div
                        key={idx}
                        className="border border-gray-100 rounded p-3 text-sm"
                      >
                        <span
                          className={`px-1.5 py-0.5 text-xs rounded ${
                            diff.diff_type === "added"
                              ? "bg-green-100 text-green-700"
                              : diff.diff_type === "removed"
                                ? "bg-red-100 text-red-700"
                                : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {diff.diff_type}
                        </span>
                        {diff.original_text && (
                          <p className="mt-1 text-red-700 line-through font-mono text-xs">
                            {diff.original_text}
                          </p>
                        )}
                        {diff.negotiated_text && (
                          <p className="mt-1 text-green-700 underline font-mono text-xs">
                            {diff.negotiated_text}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learned patterns */}
      {patterns.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Learned Patterns ({patterns.length})
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            These patterns will be used when analyzing new NDAs. Toggle off any
            patterns you don't want applied.
          </p>
          <div className="space-y-2">
            {patterns.map((pattern) => (
              <div
                key={pattern.id}
                className={`bg-white border rounded-lg p-4 ${
                  pattern.active ? "border-gray-200" : "border-gray-100 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          pattern.pattern_type === "always_remove"
                            ? "bg-red-100 text-red-700"
                            : pattern.pattern_type === "always_add"
                              ? "bg-green-100 text-green-700"
                              : "bg-blue-100 text-blue-700"
                        }`}
                      >
                        {pattern.pattern_type.replace("always_", "")}
                      </span>
                      {pattern.frequency > 1 && (
                        <span className="text-xs text-gray-400">
                          seen {pattern.frequency}x
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-800">
                      {pattern.description}
                    </p>
                  </div>
                  <label className="flex items-center gap-2 ml-4 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!pattern.active}
                      onChange={(e) =>
                        handleTogglePattern(pattern.id, e.target.checked)
                      }
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    <span className="text-xs text-gray-500">Active</span>
                  </label>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {examples.length === 0 && patterns.length === 0 && (
        <div className="text-center py-12 bg-white border border-gray-200 rounded-lg">
          <p className="text-gray-500 text-lg">No training data yet</p>
          <p className="text-gray-400 mt-1">
            Upload pairs of clean and negotiated NDAs above to teach the tool
            your negotiation style.
          </p>
        </div>
      )}
    </div>
  );
}
