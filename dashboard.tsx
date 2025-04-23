import MemoryPanel from '../components/MemoryPanel';
import TaskQueue from '../components/TaskQueue';

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-black text-white p-6 grid grid-cols-2 gap-4">
      <MemoryPanel />
      <TaskQueue />
    </div>
  );
}
