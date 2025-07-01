# Summary: Issues #7-10 in KNOWN_ISSUES.md Problem Set #2

## Investigation Results

I investigated issues #7-10 which relate to multi-line constant extraction problems in the cleaning and conversion pipeline.

### The Problem

The issues describe various cases where multi-line constants were being truncated or improperly extracted:

1. **Issue #7**: List comprehensions with line continuations not fully captured
2. **Issue #8**: Constants using backslash continuation not handled properly  
3. **Issue #9**: Nested data structures with complex bracket/brace tracking
4. **Issue #10**: Constants with inline comments interfering with parsing

The primary example was `ALT_PARTIAL_SUM_TEXT` from inventing_math.py:

```python
ALT_PARTIAL_SUM_TEXT = reduce(op.add, [
    [str(partial_sum(n)), "&=", "+".join(CONVERGENT_SUM_TERMS[:n])+"\\\\"]
    for n in range(1, len(CONVERGENT_SUM_TERMS)+1)
])+ [
    "\\vdots", "&", "\\\\",
    "1.0", "&=", "+".join(CONVERGENT_SUM_TERMS)+"+\\cdots+\\frac{1}{2^n}+\\cdots"
]
```

This was being truncated mid-expression, causing syntax errors.

### The Solution (Already Implemented)

The fix has already been implemented in `systematic_pipeline_converter.py` (not in scene_dependency_analyzer.py as initially documented). The key improvements were:

1. **Enhanced bracket tracking** (lines 547-630):
   - Tracks all bracket types simultaneously: `[`, `{`, `(`
   - Properly handles nested structures
   - Accounts for brackets inside string literals

2. **Dependency sorting** (lines 300-359):
   - Added `_sort_constants_by_dependency()` function
   - Ensures constants that reference other constants are defined in the correct order
   - Prevents NameError from undefined constants

3. **String literal handling**:
   - Ignores brackets inside quoted strings
   - Handles escaped characters properly

### Evidence of Success

1. The inventing-math video converts with 100% systematic conversion (0 Claude API calls)
2. `ALT_PARTIAL_SUM_TEXT` is properly extracted in full in the validated snippets
3. Constants are in correct dependency order (CONVERGENT_SUM_TERMS defined before ALT_PARTIAL_SUM_TEXT)
4. No truncation or syntax errors in the extracted constants

### Updated Documentation

I've updated KNOWN_ISSUES.md to:
- Correct the fix location (systematic_pipeline_converter.py, not scene_dependency_analyzer.py)
- Specify that issues #7-10 are all resolved by this fix
- Add specific checkmarks for each resolved issue

## Conclusion

Issues #7-10 have been successfully resolved. The multi-line constant extraction now properly handles:
- Complex expressions with reduce() and other functions
- Multi-line list comprehensions
- Nested data structures with multiple bracket types
- String literals containing brackets
- Proper dependency ordering

The fix is working correctly in production and requires no further changes.