#!/usr/bin/env python3

import ast
import sys
sys.path.append('scripts')

from ast_systematic_converter import ASTSystematicConverter

# Test code with the problematic pattern
test_code = '''
def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)

def convergent_sum():
    return MathTex(CONVERGENT_SUM_TEXT).scale(2)
'''

print("Original code:")
print(test_code)

converter = ASTSystematicConverter()
converted = converter.convert_code(test_code)

print("\nConverted code:")
print(converted)

print("\nTransformations applied:", converter.stats.transformations_applied)
print("Patterns matched:", converter.stats.patterns_matched)