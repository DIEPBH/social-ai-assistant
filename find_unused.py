import ast
import os
import re

def get_defined_names(directory):
    defined_classes = set()
    defined_functions = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                defined_classes.add(node.name)
                            elif isinstance(node, ast.FunctionDef):
                                if not node.name.startswith("__"):
                                    defined_functions.add(node.name)
                    except SyntaxError:
                        pass
    return defined_classes, defined_functions

def check_usages(directory, names_to_check):
    usage_counts = {name: 0 for name in names_to_check}
    
    # Pre-compile regex for faster searching
    regexes = {name: re.compile(r'\b' + name + r'\b') for name in names_to_check}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for name in names_to_check:
                        # Exclude self definition if it's the only usage (rough check)
                        matches = len(regexes[name].findall(content))
                        usage_counts[name] += matches
    
    return usage_counts

classes, functions = get_defined_names("src")

print("Checking classes...")
class_usages = check_usages("src", classes)
for c, count in class_usages.items():
    if count <= 1:
        print(f"Potentially unused class: {c}")

print("\nChecking functions...")
func_usages = check_usages("src", functions)
for f, count in func_usages.items():
    if count <= 1:
        print(f"Potentially unused function: {f}")

