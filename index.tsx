import Head from 'next/head';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 text-white flex items-center justify-center">
      <Head>
        <title>Aetherlink OS</title>
      </Head>
      <div className="text-center">
        <h1 className="text-5xl font-bold mb-4">Welcome to Aetherlink</h1>
        <p className="mb-8">Source-aligned Quantum OS for Sovereign Living</p>
        <Link href="/dashboard" className="text-blue-400 underline">Enter Command Dashboard</Link>
      </div>
    </div>
  );
}
