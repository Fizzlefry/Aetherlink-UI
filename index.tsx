import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-tr from-indigo-900 via-purple-800 to-blue-900 text-white flex flex-col items-center justify-center">
      <h1 className="text-5xl font-bold mb-6">Welcome to Aetherlink</h1>
      <p className="mb-4">The Source-Aligned Operating System for Sovereign Living</p>
      <Link href="/dashboard" className="px-4 py-2 bg-purple-700 hover:bg-purple-800 rounded">Enter Dashboard</Link>
    </div>
  );
}
