// Backend for Audiobook Studio UI Extension Sidecar.
// Hosts local HTTP server and bridges Antigravity with the Python production engine.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { platform, release } from 'node:os';
import { dirname, join, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawn } from 'node:child_process';
import { Response, SidecarApp } from 'sidecar_sdk';

const HERE = dirname(fileURLToPath(import.meta.url));

// Canonical engine workspace & virtualenv Python path
const ENGINE_DIR = process.env.AUDIOBOOK_ENGINE_DIR || resolve(process.env.USERPROFILE || 'C:\\Users\\Suraj', 'Documents', 'antigravity', 'optimistic-kepler');
const PYTHON_BIN = join(ENGINE_DIR, '.venv', 'Scripts', 'python.exe');

// Private persistent storage for this sidecar
const DATA_DIR = process.env.ANTIGRAVITY_EXECUTABLE_DATA_DIR || join(HERE, '.data');
mkdirSync(DATA_DIR, { recursive: true });

const STARTED_AT = Date.now();
const app = new SidecarApp();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const readLocal = (name, fallback = '') => {
  const p = join(HERE, name);
  return existsSync(p) ? readFileSync(p, 'utf8') : fallback;
};

function runPythonBridge(subcommand, extraArgs = []) {
  try {
    const pythonExe = existsSync(PYTHON_BIN) ? PYTHON_BIN : 'python';
    const args = ['-m', 'audiobook_factory.api.studio_bridge', subcommand, ...extraArgs];
    const stdout = execFileSync(pythonExe, args, {
      cwd: ENGINE_DIR,
      encoding: 'utf-8',
      timeout: 20000,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    return JSON.parse(stdout);
  } catch (err) {
    console.error(`Bridge error on '${subcommand}':`, err.message);
    return {
      error: err.message,
      stderr: err.stderr ? err.stderr.toString() : null,
      engine_dir: ENGINE_DIR,
    };
  }
}

// ---------------------------------------------------------------------------
// Static Web Routes
// ---------------------------------------------------------------------------

app.page('/', () => readLocal('index.html', '<h1>Audiobook Studio</h1>'));
app.page('/app.js', () => readLocal('app.js', '// Audiobook Studio Frontend'));
app.api('/styles.css', () => new Response(readLocal('styles.css', '/* Audiobook Studio Styles */'), { contentType: 'text/css' }), 'GET');

// ---------------------------------------------------------------------------
// Engine & Studio APIs
// ---------------------------------------------------------------------------

// GET /api/status: Returns sidecar and Python engine health
app.api('/api/status', () => {
  const bridgeStatus = runPythonBridge('status');
  return {
    sidecar: {
      uptimeSeconds: Math.round((Date.now() - STARTED_AT) / 1000),
      node: process.version,
      platform: `${platform()} ${release()}`,
    },
    engine: bridgeStatus,
  };
}, 'GET');

// GET /api/projects: Scans all active and completed book projects
app.api('/api/projects', () => {
  return runPythonBridge('list-projects');
}, 'GET');

// GET /api/project?slug=...: Returns detailed chapters, roster, and segment states
app.api('/api/project', (data) => {
  const slug = data.slug;
  if (!slug) return { error: 'Missing slug parameter' };
  return runPythonBridge('project-detail', ['--slug', slug]);
}, 'GET');

// GET /api/voices: Returns curated voices for auditioning
app.api('/api/voices', () => {
  return runPythonBridge('list-voices');
}, 'GET');

// GET /api/audio?path=...: Streams local audio files with proper MIME type
app.api('/api/audio', (data) => {
  const relPath = data.path;
  if (!relPath) return { error: 'Missing path parameter' };

  // Resolve safe path inside ENGINE_DIR
  const safeBase = resolve(ENGINE_DIR);
  const targetPath = resolve(safeBase, relPath.replace(/^[\/\\]+/, ''));

  if (!targetPath.startsWith(safeBase)) {
    return new Response(JSON.stringify({ error: 'Access denied outside engine dir' }), { status: 403, contentType: 'application/json' });
  }

  if (!existsSync(targetPath)) {
    return new Response(JSON.stringify({ error: 'File not found' }), { status: 404, contentType: 'application/json' });
  }

  const ext = extname(targetPath).toLowerCase();
  let contentType = 'application/octet-stream';
  if (ext === '.m4a' || ext === '.m4b') contentType = 'audio/mp4';
  else if (ext === '.wav') contentType = 'audio/wav';
  else if (ext === '.mp3') contentType = 'audio/mpeg';

  try {
    const fileBuf = readFileSync(targetPath);
    return new Response(fileBuf, {
      contentType,
      headers: {
        'Content-Length': String(fileBuf.length),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500, contentType: 'application/json' });
  }
}, 'GET');

// POST /api/action: Direct execution of production commands
app.api('/api/action', (data) => {
  const action = data.action; // 'produce_chapter', 'synthesize', 'refresh'
  if (action === 'refresh') {
    return { status: 'refreshed', timestamp: Date.now() };
  }
  return { status: 'acknowledged', action, data };
}, 'POST');

// ---------------------------------------------------------------------------
// Run Server
// ---------------------------------------------------------------------------

app.run();
