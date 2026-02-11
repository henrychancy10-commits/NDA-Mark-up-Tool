import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getProject,
  uploadGuidelines,
  uploadDocument,
} from "../services/api";
import FileUpload from "../components/FileUpload";
import StatusBadge from "../components/StatusBadge";

export default function ProjectPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [mode, setMode] = useState("balanced");
  const [error, setError] = useState(null);

  function loadProject() {
    getProject(projectId)
      .then(setProject)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadProject();
  }, [projectId]);

  async function handleGuidelinesUpload(file) {
    setUploading(true);
    setError(null);
    try {
      await uploadGuidelines(projectId, file);
      loadProject();
    } catch (err) {
      setError(err.message);
    }
    setUploading(false);
  }

  async function handleDocUpload(file) {
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(projectId, file, mode);
      navigate(`/documents/${doc.id}`);
    } catch (err) {
      setError(err.message);
    }
    setUploading(false);
  }

  if (loading) return <p className="text-gray-500">Loading project...</p>;
  if (!project) return <p className="text-red-500">Project not found</p>;

  const hasGuidelines = project.guidelines && project.guidelines.length > 0;

  return (
    <div>
      <div className="mb-8">
        <button
          onClick={() => navigate("/")}
          className="text-sm text-blue-600 hover:text-blue-800 mb-2 block"
        >
          &larr; Back to projects
        </button>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          <button
            onClick={() => navigate(`/projects/${projectId}/training`)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
          >
            Training Mode
          </button>
        </div>
        {project.description && (
          <p className="text-gray-500 mt-1">{project.description}</p>
        )}
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Step 1: Upload Guidelines */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Step 1: Upload Markup Guidelines
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Upload your markup guidelines document (PDF, Word, or text file).
          These rules will be used to analyze NDA documents.
        </p>
        <FileUpload
          label="Drop guidelines file here (.pdf, .docx, .txt)"
          accept=".pdf,.docx,.doc,.txt"
          onUpload={handleGuidelinesUpload}
          disabled={uploading}
        />
        {hasGuidelines && (
          <div className="mt-3 space-y-1">
            {project.guidelines.map((g) => (
              <div
                key={g.id}
                className="text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded"
              >
                {g.filename}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Step 2: Upload NDA */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Step 2: Upload NDA Document
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Upload the NDA document to analyze (.docx only).
        </p>

        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Markup Mode
          </label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="full">Full - All recommended changes</option>
            <option value="balanced">
              Balanced - Critical + important changes
            </option>
            <option value="critical">
              Critical Only - Essential protections only
            </option>
          </select>
        </div>

        <FileUpload
          label="Drop NDA document here (.docx)"
          accept=".docx"
          onUpload={handleDocUpload}
          disabled={uploading || !hasGuidelines}
        />
        {!hasGuidelines && (
          <p className="text-sm text-amber-600 mt-2">
            Upload guidelines first before uploading an NDA document.
          </p>
        )}
      </div>

      {/* Documents list */}
      {project.documents && project.documents.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Documents
          </h2>
          <div className="space-y-2">
            {project.documents.map((doc) => (
              <div
                key={doc.id}
                onClick={() => navigate(`/documents/${doc.id}`)}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 cursor-pointer transition flex items-center justify-between"
              >
                <div>
                  <p className="font-medium text-gray-900">{doc.filename}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Mode: {doc.markup_mode} | Created:{" "}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
