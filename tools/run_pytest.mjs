#!/usr/bin/env node
// Cross-platform pytest runner that enforces PYTEST_DISABLE_PLUGIN_AUTOLOAD
// unless FC_SKIP_PYTEST_DISABLE=1 is set in the environment.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

const env = { ...process.env };
const skipDisable = env.FC_SKIP_PYTEST_DISABLE === '1';
if (!skipDisable) {
  env.PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1';
}

const platformScriptsDir = process.platform === 'win32' ? 'Scripts' : 'bin';
const pytestExecutable = process.platform === 'win32' ? 'pytest.exe' : 'pytest';

const candidateCommands = [];

const appendCandidate = (base) => {
  if (!base) {
    return;
  }
  candidateCommands.push(join(base, platformScriptsDir, pytestExecutable));
};

appendCandidate(env.VIRTUAL_ENV);
appendCandidate(join(process.cwd(), '.venv'));

const resolvedCommand =
  candidateCommands.find((cmd) => existsSync(cmd)) ??
  null;

const command = resolvedCommand ?? (process.platform === 'win32' ? 'python' : 'python3');
const args = resolvedCommand ? ['-q'] : ['-m', 'pytest', '-q'];

const child = spawn(command, args, {
  stdio: 'inherit',
  env,
  shell: false,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

child.on('error', (error) => {
  console.error('[run_pytest] Failed to execute pytest:', error);
  process.exit(1);
});
