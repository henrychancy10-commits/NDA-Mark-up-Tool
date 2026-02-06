import { useState, useRef } from "react";

export default function FileUpload({ label, accept, onUpload, disabled }) {
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState(null);
  const inputRef = useRef(null);

  function handleFile(file) {
    if (!file) return;
    setFileName(file.name);
    onUpload(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  }

  function handleChange(e) {
    const file = e.target.files[0];
    handleFile(file);
  }

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
        dragOver
          ? "border-blue-500 bg-blue-50"
          : fileName
            ? "border-green-400 bg-green-50"
            : "border-gray-300 hover:border-gray-400"
      } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      {fileName ? (
        <p className="text-green-700 font-medium">{fileName}</p>
      ) : (
        <>
          <p className="text-gray-600 font-medium">{label}</p>
          <p className="text-gray-400 text-sm mt-1">
            Click or drag and drop
          </p>
        </>
      )}
    </div>
  );
}
