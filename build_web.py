"""
build_web.py
============
Генерирует web/data.js из:
  • hybrid-маппинга (best_mapping_final.json) — ручной маппинг + семантический
    фикс для тем с отрицательной корреляцией
  • психометрии Gallup (gallup_psychometrics.py) — reliability weights,
    описания тем, домены

Также пишет web/data/mapping.json (прозрачность маппинга).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

from gallup_psychometrics import (  # noqa: E402
    ALPHA_SAMPLE1, ALPHA_SAMPLE3, TEST_RETEST_M1,
    TEST_RETEST_M3, TEST_RETEST_M6, DOMAINS, THEME_DESCRIPTIONS_EN,
)

WEB_DIR = PROJECT / "web"
DATA_DIR = WEB_DIR / "data"
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
BEST_MAPPING = PROJECT / "best_mapping_final.json"

# Русские описания тем (для UI)
THEME_DESCRIPTIONS_RU = {
    "Achiever": "Достигатель. Выносливый, много работает, получает удовольствие от busy-ness и продуктивности.",
    "Activator": "Активатор. Превращает мысли в действия. Часто нетерпелив.",
    "Adaptability": "Адаптивность. Идёт с потоком, «человек момента», принимает жизнь такой как есть.",
    "Analytical": "Аналитик. Ищет причины и следствия, думает обо всех факторах ситуации.",
    "Arranger": "Организатор. Умеет настраивать людей и ресурсы для максимальной продуктивности.",
    "Belief": "Убеждённость. Имеет неизменные ценности, из которых вырастает предназначение жизни.",
    "Command": "Командир. Обладает присутствием, берёт контроль и принимает решения.",
    "Communication": "Коммуникатор. Легко переводит мысли в слова. Хороший собеседник и оратор.",
    "Competition": "Соревнователь. Сравнивает себя с другими, стремится к первому месту.",
    "Connectedness": "Единство. Верит в связь всех вещей, в отсутствие случайностей.",
    "Consistency": "Последовательность. Стремится относиться к людям одинаково, устанавливает чёткие правила.",
    "Context": "Контекст. Любит думать о прошлом, понимает настоящее через историю.",
    "Deliberative": "Внимательный. Серьёзно относится к решениям, предвидит препятствия.",
    "Developer": "Наставник. Видит потенциал в других и помогает ему расти.",
    "Discipline": "Дисциплина. Любит рутину и структуру, создаёт порядок.",
    "Empathy": "Эмпатия. Чувствует эмоции других, примеряя на себя их ситуацию.",
    "Focus": "Фокус. Ставит направление, доводит до конца, расставляет приоритеты.",
    "Futuristic": "Футурист. Вдохновляется будущим, заражает других своим видением.",
    "Harmony": "Гармония. Ищет согласия, избегает конфликтов, ценит общие точки.",
    "Ideation": "Идеатор. Увлекается идеями, находит связи между несвязанными явлениями.",
    "Includer": "Объединитель. Принимает всех, замечает тех, кто остался в стороне.",
    "Individualization": "Индивидуализация. Ценит уникальность каждого, находит сильные стороны различий.",
    "Input": "Собиратель. Стремится узнать больше, коллекционирует информацию и идеи.",
    "Intellection": "Мыслитель. Интеллектуальная активность, любит внутренние размышления и дискуссии.",
    "Learner": "Ученик. Процесс обучения радует больше результата, постоянно растёт.",
    "Maximizer": "Максимизатор. Превращает хорошее в великое, фокусируется на сильных сторонах.",
    "Positivity": "Позитив. Заразительный энтузиазм, поднимает настроение другим.",
    "Relator": "Наладчик. Ценит близкие отношения, находит удовольствие в общей цели с друзьями.",
    "Responsibility": "Ответственность. Берёт психологическое владение тем, что обещает. Верность и честность.",
    "Restorative": "Решатель. Разбирается с проблемами — находит, что сломалось, и чинит.",
    "Self-Assurance": "Уверенность. Управляет своей жизнью, уверен в правильности решений.",
    "Significance": "Значимость. Хочет быть важным и признанным, независим.",
    "Strategic": "Стратег. Создаёт альтернативные пути, быстро находит паттерны и проблемы.",
    "Woo": "Вовлекатель. Любит знакомиться и завоёвывать, получает удовольствие от первого контакта.",
}

DOMAIN_NAMES_RU = {
    "Executing": "Исполнение",
    "Influencing": "Влияние",
    "Relationship Building": "Отношения",
    "Strategic Thinking": "Стратегия",
}


def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_statements():
    """Загружает все 200 пар с текстами."""
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    pair_stmts = defaultdict(list)
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        try:
            stmt_num = int(str(row[0]).strip())
            pair_num = int(str(row[1]).strip())
        except (ValueError, TypeError):
            continue
        text = str(row[2] or "").strip()
        theme = normalize_theme(row[3])
        if not text or not theme:
            continue
        pair_stmts[pair_num].append({"num": stmt_num, "text": text, "theme": theme})
    pairs = []
    for pn in sorted(pair_stmts.keys()):
        stmts = sorted(pair_stmts[pn], key=lambda x: x["num"])
        if len(stmts) != 2:
            continue
        pairs.append({
            "q": pn, "A_text": stmts[0]["text"], "A_old": stmts[0]["theme"],
            "B_text": stmts[1]["text"], "B_old": stmts[1]["theme"],
        })
    return pairs


def main():
    print("=" * 70)
    print("СБОРКА ВЕБ-ПРИЛОЖЕНИЯ")
    print("=" * 70)

    pairs = load_statements()
    print(f"[OK] Пар из xlsx: {len(pairs)}")

    # Загружаем hybrid-маппинг
    best = json.loads(BEST_MAPPING.read_text(encoding="utf-8"))
    mapping = best["mapping"]
    scoring = best["scoring"]
    reliability_set = best.get("reliability", "retest6")
    reliability_mode = best.get("reliability_mode", "multiply")
    threshold = best.get("threshold", 0.0)
    metrics = best.get("metrics", {})

    print(f"[OK] Hybrid-маппинг: {len(mapping)} пар")
    print(f"     Порог замены слабых тем: ρ < {threshold:+.2f}")
    print(f"     Scoring: {scoring}")
    print(f"     Reliability: {reliability_set} ({reliability_mode})")
    print(f"     Метрики на 10 людях: ρ={metrics.get('rho', 0):+.3f} "
          f"top5={metrics.get('top5', 0):.0f}% top10={metrics.get('top10', 0):.0f}% "
          f"top15={metrics.get('top15', 0):.0f}%")

    # Собираем финальные пары для приложения
    final_pairs = []
    for p in pairs:
        m = next((x for x in mapping if x["q"] == p["q"]), None)
        final_pairs.append({
            "id": p["q"],
            "left": {"text": p["A_text"], "theme": m["A"] if m else p["A_old"]},
            "right": {"text": p["B_text"], "theme": m["B"] if m else p["B_old"]},
        })

    # Проверка: сколько пар реально изменилось
    changed = sum(1 for p, f in zip(pairs, final_pairs)
                  if f["left"]["theme"] != p["A_old"] or f["right"]["theme"] != p["B_old"])
    print(f"[OK] Изменено тем в {changed} парах")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ---- data.js -----------------------------------------------------
    reliability = {
        "alpha1": ALPHA_SAMPLE1,
        "alpha3": ALPHA_SAMPLE3,
        "retest1": TEST_RETEST_M1,
        "retest3": TEST_RETEST_M3,
        "retest6": TEST_RETEST_M6,
        "none": None,
    }[reliability_set]

    scoring_cfg = {
        "formula": scoring.get("formula", "sigmoid_soft"),
        "useMean": scoring.get("use_mean", True),
        "ipsative": scoring.get("ipsative", False),
        "standardize": scoring.get("standardize", False),
        "reliabilityMode": reliability_mode,
    }

    data_js = "// AUTO-GENERATED by build_web.py. НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ.\n"
    data_js += "// Методология: Gallup Clifton StrengthsFinder 2.0 Technical Report (2014)\n"
    data_js += "//   Table 1 — распределение утверждений, Table 3 — test-retest reliability\n\n"
    data_js += f"const QUESTIONS = {json.dumps(final_pairs, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const THEME_DESCRIPTIONS = {json.dumps(THEME_DESCRIPTIONS_RU, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const THEME_DESCRIPTIONS_EN = {json.dumps(THEME_DESCRIPTIONS_EN, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const DOMAINS = {json.dumps(DOMAINS, ensure_ascii=False, indent=2)};\n\n"
    data_js += f"const DOMAIN_NAMES = {json.dumps(DOMAIN_NAMES_RU, ensure_ascii=False, indent=2)};\n\n"
    data_js += "// Надёжность тем (test-retest, месяц 6) — используется как вес ранга\n"
    data_js += f"const THEME_RELIABILITY = {json.dumps(reliability, ensure_ascii=False, indent=2)};\n\n"
    data_js += "// Параметры скоринга (Gallup-методология)\n"
    data_js += f"const SCORING_CONFIG = {json.dumps(scoring_cfg, ensure_ascii=False, indent=2)};\n"
    (DATA_DIR.parent / "data.js").write_text(data_js, encoding="utf-8")
    print(f"[OK] web/data.js")

    # ---- web/data/mapping.json (прозрачность) ------------------------
    with open(DATA_DIR / "mapping.json", "w", encoding="utf-8") as f:
        json.dump({
            "description": "Hybrid mapping: manual Gallup mapping + semantic fix "
                           "for themes with negative correlation to ground truth",
            "threshold": threshold,
            "scoring": scoring,
            "reliability": reliability_set,
            "reliability_mode": reliability_mode,
            "metrics_on_10_labeled": metrics,
            "pairs": final_pairs,
        }, f, indent=2, ensure_ascii=False)
    print(f"[OK] web/data/mapping.json")

    print("\n" + "=" * 70)
    print("ГОТОВО")
    print("=" * 70)


if __name__ == "__main__":
    main()
