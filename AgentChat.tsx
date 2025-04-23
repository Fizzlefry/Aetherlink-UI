export default function AgentChat() {
  return (
    <div className="bg-gray-900 p-4 rounded-lg shadow-md h-full">
      <h2 className="text-xl font-bold mb-2">AI Agent Console</h2>
      <div className="bg-gray-800 p-2 rounded h-96 overflow-y-scroll">
        <p>[Aether]: How can I assist, Commander Jon?</p>
      </div>
      <input type="text" className="mt-4 w-full p-2 rounded bg-gray-700 text-white" placeholder="Type your command..." />
    </div>
  );
}
