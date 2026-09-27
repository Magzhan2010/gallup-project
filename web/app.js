// =============================================================================
// Gallup Copy - Client-side test logic (redesigned)
// =============================================================================

const STORAGE_KEY = 'gallup_copy_state_v1';

// =============================================================================
// SUBMIT — отправка результатов
// =============================================================================
// POST на /api/submit (Vercel Serverless Function).
// Токен Telegram-бота хранится на сервере (env var), а не в публичном коде.
const API_ENDPOINT = '/api/submit';

// Состояние
const state = {
  current: 0,
  answers: new Array(QUESTIONS.length).fill(null),
  gallupTop5: [], // [{theme, rank}, ...]
};

// =============================================================================
// ЛОГИКА ТЕСТА
// =============================================================================

function startTest() {
  const saved = loadState();
  if (saved && Array.isArray(saved.answers) && saved.answers.length === QUESTIONS.length) {
    state.current = saved.current;
    state.answers = saved.answers;
  }
  document.getElementById('welcome').classList.add('hidden');
  document.getElementById('test').classList.remove('hidden');
  renderQuestion();
}

function renderQuestion() {
  const q = QUESTIONS[state.current];
  document.getElementById('q-current').textContent = state.current + 1;
  document.getElementById('left-text').textContent = q.left.text;
  document.getElementById('right-text').textContent = q.right.text;

  // Подсветить выбранный ответ на шкале
  document.querySelectorAll('#scale .scale-btn').forEach(btn => {
    btn.classList.toggle('selected', Number(btn.dataset.val) === state.answers[state.current]);
  });

  // Подсветить выбранную карточку (1 → левая, 5 → правая)
  const ans = state.answers[state.current];
  document.getElementById('stmt-left').classList.toggle('chosen', ans !== null && ans <= 2);
  document.getElementById('stmt-right').classList.toggle('chosen', ans !== null && ans >= 4);

  // Прогресс
  const done = state.answers.filter(a => a !== null).length;
  const pct = Math.round((done / QUESTIONS.length) * 100);
  document.getElementById('progress-pct').textContent = pct + '%';
  document.getElementById('progress-fill').style.width = pct + '%';

  // Кнопка finish на последнем вопросе
  const isLast = state.current === QUESTIONS.length - 1;
  document.getElementById('finish-btn').classList.toggle('hidden', !isLast);
}

function selectAnswer(val) {
  state.answers[state.current] = val;
  saveState();
  renderQuestion();
  // Авто-переход на следующий вопрос через 300мс
  setTimeout(() => {
    if (state.current < QUESTIONS.length - 1) {
      state.current++;
      renderQuestion();
    }
  }, 300);
}

// Клик на карточку: ставит максимально уверенный ответ
//  (1 для левой, 5 для правой). Чтобы изменить интенсивность — используйте шкалу ниже.
function selectStatementCard(side) {
  const val = side === 'left' ? 1 : 5;
  selectAnswer(val);
}

function nextQuestion() {
  if (state.current < QUESTIONS.length - 1) {
    state.current++;
    renderQuestion();
  }
}

function prevQuestion() {
  if (state.current > 0) {
    state.current--;
    renderQuestion();
  }
}

function finishTest() {
  const answered = state.answers.filter(a => a !== null).length;
  if (answered < QUESTIONS.length * 0.9) {
    if (!confirm(`Вы ответили на ${answered} из ${QUESTIONS.length} вопросов. Всё равно получить результат?`)) return;
  }
  document.getElementById('test').classList.add('hidden');
  document.getElementById('results').classList.remove('hidden');
  renderResults();
  document.getElementById('header-meta').textContent = 'Готово ✓';
}

// =============================================================================
// АЛГОРИТМ СКОРИНГА (детерминированный, инвертированная полярность)
// =============================================================================
// shift = 3 - answer:  5 → -2, 4 → -1, 3 → 0, 2 → +1, 1 → +2
//   Это даёт +2 к LEFT (если ответ=1) и +2 к RIGHT (если ответ=5).

function calculateScores(answers) {
  const scores = {};
  QUESTIONS.forEach((q, i) => {
    const a = answers[i];
    if (a == null) return;
    const shift = 3 - a;
    scores[q.left.theme] = (scores[q.left.theme] || 0) + shift;
    scores[q.right.theme] = (scores[q.right.theme] || 0) - shift;
  });
  Object.keys(THEME_DESCRIPTIONS).forEach(t => {
    if (!(t in scores)) scores[t] = 0;
  });
  return scores;
}

function ranksFromScores(scores) {
  const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  return sorted.map(([theme, score], i) => ({ theme, score, rank: i + 1 }));
}

// =============================================================================
// ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ
// =============================================================================

function renderResults() {
  const scores = calculateScores(state.answers);
  const ranks = ranksFromScores(scores);
  const top5 = ranks.slice(0, 5);

  // TOP-5 как большие карточки
  const topGrid = document.getElementById('top-grid');
  topGrid.innerHTML = '';
  top5.forEach((t, i) => {
    const card = document.createElement('div');
    card.className = 'top5-card';
    card.innerHTML = `
      <div class="top5-rank">
        <span class="top5-rank-num">${t.rank}</span>
        <span class="top5-rank-label">ранг</span>
      </div>
      <div class="top5-content">
        <div class="top5-name">${escapeHtml(t.theme)}</div>
        <div class="top5-desc">${escapeHtml(THEME_DESCRIPTIONS[t.theme] || '')}</div>
      </div>
    `;
    topGrid.appendChild(card);
  });

  // Домены (4 домена Gallup)
  renderDomains(scores);

  // Все 34 темы
  const allThemes = document.getElementById('all-themes');
  allThemes.innerHTML = '';
  ranks.forEach(t => {
    const row = document.createElement('div');
    row.className = 'theme-row' + (t.rank <= 5 ? ' top5' : '');
    row.innerHTML = `
      <span class="theme-name">${escapeHtml(t.theme)}</span>
      <span class="theme-rank">#${t.rank}</span>
    `;
    allThemes.appendChild(row);
  });

  renderGallupChips();
}

// =============================================================================
// ДОМЕНЫ (4 области Gallup)
// =============================================================================

const DOMAIN_NAMES = {
  "Executing":           "Executing — Исполнение",
  "Influencing":         "Influencing — Влияние",
  "Relationship Building": "Relationship Building — Отношения",
  "Strategic Thinking":  "Strategic Thinking — Стратегия",
};

const DOMAIN_COLORS = {
  "Executing":           "#DC1E2D",
  "Influencing":         "#1976D2",
  "Relationship Building": "#388E3C",
  "Strategic Thinking":  "#7B1FA2",
};

function renderDomains(scores) {
  const grid = document.getElementById('domains-grid');
  grid.innerHTML = '';

  Object.entries(DOMAINS).forEach(([domain, themes]) => {
    const domainScores = themes.map(t => scores[t] || 0);
    const sum = domainScores.reduce((a, b) => a + b, 0);
    // Нормализуем к шкале 0-100 (грубо): каждый максимум = +24 (12 пар × 2)
    const maxPossible = themes.length * 24;
    const pct = Math.max(0, Math.min(100, Math.round((sum + maxPossible) / (2 * maxPossible) * 100)));

    const card = document.createElement('div');
    card.className = 'domain-card';
    card.innerHTML = `
      <div class="domain-name">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${DOMAIN_COLORS[domain]};"></span>
        ${escapeHtml(DOMAIN_NAMES[domain] || domain)}
      </div>
      <div class="domain-bar">
        <div class="domain-bar-fill" style="width:${pct}%;background:${DOMAIN_COLORS[domain]};"></div>
      </div>
      <div class="domain-info">
        <span>${themes.length} тем</span>
        <span>${pct}% силы</span>
      </div>
    `;
    grid.appendChild(card);
  });
}

// =============================================================================
// GALLUP INPUT
// =============================================================================

function renderGallupChips() {
  const container = document.getElementById('gallup-chips');
  container.innerHTML = '';
  Object.keys(THEME_DESCRIPTIONS).sort().forEach(theme => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.textContent = theme;
    chip.dataset.theme = theme;
    chip.addEventListener('click', () => toggleGallupChip(theme, chip));
    container.appendChild(chip);
  });
  updateGallupChipState();
}

function toggleGallupChip(theme, chip) {
  const idx = state.gallupTop5.findIndex(t => t.theme === theme);
  if (idx >= 0) {
    state.gallupTop5.splice(idx, 1);
  } else {
    if (state.gallupTop5.length >= 5) {
      alert('Уже выбрано 5 тем. Уберите одну, чтобы добавить другую.');
      return;
    }
    state.gallupTop5.push({ theme, rank: state.gallupTop5.length + 1 });
  }
  // Перенумеровать ранги
  state.gallupTop5.forEach((t, i) => t.rank = i + 1);
  updateGallupChipState();
}

function updateGallupChipState() {
  document.querySelectorAll('#gallup-chips .chip').forEach(chip => {
    const t = chip.dataset.theme;
    const sel = state.gallupTop5.find(x => x.theme === t);
    chip.classList.toggle('selected', !!sel);
    if (sel) {
      chip.innerHTML = `${t}<span class="chip-rank">#${sel.rank}</span>`;
    } else {
      chip.innerHTML = t;
    }
  });
}

// =============================================================================
// SAVE / SUBMIT
// =============================================================================

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      current: state.current,
      answers: state.answers,
      ts: Date.now(),
    }));
  } catch (e) {}
}

function loadState() {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    return s ? JSON.parse(s) : null;
  } catch (e) { return null; }
}

function clearState() {
  localStorage.removeItem(STORAGE_KEY);
  state.current = 0;
  state.answers = new Array(QUESTIONS.length).fill(null);
  state.gallupTop5 = [];
}

async function submitResults() {
  const scores = calculateScores(state.answers);
  const ranks = ranksFromScores(scores);
  const payload = {
    timestamp: new Date().toISOString(),
    answers_count: state.answers.filter(a => a !== null).length,
    predicted_top5: ranks.slice(0, 5).map(t => ({ theme: t.theme, score: t.score })),
    gallup_top5: state.gallupTop5,
    all_ranks: ranks,
  };

  showSubmitStatus('⏳ Отправляю результат на сервер...', false);

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (response.ok && result.ok) {
      // Считаем точность локально
      let accuracyMsg = '';
      if (payload.gallup_top5.length > 0) {
        const predSet = new Set(payload.predicted_top5.slice(0, 5).map(t => t.theme));
        const gallupSet = new Set(payload.gallup_top5.map(t => t.theme));
        const match = [...predSet].filter(t => gallupSet.has(t)).length;
        accuracyMsg = `<br><span style="font-size:13px;">📈 Точность: <b>${match}/5 = ${match*20}%</b></span>`;
      } else {
        accuracyMsg = `<br><span style="font-size:13px;color:#B71C1C;">⚠️ Gallup-результат НЕ введён — данные бесполезны для обучения.</span>`;
      }
      showSubmitStatus(
        `✅ Отправлено! Данные улетели разработчику в Telegram.${accuracyMsg}`,
        false
      );
    } else {
      throw new Error(result.error || `HTTP ${response.status}`);
    }
  } catch (e) {
    showSubmitStatus(
      `⚠️ Сервер недоступен (${escapeHtml(e.message)}).<br>Скачай JSON и отправь разработчику вручную:`,
      true,
      JSON.stringify(payload, null, 2)
    );
  }
}

function showSubmitStatus(msg, showJson, json) {
  const el = document.getElementById('submit-status');
  el.innerHTML = `
    <div style="background:#F0F7FF;border:1px solid #1976D2;border-radius:8px;padding:14px 18px;font-size:14px;color:#0D2D5C;">
      ${msg}
    </div>
    ${showJson ? `
      <textarea readonly style="width:100%;height:200px;margin-top:12px;font-family:monospace;font-size:11px;background:#1a1a1a;color:#0f0;border:1px solid #ccc;padding:10px;border-radius:6px;">${escapeHtml(json)}</textarea>
      <button class="btn-secondary" style="margin-top:8px;" onclick="downloadJson()">📥 Скачать JSON</button>
    ` : ''}
  `;
  el.classList.remove('hidden');
}

function downloadJson() {
  const scores = calculateScores(state.answers);
  const ranks = ranksFromScores(scores);
  const payload = JSON.stringify({
    timestamp: new Date().toISOString(),
    answers_count: state.answers.filter(a => a !== null).length,
    predicted_top5: ranks.slice(0, 5),
    gallup_top5: state.gallupTop5,
  }, null, 2);
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gallup-result-${Date.now()}.json`;
  a.click();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// =============================================================================
// INIT
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start-btn').addEventListener('click', startTest);
  document.getElementById('prev-btn').addEventListener('click', prevQuestion);
  document.getElementById('finish-btn').addEventListener('click', finishTest);
  document.getElementById('submit-btn').addEventListener('click', submitResults);
  document.getElementById('restart-btn').addEventListener('click', () => {
    if (confirm('Начать заново? Ваши ответы будут потеряны.')) {
      clearState();
      document.getElementById('results').classList.add('hidden');
      document.getElementById('welcome').classList.remove('hidden');
      document.getElementById('header-meta').textContent = 'Бесплатный тест · 15 минут';
    }
  });

  // Шкала: клик по цифре 1-5
  document.querySelectorAll('#scale .scale-btn').forEach(btn => {
    btn.addEventListener('click', () => selectAnswer(Number(btn.dataset.val)));
  });

  // Карточки утверждений: клик = сильный ответ (1 для левой, 5 для правой)
  document.getElementById('stmt-left').addEventListener('click', () => selectStatementCard('left'));
  document.getElementById('stmt-right').addEventListener('click', () => selectStatementCard('right'));

  // Клавиатура: 1-5 для шкалы, A/D для карточек, ←→ для навигации
  document.addEventListener('keydown', (e) => {
    if (document.getElementById('test').classList.contains('hidden')) return;
    if (e.key >= '1' && e.key <= '5') {
      selectAnswer(Number(e.key));
    } else if (e.key === 'a' || e.key === 'A' || e.key === 'ф' || e.key === 'Ф') {
      selectStatementCard('left');
    } else if (e.key === 'd' || e.key === 'D' || e.key === 'в' || e.key === 'В') {
      selectStatementCard('right');
    } else if (e.key === 'ArrowLeft') {
      prevQuestion();
    } else if (e.key === 'ArrowRight') {
      // не перескакивать, пусть пользователь сам нажмёт далее если хочет
    }
  });
});
