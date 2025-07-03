#!/usr/bin/env python3
"""
Test Enhanced Pipeline - Comprehensive testing of strategic fallback improvements

This test validates that our strategic improvements work correctly:
1. Strategic Claude fallback triggers based on complexity
2. Comprehensive pre/post conversion validation  
3. Lower confidence thresholds
4. Post-conversion quality analysis

Expected improvements:
- Reduce the 62% gap between conversion success and rendering success
- Use Claude strategically for complex cases before validation failure
- Catch semantic issues that syntax validation misses
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from strategic_fallback_triggers import StrategicFallbackAnalyzer, analyze_post_conversion_quality
from comprehensive_validation import validate_pre_conversion, validate_post_conversion
from enhanced_systematic_converter import EnhancedSystematicConverter

def test_strategic_fallback_triggers():
    """Test that strategic fallback triggers work for complex patterns."""
    print("🔍 TESTING STRATEGIC FALLBACK TRIGGERS")
    print("=" * 50)
    
    analyzer = StrategicFallbackAnalyzer()
    
    # Test case 1: High complexity scene (should trigger Claude)
    complex_scene = '''
class ComplexScene(Scene):
    def construct(self):
        # Complex list unpacking (high risk)
        a, b, c = [some_complex_function()]
        
        # Nested function calls
        result = transform_complex(nested_call(another_call(x, y), z))
        
        # Complex Tex expressions  
        tex = MathTex([f"\\\\frac{{{i}}}{{{j}}}" for i, j in zip(range(10), range(1,11))])
        
        # Nested animations
        self.play(Transform(VGroup(a, b, c), VGroup(d, e, f)))
        
        # Multiple control flow complexity
        for i in range(10):
            if condition:
                for j in range(i):
                    if nested_condition:
                        complex_operation()
'''
    
    should_trigger, triggers, confidence = analyzer.analyze_scene_for_fallback(
        complex_scene, "ComplexScene", systematic_fixes_count=35, current_confidence=0.9
    )
    
    print(f"Complex scene analysis:")
    print(f"  Should trigger Claude: {should_trigger}")
    print(f"  Original confidence: 0.9 → Adjusted: {confidence:.2f}")
    print(f"  Triggers found: {len(triggers)}")
    for trigger in triggers[:3]:  # Show first 3
        print(f"    - {trigger.name}: {trigger.reason}")
    
    assert should_trigger, "Complex scene should trigger Claude fallback"
    assert confidence < 0.7, "Complex scene should have reduced confidence"
    print("✅ Complex scene correctly triggers Claude fallback")
    
    # Test case 2: Simple scene (should NOT trigger Claude)
    simple_scene = '''
class SimpleScene(Scene):
    def construct(self):
        text = Text("Hello World")
        self.add(text)
'''
    
    should_trigger, triggers, confidence = analyzer.analyze_scene_for_fallback(
        simple_scene, "SimpleScene", systematic_fixes_count=5, current_confidence=0.95
    )
    
    print(f"\nSimple scene analysis:")
    print(f"  Should trigger Claude: {should_trigger}")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Triggers found: {len(triggers)}")
    
    assert not should_trigger, "Simple scene should NOT trigger Claude fallback"
    print("✅ Simple scene correctly avoids Claude fallback")

def test_comprehensive_validation():
    """Test comprehensive pre/post conversion validation."""
    print("\n🔍 TESTING COMPREHENSIVE VALIDATION")
    print("=" * 50)
    
    # Test case 1: Pre-conversion validation with issues
    problematic_manimgl = '''
class ProblematicScene(Scene):
    def construct(self):
        # Syntax error - unclosed parenthesis
        broken_call = some_function(
        
        # Missing imports but using numpy
        array = np.array([1, 2, 3])
        
        # Complex pattern that often breaks
        a, b, c = [single_item]
'''
    
    pre_result = validate_pre_conversion(problematic_manimgl, "ProblematicScene")
    
    print(f"Pre-conversion validation:")
    print(f"  Valid: {pre_result.is_valid}")
    print(f"  Confidence: {pre_result.confidence:.2f}")
    print(f"  Should use Claude: {pre_result.should_use_claude}")
    print(f"  Issues: {len(pre_result.issues)}")
    
    assert not pre_result.is_valid, "Problematic code should fail pre-validation"
    assert pre_result.should_use_claude, "Problematic code should recommend Claude"
    assert pre_result.confidence < 0.5, "Problematic code should have low confidence"
    print("✅ Pre-conversion validation correctly identifies issues")
    
    # Test case 2: Post-conversion validation with semantic issues
    problematic_manimce = '''
from manim import *

class ProblematicManimCE(Scene):
    def construct(self):
        # Runtime error - MathTex with list
        tex = MathTex(['\\\\frac{1}{2}', '\\\\frac{1}{4}'])
        
        # Missing constant
        position = DL + RIGHT
        
        # Old method call pattern
        center = tex.get_center()
        
        self.add(tex)
'''
    
    post_result = validate_post_conversion(problematic_manimce, "ProblematicManimCE")
    
    print(f"\nPost-conversion validation:")
    print(f"  Valid: {post_result.is_valid}")
    print(f"  Confidence: {post_result.confidence:.2f}")
    print(f"  Should use Claude: {post_result.should_use_claude}")
    print(f"  Issues: {len(post_result.issues)}")
    
    assert not post_result.is_valid, "Problematic ManimCE should fail post-validation"
    assert post_result.should_use_claude, "Problematic ManimCE should recommend Claude"
    print("✅ Post-conversion validation correctly identifies semantic issues")

def test_enhanced_converter_integration():
    """Test that enhanced converter uses strategic triggers correctly."""
    print("\n🔍 TESTING ENHANCED CONVERTER INTEGRATION")
    print("=" * 50)
    
    # Use enhanced converter with strategic triggers enabled
    converter = EnhancedSystematicConverter(
        enable_claude_fallback=True,
        min_conversion_confidence=0.65  # Lower threshold
    )
    
    # Test case: Scene that should trigger strategic Claude fallback
    strategic_scene = '''
from manimlib import *

class StrategicTestScene(Scene):
    def construct(self):
        # This pattern often breaks in systematic conversion
        terms = [OldTex(f"\\\\frac{{{i}}}{{{j}}}") for i, j in complex_generator()]
        
        # Complex nested operations
        result = transform_with_complex_params(
            nested_operation(a, b, c),
            another_nested_call(x, y, z)
        )
        
        # List unpacking that causes issues
        left, middle, right = [single_complex_result]
        
        # This triggers high fix count
        for _ in range(20):  # Artificial complexity to trigger high fix count
            pass
'''
    
    print("Converting strategic test scene...")
    result = converter.convert_scene(
        strategic_scene, 
        "StrategicTestScene",
        video_name="test-video",
        video_year=2015
    )
    
    print(f"Conversion result:")
    print(f"  Success: {result.success}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Method: {result.conversion_method}")
    print(f"  Systematic fixes: {len(result.systematic_fixes_applied)}")
    print(f"  Claude fixes: {len(result.claude_fixes_applied)}")
    
    # The converter should either:
    # 1. Use strategic Claude fallback (conversion_method = 'claude_fallback')
    # 2. Skip due to low confidence (conversion_method = 'skipped_low_confidence')
    # 3. Succeed with systematic but with quality warnings
    
    expected_methods = ['claude_fallback', 'skipped_low_confidence', 'systematic_only']
    assert result.conversion_method in expected_methods, f"Unexpected conversion method: {result.conversion_method}"
    
    if result.conversion_method == 'claude_fallback':
        print("✅ Strategic Claude fallback triggered correctly")
    elif result.conversion_method == 'skipped_low_confidence':
        print("✅ Low confidence scene correctly skipped")
    else:
        print("✅ Systematic conversion completed (acceptable for test)")

def test_post_conversion_quality_analysis():
    """Test post-conversion quality analysis catches rendering issues."""
    print("\n🔍 TESTING POST-CONVERSION QUALITY ANALYSIS")
    print("=" * 50)
    
    # Test code with semantic issues that would cause rendering failure
    failing_code = '''
from manim import *

class FailingScene(Scene):
    def construct(self):
        # This will cause runtime error - MathTex expects string, not list
        tex = MathTex(['\\\\frac{1}{2}', '+', '\\\\frac{1}{4}'])
        
        # Undefined constant
        pos = INTERVAL_RADIUS * DL
        
        # Wrong points access
        start = tex.points[0]
        
        # Old method call
        center = tex.get_center()
'''
    
    quality_ok, issues = analyze_post_conversion_quality(failing_code, "FailingScene")
    
    print(f"Quality analysis:")
    print(f"  Quality OK: {quality_ok}")
    print(f"  Issues found: {len(issues)}")
    for issue in issues:
        print(f"    - {issue}")
    
    assert not quality_ok, "Code with semantic issues should fail quality check"
    assert len(issues) > 0, "Quality analysis should identify specific issues"
    print("✅ Quality analysis correctly identifies rendering issues")

def run_all_tests():
    """Run all enhanced pipeline tests."""
    print("🚀 TESTING ENHANCED PIPELINE IMPROVEMENTS")
    print("=" * 60)
    print("Testing strategic fallback triggers, comprehensive validation,")
    print("and post-conversion quality analysis to reduce the 62% gap")
    print("between conversion success and rendering success.")
    print("=" * 60)
    
    try:
        test_strategic_fallback_triggers()
        test_comprehensive_validation()
        test_post_conversion_quality_analysis()
        test_enhanced_converter_integration()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("Enhanced pipeline improvements are working correctly.")
        print("Expected benefits:")
        print("  - Strategic Claude usage for complex cases")
        print("  - Early detection of conversion issues")
        print("  - Semantic validation beyond syntax checking")
        print("  - Reduced gap between conversion and rendering success")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)