// Audiobook Studio UI Extension Frontend Logic (v6.0-STUDIO-UI)
// Communicates with Sidecar backend APIs and Antigravity Agent.

const sidecar = window.sidecar;
const $ = (id) => document.getElementById(id);

let currentSlug = '';
let currentProject = null;
let toastTimer = null;
const audioPlayer = $('audio-player');

// ---------------------------------------------------------------------------
// Helpers & Toasts
// ---------------------------------------------------------------------------

function toast(message, isError = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('error', isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
}

async function apiFetch(path, options = {}) {
  if (sidecar && typeof sidecar.fetch === 'function') {
    const res = await sidecar.fetch(path, options);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `${res.status} ${res.statusText}`);
    }
    return res.json();
  } else {
    const res = await fetch(path, options);
    return res.json();
  }
}

function formatSeconds(secs) {
  if (isNaN(secs) || secs < 0) return '00:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// ---------------------------------------------------------------------------
// Telemetry & Project Loader
// ---------------------------------------------------------------------------

async function loadStatus() {
  try {
    const data = await apiFetch('/api/status');
    if (data.engine) {
      const keys = data.engine.active_gemini_keys || 0;
      $('key-count').textContent = `${keys} Keys Active`;
      $('key-badge').className = keys > 0 ? 'status-pill ok' : 'status-pill error';
    }
  } catch (err) {
    console.warn('Status fetch error:', err);
  }
}

async function loadProjects() {
  try {
    const projects = await apiFetch('/api/projects');
    const select = $('project-select');
    select.innerHTML = '';

    if (!projects || projects.length === 0) {
      select.innerHTML = '<option value="">No projects found</option>';
      return;
    }

    projects.forEach((p, idx) => {
      const opt = document.createElement('option');
      opt.value = p.slug;
      opt.textContent = `${p.title} (${p.chapters_count} Chapters)`;
      if (idx === 0) opt.selected = true;
      select.appendChild(opt);
    });

    currentSlug = select.value;
    await loadProjectDetail(currentSlug);
  } catch (err) {
    toast(`Failed to load projects: ${err.message}`, true);
  }
}

async function loadProjectDetail(slug) {
  if (!slug) return;
  try {
    const detail = await apiFetch(`/api/project?slug=${encodeURIComponent(slug)}`);
    currentProject = detail;
    renderProjectUI(detail);
  } catch (err) {
    toast(`Failed to load project details: ${err.message}`, true);
  }
}

function renderProjectUI(p) {
  // Tags
  $('proj-author').textContent = `Author: ${p.author || 'Unknown'}`;
  $('proj-lang').textContent = `Target: Spoken Hindustani (RAW_UNRATED)`;

  // Hero Card & Numbers
  const totalCh = p.chapters ? p.chapters.length : 0;
  $('stat-chapters').textContent = totalCh;
  $('stat-takebank').textContent = `${p.takebank_metrics?.total_takes || 0} Takes`;
  $('stat-dag-clean').textContent = p.is_dag_clean ? 'CLEAN' : `${p.dirty_chapter_ids?.length || 0} DIRTY`;
  $('stat-dag-clean').className = p.is_dag_clean ? 'metric-val green' : 'metric-val yellow';

  $('hero-chapter-title').textContent = `${p.title || 'Project'}: DAG Pipeline`;
  $('hero-progress-text').textContent = p.is_dag_clean ? '100%' : 'PENDING';
  $('ring-fill').style.strokeDashoffset = p.is_dag_clean ? 0 : 60;

  // Render Cast
  renderCast(p.characters || []);

  // Render Gate Audits
  renderGateAudits(p.gate_audits || []);

  // Render Media
  renderMedia(p.media_files || []);
}

function renderCast(cast) {
  const container = $('cast-list');
  container.innerHTML = '';

  if (!cast || cast.length === 0) {
    container.innerHTML = '<div class="empty-loading">No cast assigned yet in CastLock</div>';
    return;
  }

  cast.forEach((c) => {
    const card = document.createElement('div');
    card.className = 'cast-card';
    card.innerHTML = `
      <div class="cast-top">
        <span class="cast-name">${c.name || 'Character'} <small>(${c.hindi_name || ''})</small></span>
        <span class="cast-voice-tag">${c.voice_id || 'Aoede'}</span>
      </div>
      <div class="cast-detail">
        <span>Gender: ${c.gender || 'NEUTRAL'}</span>
        <span>Pitch: ${c.pitch_offset || 0}st | Tempo: ${c.tempo_multiplier || 1.0}x</span>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderGateAudits(audits) {
  const container = $('gate-list');
  container.innerHTML = '';

  if (!audits || audits.length === 0) {
    container.innerHTML = '<div class="empty-loading">No gate audits recorded yet in ledger</div>';
    return;
  }

  audits.forEach((a) => {
    const row = document.createElement('div');
    row.className = 'gate-row';
    const isPass = a.decision === 'PASSED';
    row.innerHTML = `
      <div class="gate-header">
        <span class="gate-name">${a.gate_name}</span>
        <span class="step-badge ${isPass ? 'pass' : 'fail'}">${a.decision}</span>
      </div>
      <div class="gate-metrics">
        ${Object.entries(a.metrics || {}).map(([k, v]) => `<span><b>${k}:</b> ${v}</span>`).join(' | ')}
      </div>
    `;
    container.appendChild(row);
  });
}

function renderMedia(media) {
  const container = $('media-list');
  container.innerHTML = '';

  if (!media || media.length === 0) {
    container.innerHTML = '<div class="empty-loading">No mastered media files found on disk</div>';
    return;
  }

  media.forEach((m) => {
    const item = document.createElement('div');
    item.className = 'media-item';
    item.innerHTML = `
      <div class="media-title">🎵 ${m.name} (${m.size_mb} MB)</div>
      <button class="btn secondary-btn" style="padding: 4px 10px; font-size: 12px;">Audition</button>
    `;
    item.querySelector('button').addEventListener('click', () => {
      audioPlayer.src = `/api/audio?path=${encodeURIComponent(m.rel_path)}`;
      audioPlayer.play();
      $('playing-title').textContent = `Auditioning: ${m.name}`;
    });
    container.appendChild(item);
  });
}

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------

$('project-select').addEventListener('change', (e) => {
  currentSlug = e.target.value;
  loadProjectDetail(currentSlug);
});

$('refresh-btn').addEventListener('click', async () => {
  toast('Refreshing studio telemetry...');
  await loadStatus();
  await loadProjects();
});

$('btn-run-dag')?.addEventListener('click', async () => {
  toast('Triggering incremental DAG pipeline run...');
  await apiFetch('/api/action', {
    method: 'POST',
    body: JSON.stringify({ action: 'run_dag', project: currentSlug }),
  });
});

$('btn-master')?.addEventListener('click', async () => {
  toast('Triggering Two-Pass EBU R128 mastering...');
  await apiFetch('/api/action', {
    method: 'POST',
    body: JSON.stringify({ action: 'master', project: currentSlug }),
  });
});

$('btn-package')?.addEventListener('click', async () => {
  toast('Triggering M4B container packaging...');
  await apiFetch('/api/action', {
    method: 'POST',
    body: JSON.stringify({ action: 'package', project: currentSlug }),
  });
});

// Audio duration tracking
audioPlayer.addEventListener('timeupdate', () => {
  const cur = formatSeconds(audioPlayer.currentTime);
  const dur = formatSeconds(audioPlayer.duration || 0);
  $('playing-time').textContent = `${cur} / ${dur}`;
});

// Initialization
window.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  await loadProjects();
});
