/**
 * Example AI Agent Integration
 *
 * This shows how your AI assistant (Claude, GPT, etc.) can query
 * the AetherLink ops state and provide intelligent responses.
 *
 * Usage:
 *   node example-agent.js
 */

const AI_BRIDGE_URL = process.env.AI_BRIDGE_URL || 'http://localhost:3001';

/**
 * Fetch ops snapshot from the bridge
 */
async function getOpsSnapshot() {
  const res = await fetch(`${AI_BRIDGE_URL}/ops/snapshot`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ops snapshot: ${res.status}`);
  }
  return res.json();
}

/**
 * Generate AI-friendly summary
 */
function generateSummary(snapshot) {
  const lines = [];

  // Header
  lines.push('📊 AetherLink Ops Status Report');
  lines.push('='.repeat(50));
  lines.push('');

  // Timestamp
  lines.push(`⏰ Generated: ${new Date(snapshot.timestamp).toLocaleString()}`);
  lines.push(`🏥 Health: ${snapshot.health.toUpperCase()}`);
  lines.push('');

  // Anomalies
  if (snapshot.anomalies.total > 0) {
    lines.push(`🚨 ANOMALIES DETECTED: ${snapshot.anomalies.total}`);
    lines.push(`   Critical: ${snapshot.anomalies.critical}`);
    lines.push(`   Warnings: ${snapshot.anomalies.warnings}`);
    lines.push('');

    if (snapshot.anomalies.incidents.length > 0) {
      lines.push('   Details:');
      snapshot.anomalies.incidents.forEach(incident => {
        const emoji = incident.severity === 'critical' ? '🔴' : '🟡';
        lines.push(`   ${emoji} ${incident.message || incident.type}`);
        if (incident.affected_tenant) {
          lines.push(`      Tenant: ${incident.affected_tenant}`);
        }
        if (incident.affected_endpoint) {
          lines.push(`      Endpoint: ${incident.affected_endpoint}`);
        }
      });
      lines.push('');
    }
  } else {
    lines.push('✅ No anomalies detected');
    lines.push('');
  }

  // Deliveries
  lines.push(`📮 Deliveries: ${snapshot.deliveries.total} total`);
  if (snapshot.deliveries.problematic > 0) {
    lines.push(`   ⚠️  Problematic: ${snapshot.deliveries.problematic}`);
    lines.push(`   ❌ Failed: ${snapshot.deliveries.failed}`);
    lines.push(`   ⏳ Pending: ${snapshot.deliveries.pending}`);
    lines.push(`   🛑 Dead Letter: ${snapshot.deliveries.dead_letter}`);
    lines.push('');

    if (snapshot.deliveries.items.length > 0) {
      lines.push('   Recent Issues:');
      snapshot.deliveries.items.slice(0, 5).forEach(item => {
        lines.push(`   • ${item.rule_name || 'Unknown'}`);
        lines.push(`     ID: ${item.id}`);
        lines.push(`     Status: ${item.status} (${item.attempts}/${item.max_attempts} attempts)`);
        if (item.last_error) {
          lines.push(`     Error: ${item.last_error.slice(0, 80)}...`);
        }
        lines.push(`     Tenant: ${item.tenant_id || 'N/A'}`);
      });
      lines.push('');
    }
  } else {
    lines.push('   ✅ All deliveries successful');
    lines.push('');
  }

  // Recommendations
  lines.push('💡 Recommendations:');
  snapshot.recommendations.forEach(rec => {
    const emoji = rec.priority === 'high' ? '🔴' : rec.priority === 'medium' ? '🟡' : '🟢';
    lines.push(`   ${emoji} [${rec.priority.toUpperCase()}] ${rec.message}`);
    lines.push(`      → ${rec.action}`);
  });
  lines.push('');

  return lines.join('\n');
}

/**
 * Example: AI agent checks ops and responds
 */
async function aiAgentCheck() {
  console.log('🤖 AI Agent: Checking AetherLink ops state...\n');

  try {
    const snapshot = await getOpsSnapshot();
    const summary = generateSummary(snapshot);

    console.log(summary);

    // Example AI decision-making
    if (snapshot.anomalies.critical > 0) {
      console.log('🚨 AI Agent Decision: ESCALATE to on-call engineer');
      console.log('   Reason: Critical anomalies detected\n');
    } else if (snapshot.deliveries.failed > 3) {
      console.log('💡 AI Agent Suggestion: Batch replay failed deliveries');
      console.log('   Reason: Multiple delivery failures detected\n');
    } else if (snapshot.deliveries.dead_letter > 0) {
      console.log('⚠️  AI Agent Alert: Dead letter queue requires attention');
      console.log('   Reason: Max retry attempts exceeded\n');
    } else {
      console.log('✅ AI Agent: All systems nominal - no action required\n');
    }

    // Example: Auto-replay failed deliveries (commented out for safety)
    // if (snapshot.deliveries.failed > 0) {
    //   for (const item of snapshot.deliveries.items.filter(d => d.status === 'failed')) {
    //     console.log(`🔄 AI Agent: Would replay delivery ${item.id}`);
    //     // await fetch(`${AI_BRIDGE_URL}/ops/replay/${item.id}`, { method: 'POST' });
    //   }
    // }

  } catch (error) {
    console.error('❌ AI Agent Error:', error.message);
    console.error('   Unable to fetch ops state. Is the bridge running?\n');
    process.exit(1);
  }
}

// Run the example
if (require.main === module) {
  aiAgentCheck();
}

module.exports = { getOpsSnapshot, generateSummary };
