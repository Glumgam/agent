import os
import shutil

from project_map import safe_path


def move_file(source, destination):
    if not source or not destination:
        return "Error: source and destination are required"
    try:
        src = safe_path(source)
        dest_path = safe_path(destination)
        parent = os.path.dirname(dest_path) or "."
        os.makedirs(parent, exist_ok=True)
        shutil.move(src, dest_path)
        return f"Moved {source} to {destination}"
    except Exception as e:
        return f"Error moving file: {e}"


def delete_file(path):
    if not path:
        return "Error: path is required"
    try:
        full = safe_path(path)
        if not os.path.exists(full):
            return f"Error: path not found: {path}"
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return f"Deleted {path}"
    except Exception as e:
        return f"Error deleting path: {e}"
