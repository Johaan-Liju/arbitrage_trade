import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

// Pass the installed REA scripts/rea.mjs path; no packages or configuration are changed.
const entry = process.argv[2];
if (!entry) throw new Error('Usage: node scripts/check-rea-mcp.mjs <REA scripts/rea.mjs>');
const child = spawn(process.execPath, [entry, 'mcp'], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
let completed = false;
const timer = setTimeout(() => { console.error('MCP handshake timed out'); child.kill(); process.exitCode = 1; }, 20000);
const send = message => child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', ...message })}\n`);
child.stderr.on('data', data => process.stderr.write(data));
child.on('error', error => { clearTimeout(timer); console.error(error.message); process.exitCode = 1; });
child.on('exit', () => { clearTimeout(timer); if (!completed) process.exitCode = 1; });
createInterface({ input: child.stdout }).on('line', line => {
  try {
    const response = JSON.parse(line);
    if (response.error) throw new Error(JSON.stringify(response.error));
    if (response.id === 1) {
      console.log(JSON.stringify({ initialize: 'ok', server: response.result.serverInfo, protocolVersion: response.result.protocolVersion }));
      send({ method: 'notifications/initialized' });
      send({ id: 2, method: 'tools/list', params: {} });
    } else if (response.id === 2) {
      const tools = response.result.tools;
      if (!tools.some(tool => tool.name === 'binary_session')) throw new Error('binary_session unavailable');
      console.log(JSON.stringify({ toolsList: 'ok', count: tools.length, binarySession: true }));
      completed = true; clearTimeout(timer); child.kill();
    }
  } catch (error) { console.error(error.message); clearTimeout(timer); child.kill(); process.exitCode = 1; }
});
send({ id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'goldlens-local-check', version: '0.1.0' } } });
