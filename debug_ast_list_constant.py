#!/usr/bin/env python3
"""Debug script to test AST converter list constant pattern matching."""

import ast
import sys
sys.path.append('/Users/timholdsworth/code/3b1b_dataset/scripts')

from ast_systematic_converter import ASTSystematicConverter

def test_list_constant_pattern():
    """Test if the AST converter can fix list constant patterns."""
    
    # Test code with the problematic pattern
    test_code = '''
DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\\\\cdots', '+2^n', '+\\\\cdots', '= -1']

def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)
'''
    
    print("=== Original Code ===")
    print(test_code)
    
    # Create converter
    converter = ASTSystematicConverter()
    
    # Convert the code
    try:
        converted_code = converter.convert_code(test_code)
        print("\n=== Converted Code ===")
        print(converted_code)
        
        # Check if the fix was applied
        if "''.join(DIVERGENT_SUM_TEXT)" in converted_code:
            print("\n✅ SUCCESS: List constant fix was applied!")
        else:
            print("\n❌ FAILED: List constant fix was NOT applied")
            
        # Print stats
        print(f"\n=== Conversion Stats ===")
        print(f"Transformations applied: {converter.stats.transformations_applied}")
        print(f"Patterns matched: {converter.stats.patterns_matched}")
        
    except Exception as e:
        print(f"\n❌ ERROR during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_list_constant_pattern()