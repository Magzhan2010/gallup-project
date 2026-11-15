"""
build_v3.py — сборка скоринга v3 и честная проверка точности.

    python build_v3.py            # LOO-оценка + запись web/data.js и web/data/mapping.json
    python build_v3.py --check    # только оценка, без записи

Источники (всё в репозитории):
    data/pairs_original.json   — 200 пар утверждений и их исходные темы
    data/labeled_people.json   — ответы + настоящий рейтинг Gallup (сюда добавлять новых людей)
    relabel_v3.py              — смысловая переразметка пар

Схема скоринга v3:
  1. Каждое утверждение даёт + теме, которую описывает, или − теме, противоположность которой
     описывает (relabel_v3.py). Пары без смысла для тем не дают баллов.
  2. Неипсативно (отчёт Gallup: <30% пунктов ипсативны): выбранная сторона получает
     интенсивность ответа, невыбранная — только штраф C_OTHER от неё.
  3. Вес пары = насколько ответы на неё согласуются с настоящими рейтингами (K_WEIGHT).
  4. Балл темы делится на сумму весов её утверждений (среднее, как у Gallup).
Все цифры точности считаются leave-one-out: веса учатся без проверяемого человека.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from relabel_v3 import RELABEL

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
C_OTHER = 0.5
K_WEIGHT = 1.0

PAIRS = json.load(open(ROOT / "data/pairs_original.json", encoding="utf-8"))
PEOPLE = json.load(open(ROOT / "data/labeled_people.json", encoding="utf-8"))["people"]
THEMES = sorted({p[s]["theme"] for p in PAIRS for s in ("left", "right")})
assert len(THEMES) == 34
ti = {t: i for i, t in enumerate(THEMES)}
key = {t.lower().replace("-", ""): t for t in THEMES}


def side(spec):
    """'woo' -> {Woo: 1}, '-woo' -> {Woo: -1}, None -> {}"""
    if not spec:
        return {}
    return {key[spec.lstrip("-")]: -1.0 if spec.startswith("-") else 1.0}


def build_sides():
    out = []
    for p in PAIRS:
        if p["id"] in RELABEL:
            l, r = RELABEL[p["id"]]
            out.append((side(l), side(r)))
        else:
            out.append(({p["left"]["theme"]: 1.0}, {p["right"]["theme"]: 1.0}))
    return out


SIDES = build_sides()
L = np.zeros((200, 34))
R = np.zeros((200, 34))
for q, (l, r) in enumerate(SIDES):
    for t, w in l.items():
        L[q, ti[t]] = w
    for t, w in r.items():
        R[q, ti[t]] = w

X = np.array([[0 if a is None else a - 3 for a in p["answers"]] for p in PEOPLE], float)
TRUE = [{t: i + 1 for i, t in enumerate(p["gallup_ranking"])} for p in PEOPLE]
Y = np.array([[35 - tr[t] for t in THEMES] for tr in TRUE], float)
YZ = (Y - Y.mean(1, keepdims=True)) / Y.std(1, keepdims=True)


def contrib(x):
    """200x34: вклад каждой пары в каждую тему для ответов x (−2..+2, + = правое)."""
    p = np.clip(x, 0, None)[:, None]
    m = np.clip(-x, 0, None)[:, None]
    return p * R - C_OTHER * p * L + m * L - C_OTHER * m * R


def pair_weights(idx):
    if not idx or K_WEIGHT == 0:
        return np.ones(200)
    agree = np.array([contrib(X[j]) @ YZ[j] for j in idx])  # people x 200
    t = agree.mean(0) / (agree.std(0) + 1e-9)
    return np.maximum(0, 1 + K_WEIGHT * np.tanh(t))


def score(x, w):
    s = (contrib(x) * w[:, None]).sum(0)
    denom = ((np.abs(L) + np.abs(R)) * w[:, None]).sum(0)
    return s / np.maximum(denom, 1e-9)


def metrics(s, tr):
    t = np.array([tr[th] for th in THEMES])
    pr = np.argsort(np.argsort(-s)) + 1
    top = lambda k: len(set(np.where(pr <= k)[0]) & set(np.where(t <= k)[0]))
    return spearmanr(-s, t)[0], top(5), top(10)


def loo():
    rows = []
    for i in range(len(PEOPLE)):
        w = pair_weights([j for j in range(len(PEOPLE)) if j != i])
        rows.append(metrics(score(X[i], w), TRUE[i]))
    return np.array(rows)


def main():
    M = loo()
    print(f"Людей: {len(PEOPLE)}   (оценка leave-one-out)")
    for p, (rho, t5, t10) in zip(PEOPLE, M):
        print(f"  {p['name']:12s} rho={rho:.2f}  top5={int(t5)}/5  top10={int(t10)}/10")
    rho, t5, t10 = M.mean(0)
    se = M[:, 0].std() / np.sqrt(len(M))
    print(f"\nИТОГО: rho={rho:.3f}±{se:.3f}  top5={t5:.2f}/5  top10={t10:.2f}/10")
    if "--check" in sys.argv:
        return

    w = pair_weights(list(range(len(PEOPLE))))
    questions = []
    for q, p in enumerate(PAIRS):
        l, r = SIDES[q]
        questions.append({
            "id": p["id"],
            "w": round(float(w[q]), 4),
            "left": {"text": p["left"]["text"], "themes": l},
            "right": {"text": p["right"]["text"], "themes": r},
        })
    cfg = {"version": 3, "cOther": C_OTHER}
    metrics_d = {"rho": round(rho, 3), "top5": round(t5, 2), "top10": round(t10, 2),
                 "n_people": len(PEOPLE), "method": "leave-one-out"}

    js_path = ROOT / "web/data.js"
    js = js_path.read_text(encoding="utf-8")
    js = re.sub(r"const QUESTIONS = \[.*?\n\];",
                "const QUESTIONS = " + json.dumps(questions, ensure_ascii=False, indent=2) + ";",
                js, count=1, flags=re.S)
    js = re.sub(r"// Параметры скоринга.*?\n\};",
                "// Параметры скоринга v3 (собрано build_v3.py)\nconst SCORING_CONFIG = "
                + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
                + "const MODEL_METRICS = " + json.dumps(metrics_d, ensure_ascii=False) + ";",
                js, count=1, flags=re.S)
    js = js.replace("// AUTO-GENERATED by build_web.py.", "// AUTO-GENERATED by build_web.py + build_v3.py.")
    js_path.write_text(js, encoding="utf-8")

    (ROOT / "web/data/mapping.json").write_text(json.dumps({
        "description": "Scoring v3: semantic relabel + non-ipsative scoring + per-pair weights (build_v3.py)",
        "scoring": cfg, "metrics_loo": metrics_d, "pairs": questions,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nЗаписано: web/data.js, web/data/mapping.json")


if __name__ == "__main__":
    main()
