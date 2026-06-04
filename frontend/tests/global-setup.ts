import { spawn, execSync } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';

let backendProcess: ReturnType<typeof spawn> | null = null;

async function waitForBackend(url: string, timeout = 30000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Backend did not become ready at ${url} within ${timeout}ms`);
}

function killPythonOnPort8000(): void {
  try {
    // Find and kill any process listening on port 8000
    const netstat = execSync(
      'netstat -ano | findstr :8000',
      { encoding: 'utf-8', shell: 'cmd.exe' }
    );
    const lines = netstat.split('\n').filter((l) => l.includes(':8000'));
    const pids = new Set<number>();
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      const pid = parseInt(parts[parts.length - 1], 10);
      if (!isNaN(pid)) pids.add(pid);
    }
    for (const pid of pids) {
      try {
        execSync(`taskkill /F /PID ${pid}`, { shell: 'cmd.exe' });
        console.log(`Killed process ${pid} on port 8000`);
      } catch {
        // ignore
      }
    }
  } catch {
    // no process on port 8000
  }
}

export default async function globalSetup() {
  // Kill any existing backend on port 8000
  killPythonOnPort8000();
  await new Promise((r) => setTimeout(r, 1000));

  // Start test backend
  const backendPath = path.resolve(__dirname, '../../backend/run_test_backend.py');
  if (!existsSync(backendPath)) {
    throw new Error(`Test backend script not found: ${backendPath}`);
  }

  console.log('Starting test backend...');
  backendProcess = spawn('python', [backendPath], {
    stdio: 'pipe',
    shell: true,
    detached: false,
  });

  backendProcess.stdout?.on('data', (data) => {
    console.log(`[TEST-BACKEND] ${data.toString().trim()}`);
  });

  backendProcess.stderr?.on('data', (data) => {
    console.error(`[TEST-BACKEND] ${data.toString().trim()}`);
  });

  backendProcess.on('error', (err) => {
    console.error('Test backend failed to start:', err);
  });

  // Wait for backend to be ready
  await waitForBackend('http://localhost:8000/health');
  console.log('Test backend is ready on port 8000');

  // Return teardown function
  return async () => {
    if (backendProcess) {
      console.log('Stopping test backend...');
      try {
        backendProcess.kill('SIGTERM');
      } catch {
        // ignore
      }
      // Force kill on Windows
      try {
        execSync(`taskkill /F /PID ${backendProcess.pid}`, { shell: 'cmd.exe' });
      } catch {
        // ignore
      }
    }
    // Also clean up any lingering Python processes on port 8000
    killPythonOnPort8000();
  };
}
