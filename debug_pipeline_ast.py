#!/usr/bin/env python3
"""Debug script to test the actual pipeline AST converter flow."""

import sys
sys.path.append('/Users/timholdsworth/code/3b1b_dataset/scripts')

from enhanced_systematic_converter import EnhancedSystematicConverter

def test_pipeline_ast_converter():
    """Test if the pipeline AST converter can fix list constant patterns."""
    
    # Test code with the problematic pattern from actual files
    test_code = '''
def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)

def convergent_sum():
    return MathTex(CONVERGENT_SUM_TEXT).scale(2)

DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\\\\cdots', '+2^n', '+\\\\cdots', '= -1']
CONVERGENT_SUM_TEXT = ['\\\\frac{1}{2}', '+\\\\frac{1}{4}', '+\\\\frac{1}{8}', '+\\\\frac{1}{16}', '+\\\\cdots', '+\\\\frac{1}{2^n}', '+\\\\cdots', '=1']
'''
    
    print("=== Original Code ===")
    print(test_code)
    
    # Create enhanced converter
    converter = EnhancedSystematicConverter(enable_claude_fallback=False)
    
    # Convert the scene
    try:
        result = converter.convert_scene(
            scene_code=test_code,
            scene_name="TestScene", 
            video_name="test-video",
            video_year="2024"
        )
        
        print(f"\n=== Conversion Result ===")
        print(f"Success: {result.success}")
        print(f"Method: {result.conversion_method}")
        print(f"Errors: {result.errors}")
        
        print(f"\n=== Final Code ===")
        print(result.final_code)
        
        # Check if the fix was applied
        if "''.join(DIVERGENT_SUM_TEXT)" in result.final_code:
            print("\n✅ SUCCESS: List constant fix was applied!")
        else:
            print("\n❌ FAILED: List constant fix was NOT applied")
            
        # Print detailed fixes
        print(f"\n=== Systematic Fixes ===")
        for fix in result.systematic_fixes_applied:
            print(f"  - {fix}")
            
    except Exception as e:
        print(f"\n❌ ERROR during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_ast_converter()