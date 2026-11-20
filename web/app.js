// =============================================================================
// Gallup Copy - Client-side test logic (redesigned)
// =============================================================================

const STORAGE_KEY = 'gallup_copy_state_v1';

// База данных Gallup-результатов (заполняется разработчиком вручную из PDF).
// Содержит известные Gallup топ-5 для людей, которые сдавали Gallup.
// Загружается при старте и используется для автоподтягивания по имени.
let GALLUP_DB = [];

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
  document.getElementById('header-meta').textContent = 'Идёт тест';
  window.scrollTo(0, 0);
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
  window.scrollTo(0, 0);
  renderResults();
  document.getElementById('header-meta').textContent = 'Результат готов';
}
// =============================================================================
// АЛГОРИТМ СКОРИНГА v3 (собирается build_v3.py, проверка — leave-one-out)
// =============================================================================
// Ответ: 1 = точно левое утверждение, 5 = точно правое, 3 = нейтрально.
// 1. Каждое утверждение даёт + теме, которую описывает, или − теме, противоположность
//    которой описывает (q.left.themes / q.right.themes).
// 2. Неипсативно (отчёт Gallup 2014: <30% пунктов ипсативны): выбранная сторона получает
//    интенсивность ответа, невыбранная — только штраф cOther от неё.
// 3. У каждой пары свой вес q.w (насколько она согласуется с реальными Gallup-отчётами).
// 4. Балл темы = взвешенное среднее по её утверждениям.

function calculateScores(answers) {
  const cOther = (typeof SCORING_CONFIG !== 'undefined' && SCORING_CONFIG.cOther != null)
    ? SCORING_CONFIG.cOther : 0.5;
  const sum = {}, denom = {};
  Object.keys(THEME_DESCRIPTIONS).forEach(t => { sum[t] = 0; denom[t] = 0; });

  const add = (themes, amount) => {
    for (const [t, w] of Object.entries(themes || {})) sum[t] += w * amount;
  };

  QUESTIONS.forEach((q, i) => {
    const w = q.w != null ? q.w : 1;
    for (const side of [q.left, q.right]) {
      for (const [t, k] of Object.entries(side.themes || {})) denom[t] += Math.abs(k) * w;
    }
    const a = answers[i];
    if (a == null) return;
    const x = a - 3;            // +2 = точно правое, −2 = точно левое
    if (x > 0) {
      add(q.right.themes, w * x);
      add(q.left.themes, -cOther * w * x);
    } else if (x < 0) {
      add(q.left.themes, -w * x);
      add(q.right.themes, cOther * w * x);
    }
  });

  const scores = {};
  Object.keys(sum).forEach(t => { scores[t] = denom[t] > 0 ? sum[t] / denom[t] : 0; });
  return scores;
}

function ranksFromScores(scores) {
  const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  return sorted.map(([theme, score], i) => ({ theme, score, rank: i + 1 }));
}

// =============================================================================
// ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ
// =============================================================================


const DOMAIN_CLASS = {
  "Executing": "d-exec", "Influencing": "d-infl",
  "Relationship Building": "d-rel", "Strategic Thinking": "d-strat",
};
const DOMAIN_OF = {};
Object.entries(DOMAINS).forEach(([d, themes]) => themes.forEach(t => { DOMAIN_OF[t] = d; }));
const themeName = t => t; // названия талантов — на английском, как в отчёте Gallup
const domainClass = t => DOMAIN_CLASS[DOMAIN_OF[t]] || '';

// Мозаика 34 талантов. Без ranks — витрина на главной (по доменам),
// с ranks — результат: яркость клетки зависит от места таланта.
function renderMosaic(container, ranks) {
  if (!container) return;
  container.innerHTML = '';
  const rankOf = t => ranks ? ranks.find(r => r.theme === t).rank : null;
  Object.entries(DOMAINS).forEach(([domain, themes]) => {
    const col = document.createElement('div');
    col.className = 'mcol ' + DOMAIN_CLASS[domain];
    const list = ranks ? [...themes].sort((a, b) => rankOf(a) - rankOf(b)) : themes;
    list.forEach(theme => {
      const tile = document.createElement('div');
      tile.className = 'tile';
      tile.innerHTML = `<span>${escapeHtml(themeName(theme))}</span>`;
      if (ranks) {
        const rank = rankOf(theme);
        tile.style.setProperty('--o', (1 - (rank - 1) / 33 * 0.82).toFixed(2));
        tile.style.setProperty('--delay', ((rank - 1) * 0.035).toFixed(3) + 's');
        tile.title = `${theme} — место ${rank}`;
        if (rank <= 5) {
          tile.classList.add('is-top');
          tile.insertAdjacentHTML('beforeend', `<b class="rank-badge">${rank}</b>`);
        }
      }
      col.appendChild(tile);
    });
    container.appendChild(col);
  });
  if (ranks) {
    container.classList.remove('reveal');
    void container.offsetWidth;
    container.classList.add('reveal');
  }
}

function renderResults() {
  const scores = calculateScores(state.answers);
  const ranks = ranksFromScores(scores);

  renderMosaic(document.getElementById('result-mosaic'), ranks);

  // Топ-5
  const topList = document.getElementById('top-grid');
  topList.innerHTML = '';
  ranks.slice(0, 5).forEach(t => {
    const li = document.createElement('li');
    li.className = domainClass(t.theme);
    li.innerHTML = `
      <div class="top5-num">${t.rank}</div>
      <div>
        <div class="top5-name">${escapeHtml(themeName(t.theme))}</div>
        <div class="top5-domain">${escapeHtml(DOMAIN_NAMES[DOMAIN_OF[t.theme]] || '')}</div>
        <p class="top5-desc">${escapeHtml(THEME_DESCRIPTIONS[t.theme] || '')}</p>
      </div>
    `;
    topList.appendChild(li);
  });

  renderDomains(ranks);

  // Все 34
  const ladder = document.getElementById('all-themes');
  ladder.innerHTML = '';
  ranks.forEach(t => {
    const li = document.createElement('li');
    li.className = domainClass(t.theme) + (t.rank <= 5 ? ' top5' : '');
    li.innerHTML = `
      <span class="l-rank">${t.rank}</span>
      <span class="l-dot" aria-hidden="true"></span>
      <span>${escapeHtml(themeName(t.theme))}</span>
    `;
    ladder.appendChild(li);
  });

  renderGallupChips();
}

// Домены: сколько тем домена попало в топ-10
function renderDomains(ranks) {
  const grid = document.getElementById('domains-grid');
  grid.innerHTML = '';
  const top10 = new Set(ranks.slice(0, 10).map(r => r.theme));
  Object.entries(DOMAINS).forEach(([domain, themes]) => {
    const inTop = themes.filter(t => top10.has(t))
      .sort((a, b) => ranks.find(r => r.theme === a).rank - ranks.find(r => r.theme === b).rank);
    const card = document.createElement('div');
    card.className = 'domain ' + DOMAIN_CLASS[domain];
    card.innerHTML = `
      <div class="domain-name">${escapeHtml(DOMAIN_NAMES[domain] || domain)}</div>
      <div class="domain-count">${inTop.length}<span> из ${themes.length} тем в твоём топ-10</span></div>
      <div class="domain-pips" aria-hidden="true">${themes.map((t, i) => `<i class="${i < inTop.length ? 'on' : ''}"></i>`).join('')}</div>
      <div class="domain-themes">${inTop.length ? inTop.map(t => escapeHtml(themeName(t))).join(', ') : 'Нет тем в топ-10'}</div>
    `;
    grid.appendChild(card);
  });
}

// =============================================================================
// GALLUP INPUT
// =============================================================================

function normalizeThemeName(s) {
  // Нормализация разных написаний: "Self-assurance" → "Self-Assurance"
  if (!s) return '';
  let n = String(s).trim();
  if (n.includes('-')) {
    n = n.split('-').map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join('-');
  } else {
    n = n.charAt(0).toUpperCase() + n.slice(1).toLowerCase();
  }
  return n;
}

function parseGallupText(text) {
  // Разбить текст на отдельные названия тем и сопоставить с 34 Gallup-темами.
  // Разделители: пробелы, запятая, новая строка, точка с запятой, табы, "1." "1)" и т.п.
  const known = Object.keys(THEME_DESCRIPTIONS).map(normalizeThemeName);
  const tokens = text
    .split(/[\s,;|\t\n\r]+/)
    .map(t => t.replace(/^\d+[\.\)\-\:]\s*/, '').trim()) // убрать "1." "2)" "3-"
    .filter(t => t.length > 0);
  const matched = [];
  const unmatched = [];
  for (const tok of tokens.slice(0, 5)) {
    const norm = normalizeThemeName(tok);
    if (known.includes(norm)) {
      matched.push(norm);
    } else {
      // попробовать нечёткое совпадение (case-insensitive + strip hyphen)
      const fuzzy = known.find(k => k.toLowerCase() === norm.toLowerCase() || k.replace('-', '').toLowerCase() === norm.replace('-', '').toLowerCase());
      if (fuzzy) matched.push(fuzzy);
      else unmatched.push(tok);
    }
  }
  return { matched, unmatched };
}

function applyParsedGallup(matched) {
  state.gallupTop5 = matched.slice(0, 5).map((theme, i) => ({ theme, rank: i + 1 }));
  updateGallupChipState();
  updateTextPreview();
  updateMetaVisibility();
}

function updateTextPreview() {
  const preview = document.getElementById('gallup-text-preview');
  if (!preview) return;
  const n = state.gallupTop5.length;
  if (n === 0) {
    preview.innerHTML = 'Введи 5 тем — здесь появится то, что распознано.';
  } else if (n < 5) {
    preview.innerHTML = `<span class="t-warn">Распознано ${n} из 5 тем, нужно ещё ${5-n}:</span> <b>${state.gallupTop5.map(t => escapeHtml(t.theme)).join(', ')}</b>`;
  } else {
    preview.innerHTML = `<span class="t-ok">Распознаны все 5 тем:</span> <b>${state.gallupTop5.map(t => escapeHtml(t.theme)).join(', ')}</b>`;
  }
}

function updateMetaVisibility() {
  const meta = document.getElementById('gallup-meta');
  if (!meta) return;
  if (state.gallupTop5.length === 5) {
    meta.classList.remove('hidden');
  } else {
    meta.classList.add('hidden');
  }
}

function getMetaValues() {
  const dateRadio = document.querySelector('input[name="gallup-date"]:checked');
  const confRadio = document.querySelector('input[name="gallup-confidence"]:checked');
  return {
    gallup_date: dateRadio ? dateRadio.value : 'unknown',
    gallup_confidence: confRadio ? confRadio.value : 'unknown',
  };
}

// =============================================================================
// NAME LOOKUP — поиск в БД по имени
// =============================================================================

function handleNameLookup() {
  const nameInput = document.getElementById('user-name');
  if (!nameInput) return;

  nameInput.addEventListener('input', () => {
    const name = nameInput.value.trim();
    const lookupStatus = document.getElementById('name-lookup-status');
    const gallupSection = document.getElementById('gallup-section');

    if (!name) {
      if (lookupStatus) lookupStatus.innerHTML = '';
      return;
    }

    const match = lookupGallupByName(name);
    if (match) {
      // Нашли в БД — автозаполняем
      state.gallupTop5 = match.gallup_top5.map((t, i) => ({ theme: t.theme, rank: i + 1 }));
      // Помечаем как "verified" — данные из БД, не нужно вводить вручную
      state.gallupFromDB = true;
      state.gallupMatchedEntry = match;
      updateGallupChipState();
      updateTextPreview();
      updateMetaVisibility();
      if (lookupStatus) {
        const dateStr = match.gallup_date ? ` от ${match.gallup_date}` : '';
        lookupStatus.innerHTML = `
          <div class="notice ok">
            Нашли тебя в базе: <b>${escapeHtml(match.name)}</b>${dateStr}.<br>
            Gallup топ-5: <b>${match.gallup_top5.map(t => escapeHtml(t.theme)).join(', ')}</b>
            <small>Вводить вручную ничего не нужно — просто нажми «Отправить результат».</small>
          </div>
        `;
      }
      // Скрываем поле ручного ввода и мета-поля
      if (gallupSection) {
        gallupSection.style.display = 'none';
      }
    } else {
      state.gallupTop5 = [];
      state.gallupFromDB = false;
      state.gallupMatchedEntry = null;
      updateGallupChipState();
      updateTextPreview();
      updateMetaVisibility();
      if (lookupStatus) {
        lookupStatus.innerHTML = `
          <div class="notice warn">
            Имени «${escapeHtml(name)}» нет в базе результатов Gallup.
            <small>Введи свой топ-5 вручную ниже.</small>
          </div>
        `;
      }
      if (gallupSection) {
        gallupSection.style.display = 'block';
      }
    }
  });
}

function handleTextInput() {
  const textarea = document.getElementById('gallup-text-input');
  if (!textarea) return;
  textarea.addEventListener('input', () => {
    const { matched, unmatched } = parseGallupText(textarea.value);
    if (matched.length > 0) {
      applyParsedGallup(matched);
    } else {
      state.gallupTop5 = [];
      updateGallupChipState();
      updateTextPreview();
    }
    if (unmatched.length > 0) {
      const preview = document.getElementById('gallup-text-preview');
      if (preview) {
        preview.innerHTML += `<br><span class="t-bad">Не распознано: ${unmatched.map(u => `«${escapeHtml(u)}»`).join(', ')}. Проверь написание — названия тем на английском, как в отчёте.</span>`;
      }
    }
  });
}

function renderGallupChips() {
  const container = document.getElementById('gallup-chips');
  if (!container) return;
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
  updateTextPreview();
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
  state.gallupTop5.forEach((t, i) => t.rank = i + 1);
  updateGallupChipState();
  // Обновить textarea, чтобы отразить выбор
  const textarea = document.getElementById('gallup-text-input');
  if (textarea) {
    textarea.value = state.gallupTop5.map(t => t.theme).join(', ');
    updateTextPreview();
  }
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
  const meta = state.gallupFromDB
    ? { gallup_date: state.gallupMatchedEntry?.gallup_date || 'unknown', gallup_confidence: 'pdf', gallup_source: 'database' }
    : getMetaValues();
  const userName = (document.getElementById('user-name')?.value || '').trim();

  const payload = {
    timestamp: new Date().toISOString(),
    user_name: userName,
    answers_count: state.answers.filter(a => a !== null).length,
    predicted_top5: ranks.slice(0, 5).map(t => ({ theme: t.theme, score: t.score })),
    gallup_top5: state.gallupTop5,
    gallup_meta: meta,
    all_ranks: ranks,
  };

  showSubmitStatus('Отправляем результат…', false, null, 'info');

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (response.ok && result.ok) {
      let accuracyMsg = '';
      if (payload.gallup_top5.length > 0) {
        const predSet = new Set(payload.predicted_top5.slice(0, 5).map(t => t.theme));
        const gallupSet = new Set(payload.gallup_top5.map(t => t.theme));
        const match = [...predSet].filter(t => gallupSet.has(t)).length;
        const sourceLabel = state.gallupFromDB ? 'данные из базы' : 'введено вручную';
        accuracyMsg = `<small>Совпало с Gallup: <b>${match} из 5</b> (${sourceLabel}).</small>`;
        if (!state.gallupFromDB && (meta.gallup_confidence === 'guess' || meta.gallup_date === 'gt1y' || meta.gallup_date === 'unknown')) {
          accuracyMsg += `<small>Данные помечены как ненадёжные, поэтому в обучение не попадут.</small>`;
        }
      } else {
        accuracyMsg = `<small>Без настоящего топ-5 Gallup этот результат нельзя использовать для проверки точности.</small>`;
      }
      showSubmitStatus(
        `Результат отправлен разработчику.${accuracyMsg}`,
        false, null, 'ok'
      );
    } else {
      throw new Error(result.error || `HTTP ${response.status}`);
    }
  } catch (e) {
    showSubmitStatus(
      `Не удалось отправить: сервер не ответил (${escapeHtml(e.message)}). Скачай файл с результатом и отправь его разработчику сам.`,
      true,
      JSON.stringify(payload, null, 2), 'bad'
    );
  }
}

function showSubmitStatus(msg, showJson, json, kind = 'info') {
  const el = document.getElementById('submit-status');
  el.innerHTML = `
    <div class="notice ${kind}" role="status">${msg}</div>
    ${showJson ? `
      <textarea readonly class="json-out" aria-label="Результат в формате JSON">${escapeHtml(json)}</textarea>
      <button class="btn btn-ghost" style="margin-top:10px" onclick="downloadJson()">Скачать файл</button>
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
// GALLUP DATABASE
// =============================================================================

async function loadGallupDB() {
  try {
    const response = await fetch('data/gallup_db.json');
    if (response.ok) {
      GALLUP_DB = await response.json();
      console.log(`[Gallup DB] Loaded ${GALLUP_DB.length} entries`);
    } else {
      console.warn('[Gallup DB] Could not load gallup_db.json');
      GALLUP_DB = [];
    }
  } catch (e) {
    console.warn('[Gallup DB] Error:', e);
    GALLUP_DB = [];
  }
}

function lookupGallupByName(name) {
  if (!name || !GALLUP_DB.length) return null;
  const normalized = name.trim().toLowerCase();
  // Точное совпадение
  let match = GALLUP_DB.find(e => e.name.toLowerCase() === normalized);
  if (match) return match;
  // Частичное совпадение (без дефиса, без окончания PDF)
  const cleanName = normalized.replace(/\.pdf$/, '').replace(/-/g, '');
  match = GALLUP_DB.find(e => {
    const cleanE = e.name.toLowerCase().replace(/\.pdf$/, '').replace(/-/g, '');
    return cleanE === cleanName || cleanE.includes(cleanName) || cleanName.includes(cleanE);
  });
  return match;
}


// =============================================================================
// INIT
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  renderMosaic(document.getElementById('hero-mosaic'));
  // Загружаем БД Gallup-результатов
  await loadGallupDB();

  document.getElementById('start-btn').addEventListener('click', startTest);
  document.getElementById('prev-btn').addEventListener('click', prevQuestion);
  document.getElementById('finish-btn').addEventListener('click', finishTest);
  document.getElementById('submit-btn').addEventListener('click', submitResults);
  document.getElementById('restart-btn').addEventListener('click', () => {
    if (confirm('Начать заново? Ваши ответы будут потеряны.')) {
      clearState();
      document.getElementById('results').classList.add('hidden');
      document.getElementById('welcome').classList.remove('hidden');
      document.getElementById('header-meta').textContent = '200 вопросов';
    }
  });

  // Текстовый ввод Gallup-результата
  handleTextInput();
  // Поиск по имени в БД
  handleNameLookup();

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
