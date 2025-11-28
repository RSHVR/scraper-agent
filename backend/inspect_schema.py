#!/usr/bin/env python3
"""Quick script to inspect JSON schema structure without loading full content."""
import json
import sys

def inspect_structure(obj, max_string_len=100, max_array_items=2, depth=0, max_depth=10):
    """Recursively inspect JSON structure, truncating large strings and arrays."""
    if depth > max_depth:
        return "..."

    indent = "  " * depth

    if isinstance(obj, dict):
        result = "{\n"
        for i, (key, value) in enumerate(obj.items()):
            result += f"{indent}  \"{key}\": {inspect_structure(value, max_string_len, max_array_items, depth + 1, max_depth)}"
            if i < len(obj) - 1:
                result += ","
            result += "\n"
        result += f"{indent}}}"
        return result

    elif isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        result = "[\n"
        items_to_show = min(len(obj), max_array_items)
        for i in range(items_to_show):
            result += f"{indent}  {inspect_structure(obj[i], max_string_len, max_array_items, depth + 1, max_depth)}"
            if i < items_to_show - 1:
                result += ","
            result += "\n"
        if len(obj) > max_array_items:
            result += f"{indent}  ... ({len(obj) - max_array_items} more items)\n"
        result += f"{indent}]"
        return result

    elif isinstance(obj, str):
        if len(obj) > max_string_len:
            return f'"{obj[:max_string_len]}..." (length: {len(obj)})'
        return f'"{obj}"'

    elif isinstance(obj, (int, float, bool)) or obj is None:
        return json.dumps(obj)

    else:
        return str(type(obj))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_schema.py <json_file>")
        sys.exit(1)

    filepath = sys.argv[1]

    with open(filepath, 'r') as f:
        data = json.load(f)

    print(inspect_structure(data))
