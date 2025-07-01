#!/usr/bin/env python3
"""Debug CycloidScene extraction issue."""

import ast
import json
from pathlib import Path

# Check what's in the cleaned file
cleaned_file = Path("data/claude_fixes/IntroduceCycloid_2025-06-26T22-50-53.390439_8ed33c67/original.py")

if cleaned_file.exists():
    print(f"Reading cleaned file: {cleaned_file}")
    with open(cleaned_file, 'r') as f:
        content = f.read()
    
    print("\n=== Cleaned File Content (first 1000 chars) ===")
    print(content[:1000])
    
    # Parse and analyze
    tree = ast.parse(content)
    
    # Find all classes
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append({
                'name': node.name,
                'bases': [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases],
                'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                'has_pass': any(isinstance(n, ast.Pass) for n in node.body),
                'body_count': len(node.body)
            })
    
    print("\n=== Classes Found ===")
    for cls in classes:
        print(f"\nClass: {cls['name']}")
        print(f"  Bases: {cls['bases']}")
        print(f"  Methods: {cls['methods']}")
        print(f"  Has pass: {cls['has_pass']}")
        print(f"  Body elements: {cls['body_count']}")

# Check symbol index
symbol_index_path = Path("data/symbol_index.json")
if symbol_index_path.exists():
    print("\n=== Checking Symbol Index ===")
    with open(symbol_index_path, 'r') as f:
        symbol_index = json.load(f)
    
    # Look for Cycloid class
    cycloid_found = False
    for file_path, symbols in symbol_index.items():
        if 'Cycloid' in symbols.get('classes', {}):
            print(f"\nFound Cycloid class in: {file_path}")
            cycloid_found = True
            
        if 'CycloidScene' in symbols.get('classes', {}):
            print(f"\nFound CycloidScene class in: {file_path}")
            
    if not cycloid_found:
        print("\nCycloid class NOT found in symbol index!")

# Check if curves.py exists
curves_files = list(Path("data/videos").rglob("*curves.py"))
print(f"\n=== Curves Files Found ===")
for f in curves_files[:5]:
    print(f"  {f}")
    
# Check brachistochrone directory
brach_dir = Path("data/videos/_2016/brachistochrone")
if brach_dir.exists():
    print(f"\n=== Files in {brach_dir} ===")
    for f in brach_dir.glob("*.py"):
        print(f"  {f.name}")