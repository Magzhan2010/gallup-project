"""
manage_gallup_db.py
==================
CLI для управления БД Gallup-результатов.

Использование:
  python manage_gallup_db.py              # интерактивный режим
  python manage_gallup_db.py --list      # показать все записи
  python manage_gallup_db.py --add NAME T1 T2 T3 T4 T5
  python manage_gallup_db.py --remove NAME
  python manage_gallup_db.py --import FILE.csv
  python manage_gallup_db.py --export FILE.csv
  python manage_gallup_db.py --check      # проверить на ошибки

БД хранится в: web/data/gallup_db.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(__file__).resolve().parent
DB_PATH = PROJECT / "web" / "data" / "gallup_db.json"

# 34 Gallup-темы
GALLUP_THEMES = [
    "Achiever", "Discipline", "Activator", "Maximizer", "Adaptability",
    "Includer", "Analytical", "Input", "Arranger", "Focus",
    "Command", "Self-Assurance", "Connectedness", "Individualization", "Context",
    "Intellection", "Belief", "Responsibility", "Communication", "Significance",
    "Developer", "Positivity", "Futuristic", "Learner", "Consistency",
    "Restorative", "Competition", "Woo", "Empathy", "Relator",
    "Ideation", "Strategic", "Deliberative", "Harmony",
]


def normalize_theme(name):
    if not name: return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_db():
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return []


def save_db(db):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_top5(top5_str):
    """Парсит 'Strategic, Achiever, ...' → ['Strategic', 'Achiever', ...]"""
    known = [normalize_theme(t) for t in GALLUP_THEMES]
    items = [t.strip() for t in top5_str.replace("\n", ",").split(",") if t.strip()]
    normalized = []
    for item in items[:5]:
        n = normalize_theme(item)
        # Нечёткое совпадение
        if n in known:
            normalized.append(n)
        else:
            fuzzy = next((k for k in known if k.lower() == n.lower() or k.replace("-", "").lower() == n.replace("-", "").lower()), None)
            if fuzzy:
                normalized.append(fuzzy)
            else:
                print(f"  ⚠️ Не распознано: '{item}'")
                return None
    if len(normalized) < 5:
        print(f"  ⚠️ Найдено только {len(normalized)} тем, нужно 5")
        return None
    return normalized


def add_entry(db, name, top5, date=None, notes=None, source="manual"):
    """Добавить или обновить запись."""
    # Удалить старую если есть
    db = [e for e in db if e["name"].lower() != name.lower()]
    entry = {
        "name": name,
        "gallup_top5": [{"theme": t, "rank": i + 1} for i, t in enumerate(top5)],
        "source": source,
        "added_at": __import__("datetime").datetime.now().isoformat(),
    }
    if date:
        entry["gallup_date"] = date
    if notes:
        entry["notes"] = notes
    db.append(entry)
    return db


def interactive_mode():
    """Интерактивный режим — ввод записей по одной."""
    print("=" * 70)
    print("Gallup DB Manager — интерактивный режим")
    print("=" * 70)
    print("Введите данные. Пустое имя = выход.")
    print("Темы вводятся через запятую или с новой строки.")
    print("Формат: Strategic, Achiever, Context, Deliberative, Discipline")
    print()

    db = load_db()
    print(f"📁 Текущая БД: {len(db)} записей\n")

    while True:
        try:
            name = input("👤 Имя/ID человека (Enter для выхода): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not name:
            break

        print(f"  🎓 Gallup топ-5 для '{name}':")
        top5_input_lines = []
        while len(top5_input_lines) < 5:
            try:
                line = input(f"    [{len(top5_input_lines)+1}/5] или всё сразу через запятую: ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not line:
                if top5_input_lines:
                    break
                continue
            # Если есть запятая — разбить
            if "," in line or "\n" in line:
                parts = [p.strip() for p in line.replace("\n", ",").split(",") if p.strip()]
                top5_input_lines.extend(parts)
                break
            else:
                top5_input_lines.append(line)
                if len(top5_input_lines) >= 5:
                    break

        top5_input = ", ".join(top5_input_lines[:5])
        top5 = normalize_top5(top5_input)
        if not top5:
            print("  ❌ Не удалось распознать. Попробуйте ещё раз.\n")
            continue

        print(f"  ✓ Распознано: {', '.join(top5)}")

        date = input("  📅 Когда сдавал Gallup (ГГГГ-ММ-ДД, Enter если не знаешь): ").strip() or None
        notes = input("  📝 Заметка (Enter чтобы пропустить): ").strip() or None

        db = add_entry(db, name, top5, date=date, notes=notes, source="manual")
        save_db(db)
        print(f"  ✅ Сохранено: {name} → {' → '.join(top5)}\n")


def cmd_list(args):
    db = load_db()
    if not db:
        print("📁 БД пуста.")
        return
    print(f"📁 Записей: {len(db)}\n")
    for e in db:
        top5 = " → ".join(t["theme"] for t in e["gallup_top5"])
        date = e.get("gallup_date", "—")
        source = e.get("source", "manual")
        print(f"  • {e['name']:<25} {top5}")
        print(f"    📅 Gallup: {date}  |  источник: {source}")
        if e.get("notes"):
            print(f"    📝 {e['notes']}")
        print()


def cmd_add(args):
    if len(args.theme) != 5:
        print(f"❌ Нужно ровно 5 тем, передано {len(args.theme)}")
        return
    db = load_db()
    top5 = normalize_top5(", ".join(args.theme))
    if not top5:
        return
    db = add_entry(db, args.name, top5, date=args.date, notes=args.notes, source=args.source)
    save_db(db)
    print(f"✅ Добавлено: {args.name} → {' → '.join(top5)}")


def cmd_remove(args):
    db = load_db()
    new_db = [e for e in db if e["name"].lower() != args.name.lower()]
    if len(new_db) == len(db):
        print(f"❌ Не найдено: {args.name}")
        return
    save_db(new_db)
    print(f"✅ Удалено: {args.name}")


def cmd_import(args):
    """Импорт из CSV: name,theme1,theme2,theme3,theme4,theme5[,date,notes]"""
    db = load_db()
    added = 0
    failed = 0
    with open(args.import_, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 6:
                failed += 1
                continue
            name = row[0].strip()
            top5_str = ",".join(row[1:6])
            date = row[6].strip() if len(row) > 6 and row[6].strip() else None
            notes = row[7].strip() if len(row) > 7 and row[7].strip() else None
            top5 = normalize_top5(top5_str)
            if not top5 or not name:
                failed += 1
                print(f"  ❌ Пропущено: {name if name else '(без имени)'} — {top5_str[:50]}")
                continue
            db = add_entry(db, name, top5, date=date, notes=notes, source="csv-import")
            added += 1
            print(f"  ✓ {name} → {' → '.join(top5)}")
    save_db(db)
    print(f"\n📊 Импортировано: {added}, ошибок: {failed}")


def cmd_export(args):
    db = load_db()
    if not db:
        print("📁 БД пуста.")
        return
    with open(args.export, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "theme1", "theme2", "theme3", "theme4", "theme5", "date", "notes", "source"])
        for e in db:
            row = [e["name"]]
            themes = [t["theme"] for t in e["gallup_top5"]]
            # Дополним до 5 если меньше
            while len(themes) < 5:
                themes.append("")
            row.extend(themes[:5])
            row.append(e.get("gallup_date", ""))
            row.append(e.get("notes", ""))
            row.append(e.get("source", ""))
            writer.writerow(row)
    print(f"✅ Экспортировано {len(db)} записей в {args.export}")


def cmd_check(args):
    """Проверить БД на ошибки."""
    db = load_db()
    if not db:
        print("📁 БД пуста.")
        return
    issues = []
    seen = set()
    for i, e in enumerate(db):
        name = e.get("name", "").strip()
        if not name:
            issues.append(f"  Запись #{i+1}: пустое имя")
            continue
        if name.lower() in seen:
            issues.append(f"  Дубликат имени: '{name}'")
        seen.add(name.lower())

        top5 = e.get("gallup_top5", [])
        if len(top5) != 5:
            issues.append(f"  '{name}': {len(top5)} тем вместо 5")
            continue

        themes = [t["theme"] for t in top5]
        if len(set(themes)) != 5:
            issues.append(f"  '{name}': дубликаты тем в топ-5")

        for t in themes:
            if normalize_theme(t) not in [normalize_theme(x) for x in GALLUP_THEMES]:
                issues.append(f"  '{name}': неизвестная тема '{t}'")

    if issues:
        print(f"⚠️ Найдено проблем: {len(issues)}")
        for i in issues:
            print(i)
    else:
        print(f"✅ БД валидна. {len(db)} записей.")


def main():
    parser = argparse.ArgumentParser(description="Gallup DB Manager")
    parser.add_argument("--list", action="store_true", help="Показать все записи")
    parser.add_argument("--add", metavar="NAME", help="Добавить запись (--add NAME T1 T2 T3 T4 T5)")
    parser.add_argument("--remove", metavar="NAME", help="Удалить запись по имени")
    parser.add_argument("--import", metavar="FILE", dest="import_", help="Импорт из CSV")
    parser.add_argument("--export", metavar="FILE", help="Экспорт в CSV")
    parser.add_argument("--check", action="store_true", help="Проверить БД")
    parser.add_argument("--theme", nargs=5, metavar=("T1", "T2", "T3", "T4", "T5"), help="5 тем")
    parser.add_argument("--date", help="Дата Gallup (ГГГГ-ММ-ДД)")
    parser.add_argument("--notes", help="Заметка")
    parser.add_argument("--source", default="manual", help="Источник данных")
    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.add:
        args.name = args.add
        cmd_add(args)
    elif args.remove:
        cmd_remove(args)
    elif args.import_:
        cmd_import(args)
    elif args.export:
        cmd_export(args)
    elif args.check:
        cmd_check(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
