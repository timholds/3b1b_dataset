#!/usr/bin/env python3

import ast
import sys
sys.path.append('scripts')

from ast_systematic_converter import ASTSystematicConverter

# Test actual code from the pipeline
test_code = '''
def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)

def convergent_sum():
    return MathTex(CONVERGENT_SUM_TEXT).scale(2)

# Constants
DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\\\\cdots', '+2^n', '+\\\\cdots', '= -1']
CONVERGENT_SUM_TEXT = ['\\\\frac{1}{2}', '+\\\\frac{1}{4}', '+\\\\frac{1}{8}', '+\\\\frac{1}{16}', '+\\\\cdots', '+\\\\frac{1}{2^n}', '+\\\\cdots', '=1']
'''

print("Original code:")
print(test_code)

converter = ASTSystematicConverter()
converted = converter.convert_code(test_code)

print("\nConverted code:")
print(converted)

print(f"\nTransformations applied: {converter.stats.transformations_applied}")
print(f"Patterns matched: {converter.stats.patterns_matched}")

# Specifically check for our pattern
if 'mathtex_list_constant_join' in converter.stats.patterns_matched:
    print("✅ List constant pattern WAS applied!")
else:
    print("❌ List constant pattern was NOT applied")
    
# Let's also manually check if the fix is in the converted code
if "''.join(DIVERGENT_SUM_TEXT)" in converted:
    print("✅ DIVERGENT_SUM_TEXT fix found in output")
else:
    print("❌ DIVERGENT_SUM_TEXT fix NOT found in output")
    
if "''.join(CONVERGENT_SUM_TEXT)" in converted:
    print("✅ CONVERGENT_SUM_TEXT fix found in output")
else:
    print("❌ CONVERGENT_SUM_TEXT fix NOT found in output")