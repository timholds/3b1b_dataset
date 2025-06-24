#!/usr/bin/env python3
"""
Fix common syntax errors in cleaned/converted Manim code files.
Specifically fixes extra closing parentheses in Tex/OldTex calls.
"""

import re
import sys
from pathlib import Path

def fix_tex_parentheses(content):
    """Fix extra closing parentheses in Tex/OldTex calls."""
    # Pattern 1: Fix Tex calls with string formatting that have extra )
    # e.g., Tex(r'\frac{%d}{%d}') % (n, d)) -> Tex(r'\frac{%d}{%d}' % (n, d))
    content = re.sub(
        r"((?:Old)?Tex\(r?['\"].*?['\"])\)\s*%\s*([^)]+)\)\)",
        r"\1 % \2)",
        content
    )
    
    # Pattern 2: Fix Tex calls ending with '))
    # e.g., Tex(r'\int')) -> Tex(r'\int')
    content = re.sub(
        r"((?:Old)?Tex\(r?['\"][^'\"]+?['\"]\))\)",
        r"\1",
        content
    )
    
    # Pattern 3: Fix indentation issues after class definitions
    # Find class definitions followed by unindented def
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        if i > 0 and lines[i-1].strip().startswith('class ') and lines[i-1].strip().endswith(':'):
            # Previous line was a class definition
            if line.startswith('def ') and not line.startswith('    '):
                # This def should be indented
                line = '    ' + line
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_tex_parentheses.py <file_path>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    
    if not file_path.exists():
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the syntax errors
    fixed_content = fix_tex_parentheses(content)
    
    # Write back if changes were made
    if fixed_content != content:
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        print(f"Fixed syntax errors in {file_path}")
    else:
        print(f"No syntax errors found in {file_path}")

if __name__ == "__main__":
    main()