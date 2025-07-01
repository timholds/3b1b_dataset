#!/usr/bin/env python3
"""
Test script for critical runtime fixes that prevent rendering
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter

def test_runtime_fixes():
    """Test the critical runtime fixes that prevent rendering."""
    
    # Test case for the actual runtime issues found
    runtime_error_code = '''
from manim import *

# Constants that cause runtime errors
DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\\cdots', '+2^n', '+\\cdots', '= -1']
CONVERGENT_SUM_TEXT = ['\\frac{1}{2}', '+\\frac{1}{4}', '+\\frac{1}{8}', '+\\frac{1}{16}', '+\\cdots']
INTERVAL_RADIUS = 5

def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)  # CRITICAL ERROR: list not string

def zero_to_one_interval():
    interval = NumberLine()
    zero = Tex('0').shift(INTERVAL_RADIUS * DL)  # CRITICAL ERROR: DL undefined
    one = Tex('1').shift(INTERVAL_RADIUS * DR)   # CRITICAL ERROR: DR undefined
    return VGroup(interval, zero, one)

def Underbrace(left, right):
    result = Tex('\\Underbrace{%s}' % (14 * '\\quad'))
    result.stretch_to_fit_width(right[0] - left[0])
    result.shift(left - result.points[0])  # POTENTIAL ERROR: points access
    return result

class TestScene(Scene):
    def args_to_string(self, text):
        return initials([c for c in text if c in string.ascii_letters + ' '])  # ERROR: initials undefined
    
    def construct(self):
        # Test the problematic patterns
        text1 = divergent_sum()
        interval = zero_to_one_interval()
        self.add(text1, interval)
'''
    
    print("🔥 TESTING CRITICAL RUNTIME FIXES")
    print("=" * 70)
    
    converter = ASTSystematicConverter()
    converted = converter.convert_code(runtime_error_code)
    
    # Check for successful runtime fixes
    checks = [
        ("MathTex list constant fix", "''.join(DIVERGENT_SUM_TEXT)" in converted),
        ("DL constant replacement", "DOWN + LEFT" in converted),
        ("DR constant replacement", "DOWN + RIGHT" in converted),
        ("Points access preserved", ".points[0]" in converted),
        ("Import fix applied", "from manim import *" in converted)
    ]
    
    print("✅ RUNTIME FIXES APPLIED:")
    for description, check in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {description}")
    
    # Print statistics
    stats = converter.get_conversion_report()
    print(f"\n📊 Total transformations applied: {stats['transformations_applied']}")
    
    # Show runtime-specific fixes
    runtime_fixes = 0
    for pattern_name, count in stats['patterns_matched'].items():
        if any(keyword in pattern_name for keyword in [
            'list_constant_join', 'constant_', 'standalone_constant_',
            'added_initials_function'
        ]):
            runtime_fixes += count
            print(f"🎯 {pattern_name}: {count} instances")
    
    print(f"\n🎯 Critical runtime fixes applied: {runtime_fixes}")
    
    # Save converted code for inspection
    output_file = Path(__file__).parent / 'converted_runtime_test.py'
    with open(output_file, 'w') as f:
        f.write(converted)
    
    print(f"\n📁 Converted code saved to: {output_file}")
    print("🚀 Runtime fixes ready for testing!")

if __name__ == '__main__':
    test_runtime_fixes()