import pytest


def test_all_modules_importable():
    import importlib
    import pkgutil
    import openemail

    fails = []
    for _, modname, _ in pkgutil.walk_packages(openemail.__path__, prefix="openemail."):
        try:
            importlib.import_module(modname)
        except Exception as e:
            fails.append(f"{modname}: {e}")
    assert not fails, f"Import failures: {fails}"


def test_no_duplicate_methods():
    import ast
    import os

    dupes = []
    for root, _, files in os.walk("src/openemail"):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            with open(fp) as fh:
                src = fh.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    seen = {}
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            is_setter = any(
                                isinstance(d, ast.Attribute) and d.attr == "setter"
                                for d in item.decorator_list
                            )
                            if item.name in seen and not is_setter:
                                dupes.append(
                                    f"{fp}:{item.lineno} {node.name}.{item.name}"
                                )
                            seen[item.name] = item.lineno
    assert not dupes, f"Duplicate methods: {dupes}"


def test_no_duplicate_except():
    import ast
    import os

    dupes = []
    for root, _, files in os.walk("src/openemail"):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            with open(fp) as fh:
                src = fh.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    seen = set()
                    for handler in node.handlers:
                        if isinstance(handler.type, ast.Name):
                            if handler.type.id in seen:
                                dupes.append(f"{fp}:{handler.lineno} {handler.type.id}")
                            seen.add(handler.type.id)
    assert not dupes, f"Duplicate except: {dupes}"
