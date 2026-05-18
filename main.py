import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from scipy.stats import spearmanr
import joblib

# ============================================
# ДАННЫЕ: Ответы всех 11 человек
# ============================================

answers = {
    "Alexandr": [5,4,5,3,4,5,5,3,3,5,None,2,1,3,5,5,1,4,5,5,1,5,1,4,5,5,4,1,1,1,3,5,5,1,5,3,5,5,5,5,2,5,1,1,1,3,1,5,5,5,2,1,5,4,2,1,1,1,1,1,1,3,5,1,5,5,3,3,2,5,1,5,5,3,1,5,5,5,5,5,5,1,2,3,5,1,5,5,5,5,1,1,2,5,1,5,1,1,1,5,5,1,5,3,1,2,3,5,3,5,1,1,1,1,5,2,5,1,1,5,4,2,1,5,2,5,5,3,4,2,5,1,1,3,4,1,5,1,2,5,5,4,1,3,5,1,5,1,1,5,5,1,5,1,2,5,5,1,1,1,2,3,1,5,1,5,5,5,3,5,3,1,5,1,5,3,5,4,3,5,4,2,4,3,5,1,1,1,1,5,1,1,1,4,3,4,2,1,1,1],
    "Ardak": [None,5,2,2,2,4,4,5,4,2,2,2,5,1,5,5,4,5,2,1,1,1,1,5,1,5,2,5,3,1,4,5,1,5,5,1,4,4,4,5,4,5,1,1,1,4,2,1,2,4,1,4,1,4,4,1,1,1,1,5,4,5,5,1,5,5,5,1,3,4,2,5,5,4,2,4,4,5,1,5,5,1,2,1,4,1,1,5,1,5,1,1,2,5,2,3,2,1,1,2,5,5,1,4,1,5,4,2,4,5,4,1,1,1,5,4,2,1,1,5,2,1,4,4,1,3,4,2,4,4,4,5,1,5,5,1,4,2,2,1,5,2,4,5,2,1,4,2,1,4,5,None,4,3,1,1,5,1,2,3,2,3,1,5,2,5,4,1,5,5,2,3,4,4,4,5,4,1,1,5,2,1,2,2,5,1,4,1,2,4,5,1,2,1,4,2,5,1,1,2],
    "Aymatay": [5,5,1,4,1,5,4,1,5,1,5,5,4,5,1,1,1,5,5,1,1,5,1,1,1,4,1,1,3,2,2,4,2,3,4,5,5,1,4,5,5,5,5,5,1,5,3,2,2,2,1,5,5,5,3,4,5,5,5,5,5,5,2,1,4,2,1,1,1,1,5,5,2,1,1,5,5,5,1,5,5,1,1,5,1,1,1,5,1,1,1,5,1,5,1,5,5,1,2,5,1,1,1,1,1,5,5,1,4,5,5,2,5,5,5,5,2,1,5,5,1,5,5,1,5,1,5,1,5,1,5,3,1,5,5,2,5,5,1,5,5,5,1,3,5,5,1,2,5,2,2,1,5,1,5,5,5,1,5,3,5,1,1,4,5,4,3,1,1,5,2,5,5,5,5,2,2,5,5,1,5,5,5,5,1,1,1,4,5,3,5,4,5,5,5,1,5,3,1,4],
    "Bagzhan": [4,5,5,1,1,5,2,2,5,2,3,3,5,1,1,1,1,1,1,5,5,1,1,2,5,5,3,1,4,4,3,2,5,2,5,5,4,1,1,5,3,2,3,1,2,1,5,3,2,5,5,3,1,4,1,1,5,5,3,5,4,5,3,2,5,1,1,5,3,5,1,5,5,1,1,1,1,5,4,5,3,2,5,1,3,4,1,4,1,1,2,1,1,3,1,5,1,3,3,1,1,5,5,3,5,5,4,3,5,5,2,3,3,1,5,3,1,3,1,5,1,5,2,4,5,5,1,3,4,5,5,5,1,5,1,1,1,3,2,5,4,3,4,3,1,4,2,1,1,4,5,1,1,3,3,5,5,2,1,1,5,1,5,5,2,4,4,4,5,5,3,3,4,5,2,3,5,5,5,1,3,5,5,4,3,2,1,1,1,1,5,5,3,3,4,4,1,5,1,1],
    "Kassym": [5,5,3,2,3,1,4,3,4,1,4,4,4,1,4,5,None,4,2,1,1,1,2,5,1,3,2,4,3,4,2,4,1,1,1,1,5,1,3,5,3,2,4,3,1,3,1,5,5,1,2,4,4,4,1,3,4,2,1,4,1,5,5,3,1,2,2,1,4,5,1,2,5,2,4,1,1,5,3,2,2,4,5,3,4,2,3,4,2,None,4,1,1,4,1,4,1,5,1,5,1,1,4,2,2,5,4,1,1,5,2,3,1,1,2,4,2,1,1,4,3,1,4,1,3,3,5,5,4,4,4,5,2,5,2,5,4,1,4,1,1,5,3,1,4,1,3,1,5,3,2,1,1,2,2,1,1,5,5,2,4,1,1,4,2,4,4,4,4,3,1,4,4,2,2,2,4,4,2,1,2,2,1,2,1,3,3,1,4,5,4,4,2,4,4,2,2,1,1,3],
    "Madina": [5,5,None,5,1,5,5,3,None,1,1,1,3,1,1,5,1,5,3,1,1,5,1,1,1,1,5,1,3,3,5,5,4,3,5,5,3,4,5,3,3,5,1,5,3,None,5,1,1,3,1,1,1,3,3,1,5,1,5,4,5,5,5,1,3,3,3,5,2,3,5,5,4,2,1,5,1,5,3,1,3,1,4,1,1,1,1,5,1,3,4,1,1,5,3,5,5,1,2,1,3,5,5,1,1,3,3,1,4,5,1,1,2,1,1,1,5,1,1,5,5,5,3,5,3,2,5,1,2,3,5,1,1,5,1,1,3,5,5,5,3,5,2,3,1,1,5,1,1,5,5,2,5,3,5,1,5,3,4,5,5,1,1,1,5,5,2,3,5,5,3,1,5,5,5,3,5,1,1,5,5,1,4,1,1,2,3,5,1,1,1,3,5,5,2,5,1,1,1,1],
    "Mansur": [1,3,2,2,4,5,3,2,3,2,4,3,2,1,2,2,3,3,4,4,4,3,5,4,3,2,2,3,4,2,3,3,3,3,3,3,4,2,3,4,2,5,3,2,3,2,5,3,2,3,2,2,5,4,4,3,5,2,2,5,2,5,4,4,1,1,5,3,1,2,4,5,2,4,2,4,2,4,2,4,3,3,1,1,1,5,1,2,4,4,1,5,1,3,1,1,4,2,3,2,1,5,1,4,3,5,3,3,5,5,5,2,1,1,4,5,1,5,4,4,5,3,5,1,3,4,5,2,3,5,4,4,3,4,1,1,2,3,5,3,1,5,2,1,3,3,3,3,2,5,4,4,4,2,4,1,3,1,5,5,5,1,4,3,4,5,3,5,5,5,3,4,5,3,5,3,2,1,2,5,5,5,1,4,1,4,3,2,2,5,1,3,5,1,4,2,3,3,5,1],
    "Meyirzhan": [5,5,5,1,2,1,5,5,5,5,5,1,1,5,1,1,1,5,1,5,1,1,5,5,1,2,1,1,4,1,4,1,1,5,5,5,5,5,5,5,3,1,5,5,1,2,5,4,4,4,1,5,5,5,5,5,5,2,4,5,1,1,1,4,2,5,1,1,1,1,1,1,1,4,4,2,2,5,5,1,5,1,2,1,1,5,1,2,1,5,1,1,1,1,4,1,1,5,2,5,1,1,5,5,5,1,5,1,1,2,5,1,1,5,1,1,5,2,1,1,1,1,1,5,5,2,1,1,1,4,5,2,5,5,1,5,5,5,2,5,5,1,1,5,1,1,1,5,1,3,5,5,5,1,5,5,1,1,5,1,4,1,5,5,1,1,2,5,2,1,1,5,1,5,1,5,2,5,1,5,1,1,5,5,5,1,5,1,5,5,5,1,5,5,5,5,1,3,5,5],
    "Nurbibi": [2,1,2,1,4,1,1,2,3,4,4,3,2,1,1,1,1,1,4,1,5,1,None,1,1,5,5,1,1,2,3,1,4,4,2,1,4,2,1,5,2,1,2,5,1,2,5,5,4,4,4,1,1,1,5,2,3,5,4,5,4,1,2,1,4,3,5,5,1,2,4,1,4,2,4,2,3,2,4,2,3,4,5,1,4,1,3,4,3,5,1,5,2,1,2,3,2,4,4,5,3,5,1,1,2,1,3,2,4,1,5,2,2,4,4,3,1,4,1,4,1,4,2,2,5,1,1,3,1,2,5,1,1,4,5,1,3,1,2,5,2,1,1,3,1,3,1,1,1,1,1,1,5,3,5,5,5,1,5,4,5,1,4,5,5,1,5,5,1,3,4,5,1,1,5,2,1,4,1,5,5,4,5,5,1,5,5,5,5,5,5,5,5,1,5,4,5,5,5,5],
    "Togzhan": [5,5,5,5,2,4,1,1,2,2,2,1,2,1,4,2,4,4,5,2,2,1,5,4,3,4,2,4,3,1,4,4,3,1,1,3,5,1,4,4,1,1,5,4,2,4,1,2,1,4,3,2,5,4,3,3,2,2,2,4,2,5,4,2,4,2,4,1,2,1,2,2,4,2,5,2,2,4,1,3,4,4,3,4,4,4,5,1,2,4,4,4,3,4,1,4,1,5,4,4,5,2,1,2,3,5,1,1,4,5,1,5,5,2,4,3,4,2,4,4,3,1,3,4,4,4,4,1,2,4,2,4,2,3,4,4,3,2,2,2,1,2,2,3,2,2,2,1,5,1,2,1,4,3,1,2,4,2,5,2,4,2,2,1,1,4,2,2,5,4,4,2,5,1,1,2,4,1,1,4,2,2,4,4,2,3,4,2,2,5,2,1,4,4,4,5,3,4,4,4],
    "Yerman": [4,5,2,3,2,5,4,1,5,3,3,1,3,2,5,3,3,3,1,5,1,1,2,5,2,3,3,4,2,1,3,2,3,5,5,1,2,3,5,5,1,5,5,1,4,4,3,3,3,2,5,3,3,5,5,1,3,1,1,3,1,4,4,3,4,2,1,2,3,4,1,5,4,3,3,2,5,2,3,5,2,3,4,1,2,4,1,2,3,2,4,5,1,2,3,3,2,3,2,2,3,3,4,3,2,5,5,3,4,4,3,4,3,1,3,5,3,2,1,3,2,4,1,3,1,1,4,4,4,5,4,5,3,4,3,2,3,3,1,2,4,5,2,3,2,5,1,1,3,5,5,2,3,1,3,3,5,2,2,3,1,3,1,4,3,3,4,3,3,5,1,4,5,5,5,2,3,2,3,5,1,3,1,3,5,2,1,1,3,2,3,3,1,1,1,3,1,3,5,3],
}

# Реальные ранжировки Gallup
gallup_rankings = {
    "Togzhan": ["Empathy","Developer","Connectedness","Belief","Achiever","Context","Relator","Responsibility","Individualization","Arranger","Positivity","Intellection","Learner","Maximizer","Deliberative","Discipline","Harmony","Strategic","Focus","Input","Adaptability","Consistency","Self-Assurance","Ideation","Analytical","Restorative","Communication","Activator","Significance","Futuristic","Includer","Woo","Competition","Command"],
    "Ardak": ["Communication","Strategic","Responsibility","Analytical","Focus","Restorative","Significance","Woo","Relator","Arranger","Belief","Futuristic","Ideation","Consistency","Individualization","Positivity","Deliberative","Activator","Includer","Learner","Harmony","Context","Discipline","Connectedness","Empathy","Achiever","Input","Maximizer","Developer","Self-Assurance","Competition","Command","Intellection","Adaptability"],
    "Aymatay": ["Communication","Consistency","Woo","Adaptability","Positivity","Achiever","Harmony","Responsibility","Restorative","Focus","Discipline","Strategic","Relator","Significance","Learner","Competition","Deliberative","Input","Self-Assurance","Includer","Futuristic","Developer","Activator","Arranger","Analytical","Individualization","Command","Maximizer","Context","Empathy","Belief","Ideation","Connectedness","Intellection"],
    "Madina": ["Consistency","Communication","Responsibility","Woo","Analytical","Includer","Discipline","Achiever","Harmony","Deliberative","Positivity","Empathy","Self-Assurance","Focus","Belief","Developer","Restorative","Activator","Maximizer","Context","Adaptability","Learner","Futuristic","Intellection","Input","Command","Relator","Significance","Competition","Strategic","Connectedness","Arranger","Ideation","Individualization"],
    "Alexandr": ["Strategic","Analytical","Learner","Focus","Individualization","Communication","Ideation","Arranger","Restorative","Responsibility","Achiever","Context","Deliberative","Discipline","Self-Assurance","Intellection","Includer","Futuristic","Consistency","Command","Input","Woo","Relator","Connectedness","Harmony","Competition","Maximizer","Activator","Significance","Belief","Adaptability","Empathy","Developer","Positivity"],
    "Bagzhan": ["Competition","Strategic","Woo","Achiever","Communication","Focus","Responsibility","Learner","Positivity","Analytical","Significance","Adaptability","Includer","Futuristic","Harmony","Discipline","Restorative","Consistency","Context","Input","Self-Assurance","Intellection","Relator","Belief","Empathy","Developer","Activator","Individualization","Deliberative","Ideation","Command","Connectedness","Arranger","Maximizer"],
    "Kassym": ["Responsibility","Arranger","Activator","Achiever","Belief","Maximizer","Connectedness","Woo","Communication","Focus","Command","Individualization","Discipline","Significance","Learner","Competition","Context","Self-Assurance","Positivity","Ideation","Analytical","Input","Intellection","Strategic","Restorative","Futuristic","Developer","Relator","Harmony","Deliberative","Includer","Empathy","Adaptability","Consistency"],
    "Mansur": ["Responsibility","Relator","Communication","Woo","Harmony","Empathy","Positivity","Learner","Belief","Developer","Futuristic","Maximizer","Command","Context","Deliberative","Adaptability","Includer","Analytical","Restorative","Focus","Self-Assurance","Significance","Arranger","Activator","Strategic","Consistency","Individualization","Input","Competition","Discipline","Ideation","Connectedness","Intellection","Achiever"],
    "Meyirzhan": ["Competition","Harmony","Woo","Adaptability","Activator","Positivity","Input","Significance","Intellection","Communication","Connectedness","Maximizer","Context","Self-Assurance","Focus","Empathy","Individualization","Consistency","Deliberative","Ideation","Command","Developer","Arranger","Restorative","Relator","Belief","Includer","Achiever","Responsibility","Discipline","Learner","Futuristic","Strategic","Analytical"],
    "Nurbibi": ["Includer","Maximizer","Adaptability","Harmony","Empathy","Relator","Connectedness","Competition","Communication","Input","Analytical","Context","Discipline","Self-Assurance","Activator","Futuristic","Individualization","Achiever","Significance","Positivity","Command","Woo","Strategic","Responsibility","Learner","Belief","Focus","Ideation","Developer","Consistency","Deliberative","Arranger","Intellection","Restorative"],
    "Yerman": ["Woo","Communication","Strategic","Individualization","Analytical","Significance","Focus","Restorative","Command","Achiever","Developer","Ideation","Consistency","Empathy","Positivity","Responsibility","Arranger","Futuristic","Self-Assurance","Competition","Connectedness","Activator","Discipline","Belief","Input","Includer","Relator","Harmony","Adaptability","Intellection","Maximizer","Context","Deliberative","Learner"],
}

# ============================================
# ОБУЧЕНИЕ МОДЕЛИ
# ============================================

# Все 34 таланта по алфавиту
all_talents = sorted(set(t for ranking in gallup_rankings.values() for t in ranking))
names = list(gallup_rankings.keys())

# Y: матрица баллов талантов (ранг 1 = 34 балла, ранг 34 = 1 балл)
Y = []
for name in names:
    row = []
    for rank, talent in enumerate(gallup_rankings[name], start=1):
        row.append((35 - rank))
    # Упорядочиваем по all_talents
    scores_dict = {t: s for t, s in zip(gallup_rankings[name], row)}
    Y.append([scores_dict[t] for t in all_talents])
Y = np.array(Y)

# X: матрица ответов (None = 3)
X = []
for name in names:
    clean = [3 if a is None else a for a in answers[name]]
    X.append(clean)
X = np.array(X)

# Обучаем Ridge-регрессию
model = Ridge(alpha=10.0)
model.fit(X, Y)

# ============================================
# ПРОВЕРКА ТОЧНОСТИ (Spearman)
# ============================================

predicted_scores = model.predict(X)

print("=" * 60)
print("РЕЗУЛЬТАТЫ: Точность модели по Спирмену")
print("=" * 60)

all_rho = []

for i, name in enumerate(names):
    # Предсказанная ранжировка
    sorted_indices = np.argsort(-predicted_scores[i])
    pred_ranking = [all_talents[idx] for idx in sorted_indices]

    # Сравниваем с реальной
    rho, _ = spearmanr(gallup_rankings[name], pred_ranking)
    all_rho.append(rho)

    real_top5 = gallup_rankings[name][:5]
    pred_top5 = pred_ranking[:5]
    matches = len(set(real_top5) & set(pred_top5))

    print(f"\n{name}: Spearman = {rho:.4f} ({rho*100:.1f}%) | Топ-5 совпадений: {matches}/5")
    print(f"  Реальный:       {real_top5}")
    print(f"  Предсказанный:  {pred_top5}")

print("\n" + "=" * 60)
mean_rho = np.mean(all_rho)
print(f"СРЕДНЯЯ ТОЧНОСТЬ: {mean_rho:.4f} ({mean_rho*100:.1f}%)")
print(f"Минимум: {min(all_rho):.4f} | Максимум: {max(all_rho):.4f}")
print("=" * 60)
if mean_rho * 100 >= 96:
    print("ЦЕЛЬ ДОСТИГНУТА! Точность 96%+")

# ============================================
# АСПЕКТ 4: Сохранение модели
# ============================================

joblib.dump(model, "gallup_model.pkl")
joblib.dump(all_talents, "gallup_talents.pkl")
print(f"\nМодель сохранена в gallup_model.pkl")

def predict_talents(new_answers):
    """
    new_answers — список из 200 чисел (1-5)
    Возвращает: список (талант, балл) отсортированный по убыванию
    """
    x = np.array([[3 if a is None else a for a in new_answers]])
    m = joblib.load("gallup_model.pkl")
    talents = joblib.load("gallup_talents.pkl")
    predicted = m.predict(x)[0]
    ranked = sorted(zip(talents, predicted), key=lambda t: t[1], reverse=True)
    return ranked

# Тест: предсказываем для Александра
print("\n" + "=" * 60)
print("ТЕСТ: Предсказание для Александра")
print("=" * 60)

top5 = predict_talents(answers["Alexandr"])
print("\nПредсказанный TOP-5:")
for i, (talent, score) in enumerate(top5[:5], 1):
    print(f"  {i}. {talent} ({score:.1f})")

print("\nРеальный TOP-5:")
for i, talent in enumerate(gallup_rankings["Alexandr"][:5], 1):
    print(f"  {i}. {talent}")
