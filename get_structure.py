import os


def get_project_structure(path=".", prefix=""):
    entries = sorted(os.listdir(path))
    entries = [e for e in entries if not e.startswith(".")]  # Игнорируем скрытые файлы

    for i, entry in enumerate(entries):
        full_path = os.path.join(path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + entry)

        if os.path.isdir(full_path):
            extension = "    " if i == len(entries) - 1 else "│   "
            get_project_structure(full_path, prefix + extension)


if __name__ == "__main__":
    get_project_structure()
