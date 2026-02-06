import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getDocument,
  analyzeDocument,
  approveAllChanges,
  generateMarkup,
  getDownloadUrl,
} from "../services/api";
import StatusBadge from "../components/StatusBadge";
import ChangeReview from "../components/ChangeReview";

export default function DocumentPage() {
  const { docId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  function loadDocument() {
    getDocument(docId)
      .then((data) => {
        setDoc(data);
        setChanges(data.changes || []);
        if (data.markup_result) {
          setResult(data.markup_result);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadDocument();
  }, [docId]);

  async function handleAnalyze() {
    setActionLoading(true);
    setError(null);
    try {
      const data = await analyzeDocument(docId);
      setChanges(data.changes || []);
      loadDocument();
    } catch (err) {
      setError(err.message);
    }
    setActionLoading(false);
  }

  async function handleApproveAll() {
    setActionLoading(true);
    try {
      await approveAllChanges(docId);
      setChanges((prev) =>
        prev.map((c) =>
          c.status === "pending" ? { ...c, status: "approved" } : c
        )
      );
    } catch (err) {
      setError(err.message);
    }
    setActionLoading(false);
  }

  async function handleGenerate() {
    setActionLoading(true);
    setError(null);
    try {
      const data = await generateMarkup(docId);
      setResult(data);
      loadDocument();
    } catch (err) {
      setError(err.message);
    }
    setActionLoading(false);
  }

  function handleChangeStatus(changeId, newStatus) {
    setChanges((prev) =>
      prev.map((c) => (c.id === changeId ? { ...c, status: newStatus } : c))
    );
  }

  if (loading) return <p className="text-gray-500">Loading document...</p>;
  if (!doc) return <p className="text-red-500">Document not found</p>;

  const approvedCount = changes.filter((c) => c.status === "approved").length;
  const pendingCount = changes.filter((c) => c.status === "pending").length;
  const rejectedCount = changes.filter((c) => c.status === "rejected").length;

  return (
    <div>
      <button
        onClick={() => navigate(`/projects/${doc.project_id}`)}
        className="text-sm text-blue-600 hover:text-blue-800 mb-4 block"
      >
        &larr; Back to project
      </button>

      {/* Document header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{doc.filename}</h1>
            <p className="text-sm text-gray-500 mt-1">
              Mode: {doc.markup_mode} | Status: {doc.status}
            </p>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-4 flex flex-wrap gap-3">
          {doc.status === "uploaded" && (
            <button
              onClick={handleAnalyze}
              disabled={actionLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
            >
              {actionLoading ? "Analyzing..." : "Analyze with Claude"}
            </button>
          )}

          {changes.length > 0 && pendingCount > 0 && (
            <button
              onClick={handleApproveAll}
              disabled={actionLoading}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
            >
              Approve All ({pendingCount})
            </button>
          )}

          {approvedCount > 0 && (
            <button
              onClick={handleGenerate}
              disabled={actionLoading}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium"
            >
              {actionLoading
                ? "Generating..."
                : `Generate Markup (${approvedCount} changes)`}
            </button>
          )}

          {(doc.status === "completed" || result) && (
            <a
              href={getDownloadUrl(docId)}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 text-sm font-medium inline-block"
            >
              Download Marked-Up Document
            </a>
          )}
        </div>
      </div>

      {/* Results summary */}
      {result && result.stats && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Markup Results
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {result.stats.total_changes}
              </p>
              <p className="text-xs text-gray-500">Total Changes</p>
            </div>
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-green-700">
                {result.stats.applied}
              </p>
              <p className="text-xs text-gray-500">Applied</p>
            </div>
            <div className="bg-red-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-red-700">
                {result.stats.failed}
              </p>
              <p className="text-xs text-gray-500">Failed</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-blue-700">
                {Object.keys(result.stats.by_type || {}).length}
              </p>
              <p className="text-xs text-gray-500">Change Types</p>
            </div>
          </div>
        </div>
      )}

      {/* Change review */}
      {changes.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Changes ({changes.length})
            </h2>
            <div className="flex gap-3 text-sm text-gray-500">
              <span className="text-green-600">{approvedCount} approved</span>
              <span className="text-gray-400">{pendingCount} pending</span>
              <span className="text-red-600">{rejectedCount} rejected</span>
            </div>
          </div>
          <div className="space-y-3">
            {changes.map((change) => (
              <ChangeReview
                key={change.id}
                change={change}
                onStatusChange={handleChangeStatus}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
