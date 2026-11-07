"""
rebuild_mapping.py
==================
Пересборка маппинга "утверждение → тема" на основе официальных данных Gallup:

  • Table 1 (отчёт 2014)  → сколько утверждений должно быть у каждой темы
  • Appendix A (отчёт 2014) → официальные описания тем (смысл каждой темы)
  • эмпирическая проверка → контроль качества на 10 размеченных людях

Алгоритм:
  1. Для каждого утверждения считаем семантическую близость к каждой из 34 тем
     (взвешенные ключевые слова + TF-IDF по описаниям тем).
  2. Решаем задачу назначения (Hungarian / linear_sum_assignment) с ограничением:
     кол-во утверждений на тему = round(доля_Gallup × наше_кол-во).
  3. Пост-обработка: если обе стороны пары получили одну тему — меняем одну
     на лучшую альтернативу.
  4. Сравниваем новый маппинг со старым на 10 размеченных людях.
"""

import json
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(r"C:\Users\User\gallup-project")
sys.path.insert(0, str(PROJECT))
from gallup_psychometrics import GALLUP_ITEM_COUNTS, THEME_DESCRIPTIONS_EN  # noqa: E402

MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
MISSING_RANK = 2000

THEMES = sorted(GALLUP_ITEM_COUNTS.keys())

# ============================================================================
# КЛЮЧЕВЫЕ СЛОВА ПО ТЕМАМ (русский) — выведены из сути тем (Appendix A)
# Вес = важность слова. Расширенный словарь на основе официальных описаний.
# ============================================================================

THEME_KEYWORDS = {
    "Achiever": {
        "достига": 3, "результат": 2, "вынослив": 3, "выносливост": 3, "работа": 2,
        "работ": 2, "продуктив": 3, "законч": 2, "добива": 3, "успех": 2, "успешн": 2,
        "целеустрем": 3, "упор": 2, "нагрузк": 2, "занят": 2, "занятост": 2, "активн": 1,
        "стара": 2, "старать": 2, "долг": 1, "много работа": 3, "уста": 2,
    },
    "Activator": {
        "действ": 2, "начина": 3, "побуж": 3, "мотивир": 2, "запуск": 3, "запуска": 3,
        "нетерп": 3, "предпринима": 2, "инициатив": 2, "первый шаг": 3, "энерги": 2,
        "быстро начина": 3, "двигател": 2, "реализ": 2, "план в действие": 3,
    },
    "Adaptability": {
        "адаптив": 3, "гибк": 3, "приспособ": 3, "изменчив": 2, "текущ": 2, "момент": 2,
        "иду с": 2, "легко адапт": 3, "принимаю как": 3, "спонтан": 2, "не планир": 2,
        "текущий момент": 3, "уступчив": 2, "новые обстоятельств": 3, "свободно": 1,
    },
    "Analytical": {
        "анализ": 3, "аналитич": 3, "данн": 2, "факт": 2, "логик": 3, "причин": 3,
        "доказательств": 3, "обоснов": 3, "исследу": 2, "проверя": 2, "проверк": 2,
        "гипотез": 3, "рассужда": 2, "изуча": 2, "критич": 2, "оцен": 1, "причинно": 3,
    },
    "Arranger": {
        "организ": 3, "координ": 3, "координир": 3, "распред": 2, "структур": 2,
        "расставля": 3, "комбинир": 2, "собира": 2, "настраива": 2, "логистик": 3,
        "ресурс": 2, "производительн": 2, "команд": 1, "группу": 1, "систем": 1,
        "расстановк": 3, "свод": 2, "компонов": 2,
    },
    "Belief": {
        "ценност": 3, "вер": 2, "убежд": 3, "принцип": 3, "идеал": 3, "мисси": 3,
        "смысл": 2, "смыслом": 2, "предназначен": 3, "верит": 2, "посвящ": 2,
        "глубок": 1, "корен": 2, "неизменн": 3, "веру": 2,
    },
    "Command": {
        "команд": 3, "руковод": 3, "лидер": 2, "власт": 3, "управля": 2, "реша": 2,
        "приним реш": 3, "контрол": 3, "высок": 1, "проявля": 1, "присутств": 2,
        "прямолиней": 2, "организую": 2, "ставлю": 1, "директив": 3, "наказыва": 2,
    },
    "Communication": {
        "коммуник": 3, "рассказ": 3, "объясн": 3, "выраж": 2, "реч": 2, "истор": 2,
        "слов": 2, "говор": 2, "лекц": 3, "убеди": 3, "презентац": 3, "пиш": 2,
        "текст": 2, "язык": 2, "разговарив": 2, "формулир": 3, "просто объясн": 3,
    },
    "Competition": {
        "соревн": 3, "конкур": 3, "побед": 3, "первое мест": 3, "лидерств": 2,
        "выигр": 3, "противник": 3, "превосход": 2, "соперничеств": 3, "рейтинг": 3,
        "лучше всех": 3, "первенств": 3, "очки": 2, "сравнива": 2, "рекорд": 2,
    },
    "Connectedness": {
        "связ": 3, "единств": 3, "целостн": 3, "общност": 2, "миров": 2,
        "взаимосвяз": 3, "всё связано": 3, "совпадени": 2, "часть целого": 3,
        "принадлежн": 2, "духовн": 2, "вселенн": 3, "неразделимо": 3, "родств": 1,
    },
    "Consistency": {
        "справедлив": 3, "правил": 3, "порядк": 2, "одинаков": 3, "одинаково": 3,
        "последовательн": 3, "стабильн": 2, "принцип": 2, "честн": 2, "беспристраст": 3,
        "системн": 1, "единообраз": 3, "неравенств": 2, "равноправ": 3, "традиц": 1,
    },
    "Context": {
        "прошло": 3, "истори": 3, "прошл": 2, "традиц": 2, "предков": 3, "древн": 2,
        "корн": 2, "лет назад": 3, "времена": 2, "эпох": 3, "учитывая истор": 3,
        "накопленн": 2, "опыт прошл": 3, "исток": 3,
    },
    "Deliberative": {
        "осторожн": 3, "обдум": 3, "внимательн": 2, "предвид": 3, "предусмотр": 3,
        "решение": 2, "взвешива": 3, "риск": 2, "убежда": 1, "подожду": 2,
        "не тороп": 3, "продума": 3, "серьезно отношу": 3, "избегаю риск": 3,
    },
    "Developer": {
        "помог": 2, "развив": 3, "потенциал": 3, "наставник": 3, "расти": 2,
        "талант": 3, "улучша": 2, "учи": 2, "обуч": 2, "вдохновл": 2, "поддерж": 2,
        "улучшен": 2, "способност": 2, "помогаю другим": 3, "выращива": 3,
    },
    "Discipline": {
        "дисциплин": 3, "структур": 2, "рутин": 3, "план": 2, "организован": 3,
        "порядок": 2, "систем": 2, "график": 3, "расписан": 3, "режим": 3,
        "привычк": 2, "устав": 2, "отложен": 1, "ежедневн": 2, "регламент": 3,
    },
    "Empathy": {
        "эмпат": 3, "сочувств": 3, "чувств": 2, "эмоц": 3, "понима": 2,
        "почувств": 3, "сопережив": 3, "поставит себя": 3, "чуж": 2, "пережив": 2,
        "береж": 1, "забот": 2, "сострадан": 3, "эмоциональн": 3,
    },
    "Focus": {
        "фокус": 3, "цел": 2, "приоритет": 3, "направлен": 2, "концентр": 3,
        "сосредот": 3, "отвлека": 2, "продолжа": 2, "довожу": 2, "сначала": 2,
        "главное": 3, "не отвлека": 3, "выбираю одно": 3,
    },
    "Futuristic": {
        "будущ": 3, "мечт": 3, "футур": 3, "видение": 2, "перспектив": 2,
        "предвид": 2, "через год": 3, "завтра": 3, "мечтаю": 3, "вдохновля": 3,
        "будущее": 3, "через 5 лет": 3, "через 10 лет": 3, "иллюз": 2,
    },
    "Harmony": {
        "гармон": 3, "соглас": 2, "мирн": 2, "консенсус": 3, "компромисс": 3,
        "согласи": 2, "примир": 3, "конфликт": 2, "избегаю конфликт": 3,
        "общени": 1, "уступк": 3, "объедин": 1, "найти общ": 3,
    },
    "Ideation": {
        "иде": 3, "креатив": 3, "придум": 3, "изобретат": 3, "связ": 1,
        "соедин": 2, "необычн": 2, "сравнив": 2, "сопоставля": 3, "вдохновляю": 2,
        "новые идеи": 3, "генератор": 3, "озарен": 3,
    },
    "Includer": {
        "включ": 3, "принят": 3, "принадлеж": 2, "объедин": 2, "вовле": 3,
        "одинок": 2, "исключен": 3, "всех": 2, "вместе": 2, "включает": 3,
        "не оставляю": 3, "присоедин": 3, "в группу": 2,
    },
    "Individualization": {
        "индивидуал": 3, "уникальн": 3, "особен": 2, "отлич": 2, "личн": 2,
        "свой путь": 3, "разными": 2, "считаюсь": 2, "по-своему": 3,
        "у каждого свой": 3, "непохож": 3, "яркая": 1, "характерн": 2,
    },
    "Input": {
        "собира": 3, "информ": 3, "идеи": 2, "вход": 2, "любознательн": 3,
        "книг": 2, "чита": 2, "узна": 2, "архив": 3, "коллекционир": 3,
        "хочу знать": 3, "изучаю новое": 3, "узнать новое": 3, "собираю": 3,
    },
    "Intellection": {
        "мысл": 3, "размышл": 3, "философ": 3, "интро": 2, "глубок": 2,
        "абстракт": 3, "концепц": 3, "теори": 2, "дебат": 2, "умоз": 1,
        "интеллектуальн": 3, "задумыва": 3, "один на один": 1,
    },
    "Learner": {
        "учи": 3, "обучен": 3, "изуча": 3, "процесс": 2, "знан": 2, "курс": 3,
        "учеб": 3, "новому": 2, "навык": 2, "практик": 2, "студент": 2,
        "хочу научит": 3, "мне нравится учит": 3, "учени": 3,
    },
    "Maximizer": {
        "максим": 3, "совершенств": 3, "велик": 2, "улучш": 2, "уже хорош": 3,
        "сильн сторон": 3, "превосход": 2, "отличн": 2, "довожу до": 3,
        "выжима": 3, "на максимум": 3, "идеальн": 2, "высшую пробу": 1,
    },
    "Positivity": {
        "позитив": 3, "оптимиз": 3, "энтузиазм": 3, "радост": 2, "весел": 2,
        "жизнелюб": 3, "надежд": 2, "верю в лучшее": 3, "воодушевл": 3,
        "поднимаю настроен": 3, "счастлив": 2, "радуюсь": 2, "хорошее настроен": 3,
    },
    "Relator": {
        "близк": 3, "глубок": 2, "отношен": 3, "доверит": 3, "друг": 3,
        "привязан": 3, "общени с друзьями": 3, "знаю лично": 3, "свои": 2,
        "сближа": 3, "искренн": 2, "настоящ": 2, "личн": 1,
    },
    "Responsibility": {
        "ответствен": 3, "обязательств": 3, "обязательн": 3, "беру ответств": 3,
        "честн": 2, "верн": 2, "лояльн": 2, "держ слово": 3, "сдерж": 2,
        "выполняю обещан": 3, "до конца": 1, "считаю": 1, "мое слово": 3,
    },
    "Restorative": {
        "ремонт": 3, "исправ": 3, "почин": 3, "восстанавл": 3, "чинить": 3,
        "слома": 3, "разбира": 2, "починю": 3, "приводи в порядок": 3,
        "решаю проблем": 3, "устран": 3,
    },
    "Self-Assurance": {
        "уверен": 3, "вер в себя": 3, "самоуверен": 3, "решительн": 2,
        "независ": 3, "управля": 2, "внутренн": 2, "принимаю решени": 2,
        "сам": 1, "комфортн": 1, "тревож": 2, "уверенност": 3, "свой пут": 2,
    },
    "Significance": {
        "значим": 3, "признан": 3, "важн": 2, "известн": 3, "влиятельн": 3,
        "признание": 3, "лидерств в отрасли": 2, "успешн": 1, "важную роль": 3,
        "хочу чтоб меня замечали": 3, "статус": 2, "репутац": 3,
    },
    "Strategic": {
        "стратег": 3, "альтернатив": 3, "модел": 2, "вариант": 2,
        "обход": 3, "маршрут": 3, "другой путь": 3, "разными способами": 3,
        "системн подход": 3, "выстраива": 2, "общую картину": 3, "гибкий план": 2,
    },
    "Woo": {
        "знакомств": 3, "нов люд": 3, "завоев": 3, "обща": 2, "перв": 1,
        "знакомлю": 3, "незнаком": 3, "покорить": 3, "подружит": 3,
        "с легкостью обща": 3, "вызываю интерес": 3, "новые знакомства": 3,
    },
}


def tokenize(text):
    """Лёгкая токенизация русского текста."""
    text = text.lower().replace("ё", "е")
    return re.findall(r"[а-яa-z]{3,}", text)


def score_theme_for_text(text, theme):
    """Взвешенный счёт совпадений ключевых слов темы в тексте."""
    text_l = " " + text.lower().replace("ё", "е") + " "
    total = 0.0
    hits = 0
    for kw, w in THEME_KEYWORDS.get(theme, {}).items():
        if kw in text_l:
            total += w
            hits += 1
    # бонус за несколько разных ключевых слов (не только одно)
    bonus = 1.0 + 0.35 * (hits - 1) if hits > 1 else 1.0
    return total * bonus


def build_score_matrix(statements):
    """Матрица [n_statements × 34 themes] семантических баллов."""
    themes = THEMES
    mat = np.zeros((len(statements), len(themes)))
    for i, text in enumerate(statements):
        for j, t in enumerate(themes):
            mat[i, j] = score_theme_for_text(text, t)
    return mat, themes


def assign_with_counts(statements, target_counts):
    """
    Назначение утверждений темам с ограничением по количеству.
    Используется Hungarian algorithm: каждая тема разворачивается в N «слотов».
    """
    n = len(statements)
    n_slots = sum(target_counts.values())
    if n_slots != n:
        # масштабируем цели под n
        scale = n / max(1, n_slots)
        target_counts = {t: max(1, int(round(c * scale))) for t, c in target_counts.items()}
        # подгоняем сумму
        while sum(target_counts.values()) > n:
            t = max(target_counts, key=lambda k: target_counts[k])
            target_counts[t] -= 1
        while sum(target_counts.values()) < n:
            t = max(GALLUP_ITEM_COUNTS, key=lambda k: GALLUP_ITEM_COUNTS[k] / target_counts[k])
            target_counts[t] += 1

    mat, themes = build_score_matrix(statements)

    # Расширяем матрицу: каждый слот темы = отдельная колонка
    slot_theme = []
    for t in themes:
        for _ in range(target_counts.get(t, 0)):
            slot_theme.append(t)
    slot_theme = slot_theme[:n]
    while len(slot_theme) < n:
        slot_theme.append(themes[0])

    cost = np.zeros((n, len(slot_theme)))
    for j, t in enumerate(slot_theme):
        tj = themes.index(t)
        cost[:, j] = -mat[:, tj]  # минимизируем отрицательную похожесть

    row_ind, col_ind = linear_sum_assignment(cost)
    assignment = {}
    for r, c in zip(row_ind, col_ind):
        assignment[r] = slot_theme[c]
    return assignment, themes


def load_all_statements():
    """Загружает все пары с текстами из xlsx."""
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
        pair_stmts[pair_num].append({"num": stmt_num, "text": text, "theme": theme})

    pairs = []
    for pn in sorted(pair_stmts.keys()):
        stmts = sorted(pair_stmts[pn], key=lambda x: x["num"])
        if len(stmts) != 2:
            continue
        pairs.append({
            "q": pn,
            "A": stmts[0]["theme"], "B": stmts[1]["theme"],
            "A_text": stmts[0]["text"], "B_text": stmts[1]["text"],
        })
    return pairs


def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_answers(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    answers = [None] * 200
    answer_col = None
    for col_idx in range(len(rows[0])):
        col_vals = [r[col_idx] for r in rows[1:] if r[col_idx] is not None]
        nums = []
        for v in col_vals:
            try:
                n = int(str(v).strip())
                if 1 <= n <= 5:
                    nums.append(n)
            except (ValueError, TypeError):
                pass
        if len(nums) >= 50:
            answer_col = col_idx
            break
    for row in rows[1:]:
        if row[0] is None:
            continue
        try:
            q = int(str(row[0]).strip())
        except (ValueError, TypeError):
            continue
        if not (1 <= q <= 200):
            continue
        ans = row[answer_col]
        if ans is None:
            continue
        try:
            n = int(str(ans).strip())
            if 1 <= n <= 5:
                answers[q - 1] = n
        except (ValueError, TypeError):
            continue
    return answers


def load_gt():
    df = pd.read_csv(DATASET_CSV, encoding="utf-8")
    result = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        if name.endswith(".pdf"):
            name = name[:-4]
        ranks = {}
        for theme in df.columns:
            if theme == "name":
                continue
            r = row[theme]
            if pd.notna(r) and int(r) != MISSING_RANK:
                ranks[normalize_theme(theme)] = int(r)
        result[name] = ranks
    return result


def score(answers, mapping, invert=True):
    scores = defaultdict(float)
    for entry in mapping:
        q_idx = entry["q"] - 1
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        v = (3 - ans) if invert else (ans - 3)
        scores[entry["A"]] += v
        scores[entry["B"]] -= v
    for t in THEMES:
        scores.setdefault(t, 0.0)
    return dict(scores)


def ranks_from_scores(scores):
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    return {t: i + 1 for i, (t, _) in enumerate(sorted_items)}


def evaluate(answers, mapping, gt):
    sc = score(answers, mapping)
    pred = ranks_from_scores(sc)
    common = sorted(set(pred) & set(gt))
    if len(common) < 5:
        return None
    p = [pred[t] for t in common]
    t = [gt[t] for t in common]
    rho, _ = spearmanr(p, t)
    pred5 = set(x for x, r in pred.items() if r <= 5)
    true5 = set(x for x, r in gt.items() if r <= 5)
    pred10 = set(x for x, r in pred.items() if r <= 10)
    true10 = set(x for x, r in gt.items() if r <= 10)
    pred15 = set(x for x, r in pred.items() if r <= 15)
    true15 = set(x for x, r in gt.items() if r <= 15)
    return {"rho": rho, "top5": len(pred5 & true5) / 5,
            "top10": len(pred10 & true10) / 10, "top15": len(pred15 & true15) / 15}


def theme_correlations(mapping, matched):
    """Эмпирическая корреляция по каждой теме."""
    theme_obs = defaultdict(list)
    for name, answers, g in matched:
        for p in mapping:
            q_idx = p["q"] - 1
            if q_idx >= len(answers) or answers[q_idx] is None:
                continue
            ans = answers[q_idx]
            signed = (3 - ans)
            if signed == 0:
                continue
            tA = 35 - g.get(p["A"], 17)
            tB = 35 - g.get(p["B"], 17)
            theme_obs[p["A"]].append((signed, tA))
            theme_obs[p["B"]].append((-signed, tB))
    out = {}
    for t in THEMES:
        obs = theme_obs.get(t, [])
        if len(obs) < 8:
            out[t] = 0.0
            continue
        rho, _ = spearmanr([o[0] for o in obs], [o[1] for o in obs])
        out[t] = rho
    return out


def main():
    print("=" * 78)
    print("ПЕРЕСБОРКА МАППИНГА по структуре Gallup (Table 1) + описаниям (Appendix A)")
    print("=" * 78)

    pairs = load_all_statements()
    gt = load_gt()
    print(f"[OK] {len(pairs)} пар (включая сломанные)")

    files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and not f.stem.startswith(("Gallup_200", "Gallup_Talent")):
            files[f.stem] = f
    matched = []
    for stem, path in files.items():
        gt_name = None
        for g in gt:
            if g == stem or g.startswith(stem + "-") or g.startswith(stem):
                gt_name = g
                break
        if gt_name is None:
            continue
        matched.append((stem, load_answers(path), gt[gt_name]))
    print(f"[OK] {len(matched)} людей с ground truth\n")

    def report(mapping, label):
        results = [evaluate(m[1], mapping, m[2]) for m in matched]
        results = [r for r in results if r]
        rho = np.mean([r["rho"] for r in results])
        t5 = np.mean([r["top5"] for r in results]) * 100
        t10 = np.mean([r["top10"] for r in results]) * 100
        t15 = np.mean([r["top15"] for r in results]) * 100
        print(f"  {label:<44} ρ={rho:+.3f}  top5={t5:>3.0f}%  top10={t10:>3.0f}%  top15={t15:>3.0f}%")
        return rho, t5, t10, t15

    # ------------------------------------------------------------------
    # ВАРИАНТ 0: текущий маппинг (baseline)
    # ------------------------------------------------------------------
    print("=" * 78)
    print("СРАВНЕНИЕ ВАРИАНТОВ")
    print("=" * 78)
    old_mapping = [p for p in pairs if p["A"] != p["B"]]
    report(old_mapping, "СТАРЫЙ маппинг (в проде)")

    # ------------------------------------------------------------------
    # ВАРИАНТ 1: чисто семантический (без ограничений по количеству)
    # ------------------------------------------------------------------
    print("\n--- Семантическое переназначение ---")
    statements = []
    index_map = []  # (pair_q, side)
    for p in pairs:
        statements.append(p["A_text"])
        index_map.append((p["q"], "A"))
        statements.append(p["B_text"])
        index_map.append((p["q"], "B"))

    mat, themes = build_score_matrix(statements)
    # Чистое назначение без ограничений по количеству:
    # равные квоты на каждую тему.
    uniform_targets = {t: max(1, len(statements) // len(THEMES)) for t in THEMES}
    sem_assignment, themes = assign_with_counts(statements, uniform_targets)
    semantic_raw = {}
    for r, key in enumerate(index_map):
        semantic_raw[key] = sem_assignment[r]

    # Пост-обработка конфликтов (одна тема на обе стороны пары)
    for p in pairs:
        ta = semantic_raw[(p["q"], "A")]
        tb = semantic_raw[(p["q"], "B")]
        if ta == tb:
            idx_b = index_map.index((p["q"], "B"))
            best_alt, best_score = None, -1e9
            for j, t in enumerate(themes):
                if t == ta:
                    continue
                if mat[idx_b, j] > best_score:
                    best_score = mat[idx_b, j]
                    best_alt = t
            semantic_raw[(p["q"], "B")] = best_alt

    semantic_mapping = []
    for p in pairs:
        semantic_mapping.append({
            "q": p["q"],
            "A": semantic_raw[(p["q"], "A")],
            "B": semantic_raw[(p["q"], "B")],
            "A_text": p["A_text"], "B_text": p["B_text"],
        })
    report(semantic_mapping, "Семантическое (keywords)")

    # ------------------------------------------------------------------
    # ВАРИАНТ 2: семантическое + ограничение по Table 1
    # ------------------------------------------------------------------
    print("\n--- Семантическое + ограничение по Gallup Table 1 ---")
    total_gallup = sum(GALLUP_ITEM_COUNTS.values())
    n_statements = len(statements)
    target = {t: max(1, round(GALLUP_ITEM_COUNTS[t] / total_gallup * n_statements))
              for t in THEMES}
    # подгонка суммы
    while sum(target.values()) > n_statements:
        t = max(target, key=lambda k: target[k] / GALLUP_ITEM_COUNTS[k])
        target[t] -= 1
    while sum(target.values()) < n_statements:
        t = max(GALLUP_ITEM_COUNTS, key=lambda k: GALLUP_ITEM_COUNTS[k] / target[k])
        target[t] += 1

    assignment, themes = assign_with_counts(statements, target)
    constrained = {}
    for (q, side), r in zip(index_map, range(len(statements))):
        constrained[(q, side)] = assignment[r]
    for p in pairs:
        ta = constrained[(p["q"], "A")]
        tb = constrained[(p["q"], "B")]
        if ta == tb:
            idx_b = index_map.index((p["q"], "B"))
            best_alt, best_score = None, -1e9
            for j, t in enumerate(themes):
                if t == ta:
                    continue
                if mat[idx_b, j] > best_score:
                    best_score = mat[idx_b, j]
                    best_alt = t
            constrained[(p["q"], "B")] = best_alt

    constrained_mapping = []
    for p in pairs:
        constrained_mapping.append({
            "q": p["q"],
            "A": constrained[(p["q"], "A")],
            "B": constrained[(p["q"], "B")],
            "A_text": p["A_text"], "B_text": p["B_text"],
        })
    report(constrained_mapping, "Семантическое + Table 1")

    # ------------------------------------------------------------------
    # ВАРИАНТ 3: гибрид — старый маппинг для «хороших» тем,
    #             семантический для плохих
    # ------------------------------------------------------------------
    print("\n--- Гибрид: семантический для тем со слабой корреляцией ---")
    old_corr = theme_correlations(old_mapping, matched)
    WEAK = -0.02  # порог "тема работает плохо"
    weak_themes = {t for t in THEMES if old_corr.get(t, 0) < WEAK}
    print(f"  Слабые темы ({len(weak_themes)}): {sorted(weak_themes)}")

    hybrid = []
    for p in pairs:
        a = constrained[(p["q"], "A")] if p["A"] in weak_themes else p["A"]
        b = constrained[(p["q"], "B")] if p["B"] in weak_themes else p["B"]
        if a == b:
            a = p["A"] if p["A"] != b else constrained[(p["q"], "A")]
            b = p["B"] if p["B"] != a else constrained[(p["q"], "B")]
        hybrid.append({"q": p["q"], "A": a, "B": b,
                       "A_text": p["A_text"], "B_text": p["B_text"]})
    report(hybrid, "Гибрид")

    # ------------------------------------------------------------------
    # ВАРИАНТ 4: гибрид со СВОИМИ keywords для слабых тем
    # ------------------------------------------------------------------
    print("\n--- Гибрид v2: семантический для слабых тем + Table 1 ---")
    hybrid2 = []
    for p in pairs:
        a = semantic_raw[(p["q"], "A")] if p["A"] in weak_themes else p["A"]
        b = semantic_raw[(p["q"], "B")] if p["B"] in weak_themes else p["B"]
        if a == b:
            b = semantic_raw[(p["q"], "B")] if semantic_raw[(p["q"], "B")] != a else p["B"]
        hybrid2.append({"q": p["q"], "A": a, "B": b,
                        "A_text": p["A_text"], "B_text": p["B_text"]})
    report(hybrid2, "Гибрид v2 (semantic для слабых)")

    # ------------------------------------------------------------------
    # Сравнение корреляций по темам: старый vs новый
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("КОРРЕЛЯЦИИ ПО ТЕМАМ: старый маппинг vs семантический+Table1")
    print("=" * 78)
    new_corr = theme_correlations(constrained_mapping, matched)
    print(f"{'Theme':<22}{'old ρ':>9}{'new ρ':>9}{'Δ':>9}")
    print("-" * 50)
    improved = 0
    for t in THEMES:
        d = new_corr.get(t, 0) - old_corr.get(t, 0)
        if d > 0.01:
            improved += 1
        print(f"{t:<22}{old_corr.get(t,0):>+9.3f}{new_corr.get(t,0):>+9.3f}{d:>+9.3f}")
    print(f"\nТем с улучшенной корреляцией: {improved} из 34")

    # Сохраняем лучший новый маппинг
    best_map = constrained_mapping
    out = PROJECT / "mapping_rebuilt.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(best_map, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Новый маппинг сохранён: {out}")


if __name__ == "__main__":
    main()
