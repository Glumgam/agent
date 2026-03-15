import ast
import astor

from project_map import safe_path


def add_function(path, function_code):

    path = safe_path(path)

    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    func_node = ast.parse(function_code).body[0]

    tree.body.append(func_node)

    new_code = astor.to_source(tree)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_code)

    return "function added"
