import { useState } from "react";
import { approveChange, rejectChange } from "../services/api";

const priorityColors = {
  critical: "bg-red-100 text-red-800 border-red-300",
  high: "bg-orange-100 text-orange-800 border-orange-300",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
  low: "bg-gray-100 text-gray-700 border-gray-300",
};

const typeLabels = {
  deletion: "Delete",
  insertion: "Insert",
  replacement: "Replace",
  comment_only: "Comment",
};

export default function ChangeReview({ change, onStatusChange }) {
  const [loading, setLoading] = useState(false);

  async function handleApprove() {
    setLoading(true);
    try {
      await approveChange(change.id);
      onStatusChange(change.id, "approved");
    } catch (err) {
      alert(err.message);
    }
    setLoading(false);
  }

  async function handleReject() {
    setLoading(true);
    try {
      await rejectChange(change.id);
      onStatusChange(change.id, "rejected");
    } catch (err) {
      alert(err.message);
    }
    setLoading(false);
  }

  const statusBadge =
    change.status === "approved" ? (
      <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800">
        Approved
      </span>
    ) : change.status === "rejected" ? (
      <span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-800">
        Rejected
      </span>
    ) : (
      <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
        Pending
      </span>
    );

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 text-xs font-medium rounded border ${priorityColors[change.priority] || priorityColors.medium}`}
          >
            {change.priority}
          </span>
          <span className="px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800">
            {typeLabels[change.change_type] || change.change_type}
          </span>
          {statusBadge}
        </div>
        {change.section && (
          <span className="text-xs text-gray-500">{change.section}</span>
        )}
      </div>

      {change.change_type === "deletion" || change.change_type === "replacement" ? (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-1">Original text:</p>
          <p className="text-sm text-red-700 line-through bg-red-50 px-2 py-1 rounded font-mono">
            {change.original_text}
          </p>
        </div>
      ) : null}

      {change.change_type === "insertion" || change.change_type === "replacement" ? (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-1">
            {change.change_type === "insertion" ? "Insert after:" : "New text:"}
          </p>
          {change.change_type === "insertion" && (
            <p className="text-sm text-gray-600 bg-gray-50 px-2 py-1 rounded font-mono mb-1">
              ...{change.original_text}
            </p>
          )}
          <p className="text-sm text-blue-700 underline bg-blue-50 px-2 py-1 rounded font-mono">
            {change.new_text}
          </p>
        </div>
      ) : null}

      {change.change_type === "comment_only" && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-1">Applies to:</p>
          <p className="text-sm text-gray-700 bg-gray-50 px-2 py-1 rounded font-mono">
            {change.original_text}
          </p>
        </div>
      )}

      {change.rationale && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">Rationale:</p>
          <p className="text-sm text-gray-700 italic">{change.rationale}</p>
        </div>
      )}

      {change.status === "pending" && (
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={loading}
            className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            Approve
          </button>
          <button
            onClick={handleReject}
            disabled={loading}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
