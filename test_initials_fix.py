#!/usr/bin/env python3
"""
Test the initials function fix
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter

def test_initials_fix():
    """Test the initials function fix."""
    
    # Test case with initials function call
    test_code = '''
from manim import *
import string

DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8']

class SimpleText(Scene):
    @staticmethod
    def args_to_string(text):
        return initials([c for c in text if c in string.ascii_letters + ' '])
    
    def construct(self):
        self.add(Text("Test"))
'''
    
    print("🔍 TESTING INITIALS FUNCTION FIX")
    print("=" * 50)
    print("ORIGINAL CODE:")
    print(test_code)
    print("\n" + "=" * 50)
    
    converter = ASTSystematicConverter()
    converted = converter.convert_code(test_code)
    
    print("CONVERTED CODE:")
    print(converted)
    
    # Check for initials function
    checks = [
        ("initials function defined", "def initials(" in converted),
        ("initials function called", "return initials(" in converted),
        ("MathTex list fix applied", "''.join(DIVERGENT_SUM_TEXT)" in converted),
    ]
    
    print("\n✅ FIXES APPLIED:")
    for desc, check in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {desc}")
    
    print(f"\n📊 Transformations applied: {converter.stats.transformations_applied}")
    print(f"📊 Patterns matched: {converter.stats.patterns_matched}")

if __name__ == '__main__':
    test_initials_fix()