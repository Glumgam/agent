import ast

from project_map import safe_path


def _parse_new_body(new_code: str):
    if not new_code:
        return None
    try:
        tree = ast.parse(new_code)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.body
    return tree.body or None


def replace_function(file_path: str, function_name: str, new_code: str):
    if not file_path or not function_name:
        return "Error: file_path and function_name are required"

    path = safe_path(file_path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        return f"Error: file not found: {file_path}"

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"Error: syntax error in file: {e}"

    new_body = _parse_new_body(new_code)
    if not new_body:
        return "Error: could not parse new_code"

    replaced = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            node.body = new_body
            replaced = True
            break

    if not replaced:
        return f"Error: function not found: {function_name}"

    try:
        updated = ast.unparse(tree)
    except Exception as e:
        return f"Error: failed to unparse AST: {e}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated + "\n")

    return f"Success: replaced function {function_name} in {file_path}"
