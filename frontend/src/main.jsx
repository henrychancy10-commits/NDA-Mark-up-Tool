import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import ProjectPage from "./pages/ProjectPage";
import DocumentPage from "./pages/DocumentPage";
import TrainingPage from "./pages/TrainingPage";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/documents/:docId" element={<DocumentPage />} />
          <Route path="/projects/:projectId/training" element={<TrainingPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
