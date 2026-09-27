"""
inspect_mapping.py
==================
Выгружает все 200 пар с текущим маппингом в удобные для просмотра форматы:
  - mapping_review.csv     — для Excel/Google Sheets
  - mapping_review.html    — для браузера (с подсветкой подозрительных)
  - mapping_review.txt     — для просмотра в консоли

Структура Gallup_200pairs_4columns.xlsx:
  Ряд 0 = пара №1, ряд 1 = пара №2, ..., ряд 199 = пара №200
  Колонки: 0=текст A, 1=тема A, 2=текст B, 3=тема B
"""

import json
import sys
from collections import Counter
from pathlib import Path

import openpyxl
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = Path(__file__).resolve().parent
MAPPING_JSON = PROJECT_DIR / "smart_mapping.json"
PAIRS_XLSX = PROJECT_DIR / "Gallup_200pairs_4columns.xlsx"


def normalize_theme(name: str) -> str:
    """'Self-assurance' <-> 'Self-Assurance' <-> 'SELF-ASSURANCE' -> 'Self-Assurance'."""
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        parts = n.split("-")
        n = "-".join(p.capitalize() for p in parts)
    return n


# ============================================================================
# Загрузка данных
# ============================================================================

def load_pairs():
    """Загружает пары из xlsx (с полными текстами утверждений).
    Структура xlsx: (left_text, left_theme, right_text, right_theme).
    Номера вопросов — это индексы строк, начиная с 0 = pair #1.
    """
    wb = openpyxl.load_workbook(PAIRS_XLSX, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    pairs = {}
    for q_idx, row in enumerate(rows, start=1):  # pair #1 = row 0
        if not row or len(row) < 4:
            continue
        left_text = str(row[0] or "").strip()
        left_theme = normalize_theme(row[1])
        right_text = str(row[2] or "").strip()
        right_theme = normalize_theme(row[3])
        if not left_text or not right_text:
            continue
        pairs[q_idx] = {
            "left_text": left_text,
            "left_theme": left_theme,
            "right_text": right_text,
            "right_theme": right_theme,
        }
    return pairs


def load_mapping_json():
    """Загружает маппинг из JSON (компактная версия)."""
    with open(MAPPING_JSON, encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for entry in data:
        result[entry["q"]] = (normalize_theme(entry["talent_A"]), normalize_theme(entry["talent_B"]))
    return result


# ============================================================================
# Анализ
# ============================================================================

def analyze_mapping(pairs, mapping):
    theme_count = Counter()
    rows = []
    suspicious_clusters = []

    last_theme = None
    cluster_qs = []

    for q in range(1, 201):
        if q not in pairs:
            continue
        left_theme = pairs[q]["left_theme"]
        right_theme = pairs[q]["right_theme"]
        json_a, json_b = mapping.get(q, (None, None))

        theme_count[left_theme] += 1
        theme_count[right_theme] += 1

        # Кластеры: 4+ пары подряд, где одна сторона - одна и та же тема
        if left_theme == last_theme:
            cluster_qs.append(q - 1)
        else:
            if len(cluster_qs) >= 3:
                suspicious_clusters.append((last_theme, cluster_qs))
            cluster_qs = []
            last_theme = left_theme

        is_same = left_theme == right_theme

        rows.append({
            "q": q,
            "left_text": pairs[q]["left_text"],
            "left_theme": left_theme,
            "right_text": pairs[q]["right_text"],
            "right_theme": right_theme,
            "json_A": json_a or "",
            "json_B": json_b or "",
            "themes_match": (json_a == left_theme and json_b == right_theme) or
                            (json_a == right_theme and json_b == left_theme),
            "same_theme_both_sides": is_same,
        })

    if len(cluster_qs) >= 3:
        suspicious_clusters.append((last_theme, cluster_qs))

    return rows, theme_count, suspicious_clusters


# ============================================================================
# Генерация отчётов
# ============================================================================

def save_csv(rows, theme_count):
    df = pd.DataFrame(rows)
    out = PROJECT_DIR / "mapping_review.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[OK] CSV: {out}")
    return out


def save_html(rows, theme_count):
    df = pd.DataFrame(rows)
    avg = sum(theme_count.values()) / max(1, len(theme_count))
    n_same = sum(1 for r in rows if r["same_theme_both_sides"])
    n_mismatch = sum(1 for r in rows if not r["themes_match"])

    style = """
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; max-width: 1400px; margin: 0 auto; }
      table { border-collapse: collapse; width: 100%; font-size: 12px; }
      th, td { border: 1px solid #ddd; padding: 6px; text-align: left; vertical-align: top; }
      th { background: #4CAF50; color: white; position: sticky; top: 0; }
      tr:nth-child(even) { background: #f9f9f9; }
      .same { background: #ffcccc !important; }
      .mismatch { background: #fce4ec !important; }
      .theme { font-weight: bold; color: #1976d2; }
      .stats { margin-bottom: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px; }
      .stat-bar { display: inline-block; padding: 4px 12px; margin: 2px; border-radius: 4px; background: #fff; font-size: 13px; }
      .stat-bar.high { background: #ef5350; color: white; }
      .stat-bar.low { background: #ff9800; color: white; }
      .stat-bar.ok { background: #66bb6a; color: white; }
    </style>
    """

    rows_html = []
    for r in rows:
        cls = ""
        if r["same_theme_both_sides"]:
            cls = "same"
        elif not r["themes_match"]:
            cls = "mismatch"
        rows_html.append(f"""
        <tr class="{cls}">
          <td><b>{r['q']}</b></td>
          <td>{r['left_text'][:180]}{'...' if len(r['left_text'])>180 else ''}</td>
          <td><span class="theme">{r['left_theme']}</span></td>
          <td>{r['right_text'][:180]}{'...' if len(r['right_text'])>180 else ''}</td>
          <td><span class="theme">{r['right_theme']}</span></td>
        </tr>""")

    sorted_themes = sorted(theme_count.items(), key=lambda x: -x[1])
    theme_html = []
    for theme, count in sorted_themes:
        if count > avg * 1.8:
            cls = "high"
        elif count < 3:
            cls = "low"
        else:
            cls = "ok"
        theme_html.append(f'<span class="stat-bar {cls}">{theme}: {count}</span>')

    full = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Mapping Review</title>{style}</head>
<body>
<h1>Gallup Mapping Review — 200 пар</h1>

<div class="stats">
  <h3>Распределение пар по темам ({len(theme_count)} тем):</h3>
  <p>Среднее: <b>{avg:.1f}</b> пар на тему. Идеал Gallup: ~10-12.
     <span style="background:#ef5350;color:white;padding:2px 6px;border-radius:3px;">Красные</span> — перекос (>>среднего),
     <span style="background:#ff9800;color:white;padding:2px 6px;border-radius:3px;">оранжевые</span> — слишком мало.</p>
  <p>{''.join(theme_html)}</p>
</div>

<div class="stats">
  <p><b>Подозрительных пар (та же тема с обеих сторон):</b> {n_same}</p>
  <p><b>Несовпадений xlsx vs JSON:</b> {n_mismatch}</p>
</div>

<table>
  <thead>
    <tr>
      <th>№</th>
      <th>Левое утверждение</th>
      <th>Тема A</th>
      <th>Правое утверждение</th>
      <th>Тема B</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>

</body></html>"""

    out = PROJECT_DIR / "mapping_review.html"
    out.write_text(full, encoding="utf-8")
    print(f"[OK] HTML: {out}")
    return out


def save_txt(rows, theme_count):
    lines = []
    lines.append("=" * 80)
    lines.append("GALLUP MAPPING REVIEW - 200 PAIRS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("РАСПРЕДЕЛЕНИЕ ПО ТЕМАМ (от большего к меньшему):")
    lines.append("-" * 80)
    avg = sum(theme_count.values()) / max(1, len(theme_count))
    for theme, count in sorted(theme_count.items(), key=lambda x: -x[1]):
        flag = ""
        if count > avg * 1.8:
            flag = " [ПЕРЕКОС]"
        elif count < 3:
            flag = " [МАЛО]"
        lines.append(f"  {theme:<22} {count:>3}  {flag}")

    lines.append("")
    lines.append(f"Среднее: {avg:.1f} | Тем: {len(theme_count)}")
    lines.append("")
    lines.append("=" * 80)
    lines.append("ВСЕ 200 ПАР:")
    lines.append("=" * 80)
    for r in rows:
        flag = " ⚠️ ОДНА ТЕМА" if r["same_theme_both_sides"] else ""
        lines.append(f"#{r['q']:>3}{flag}")
        lines.append(f"  A: {r['left_theme']:<18} | {r['left_text'][:110]}")
        lines.append(f"  B: {r['right_theme']:<18} | {r['right_text'][:110]}")
        lines.append("")
    out = PROJECT_DIR / "mapping_review.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] TXT: {out}")
    return out


# ============================================================================
# Главный прогон
# ============================================================================

def main():
    print("Загружаю данные...")
    pairs = load_pairs()
    mapping = load_mapping_json()
    print(f"[OK] Пар из xlsx: {len(pairs)}")
    print(f"[OK] Маппингов из JSON: {len(mapping)}")

    rows, theme_count, clusters = analyze_mapping(pairs, mapping)
    print(f"\nТем в маппинге: {len(theme_count)}")
    print(f"Пар: {len(rows)}")
    print(f"Подозрительных (same theme): {sum(1 for r in rows if r['same_theme_both_sides'])}")
    print(f"Несовпадений xlsx vs JSON: {sum(1 for r in rows if not r['themes_match'])}")
    print(f"Кластеров одной темы подряд: {len(clusters)}")

    print("\nСохранение отчётов...")
    save_csv(rows, theme_count)
    save_html(rows, theme_count)
    save_txt(rows, theme_count)

    print("\n" + "=" * 70)
    print("ГОТОВО. Открой:")
    print("  - mapping_review.html  (в браузере, с подсветкой)")
    print("  - mapping_review.csv   (в Excel, для редактирования)")
    print("  - mapping_review.txt   (краткий обзор)")
    print("=" * 70)


if __name__ == "__main__":
    main()
