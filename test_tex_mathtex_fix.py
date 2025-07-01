#!/usr/bin/env python3
"""
Test the Tex -> MathTex conversion fix
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter

def test_tex_mathtex_fix():
    """Test the Tex to MathTex conversion for math content."""
    
    # Test case with math expressions in Tex
    test_code = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        frac_text = Tex('\\\\frac{9}{10}')
        regular_text = Tex('Hello World')
        math_expr = Tex('x^2 + y_1')
        self.add(frac_text, regular_text, math_expr)
'''
    
    print("🔍 TESTING TEX -> MATHTEX CONVERSION")
    print("=" * 50)
    print("ORIGINAL CODE:")
    print(test_code)
    print("\n" + "=" * 50)
    
    converter = ASTSystematicConverter()
    converted = converter.convert_code(test_code)
    
    print("CONVERTED CODE:")
    print(converted)
    
    # Check for conversions
    checks = [
        ("\\\\frac converted to MathTex", "MathTex('\\\\frac{9}{10}')" in converted),
        ("Regular text stays Tex", "Tex('Hello World')" in converted),
        ("x^2 converted to MathTex", "MathTex('x^2 + y_1')" in converted),
    ]
    
    print("\n✅ CONVERSIONS APPLIED:")
    for desc, check in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {desc}")
    
    print(f"\n📊 Transformations applied: {converter.stats.transformations_applied}")
    print(f"📊 Patterns matched: {converter.stats.patterns_matched}")

if __name__ == '__main__':
    test_tex_mathtex_fix()