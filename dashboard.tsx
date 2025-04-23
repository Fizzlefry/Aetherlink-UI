import AgentChat from '../components/AgentChat';
import MemoryPanel from '../components/MemoryPanel';

export default function Dashboard() {
  return (
    <div className="grid grid-cols-5 min-h-screen bg-black text-white">
      <div className="col-span-3 p-6">
        <h1 className="text-3xl font-bold mb-4">Command Center</h1>
        <MemoryPanel />
      </div>
      <div className="col-span-2 p-6 border-l border-gray-700">
        <AgentChat />
      </div>
    </div>
  );
}
