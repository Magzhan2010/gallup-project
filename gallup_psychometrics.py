"""
gallup_psychometrics.py
========================
Психометрические константы, извлечённые из официального технического отчёта
Gallup "The Clifton StrengthsFinder 2.0 Technical Report" (2014).

Источник: C:\\Users\\User\\Downloads\\Gallup Report.pdf
  - Table 1: Number of Statements Associated With Each Theme
  - Table 2: Estimates of Internal Consistency Reliabilities (Cronbach's alpha)
  - Table 3: Test-Retest Reliability Estimates
  - Table 9: The Four Domains of Leadership Strengths

Ключевые цитаты из отчёта (методология):
  "A proprietary formula assigns a value to each response category. Values for items
   in the theme are aggregated to derive a theme score. The calculation of scores is
   based on the MEAN of the intensity of self-description."

  "Absolute scores are used to rank the themes, with percentiles against the database
   norms and THEME RELIABILITIES used as subsidiary ranking factors."

  "Some statements are linked to more than one theme... the respondent's score is
   counted multiple times, once for each theme."

  "for those item pairs for which both statements are attached to themes, the selection
   of one statement assigns points to the themes aligned with both statements"
   (то есть ipsative-пары не дают отрицательный вклад второй теме, а 0)
"""

# ============================================================================
# TABLE 1 — количество утверждений на каждую тему (оригинальный Gallup)
# ============================================================================

GALLUP_ITEM_COUNTS = {
    "Achiever": 6, "Activator": 7, "Adaptability": 8, "Analytical": 11,
    "Arranger": 13, "Belief": 11, "Command": 9, "Communication": 9,
    "Competition": 7, "Connectedness": 8, "Consistency": 8, "Context": 4,
    "Deliberative": 8, "Developer": 10, "Discipline": 14, "Empathy": 6,
    "Focus": 12, "Futuristic": 8, "Harmony": 5, "Ideation": 7,
    "Includer": 7, "Individualization": 6, "Input": 5, "Intellection": 10,
    "Learner": 8, "Maximizer": 7, "Positivity": 12, "Relator": 8,
    "Responsibility": 11, "Restorative": 6, "Self-Assurance": 13,
    "Significance": 12, "Strategic": 4, "Woo": 9,
}

# ============================================================================
# TABLE 2 — Cronbach's alpha (internal consistency)
# sample1 n=46,902 | sample2 n=2,219 | sample3 n=250,000
# ============================================================================

ALPHA_SAMPLE1 = {
    "Achiever": 0.66, "Activator": 0.62, "Adaptability": 0.71, "Analytical": 0.72,
    "Arranger": 0.64, "Belief": 0.60, "Command": 0.69, "Communication": 0.73,
    "Competition": 0.73, "Connectedness": 0.65, "Consistency": 0.65, "Context": 0.61,
    "Deliberative": 0.73, "Developer": 0.65, "Discipline": 0.78, "Empathy": 0.61,
    "Focus": 0.71, "Futuristic": 0.73, "Harmony": 0.68, "Ideation": 0.71,
    "Includer": 0.61, "Individualization": 0.56, "Input": 0.52, "Intellection": 0.70,
    "Learner": 0.75, "Maximizer": 0.72, "Positivity": 0.78, "Relator": 0.54,
    "Responsibility": 0.66, "Restorative": 0.70, "Self-Assurance": 0.68,
    "Significance": 0.70, "Strategic": 0.69, "Woo": 0.79,
}

ALPHA_SAMPLE3 = {
    "Achiever": 0.66, "Activator": 0.59, "Adaptability": 0.70, "Analytical": 0.72,
    "Arranger": 0.62, "Belief": 0.59, "Command": 0.67, "Communication": 0.71,
    "Competition": 0.70, "Connectedness": 0.62, "Consistency": 0.63, "Context": 0.58,
    "Deliberative": 0.71, "Developer": 0.65, "Discipline": 0.77, "Empathy": 0.60,
    "Focus": 0.68, "Futuristic": 0.69, "Harmony": 0.65, "Ideation": 0.68,
    "Includer": 0.59, "Individualization": 0.53, "Input": 0.52, "Intellection": 0.68,
    "Learner": 0.74, "Maximizer": 0.66, "Positivity": 0.76, "Relator": 0.52,
    "Responsibility": 0.65, "Restorative": 0.67, "Self-Assurance": 0.64,
    "Significance": 0.68, "Strategic": 0.65, "Woo": 0.78,
}

# ============================================================================
# TABLE 3 — Test-Retest reliability (Month 1 / Month 3 / Month 6)
# Самый релевантный показатель: насколько СТАБИЛЕН ранг темы во времени.
# ============================================================================

TEST_RETEST_M1 = {
    "Achiever": 0.66, "Activator": 0.69, "Adaptability": 0.69, "Analytical": 0.77,
    "Arranger": 0.53, "Belief": 0.66, "Command": 0.61, "Communication": 0.69,
    "Competition": 0.73, "Connectedness": 0.70, "Consistency": 0.62, "Context": 0.70,
    "Deliberative": 0.79, "Developer": 0.67, "Discipline": 0.81, "Empathy": 0.73,
    "Focus": 0.72, "Futuristic": 0.66, "Harmony": 0.64, "Ideation": 0.75,
    "Includer": 0.69, "Individualization": 0.60, "Input": 0.79, "Intellection": 0.80,
    "Learner": 0.80, "Maximizer": 0.61, "Positivity": 0.76, "Relator": 0.63,
    "Responsibility": 0.69, "Restorative": 0.63, "Self-Assurance": 0.73,
    "Significance": 0.72, "Strategic": 0.68, "Woo": 0.80,
}

TEST_RETEST_M3 = {
    "Achiever": 0.69, "Activator": 0.68, "Adaptability": 0.72, "Analytical": 0.76,
    "Arranger": 0.50, "Belief": 0.67, "Command": 0.58, "Communication": 0.69,
    "Competition": 0.71, "Connectedness": 0.71, "Consistency": 0.65, "Context": 0.71,
    "Deliberative": 0.79, "Developer": 0.63, "Discipline": 0.82, "Empathy": 0.71,
    "Focus": 0.73, "Futuristic": 0.67, "Harmony": 0.61, "Ideation": 0.73,
    "Includer": 0.67, "Individualization": 0.61, "Input": 0.78, "Intellection": 0.78,
    "Learner": 0.80, "Maximizer": 0.63, "Positivity": 0.77, "Relator": 0.63,
    "Responsibility": 0.72, "Restorative": 0.65, "Self-Assurance": 0.74,
    "Significance": 0.71, "Strategic": 0.67, "Woo": 0.82,
}

TEST_RETEST_M6 = {
    "Achiever": 0.68, "Activator": 0.64, "Adaptability": 0.66, "Analytical": 0.75,
    "Arranger": 0.53, "Belief": 0.70, "Command": 0.64, "Communication": 0.70,
    "Competition": 0.67, "Connectedness": 0.71, "Consistency": 0.65, "Context": 0.69,
    "Deliberative": 0.80, "Developer": 0.54, "Discipline": 0.76, "Empathy": 0.65,
    "Focus": 0.60, "Futuristic": 0.61, "Harmony": 0.61, "Ideation": 0.71,
    "Includer": 0.67, "Individualization": 0.58, "Input": 0.75, "Intellection": 0.76,
    "Learner": 0.78, "Maximizer": 0.48, "Positivity": 0.69, "Relator": 0.67,
    "Responsibility": 0.65, "Restorative": 0.51, "Self-Assurance": 0.72,
    "Significance": 0.65, "Strategic": 0.71, "Woo": 0.76,
}

# ============================================================================
# TABLE 9 — четыре домена (Gallup Leadership Domains)
# ============================================================================

DOMAINS = {
    "Executing": [
        "Achiever", "Activator", "Adaptability", "Arranger", "Belief",
        "Consistency", "Deliberative", "Discipline", "Focus",
        "Responsibility", "Restorative",
    ],
    "Influencing": [
        "Command", "Communication", "Competition", "Maximizer",
        "Self-Assurance", "Significance", "Woo",
    ],
    "Relationship Building": [
        "Connectedness", "Developer", "Empathy", "Harmony", "Includer",
        "Individualization", "Positivity", "Relator",
    ],
    "Strategic Thinking": [
        "Analytical", "Context", "Futuristic", "Ideation", "Input",
        "Intellection", "Learner", "Strategic",
    ],
}

# ============================================================================
# TABLE 8 — корреляции с Big Five (исправленные на надёжность)
# Можно использовать как априорную вероятность / soft prior.
# ============================================================================

BIG_FIVE = {
    # theme: (Openness, Extraversion, Agreeableness, Conscientiousness, Neuroticism)
    "Achiever": (0.20, 0.19, 0.49, 0.22, 0.38),
    "Activator": (0.51, 0.12, 0.05, 0.03, 0.35),
    "Adaptability": (0.01, 0.11, -0.27, 0.00, 0.05),
    "Analytical": (-0.15, -0.28, 0.30, 0.04, 0.28),
    "Arranger": (0.34, 0.34, 0.22, 0.28, 0.27),
    "Belief": (0.19, 0.37, 0.12, 0.06, 0.08),
    "Command": (0.30, -0.14, 0.07, -0.06, 0.49),
    "Communication": (0.71, 0.34, 0.05, 0.11, 0.26),
    "Competition": (0.19, -0.20, 0.06, -0.07, 0.41),
    "Connectedness": (0.13, 0.43, 0.01, 0.11, 0.27),
    "Consistency": (-0.21, 0.11, 0.40, -0.01, -0.41),
    "Context": (0.05, -0.15, -0.01, -0.01, 0.28),
    "Deliberative": (-0.46, -0.42, 0.15, -0.21, 0.07),
    "Developer": (0.14, 0.63, 0.05, 0.07, 0.00),
    "Discipline": (-0.10, 0.12, 0.60, -0.09, -0.12),
    "Empathy": (0.10, 0.48, -0.05, -0.07, -0.15),
    "Focus": (0.14, -0.03, 0.33, -0.03, 0.39),
    "Futuristic": (0.23, 0.12, 0.05, -0.01, 0.50),
    "Harmony": (-0.18, 0.15, 0.27, 0.06, -0.44),
    "Ideation": (0.19, 0.01, -0.16, 0.10, 0.64),
    "Includer": (0.29, 0.44, 0.04, 0.22, -0.09),
    "Individualization": (0.33, 0.16, 0.15, -0.01, 0.53),
    "Input": (0.06, 0.18, 0.01, 0.00, 0.53),
    "Intellection": (-0.12, 0.01, -0.02, -0.08, 0.50),
    "Learner": (0.11, 0.15, 0.21, 0.14, 0.56),
    "Maximizer": (0.19, 0.01, 0.18, 0.23, 0.27),
    "Positivity": (0.49, 0.59, 0.07, 0.28, 0.07),
    "Relator": (0.08, 0.17, 0.33, 0.14, 0.31),
    "Responsibility": (0.00, 0.28, 0.44, 0.15, 0.08),
    "Restorative": (0.04, 0.15, -0.04, -0.20, 0.12),
    "Self-Assurance": (0.29, -0.04, 0.23, 0.20, 0.45),
    "Significance": (0.22, -0.16, 0.17, -0.13, 0.33),
    "Strategic": (0.29, 0.09, 0.04, 0.07, 0.65),
    "Woo": (0.69, 0.39, -0.01, 0.14, 0.11),
}

# ============================================================================
# APPENDIX A — описания 34 тем (официальные, для веб-приложения)
# ============================================================================

THEME_DESCRIPTIONS_EN = {
    "Achiever": "Has a great deal of stamina and works hard. Takes great satisfaction from being busy and productive.",
    "Activator": "Can make things happen by turning thoughts into action. Often impatient.",
    "Adaptability": "Prefers to go with the flow. A now-person who takes things as they come.",
    "Analytical": "Searches for reasons and causes. Thinks about all the factors that might affect a situation.",
    "Arranger": "Can organize, with a flexibility that complements this ability. Figures out how to arrange pieces and resources for maximum productivity.",
    "Belief": "Has certain core values that are unchanging. Out of these values emerges a defined purpose for life.",
    "Command": "Has presence. Can take control of a situation and make decisions.",
    "Communication": "Generally finds it easy to put thoughts into words. Good conversationalist and presenter.",
    "Competition": "Measures progress against the performance of others. Strives to win first place.",
    "Connectedness": "Has faith in the links between all things. Believes few coincidences exist.",
    "Consistency": "Keenly aware of the need to treat people the same. Sets clear rules and adheres to them.",
    "Context": "Enjoys thinking about the past. Understands the present by researching its history.",
    "Deliberative": "Serious care in making decisions or choices. Anticipates obstacles.",
    "Developer": "Recognizes and cultivates the potential in others. Spots signs of small improvement.",
    "Discipline": "Enjoys routine and structure. World best described by the order they create.",
    "Empathy": "Can sense the feelings of other people by imagining themselves in others' lives or situations.",
    "Focus": "Can take a direction, follow through, and make corrections to stay on track. Prioritizes, then acts.",
    "Futuristic": "Inspired by the future and what could be. Inspires others with visions of the future.",
    "Harmony": "Looks for consensus. Doesn't enjoy conflict; seeks areas of agreement.",
    "Ideation": "Fascinated by ideas. Able to find connections between seemingly disparate phenomena.",
    "Includer": "Accepting of others. Aware of those who feel left out, makes an effort to include them.",
    "Individualization": "Intrigued by unique qualities of each person. Gift for figuring out how different people work together.",
    "Input": "Has a craving to know more. Often likes to collect and archive information.",
    "Intellection": "Characterized by intellectual activity. Introspective, appreciates intellectual discussions.",
    "Learner": "Great desire to learn and continuously improve. The process of learning, rather than the outcome, excites them.",
    "Maximizer": "Focuses on strengths as a way to stimulate excellence. Seeks to transform something strong into something superb.",
    "Positivity": "Has an enthusiasm that is contagious. Upbeat and can get others excited.",
    "Relator": "Enjoys close relationships. Finds deep satisfaction in working hard with friends to achieve a goal.",
    "Responsibility": "Takes psychological ownership of what they say they will do. Committed to honesty and loyalty.",
    "Restorative": "Adept at dealing with problems. Good at figuring out what is wrong and resolving it.",
    "Self-Assurance": "Feels confident in ability to manage own life. Has an inner compass.",
    "Significance": "Wants to be very important in the eyes of others. Independent and wants to be recognized.",
    "Strategic": "Creates alternative ways to proceed. Quickly spots relevant patterns and issues.",
    "Woo": "Loves the challenge of meeting new people and winning them over. Satisfaction from breaking the ice.",
}


def get_reliability(theme: str, kind: str = "test_retest_3") -> float:
    """Возвращает надёжность темы (0..1)."""
    tables = {
        "alpha1": ALPHA_SAMPLE1,
        "alpha3": ALPHA_SAMPLE3,
        "test_retest_1": TEST_RETEST_M1,
        "test_retest_3": TEST_RETEST_M3,
        "test_retest_6": TEST_RETEST_M6,
    }
    table = tables.get(kind, TEST_RETEST_M3)
    return table.get(theme, 0.65)


def theme_domain(theme: str) -> str:
    """Возвращает домен Gallup для темы."""
    for domain, themes in DOMAINS.items():
        if theme in themes:
            return domain
    return "Unknown"
