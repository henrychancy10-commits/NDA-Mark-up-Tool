import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, createProject } from "../services/api";

export default function HomePage() {
  const [projects, setProjects] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const project = await createProject(name.trim(), desc.trim());
      navigate(`/projects/${project.id}`);
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-gray-500 mt-1">
            Create a project to upload guidelines and analyze NDA documents.
          </p>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          New Project
        </button>
      </div>

      {showNew && (
        <form
          onSubmit={handleCreate}
          className="mb-8 bg-white border border-gray-200 rounded-lg p-6"
        >
          <h2 className="text-lg font-semibold mb-4">Create New Project</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Project Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Acme Corp NDA Review"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description (optional)
              </label>
              <textarea
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Brief description of the review scope..."
                rows={2}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
            >
              Create Project
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading projects...</p>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 bg-white border border-gray-200 rounded-lg">
          <p className="text-gray-500 text-lg">No projects yet</p>
          <p className="text-gray-400 mt-1">
            Create a project to get started with NDA markup.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {projects.map((p) => (
            <div
              key={p.id}
              onClick={() => navigate(`/projects/${p.id}`)}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm cursor-pointer transition"
            >
              <h3 className="font-semibold text-gray-900">{p.name}</h3>
              {p.description && (
                <p className="text-sm text-gray-500 mt-1">{p.description}</p>
              )}
              <p className="text-xs text-gray-400 mt-2">
                Created: {new Date(p.created_at).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
