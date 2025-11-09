#!/usr/bin/env node
/**
 * Quick test script for the MCP server
 * Sends JSON-RPC messages over stdio and prints responses
 */

import { spawn } from 'child_process';

const server = spawn('node', ['server.js'], {
  cwd: import.meta.dirname,
  stdio: ['pipe', 'pipe', 'inherit']
});

let buffer = '';

server.stdout.on('data', (chunk) => {
  buffer += chunk.toString();
  const lines = buffer.split('\n');
  buffer = lines.pop(); // Keep incomplete line in buffer

  for (const line of lines) {
    if (line.trim()) {
      console.log('← Server response:', line);
      try {
        const parsed = JSON.parse(line);
        console.log('  Parsed:', JSON.stringify(parsed, null, 2));
      } catch (e) {
        console.log('  (Could not parse JSON)');
      }
    }
  }
});

server.on('close', (code) => {
  console.log(`\nMCP server exited with code ${code}`);
  process.exit(code);
});

// Test sequence
const tests = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: {} },
  { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} },
  { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "aetherlink.get_ops_snapshot", arguments: {} } }
];

console.log('🧪 Testing MCP server...\n');

let index = 0;
function sendNext() {
  if (index >= tests.length) {
    console.log('\n✅ All tests sent. Waiting for responses...');
    setTimeout(() => {
      server.stdin.end();
    }, 2000);
    return;
  }

  const test = tests[index++];
  console.log(`→ Sending: ${JSON.stringify(test)}`);
  server.stdin.write(JSON.stringify(test) + '\n');

  setTimeout(sendNext, 500);
}

sendNext();
