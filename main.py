import pandas as pd
# Аспект 1
# Ответы всех 11 человек
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

# Превращаем в таблицу
df = pd.DataFrame(answers)

# Показываем первые 10 строк
print(df.head(199))  

# ============================================
# АСПЕКТ 2: Перевод ответов в баллы
# ============================================

# Функция: переводит ответ (1-5) в баллы (+2, +1, 0, -1, -2)
def answer_to_scores(answer):
    """
    Переводит ответ человека в баллы для пары утверждений.
    
    answer = 5  →  (+2, -2)  первое утверждение точно я
    answer = 4  →  (+1, -1)  первое ближе
    answer = 3  →  (0,  0)   нейтрально
    answer = 2  →  (-1, +1)  второе ближе
    answer = 1  →  (-2, +2)  второе утверждение точно я
    answer = None → (0, 0)   пропущенный вопрос = 0 баллов
    """
    if answer is None:
        return (0, 0)
    # Сдвигаем: 5→2, 4→1, 3→0, 2→-1, 1→-2
    shift = answer - 3
    return (shift, -shift)


# Пример: проверяем на ответе Александра на вопрос 0 (он ответил 5)
test_answer = answers["Alexandr"][0]  # = 5
score_first, score_second = answer_to_scores(test_answer)
print(f"Вопрос 0, ответ {test_answer}: первое = +{score_first}, второе = {score_second}")
# Должно вывести: первое = +2, второе = -2


# Переводим ВСЕ ответы ВСЕХ людей в баллы
# Результат: словарь {имя: список пар баллов для каждого вопроса}
scores = {}
for name, person_answers in answers.items():
    person_scores = []
    for ans in person_answers:
        person_scores.append(answer_to_scores(ans))
    scores[name] = person_scores

# Показываем первые 5 вопросов для Александра
print("\nБаллы Александра (первые 5 вопросов):")
for i in range(5):
    s1, s2 = scores["Alexandr"][i]
    ans = answers["Alexandr"][i]
    print(f"  Вопрос {i}: ответ={ans} → первое={s1:+d}, второе={s2:+d}")


# ============================================
# АСПЕКТ 3: Автоматическая привязка через Ridge-регрессию
# ============================================

import numpy as np
from sklearn.linear_model import Ridge

# --- 1. РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ GALLUP (ранжировки) ---

# Ранжировка каждого человека: первое имя = самый сильный талант (ранг 1)
gallup_rankings = {
    "Togzhan": [
        "Empathy","Developer","Connectedness","Belief","Achiever","Context","Relator",
        "Responsibility","Individualization","Arranger","Positivity","Intellection",
        "Learner","Maximizer","Deliberative","Discipline","Harmony","Strategic","Focus",
        "Input","Adaptability","Consistency","Self-Assurance","Ideation","Analytical",
        "Restorative","Communication","Activator","Significance","Futuristic","Includer",
        "Woo","Competition","Command"
    ],
    "Ardak": [
        "Communication","Strategic","Responsibility","Analytical","Focus","Restorative",
        "Significance","Woo","Relator","Arranger","Belief","Futuristic","Ideation",
        "Consistency","Individualization","Positivity","Deliberative","Activator",
        "Includer","Learner","Harmony","Context","Discipline","Connectedness","Empathy",
        "Achiever","Input","Maximizer","Developer","Self-Assurance","Competition",
        "Command","Intellection","Adaptability"
    ],
    "Aymatay": [
        "Communication","Consistency","Woo","Adaptability","Positivity","Achiever",
        "Harmony","Responsibility","Restorative","Focus","Discipline","Strategic",
        "Relator","Significance","Learner","Competition","Deliberative","Input",
        "Self-Assurance","Includer","Futuristic","Developer","Activator","Arranger",
        "Analytical","Individualization","Command","Maximizer","Context","Empathy",
        "Belief","Ideation","Connectedness","Intellection"
    ],
    "Madina": [
        "Consistency","Communication","Responsibility","Woo","Analytical","Includer",
        "Discipline","Achiever","Harmony","Deliberative","Positivity","Empathy",
        "Self-Assurance","Focus","Belief","Developer","Restorative","Activator",
        "Maximizer","Context","Adaptability","Learner","Futuristic","Intellection",
        "Input","Command","Relator","Significance","Competition","Strategic",
        "Connectedness","Arranger","Ideation","Individualization"
    ],
    "Alexandr": [
        "Strategic","Analytical","Learner","Focus","Individualization","Communication",
        "Ideation","Arranger","Restorative","Responsibility","Achiever","Context",
        "Deliberative","Discipline","Self-Assurance","Intellection","Includer","Futuristic",
        "Consistency","Command","Input","Woo","Relator","Connectedness","Harmony",
        "Competition","Maximizer","Activator","Significance","Belief","Adaptability",
        "Empathy","Developer","Positivity"
    ],
    "Bagzhan": [
        "Competition","Strategic","Woo","Achiever","Communication","Focus","Responsibility",
        "Learner","Positivity","Analytical","Significance","Adaptability","Includer",
        "Futuristic","Harmony","Discipline","Restorative","Consistency","Context","Input",
        "Self-Assurance","Intellection","Relator","Belief","Empathy","Developer","Activator",
        "Individualization","Deliberative","Ideation","Command","Connectedness","Arranger","Maximizer"
    ],
    "Kassym": [
        "Responsibility","Arranger","Activator","Achiever","Belief","Maximizer",
        "Connectedness","Woo","Communication","Focus","Command","Individualization",
        "Discipline","Significance","Learner","Competition","Context","Self-Assurance",
        "Positivity","Ideation","Analytical","Input","Intellection","Strategic",
        "Restorative","Futuristic","Developer","Relator","Harmony","Deliberative",
        "Includer","Empathy","Adaptability","Consistency"
    ],
    "Mansur": [
        "Responsibility","Relator","Communication","Woo","Harmony","Empathy","Positivity",
        "Learner","Belief","Developer","Futuristic","Maximizer","Command","Context",
        "Deliberative","Adaptability","Includer","Analytical","Restorative","Focus",
        "Self-Assurance","Significance","Arranger","Activator","Strategic","Consistency",
        "Individualization","Input","Competition","Discipline","Ideation","Connectedness",
        "Intellection","Achiever"
    ],
    "Meyirzhan": [
        "Competition","Harmony","Woo","Adaptability","Activator","Positivity","Input",
        "Significance","Intellection","Communication","Connectedness","Maximizer","Context",
        "Self-Assurance","Focus","Empathy","Individualization","Consistency","Deliberative",
        "Ideation","Command","Developer","Arranger","Restorative","Relator","Belief",
        "Includer","Achiever","Responsibility","Discipline","Learner","Futuristic",
        "Strategic","Analytical"
    ],
    "Nurbibi": [
        "Includer","Maximizer","Adaptability","Harmony","Empathy","Relator","Connectedness",
        "Competition","Communication","Input","Analytical","Context","Discipline",
        "Self-Assurance","Activator","Futuristic","Individualization","Achiever",
        "Significance","Positivity","Command","Woo","Strategic","Responsibility","Learner",
        "Belief","Focus","Ideation","Developer","Consistency","Deliberative","Arranger",
        "Intellection","Restorative"
    ],
    "Yerman": [
        "Woo","Communication","Strategic","Individualization","Analytical","Significance",
        "Focus","Restorative","Command","Achiever","Developer","Ideation","Consistency",
        "Empathy","Positivity","Responsibility","Arranger","Futuristic","Self-Assurance",
        "Competition","Connectedness","Activator","Discipline","Belief","Input","Includer",
        "Relator","Harmony","Adaptability","Intellection","Maximizer","Context",
        "Deliberative","Learner"
    ],
}

# Все 34 таланта (по алфавиту, чтобы порядок был постоянным)
all_talents = sorted(set(t for ranking in gallup_rankings.values() for t in ranking))
print(f"Всего талантов: {len(all_talents)}")
print(f"Таланты: {all_talents}")

# ============================================
# АСПЕКТ 3 (продолжение): Обучение Ridge-регрессии
# ============================================

# --- 2. ПРЕВРАЩАЕМ РАНЖИРОВКИ В БАЛЛЫ ---

# Ранг 1 = самый сильный талант = 34 балла
# Ранг 34 = самый слабый = 1 балл
# Формула: балл = 35 - ранг

def ranking_to_scores(ranking, all_talents):
    """
    Превращает ранжировку (список талантов по порядку) в словарь баллов.
    Талант на 1-м месте получает 34 балла, на 34-м месте — 1 балл.
    """
    scores = {}
    for rank, talent in enumerate(ranking, start=1):
        scores[talent] = 35 - rank  # ранг 1 → 34 балла, ранг 34 → 1 балл
    return scores

# Создаём таблицу: строки = люди, столбцы = 34 таланта, значения = баллы
import numpy as np

names = list(gallup_rankings.keys())  # список имён
Y = []  # матрица баллов (11 человек × 34 таланта)

for name in names:
    talent_scores = ranking_to_scores(gallup_rankings[name], all_talents)
    row = [talent_scores[t] for t in all_talents]
    Y.append(row)

Y = np.array(Y)

print(f"Матрица Y: {Y.shape[0]} человек × {Y.shape[1]} талантов")
print(f"Пример (Александр, первые 5 талантов):")
for i in range(5):
    print(f"  {all_talents[i]}: {Y[names.index('Alexandr')][i]} баллов")


# --- 3. СОЗДАЁМ МАТРИЦУ ОТВЕТОВ (X) ---

# X: строки = люди, столбцы = 200 ответов
X = []
for name in names:
    person_answers = answers[name]
    # Превращаем None в 3 (нейтрально) для ML
    clean_answers = [3 if a is None else a for a in person_answers]
    X.append(clean_answers)

X = np.array(X)

print(f"\nМатрица X: {X.shape[0]} человек × {X.shape[1]} вопросов")


# --- 4. ОБУЧАЕМ RIDGE-РЕГРЕССИЮ ---

model = Ridge(alpha=10.0)  # alpha = сила регуляризации
model.fit(X, Y)  # обучаем: ответы → баллы талантов

print(f"\nМодель обучена!")
print(f"Размер весов: {model.coef_.shape}")  # должно быть (34, 200)
print(f"Веса — это 34 таланта × 200 вопросов = {34 * 200} чисел")