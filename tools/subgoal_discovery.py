import re


def discover_subgoals(notes: list) -> list:
    tasks = []
    if not notes:
        return tasks

    pep_pattern = re.compile(r"PEP\\s*([0-9]{3,4})", re.IGNORECASE)
    pep_url_pattern = re.compile(r"pep[-/\\s]*([0-9]{3,4})", re.IGNORECASE)
    version_pattern = re.compile(r"Python\\s*([0-9]+\\.[0-9]+)", re.IGNORECASE)

    for note in notes:
        text = " ".join([
            note.get("title", ""),
            note.get("summary", ""),
            " ".join(note.get("key_points", []) or []),
            note.get("url", ""),
        ])

        for pep in pep_pattern.findall(text):
            task = f"Explain PEP {pep}"
            if task not in tasks:
                tasks.append(task)
            if len(tasks) >= 2:
                return tasks

        for pep in pep_url_pattern.findall(text):
            task = f"Explain PEP {pep}"
            if task not in tasks:
                tasks.append(task)
            if len(tasks) >= 2:
                return tasks

        for ver in version_pattern.findall(text):
            task = f"Python {ver} compatibility changes"
            if task not in tasks:
                tasks.append(task)
            if len(tasks) >= 2:
                return tasks

    return tasks
