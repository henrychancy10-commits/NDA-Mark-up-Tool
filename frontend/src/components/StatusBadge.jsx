const statusStyles = {
  uploaded: "bg-gray-100 text-gray-700",
  analyzing: "bg-yellow-100 text-yellow-800",
  analyzed: "bg-blue-100 text-blue-800",
  generating: "bg-purple-100 text-purple-800",
  completed: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

export default function StatusBadge({ status }) {
  return (
    <span
      className={`px-2.5 py-1 text-xs font-medium rounded-full ${statusStyles[status] || statusStyles.uploaded}`}
    >
      {status}
    </span>
  );
}
