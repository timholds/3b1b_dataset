#!/usr/bin/env python3
"""Test specific conversion patterns that might cause the issue"""

import re

def test_string_concatenation_fix():
    """Test the string concatenation fix pattern"""
    
    # From clean_matched_code.py line 337
    pattern = r'(?<![a-zA-Z0-9_])(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*?)\s*\\\s*\n\s*([^"\'\\]*(?:\\.[^"\'\\]*)*?)\1'
    
    test_cases = [
        'OldTex("(")',
        'OldTex("(" + ")")',
        'OldTex("(" \\n    + ")")',
        'text = "(" \\n    + ")"'
    ]
    
    print("Testing string concatenation pattern...")
    for test in test_cases:
        print(f"\nTest: {repr(test)}")
        matches = re.findall(pattern, test, flags=re.MULTILINE)
        print(f"Matches: {matches}")

def test_all_conversion_patterns():
    """Test all regex patterns that might affect OldTex("(")"""
    
    test_input = 'OldTex("(")'
    
    # All patterns from the conversion scripts that might affect this
    patterns_to_test = [
        # From manimce_conversion_utils.py
        (r'\bOldTex\b', 'Tex', "OldTex -> Tex conversion"),
        
        # Check if any pattern might add extra parentheses
        (r'(\w+\("[^"]*"\))', r'\1)', "Add extra closing paren (hypothetical)"),
        
        # From clean_matched_code.py - escape sequences
        (r'(?<!r)(["\'])([^"\']*?(?:\\[spwdb][^"\']*?)*)\1', None, "Escape sequence fix"),
    ]
    
    print(f"\nTesting patterns on: {test_input}")
    for pattern, replacement, description in patterns_to_test:
        print(f"\n{description}:")
        print(f"  Pattern: {pattern}")
        if re.search(pattern, test_input):
            print(f"  Matches: YES")
            if replacement:
                result = re.sub(pattern, replacement, test_input)
                print(f"  Result: {result}")
                if result == 'OldTex("("))':
                    print("  *** THIS CREATES THE PROBLEM! ***")
        else:
            print(f"  Matches: NO")

def check_advanced_converter():
    """Check if the issue might be in the advanced converter"""
    
    # The issue might be in how parentheses in strings are handled
    # when converting OldTex to Tex
    
    test_cases = [
        ('OldTex("(")', 'Tex("(")'),  # Expected
        ('OldTex(")")', 'Tex(")")'),  # Expected
        ('OldTex("()")', 'Tex("()")'),  # Expected
    ]
    
    print("\n\nChecking conversion expectations:")
    for original, expected in test_cases:
        print(f"{original} -> {expected}")
        # Check if simple substitution would work
        simple_result = original.replace('OldTex', 'Tex')
        print(f"  Simple substitution: {simple_result}")
        if simple_result != expected:
            print("  *** MISMATCH ***")

if __name__ == "__main__":
    test_string_concatenation_fix()
    test_all_conversion_patterns()
    check_advanced_converter()