"""
Synthetic HR-style resume generator.
Generates JSON resumes with English field names and Russian values.
"""

import json
import os
import random
import shutil
import uuid
from typing import Any, Dict, List
from pathlib import Path

from start_calculations import DEFAULT_OSINT_CATEGORIES, INFORMATION_ASSETS, random_osint_metric

BASE_DIR = Path(__file__).parent.absolute()
OUT_DIR = Path(os.path.join(BASE_DIR, "generated_resumes"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RESUME_COUNT = 100
DEFAULT_SEED = 42

CITIES = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск", "Нижний Новгород", "Самара"]
ROLES = [
    "менеджер проектов", "бизнес-аналитик", "HR-специалист", "системный администратор",
    "разработчик Python", "финансовый аналитик", "специалист по продажам", "маркетолог",
]
EMPLOYMENT_TYPES = ["полная занятость", "частичная занятость", "проектная работа"]
REMOTE_FORMATS = ["в офисе", "гибрид", "удаленно"]
ROLE_ACCESS_LEVELS = ["read", "write", "delete", "admin"]
LANGUAGE_LEVELS = ["A2", "B1", "B2", "C1"]
UNIVERSITIES = [
    "МГУ им. М.В. Ломоносова", "СПбГУ", "НИУ ВШЭ", "МГТУ им. Н.Э. Баумана", "КФУ", "УрФУ", "НИЯУ МИФИ",
]
SKILL_POOL = [
    "управление проектами", "Python", "SQL", "Excel", "Power BI", "деловая коммуникация",
    "найм персонала", "ведение переговоров", "CRM", "документооборот", "аналитическое мышление",
]
SOFT_SKILL_POOL = ["ответственность", "инициативность", "стрессоустойчивость", "работа в команде", "самоорганизация"]
CERT_POOL = ["1C:Профессионал", "Google Analytics", "Яндекс.Метрика", "ITIL Foundation", "Scrum Master"]
COMPANIES = ["ООО Альфа", "АО Вектор", "ООО ТехПром", "ЗАО Логика", "ООО Нова", "АО Профит"]


def reset_output_dir(path: str) -> None:
    """Remove previous files to guarantee clean overwrite run."""
    if os.path.exists(path):
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
    else:
        os.makedirs(path, exist_ok=True)


def random_phone() -> str:
    return f"+7-9{random.randint(10,99)}-{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}"


def random_email(full_name: str) -> str:
    translit_stub = full_name.split()[0].lower()
    domains = ["mail.ru", "yandex.ru", "gmail.com", "bk.ru"]
    return f"{translit_stub}{random.randint(10,999)}@{random.choice(domains)}"


def generate_experience(target_role: str) -> List[Dict[str, Any]]:
    entries_count = random.randint(1, 3)
    experience = []
    current_year = 2026
    start_year = current_year - random.randint(2, 8)
    for idx in range(entries_count):
        years = random.randint(1, 3)
        end_year = min(start_year + years, current_year)
        item = {
            "company": random.choice(COMPANIES),
            "position": target_role if idx == entries_count - 1 else random.choice(ROLES),
            "period": f"{start_year} - {'наст. время' if end_year == current_year else end_year}",
            "responsibilities": [
                "выполнение KPI подразделения",
                "подготовка отчетности и аналитики",
                "взаимодействие со смежными отделами",
            ],
            "achievements": [
                "сократил сроки выполнения задач на 15%",
                "автоматизировал часть рутинных операций",
            ],
        }
        experience.append(item)
        start_year = end_year
    return experience


def generate_education() -> List[Dict[str, Any]]:
    degree = random.choice(["бакалавр", "магистр", "специалитет"])
    return [
        {
            "institution": random.choice(UNIVERSITIES),
            "degree": degree,
            "major": random.choice(["экономика", "информатика", "менеджмент", "психология", "прикладная математика"]),
            "graduation_year": random.randint(2010, 2024),
        }
    ]


def generate_resume() -> Dict[str, Any]:
    desired_role = random.choice(ROLES)
    skills = random.sample(SKILL_POOL, k=random.randint(5, 8))
    soft_skills = random.sample(SOFT_SKILL_POOL, k=random.randint(3, 5))
    certifications = random.sample(CERT_POOL, k=random.randint(0, 3))
    role_access = random.choices(
        ROLE_ACCESS_LEVELS,
        weights=[35, 35, 15, 15],
    )[0]
    target_asset_id = random.choice(list(INFORMATION_ASSETS.keys()))
    target_asset = INFORMATION_ASSETS[target_asset_id]

    return {
        "id": str(uuid.uuid4()),
        "age": random.randint(22, 49),
        "city": random.choice(CITIES),
        "phone": random_phone(),
        "desired_role": desired_role,
        "employment_type": random.choice(EMPLOYMENT_TYPES),
        "remote_format": random.choice(REMOTE_FORMATS),
        "relocation_ready": random.choice([True, False]),
        "summary": f"Опытный специалист в направлении '{desired_role}', ориентирован на результат и командную работу.",
        "target_asset": {
            "asset_id": target_asset_id,
            "asset_name": target_asset["name"],
        },
        "work_experience": generate_experience(desired_role),
        "education": generate_education(),
        "skills": skills,
        "soft_skills": soft_skills,
        "languages": [
            {"language": "русский", "level": "родной"},
            {"language": "английский", "level": random.choice(LANGUAGE_LEVELS)},
        ],
        "certifications": certifications,
        # for base score calculation module
        "role_access": role_access,
        "l_initiation": round(random.uniform(0.15, 0.85), 3),
        "l_impact_controls": round(random.uniform(0.10, 0.90), 3),

        "osint_features": {category: random_osint_metric() for category in DEFAULT_OSINT_CATEGORIES},
    }


def save_resume_json(resume: Dict[str, Any], out_dir: str) -> str:
    filepath = os.path.join(out_dir, f"{resume['id']}.json")
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(resume, file, ensure_ascii=False, indent=2)
    return filepath


def run_test_stand_and_save(
    n_resumes: int = DEFAULT_RESUME_COUNT,
    seed: int = DEFAULT_SEED,
    out_dir: str = OUT_DIR,
    overwrite: bool = True,
) -> List[str]:
    """
    Generate and save synthetic resumes.
    Returns list of saved file paths.
    """
    random.seed(seed)
    if overwrite:
        reset_output_dir(out_dir)
    else:
        os.makedirs(out_dir, exist_ok=True)

    saved_files = []
    for _ in range(n_resumes):
        resume = generate_resume()
        saved_files.append(save_resume_json(resume, out_dir))
    return saved_files


if __name__ == "__main__":
    files = run_test_stand_and_save(n_resumes=100, seed=42, overwrite=True)
    print(f"Saved {len(files)} resumes to: {OUT_DIR}")
