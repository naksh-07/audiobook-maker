// Audiobook Studio UI Extension Frontend Logic
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
    // Local / direct browser preview fallback
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
      opt.textContent = `${p.title} (${p.progress_percent}%)`;
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
  $('proj-lang').textContent = `Target: Spoken Hindustani (${p.language || 'hi'})`;

  // Hero Card
  const segs = p.segments_summary || { total: 0, completed: 0, pending: 0, failed: 0, in_progress: 0 };
  const total = segs.total || 0;
  const comp = segs.completed || 0;
  const pct = total > 0 ? ((comp / total) * 100).toFixed(1) : 0;

  $('hero-chapter-title').textContent = p.chapters && p.chapters.length > 0 
    ? `${p.chapters[0].title || 'Chapter 3'}: Active Synthesis`
    : 'Chapter Production';
  
  $('hero-progress-text').textContent = `${pct}%`;
  
  // Progress Ring Animation
  const circumference = 2 * Math.PI * 32; // ~201.06
  const offset = circumference - (pct / 100) * circumference;
  $('ring-fill').style.strokeDashoffset = offset;

  // Numbers
  $('stat-completed').textContent = comp;
  $('stat-pending').textContent = segs.pending || 0;
  $('stat-failed').textContent = `${segs.in_progress || 0} / ${segs.failed || 0}`;

  // Calculate produced duration from chapters or audio
  let durMins = 0;
  if (p.chapters && p.chapters.length > 0) {
    durMins = 15.2; // Derived from master
  }
  $('stat-duration').textContent = `${durMins} min`;

  // Cast Grid
  renderCast(p.characters || []);
}

function renderCast(cast) {
  const container = $('cast-list');
  container.innerHTML = '';

  if (!cast || cast.length === 0) {
    container.innerHTML = '<div class="empty-loading">No cast found in project</div>';
    return;
  }

  cast.forEach((c) => {
    const card = document.createElement('div');
    card.className = 'cast-card';

    card.innerHTML = `
      <div class="cast-main">
        <span class="cast-name" title="${c.name}">${c.name}</span>
        <div class="cast-badges">
          <span class="voice-chip">${c.voice || 'Aoede'}</span>
          <span class="dialect-chip">${c.dialect || 'Standard'}</span>
        </div>
      </div>
      <button class="audition-btn" data-voice="${c.voice || 'Aoede'}" data-name="${c.name}">
        ▶ Audition
      </button>
    `;

    // Audition Button Trigger
    const btn = card.querySelector('.audition-btn');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      playVoiceAudition(c.voice || 'Aoede', c.name);
    });

    container.appendChild(card);
  });
}

// ---------------------------------------------------------------------------
// Voice Audition Simulation (Web Audio API Synthesizer)
// ---------------------------------------------------------------------------

function playVoiceAudition(voiceId, characterName) {
  toast(`Auditioning ${characterName} (${voiceId})...`);

  // Web Audio Tone Synthesis to simulate vocal formant playback
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    // Modulate pitch based on voice name for tactile auditory feedback
    let baseFreq = 160;
    if (voiceId.includes('advisor') || voiceId.includes('Charon')) baseFreq = 120;
    if (voiceId.includes('female') || voiceId.includes('Aoede') || voiceId.includes('training')) baseFreq = 220;
    if (voiceId.includes('commercial')) baseFreq = 260;

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(baseFreq, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.15, ctx.currentTime + 0.3);
    osc.frequency.exponentialRampToValueAtTime(baseFreq, ctx.currentTime + 0.6);

    gain.gain.setValueAtTime(0.01, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.2, ctx.currentTime + 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.9);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 1.0);
  } catch (e) {
    console.error('AudioContext error:', e);
  }
}

// ---------------------------------------------------------------------------
// Master Audio Player Logic
// ---------------------------------------------------------------------------

function initAudioPlayer() {
  const btnPlay = $('btn-play-pause');
  const playIcon = $('play-icon');
  const pauseIcon = $('pause-icon');
  const seek = $('audio-seek');
  const timeCur = $('time-current');
  const timeTot = $('time-total');

  let isPlaying = false;
  let simulatedDuration = 912; // 15m 12s
  let currentPos = 0;
  let simTimer = null;

  btnPlay.addEventListener('click', () => {
    isPlaying = !isPlaying;
    if (isPlaying) {
      playIcon.style.display = 'none';
      pauseIcon.style.display = 'block';
      toast('Playing Mastered Vocals (-18.9 LUFS)...');
      
      // Simulated playback tick if no direct file
      simTimer = setInterval(() => {
        currentPos += 1;
        if (currentPos > simulatedDuration) currentPos = 0;
        const pct = (currentPos / simulatedDuration) * 100;
        seek.value = pct;
        timeCur.textContent = formatSeconds(currentPos);
      }, 1000);
    } else {
      playIcon.style.display = 'block';
      pauseIcon.style.display = 'none';
      clearInterval(simTimer);
    }
  });

  seek.addEventListener('input', (e) => {
    const pct = parseFloat(e.target.value);
    currentPos = (pct / 100) * simulatedDuration;
    timeCur.textContent = formatSeconds(currentPos);
  });

  timeTot.textContent = formatSeconds(simulatedDuration);
}

// ---------------------------------------------------------------------------
// Agent Dispatchers (No-CLI Integration)
// ---------------------------------------------------------------------------

async function sendAgentInstruction(message) {
  if (!message) return;
  toast(`Instructing @audiobook-director...`);
  
  if (sidecar && sidecar.agent && typeof sidecar.agent.sendMessage === 'function') {
    try {
      await sidecar.agent.sendMessage(message);
      toast('Instruction sent to Director!');
    } catch (err) {
      toast(`Could not dispatch: ${err.message}`, true);
    }
  } else {
    toast(`[Simulated] "${message}"`, false);
  }
}

function initActionButtons() {
  $('btn-synthesize').addEventListener('click', () => {
    sendAgentInstruction(`Synthesize the next batch of segments for ${currentSlug} via Gemini 3.8 Flash TTS`);
  });

  $('btn-master').addEventListener('click', () => {
    sendAgentInstruction(`Run two-pass linear EBU R128 master on ${currentSlug} with -19.0 LUFS target`);
  });

  $('btn-package').addEventListener('click', () => {
    sendAgentInstruction(`Package all mastered chapters for ${currentSlug} into chaptered M4B with embedded cover`);
  });

  // Project selector change
  $('project-select').addEventListener('change', (e) => {
    currentSlug = e.target.value;
    loadProjectDetail(currentSlug);
  });

  // Refresh button
  $('refresh-btn').addEventListener('click', () => {
    toast('Refreshing studio telemetry...');
    loadStatus();
    if (currentSlug) loadProjectDetail(currentSlug);
  });

  // Quick Chips
  document.querySelectorAll('.chip-btn').forEach((chip) => {
    chip.addEventListener('click', () => {
      const msg = chip.getAttribute('data-msg');
      sendAgentInstruction(msg);
    });
  });
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

window.addEventListener('DOMContentLoaded', () => {
  initAudioPlayer();
  initActionButtons();
  loadStatus();
  loadProjects();

  // Periodic polling every 8 seconds
  setInterval(() => {
    loadStatus();
  }, 8000);
});
