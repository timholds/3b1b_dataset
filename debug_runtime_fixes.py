#!/usr/bin/env python3
"""
Debug script to isolate the runtime fixes issue
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter
import ast

def debug_runtime_fixes():
    """Debug the specific runtime fix transformations."""
    
    # Simple test case for the exact issue
    test_code = '''
from manim import *

DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8']
INTERVAL_RADIUS = 5

def test_func():
    math_text = MathTex(DIVERGENT_SUM_TEXT)
    shift_amount = INTERVAL_RADIUS * DL
    return math_text
'''
    
    print("🔍 DEBUGGING RUNTIME FIXES")
    print("=" * 50)
    print("ORIGINAL CODE:")
    print(test_code)
    print("\n" + "=" * 50)
    
    converter = ASTSystematicConverter()
    
    # Test just the critical runtime errors fix
    print("🎯 TESTING _fix_critical_runtime_errors METHOD ONLY")
    try:
        tree = ast.parse(test_code)
        print(f"✅ Original AST parsed successfully")
        
        # Apply only the critical runtime fixes
        tree = converter._fix_critical_runtime_errors(tree)
        
        # Convert back to code
        converted = ast.unparse(tree)
        print("CONVERTED CODE:")
        print(converted)
        
        # Check stats
        print(f"\n📊 Transformations applied: {converter.stats.transformations_applied}")
        print(f"📊 Patterns matched: {converter.stats.patterns_matched}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🎯 TESTING FULL CONVERTER")
    
    # Test full conversion
    converter2 = ASTSystematicConverter()
    converted_full = converter2.convert_code(test_code)
    
    print("FULL CONVERSION RESULT:")
    print(converted_full)
    
    print(f"\n📊 Full conversion - Transformations applied: {converter2.stats.transformations_applied}")
    print(f"📊 Full conversion - Patterns matched: {converter2.stats.patterns_matched}")

if __name__ == '__main__':
    debug_runtime_fixes()