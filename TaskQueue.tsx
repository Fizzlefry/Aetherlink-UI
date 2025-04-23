export default function TaskQueue() {
  return (
    <div className="bg-gray-900 p-4 rounded-lg shadow-md">
      <h2 className="text-xl font-bold mb-2">Daily Build Queue</h2>
      <ul className="list-disc list-inside">
        <li>Build AetherForge UI</li>
        <li>Update Genesis Memory Logs</li>
        <li>Log Commit History</li>
      </ul>
    </div>
  );
}
