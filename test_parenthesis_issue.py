#!/usr/bin/env python3
"""Test to identify the parenthesis issue with OldTex("(")"""

import re

def test_clean_matched_code_fix():
    """Test the fix_common_syntax_issues logic from clean_matched_code.py"""
    
    # Test case: OldTex("(")
    test_line = 'OldTex("(")'
    print(f"Original line: {test_line}")
    
    # Simulate the string replacement logic from clean_matched_code.py
    temp_line = test_line
    string_pattern = r'(\'[^\']*\'|"[^"]*")'
    strings = re.findall(string_pattern, temp_line)
    print(f"Found strings: {strings}")
    
    for j, string in enumerate(strings):
        temp_line = temp_line.replace(string, f'__STRING_{j}__')
    
    print(f"After string replacement: {temp_line}")
    
    # Count parentheses
    open_count = temp_line.count('(')
    close_count = temp_line.count(')')
    print(f"Open parens: {open_count}, Close parens: {close_count}")
    
    # Check if line ends with closing paren
    ends_with_paren = bool(re.search(r'\)\s*$', temp_line))
    print(f"Ends with closing paren: {ends_with_paren}")
    
    # Would it add extra parens?
    if open_count > close_count and ends_with_paren:
        diff = open_count - close_count
        print(f"Would add {diff} closing parentheses!")
        fixed_line = test_line.rstrip() + ')' * diff
        print(f"Result: {fixed_line}")
    else:
        print("No extra parentheses would be added")

def test_precompile_validator_fix():
    """Test the fix from manimce_precompile_validator.py"""
    
    # Test case: OldTex("(")
    test_content = 'OldTex("(")'
    print(f"\nTesting precompile validator fix...")
    print(f"Original: {test_content}")
    
    # The problematic pattern from manimce_precompile_validator.py
    pattern = r'((?:Old)?Tex\(".\))\)'
    
    if re.search(pattern, test_content):
        print(f"Pattern matches! This would remove the last parenthesis.")
        fixed = re.sub(pattern, r'\1', test_content)
        print(f"Result: {fixed}")
    else:
        print("Pattern does not match")
    
    # Let's see what the pattern actually matches
    print(f"\nPattern breakdown:")
    print(f"  (?:Old)?Tex\\(\" - matches 'OldTex(\"' or 'Tex(\"'")
    print(f"  . - matches any single character")
    print(f"  \\)\\) - matches two closing parentheses")
    print(f"\nFor OldTex(\"(\"), it's looking for: OldTex(\"()), but we have OldTex(\"(\")")
    print("So this pattern shouldn't match our test case.")
    
    # Test what it WOULD match
    test_broken = 'OldTex("a"))'
    print(f"\nTesting with extra paren: {test_broken}")
    if re.search(pattern, test_broken):
        print("Pattern matches!")
        fixed = re.sub(pattern, r'\1', test_broken)
        print(f"Result: {fixed}")

if __name__ == "__main__":
    test_clean_matched_code_fix()
    test_precompile_validator_fix()