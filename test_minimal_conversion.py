#!/usr/bin/env python3
"""Minimal test to trace the OldTex("(") conversion issue"""

import re
import sys
import os
sys.path.append('scripts')

from clean_matched_code import CodeCleaner

# Test the actual pattern
test_code = '''
def some_function():
    left_paren = OldTex("(")
    right_paren = OldTex(")")
    both = OldTex("()")
'''

print("Original code:")
print(test_code)

# Test the fix_common_syntax_issues function
cleaner = CodeCleaner(".", verbose=True)
fixed_code = cleaner.fix_common_syntax_issues(test_code)

print("\nAfter fix_common_syntax_issues:")
print(fixed_code)

# Check if it added extra parentheses
if 'OldTex("("))' in fixed_code:
    print("\n*** FOUND THE BUG! Extra parenthesis was added! ***")
else:
    print("\nNo extra parenthesis added by cleaner.")

# Now test other potential sources
# Test if it's in the string continuation fix
def test_string_continuation_pattern():
    pattern = r'(?<![a-zA-Z0-9_])(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*?)\s*\\\s*\n\s*([^"\'\\]*(?:\\.[^"\'\\]*)*?)\1'
    
    test_cases = [
        'OldTex("(")',
        'text = "(" \\\n    + ")"',
        'OldTex("(" \\\n)',
    ]
    
    print("\n\nTesting string continuation pattern:")
    for test in test_cases:
        print(f"\nTest: {repr(test)}")
        matches = re.findall(pattern, test, flags=re.MULTILINE)
        if matches:
            print(f"  Matches: {matches}")
        else:
            print("  No match")

test_string_continuation_pattern()

# Test the parenthesis balancing fix
def test_parenthesis_balancing():
    print("\n\nTesting parenthesis balancing:")
    
    lines = ['left_paren = OldTex("(")']
    
    for i, line in enumerate(lines):
        print(f"\nLine: {line}")
        
        # Simulate the logic from clean_matched_code.py
        temp_line = line
        string_pattern = r'(\'[^\']*\'|"[^"]*")'
        strings = re.findall(string_pattern, temp_line)
        for j, string in enumerate(strings):
            temp_line = temp_line.replace(string, f'__STRING_{j}__')
        
        print(f"After string replacement: {temp_line}")
        
        open_count = temp_line.count('(')
        close_count = temp_line.count(')')
        print(f"Open: {open_count}, Close: {close_count}")
        
        if open_count > close_count:
            diff = open_count - close_count
            if re.search(r'\)\s*$', temp_line) and diff > 0:
                if not re.search(r'[,\\]\s*$', line):
                    print(f"Would add {diff} closing parentheses!")
                    fixed_line = line.rstrip() + ')' * diff
                    print(f"Result: {fixed_line}")

test_parenthesis_balancing()