const API_BASE = "/api";

async function request(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || "Request failed");
  }
  return res.json();
}

export async function listProjects() {
  return request("/projects");
}

export async function createProject(name, description = "") {
  return request("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
}

export async function getProject(id) {
  return request(`/projects/${id}`);
}

export async function uploadGuidelines(projectId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return request(`/projects/${projectId}/guidelines`, {
    method: "POST",
    body: formData,
  });
}

export async function uploadDocument(projectId, file, mode = "balanced") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", mode);
  return request(`/projects/${projectId}/documents`, {
    method: "POST",
    body: formData,
  });
}

export async function getDocument(docId) {
  return request(`/documents/${docId}`);
}

export async function analyzeDocument(docId) {
  return request(`/documents/${docId}/analyze`, { method: "POST" });
}

export async function approveChange(changeId) {
  return request(`/changes/${changeId}/approve`, { method: "POST" });
}

export async function rejectChange(changeId) {
  return request(`/changes/${changeId}/reject`, { method: "POST" });
}

export async function approveAllChanges(docId) {
  return request(`/documents/${docId}/changes/approve-all`, { method: "POST" });
}

export async function generateMarkup(docId) {
  return request(`/documents/${docId}/generate`, { method: "POST" });
}

export function getDownloadUrl(docId) {
  return `${API_BASE}/documents/${docId}/download`;
}
