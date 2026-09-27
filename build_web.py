"""
build_web.py
============
Извлекает 200 пар утверждений из xlsx и собирает веб-приложение в gallup-project/web/.

Структура:
  web/
    index.html      - главная страница (тест + результаты)
    app.js          - логика (UI + алгоритм)
    style.css       - стили
    data.js         - 200 вопросов (генерируется из xlsx)

Алгоритм — детерминированный с ИНВЕРТИРОВАННОЙ полярностью:
  5 → -2 к теме A, +2 к теме B (statement A = "НЕ я", statement B = "точно я")
  Это эмпирически совпадает с Gallup (см. tune_scorer.py).
"""

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(r"C:\Users\User\gallup-project")
WEB_DIR = PROJECT / "web"
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"

# ============================================================================
# ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ XLSX
# ============================================================================

def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        parts = n.split("-")
        n = "-".join(p.capitalize() for p in parts)
    return n


def extract_pairs():
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Группируем утверждения по парам (там же, где они в "200 пар - баланс 11-12" sheet)
    wb2 = openpyxl.load_workbook(PROJECT / "Gallup_200pairs_4columns.xlsx", read_only=True)
    ws2 = wb2.active
    rows2 = list(ws2.iter_rows(values_only=True))
    wb2.close()

    pairs = []
    for q_idx, row in enumerate(rows2, start=1):
        if not row or len(row) < 4:
            continue
        if row[0] is None:
            continue
        left_text = str(row[0] or "").strip()
        left_theme = normalize_theme(row[1])
        right_text = str(row[2] or "").strip()
        right_theme = normalize_theme(row[3])
        if not left_text or not right_text:
            continue
        pairs.append({
            "id": q_idx,
            "left": {"text": left_text, "theme": left_theme},
            "right": {"text": right_text, "theme": right_theme},
        })
    return pairs


# ============================================================================
# ОПИСАНИЯ ТЕМ (краткие, на русском)
# ============================================================================

THEME_DESCRIPTIONS = {
    "Achiever":         "Достигатель. Работоспособный, всегда стремится к результату.",
    "Activator":        "Активатор. Действует быстро, превращает идеи в реальность.",
    "Adaptability":     "Адаптивность. Гибкий, живёт «здесь и сейчас».",
    "Analytical":       "Аналитик. Любит данные, факты, логику.",
    "Arranger":         "Организатор. Умеет координировать людей и ресурсы.",
    "Belief":           "Убеждённость. Живёт по своим ценностям.",
    "Command":          "Командир. Уверенно берёт на себя руководство.",
    "Communication":    "Коммуникатор. Легко объясняет сложные идеи.",
    "Competition":      "Соревнователь. Стремится побеждать, сравнивает себя с другими.",
    "Connectedness":    "Единство. Верит в связь всего живого.",
    "Consistency":      "Последовательность. Ценит правила и справедливость.",
    "Context":          "Контекст. Любит историю, изучает прошлое для понимания настоящего.",
    "Deliberative":     "Внимательный. Осторожен, всё обдумывает заранее.",
    "Developer":        "Наставник. Видит потенциал в людях и помогает расти.",
    "Discipline":       "Дисциплина. Любит порядок, структуру и рутину.",
    "Empathy":          "Эмпатия. Чувствует эмоции других.",
    "Focus":            "Фокус. Ставит цели и идёт к ним без отвлечений.",
    "Futuristic":       "Футурист. Видит будущее, мечтатель.",
    "Harmony":          "Гармония. Ищет согласие, избегает конфликтов.",
    "Ideation":         "Идеатор. Креативщик, генератор идей.",
    "Includer":         "Объединитель. Принимает всех, никого не оставляет за бортом.",
    "Individualization":"Индивидуализация. Видит уникальность каждого человека.",
    "Input":            "Собиратель. Любознательный, собирает идеи и информацию.",
    "Intellection":     "Мыслитель. Любит размышлять, философ.",
    "Learner":          "Учёный. Процесс обучения радует больше результата.",
    "Maximizer":        "Максимизатор. Превращает хорошее в великое.",
    "Positivity":       "Позитив. Заражает оптимизмом.",
    "Relator":          "Наладчик. Строит глубокие отношения с близкими.",
    "Responsibility":   "Ответственный. Берёт обязательства и выполняет.",
    "Restorative":      "Решатель. Любит чинить то, что сломалось.",
    "Self-Assurance":   "Уверенность. Верит в себя, не боится рисковать.",
    "Significance":     "Значимость. Хочет быть признанным, важным.",
    "Strategic":        "Стратег. Видит альтернативные пути и выбирает лучший.",
    "Woo":              "Вовлекатель. Обожает знакомиться и завоёвывать.",
}

# 4 домена Gallup
DOMAINS = {
    "Executing":          ["Achiever", "Activator", "Arranger", "Belief", "Consistency", "Deliberative", "Discipline", "Focus", "Responsibility", "Restorative"],
    "Influencing":        ["Activator", "Command", "Communication", "Competition", "Maximizer", "Self-Assurance", "Significance", "Woo"],
    "Relationship Building": ["Developer", "Empathy", "Harmony", "Includer", "Individualization", "Positivity", "Relator"],
    "Strategic Thinking": ["Analytical", "Context", "Futuristic", "Ideation", "Input", "Intellection", "Learner", "Strategic"],
}


# ============================================================================
# ГЕНЕРАЦИЯ ФАЙЛОВ
# ============================================================================

def main():
    print("=" * 70)
    print("СБОРКА ВЕБ-ПРИЛОЖЕНИЯ")
    print("=" * 70)

    pairs = extract_pairs()
    print(f"[OK] Извлечено пар: {len(pairs)}")
    # Соберём список всех тем
    themes = sorted(set(p["left"]["theme"] for p in pairs) | set(p["right"]["theme"] for p in pairs))
    print(f"[OK] Уникальных тем: {len(themes)}")

    WEB_DIR.mkdir(exist_ok=True)

    # ---- data.js ---------------------------------------------------------
    data_js = "// AUTO-GENERATED. НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ.\n"
    data_js += f"const QUESTIONS = {json.dumps(pairs, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const THEME_DESCRIPTIONS = {json.dumps(THEME_DESCRIPTIONS, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const DOMAINS = {json.dumps(DOMAINS, ensure_ascii=False, indent=2)};\n\n"
    (WEB_DIR / "data.js").write_text(data_js, encoding="utf-8")
    print(f"[OK] {WEB_DIR / 'data.js'}")

    # ---- style.css --------------------------------------------------------
    style_css = """
:root {
  --bg: #0f1419;
  --bg-card: #1a2129;
  --bg-card-2: #232b35;
  --border: #2d3743;
  --text: #e6e9ef;
  --text-muted: #8a96a6;
  --accent: #f5a623;
  --accent-2: #f7c948;
  --primary: #f5a623;
  --primary-dark: #c97f00;
  --success: #4caf50;
  --danger: #ef5350;
  --radius: 14px;
  --shadow: 0 8px 32px rgba(0,0,0,0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

body {
  background:
    radial-gradient(circle at 15% 0%, rgba(245,166,35,0.08) 0%, transparent 50%),
    radial-gradient(circle at 85% 100%, rgba(76,175,80,0.05) 0%, transparent 50%),
    var(--bg);
}

.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}

/* ===== HEADER ===== */
.header {
  text-align: center;
  padding: 32px 0 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}
.header h1 {
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}
.header p { color: var(--text-muted); font-size: 15px; }

/* ===== HERO / WELCOME ===== */
.hero {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 40px 32px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
}
.hero h2 {
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--text);
}
.hero p { color: var(--text-muted); margin-bottom: 14px; }
.hero ul {
  list-style: none;
  margin: 18px 0;
}
.hero li {
  padding: 10px 0;
  padding-left: 28px;
  position: relative;
  color: var(--text-muted);
}
.hero li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: var(--accent);
  font-weight: 800;
}
.disclaimer {
  background: rgba(245,166,35,0.08);
  border: 1px solid rgba(245,166,35,0.3);
  border-radius: 10px;
  padding: 16px;
  margin: 18px 0;
  font-size: 13px;
  color: var(--accent-2);
}

/* ===== BUTTONS ===== */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 28px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--primary-dark) 100%);
  color: #1a0f00;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
  transition: transform 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(245,166,35,0.3);
}
.btn:active { transform: translateY(0); }
.btn-secondary {
  background: var(--bg-card-2);
  color: var(--text);
  border: 1px solid var(--border);
}
.btn-secondary:hover {
  background: var(--border);
  box-shadow: none;
}
.btn-lg { padding: 18px 36px; font-size: 17px; }

/* ===== PROGRESS ===== */
.progress-bar {
  width: 100%;
  height: 6px;
  background: var(--bg-card-2);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 24px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-2) 100%);
  width: 0%;
  transition: width 0.3s;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--text-muted);
}

/* ===== TEST CARD ===== */
.test-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 36px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  animation: fadeIn 0.3s;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.test-card .q-number {
  font-size: 12px;
  color: var(--accent);
  letter-spacing: 1px;
  font-weight: 700;
  margin-bottom: 18px;
}
.statement {
  padding: 22px 24px;
  background: var(--bg-card-2);
  border-radius: 12px;
  border: 2px solid transparent;
  margin-bottom: 12px;
  transition: all 0.2s;
}
.statement.chosen {
  border-color: var(--accent);
  background: rgba(245,166,35,0.1);
}
.statement-text { font-size: 16px; color: var(--text); }

.scale {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 24px;
}
.scale button {
  padding: 14px 8px;
  background: var(--bg-card-2);
  color: var(--text);
  border: 2px solid var(--border);
  border-radius: 10px;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}
.scale button:hover {
  background: var(--border);
  border-color: var(--text-muted);
}
.scale button.selected {
  background: var(--accent);
  color: #1a0f00;
  border-color: var(--accent);
}
.scale-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

/* ===== NAVIGATION ===== */
.nav {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
  gap: 12px;
}

/* ===== RESULTS ===== */
.results-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 40px 32px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  margin-bottom: 20px;
}
.results-title {
  font-size: 28px;
  margin-bottom: 8px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.results-subtitle { color: var(--text-muted); margin-bottom: 28px; }

.top-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 32px;
}
.top-card {
  background: var(--bg-card-2);
  border-radius: 12px;
  padding: 18px 20px;
  border-left: 4px solid var(--accent);
}
.top-card-rank {
  font-size: 12px;
  font-weight: 800;
  color: var(--accent);
  letter-spacing: 1px;
}
.top-card-name {
  font-size: 18px;
  font-weight: 700;
  margin: 4px 0 6px;
  color: var(--text);
}
.top-card-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.45;
}

@media (max-width: 600px) {
  .top-grid { grid-template-columns: 1fr; }
  .scale { grid-template-columns: 1fr 1fr 1fr 1fr 1fr; }
  .scale button { padding: 12px 4px; font-size: 16px; }
}

/* ===== CHART ===== */
.chart-wrap {
  background: var(--bg-card-2);
  border-radius: 12px;
  padding: 20px;
  margin-top: 16px;
}
.chart-title {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* ===== ALL THEMES ===== */
.all-themes {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
  margin-top: 24px;
}
.theme-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-card-2);
  border-radius: 8px;
  font-size: 13px;
}
.theme-row.top5 { border: 1px solid var(--accent); }
.theme-row .name { font-weight: 600; }
.theme-row .rank {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg);
  padding: 3px 10px;
  border-radius: 20px;
}

/* ===== GALLUP INPUT ===== */
.gallup-input {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 32px;
  margin-top: 20px;
  border: 1px solid var(--border);
}
.gallup-input h3 {
  font-size: 20px;
  margin-bottom: 12px;
}
.gallup-input p {
  color: var(--text-muted);
  margin-bottom: 20px;
  font-size: 14px;
}
.theme-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0 24px;
}
.chip {
  padding: 7px 14px;
  background: var(--bg-card-2);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--text-muted);
}
.chip:hover { color: var(--text); border-color: var(--text-muted); }
.chip.selected {
  background: var(--accent);
  color: #1a0f00;
  border-color: var(--accent);
  font-weight: 700;
}
.chip.selected .chip-rank {
  background: rgba(0,0,0,0.2);
}
.chip-rank {
  margin-left: 6px;
  font-size: 11px;
  background: var(--bg);
  padding: 2px 7px;
  border-radius: 10px;
}

/* ===== SUBMIT ===== */
.submit-row {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  flex-wrap: wrap;
}

/* ===== FOOTER ===== */
.footer {
  text-align: center;
  margin-top: 48px;
  padding: 24px;
  color: var(--text-muted);
  font-size: 12px;
}
.footer a { color: var(--accent); text-decoration: none; }

/* ===== UTILS ===== */
.hidden { display: none !important; }
.fade-in { animation: fadeIn 0.4s; }
"""
    (WEB_DIR / "style.css").write_text(style_css, encoding="utf-8")
    print(f"[OK] {WEB_DIR / 'style.css'}")

    # ---- index.html -------------------------------------------------------
    index_html = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gallup Copy — Тест сильных сторон</title>
  <link rel="stylesheet" href="style.css">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='80' font-size='80'%3E%F0%9F%9A%80%3C/text%3E%3C/svg%3E">
</head>
<body>

<div class="container">
  <header class="header">
    <h1>🚀 Gallup Copy</h1>
    <p>Узнай свои 34 таланта. Бесплатно, без регистрации.</p>
  </header>

  <!-- WELCOME SCREEN -->
  <section id="welcome" class="hero">
    <h2>Что это?</h2>
    <p>Это <b>клон теста Gallup CliftonStrengths</b> — инструмента, который за $50+ определяет ваши 34 сильные стороны. Здесь — то же самое, но бесплатно.</p>
    <ul>
      <li><b>200 пар утверждений</b> (≈ 15-20 минут)</li>
      <li><b>34 темы (таланта)</b> — те же, что в оригинальном Gallup</li>
      <li><b>Топ-5</b> ваших сильных сторон после прохождения</li>
      <li><b>Прогресс сохраняется</b> — можно прервать и продолжить</li>
    </ul>
    <div class="disclaimer">
      ⚠️ Это экспериментальная версия. Точность алгоритма ~30% по сравнению с оригинальным Gallup
      (см. отчёт). Результат — ориентир, не истина в последней инстанции.
    </div>
    <button id="start-btn" class="btn btn-lg" style="margin-top: 24px;">
      Начать тест →
    </button>
  </section>

  <!-- TEST SCREEN -->
  <section id="test" class="hidden">
    <div class="progress-info">
      <span id="progress-text">Вопрос 1 из 200</span>
      <span id="progress-pct">0%</span>
    </div>
    <div class="progress-bar"><div id="progress-fill" class="progress-fill"></div></div>

    <div class="test-card">
      <div class="q-number">ВОПРОС <span id="q-num">1</span></div>

      <div class="statement" id="stmt-left">
        <div class="statement-text" id="left-text"></div>
      </div>

      <div class="statement" id="stmt-right">
        <div class="statement-text" id="right-text"></div>
      </div>

      <div class="scale" id="scale">
        <button data-val="1">1</button>
        <button data-val="2">2</button>
        <button data-val="3">3</button>
        <button data-val="4">4</button>
        <button data-val="5">5</button>
      </div>
      <div class="scale-labels">
        <span>← Левое больше про меня</span>
        <span>Правое больше про меня →</span>
      </div>

      <div class="nav">
        <button id="prev-btn" class="btn btn-secondary">← Назад</button>
        <button id="next-btn" class="btn">Далее →</button>
        <button id="finish-btn" class="btn hidden">Получить результат 🎯</button>
      </div>
    </div>
  </section>

  <!-- RESULTS SCREEN -->
  <section id="results" class="hidden">
    <div class="results-card fade-in">
      <h2 class="results-title">🎯 Ваши сильные стороны</h2>
      <p class="results-subtitle">На основе ваших ответов. Ниже — топ-5 + полный ранг всех 34 тем.</p>

      <div id="top-grid" class="top-grid"></div>

      <div class="chart-wrap">
        <div class="chart-title">📊 Все 34 темы (по убыванию силы)</div>
        <div id="all-themes" class="all-themes"></div>
      </div>
    </div>

    <div class="gallup-input">
      <h3>🎓 У вас есть результат Gallup?</h3>
      <p>Если вы проходили оригинальный Gallup и помните свой топ-5 — выберите ниже. Это поможет улучшить алгоритм (ваши данные пойдут в обезличенную статистику).</p>

      <p style="margin-top: 16px; font-size: 13px;">Выберите 5 тем (кликом), затем укажите их ранги (1-5):</p>
      <div id="gallup-chips" class="theme-chips"></div>

      <div class="submit-row">
        <button id="submit-btn" class="btn">📤 Отправить результат</button>
        <button id="restart-btn" class="btn btn-secondary">🔄 Пройти заново</button>
      </div>
      <div id="submit-status" class="disclaimer hidden" style="margin-top: 16px;"></div>
    </div>
  </section>

  <footer class="footer">
    <p>Открытый проект · GitHub Pages хостинг · Данные пользователей не сохраняются на сервере</p>
  </footer>
</div>

<script src="data.js"></script>
<script src="app.js"></script>
</body>
</html>
"""
    (WEB_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[OK] {WEB_DIR / 'index.html'}")

    # ---- app.js -----------------------------------------------------------
    app_js = """
// =============================================================================
// Gallup Copy - Client-side test logic
// =============================================================================

const STORAGE_KEY = 'gallup_copy_state_v1';

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
  // Восстановим прогресс если есть
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
  document.getElementById('q-num').textContent = state.current + 1;
  document.getElementById('left-text').textContent = q.left.text;
  document.getElementById('right-text').textContent = q.right.text;

  // Подсветить выбранный ответ
  document.querySelectorAll('#scale button').forEach(btn => {
    btn.classList.toggle('selected', Number(btn.dataset.val) === state.answers[state.current]);
  });

  // Прогресс
  const done = state.answers.filter(a => a !== null).length;
  const pct = Math.round((done / QUESTIONS.length) * 100);
  document.getElementById('progress-text').textContent = `Вопрос ${state.current + 1} из ${QUESTIONS.length} (${done} отвечено)`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
  document.getElementById('progress-fill').style.width = pct + '%';

  // Кнопки навигации
  document.getElementById('prev-btn').disabled = state.current === 0;
  const isLast = state.current === QUESTIONS.length - 1;
  document.getElementById('next-btn').classList.toggle('hidden', isLast);
  document.getElementById('finish-btn').classList.toggle('hidden', !isLast);
}

function selectAnswer(val) {
  state.answers[state.current] = val;
  saveState();
  renderQuestion();
  // Авто-переход на следующий вопрос через 200мс
  setTimeout(() => {
    if (state.current < QUESTIONS.length - 1) {
      state.current++;
      renderQuestion();
    }
  }, 200);
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
  if (state.answers.filter(a => a !== null).length < QUESTIONS.length * 0.95) {
    if (!confirm(`Вы ответили не на все вопросы (${state.answers.filter(a => a !== null).length}/${QUESTIONS.length}). Продолжить?`)) return;
  }
  document.getElementById('test').classList.add('hidden');
  document.getElementById('results').classList.remove('hidden');
  renderResults();
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
  // Гарантируем наличие всех тем (даже если 0)
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

  // Top-5 grid
  const topGrid = document.getElementById('top-grid');
  topGrid.innerHTML = '';
  top5.forEach((t, i) => {
    const card = document.createElement('div');
    card.className = 'top-card';
    card.innerHTML = `
      <div class="top-card-rank">#${t.rank} ИЗ 34</div>
      <div class="top-card-name">${escapeHtml(t.theme)}</div>
      <div class="top-card-desc">${escapeHtml(THEME_DESCRIPTIONS[t.theme] || '')}</div>
    `;
    topGrid.appendChild(card);
  });

  // Все 34 темы
  const allThemes = document.getElementById('all-themes');
  allThemes.innerHTML = '';
  ranks.forEach(t => {
    const row = document.createElement('div');
    row.className = 'theme-row' + (t.rank <= 5 ? ' top5' : '');
    row.innerHTML = `
      <span class="name">${escapeHtml(t.theme)}</span>
      <span class="rank">#${t.rank}</span>
    `;
    allThemes.appendChild(row);
  });

  // Gallup chips для ввода
  renderGallupChips();
}

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
  updateGallupChipState();
}

function updateGallupChipState() {
  document.querySelectorAll('#gallup-chips .chip').forEach(chip => {
    const t = chip.dataset.theme;
    const sel = state.gallupTop5.find(x => x.theme === t);
    chip.classList.toggle('selected', !!sel);
    if (sel) {
      chip.innerHTML = `${t} <span class="chip-rank">#${sel.rank}</span>`;
    } else {
      chip.innerHTML = t;
    }
  });
}

// =============================================================================
// СОХРАНЕНИЕ / ОТПРАВКА
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

function submitResults() {
  const scores = calculateScores(state.answers);
  const ranks = ranksFromScores(scores);
  const payload = {
    timestamp: new Date().toISOString(),
    answers_count: state.answers.filter(a => a !== null).length,
    predicted_top5: ranks.slice(0, 5).map(t => ({ theme: t.theme, score: t.score })),
    gallup_top5: state.gallupTop5,
    all_ranks: ranks,
  };

  const json = JSON.stringify(payload, null, 2);

  // Попробуем POST на тот же origin (если есть бэкенд), иначе покажем JSON
  fetch('/api/submit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: json,
  }).then(r => {
    if (r.ok) {
      showSubmitStatus('✅ Отправлено! Спасибо, ваши данные помогут улучшить алгоритм.', false);
    } else {
      throw new Error('no backend');
    }
  }).catch(() => {
    // Fallback: показать JSON и предложить скачать
    showSubmitStatus('⚠️ Бэкенд недоступен. Скопируйте или скачайте JSON и отправьте разработчику.', true, json);
  });
}

function showSubmitStatus(msg, showJson, json) {
  const el = document.getElementById('submit-status');
  el.innerHTML = `<div>${msg}</div>` +
    (showJson ? `<textarea readonly style="width:100%;height:200px;margin-top:12px;font-family:monospace;font-size:11px;background:#000;color:#0f0;border:none;padding:8px;border-radius:6px;">${escapeHtml(json)}</textarea>
    <button class="btn btn-secondary" style="margin-top:8px;" onclick="downloadJson()">📥 Скачать JSON</button>` : '');
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
  document.getElementById('next-btn').addEventListener('click', nextQuestion);
  document.getElementById('prev-btn').addEventListener('click', prevQuestion);
  document.getElementById('finish-btn').addEventListener('click', finishTest);
  document.getElementById('submit-btn').addEventListener('click', submitResults);
  document.getElementById('restart-btn').addEventListener('click', () => {
    if (confirm('Начать заново? Ваши ответы будут потеряны.')) {
      clearState();
      document.getElementById('results').classList.add('hidden');
      document.getElementById('welcome').classList.remove('hidden');
    }
  });

  document.querySelectorAll('#scale button').forEach(btn => {
    btn.addEventListener('click', () => selectAnswer(Number(btn.dataset.val)));
  });

  // Keyboard navigation: 1-5 for answers, Enter for next
  document.addEventListener('keydown', (e) => {
    if (document.getElementById('test').classList.contains('hidden')) return;
    if (e.key >= '1' && e.key <= '5') {
      selectAnswer(Number(e.key));
    } else if (e.key === 'ArrowLeft') {
      prevQuestion();
    } else if (e.key === 'ArrowRight') {
      nextQuestion();
    }
  });
});
"""
    (WEB_DIR / "app.js").write_text(app_js, encoding="utf-8")
    print(f"[OK] {WEB_DIR / 'app.js'}")

    # ---- README -----------------------------------------------------------
    readme = """# Gallup Copy — Веб-приложение

## Что это

Бесплатный клон теста Gallup CliftonStrengths. 200 вопросов → топ-5 сильных сторон из 34 тем.

## Файлы

- `index.html` — главная страница
- `style.css` — стили (тёмная тема)
- `data.js` — 200 вопросов и описания тем (генерируется из `build_web.py`)
- `app.js` — логика теста и алгоритм подсчёта

## Локальный запуск

Просто откройте `index.html` в браузере, либо запустите локальный сервер:

```bash
cd web
python -m http.server 8000
# Откройте http://localhost:8000
```

## Деплой (бесплатно)

### GitHub Pages
1. Создай репозиторий
2. Залей файлы из `web/`
3. Settings → Pages → выбери ветку
4. Готово — будет URL вида `username.github.io/repo/`

### Netlify
1. Зайди на https://app.netlify.com/drop
2. Перетащи папку `web/`
3. Получишь URL сразу

### Vercel
1. `npm i -g vercel`
2. `cd web && vercel --prod`
3. Следуй инструкциям

## Сбор данных

В MVP данные пользователей **не отправляются** ни на какой сервер.
Кнопка «Отправить результат» пытается POST на `/api/submit`. Если бэкенда нет —
показывает JSON, который можно скопировать или скачать.

Для приёма данных в будущем: добавь бэкенд на любом бесплатном хостинге
(Railway, Render, Fly.io — есть free tier).

## Точность алгоритма

~30% top-10 совпадение с оригинальным Gallup (на текущих 10 размеченных людей).
Для повышения точности нужно больше данных — собирай результаты через форму
внизу страницы.
"""
    (WEB_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"[OK] {WEB_DIR / 'README.md'}")

    print("\n" + "=" * 70)
    print(f"ГОТОВО! Файлы в {WEB_DIR}")
    print("=" * 70)
    print(f"  {WEB_DIR / 'index.html'}")
    print(f"  {WEB_DIR / 'style.css'}")
    print(f"  {WEB_DIR / 'app.js'}")
    print(f"  {WEB_DIR / 'data.js'}")
    print(f"  {WEB_DIR / 'README.md'}")
    print()
    print("Запуск:")
    print(f"  cd {WEB_DIR}")
    print(f"  python -m http.server 8000")
    print(f"  Открой http://localhost:8000")


if __name__ == "__main__":
    main()
