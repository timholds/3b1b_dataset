#!/usr/bin/env python3
"""
Test the enhanced scene converter with real scene data from inventing-math.
"""

import ast
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from enhanced_scene_converter import EnhancedSceneConverter

def test_with_real_scene():
    """Test with actual DivergentSum scene that has dependencies."""
    
    # Read the cleaned scene file
    scene_file = Path("outputs/2015/inventing-math/cleaned_scenes/DivergentSum.py")
    if not scene_file.exists():
        print(f"Scene file not found: {scene_file}")
        return
        
    with open(scene_file, 'r') as f:
        scene_content = f.read()
    
    # Read the full cleaned code to get complete AST
    full_code_file = Path("outputs/2015/inventing-math/cleaned_code.py")
    if not full_code_file.exists():
        print(f"Full code file not found: {full_code_file}")
        return
        
    with open(full_code_file, 'r') as f:
        full_code = f.read()
    
    try:
        # Parse full module AST for dependency analysis
        full_ast = ast.parse(full_code)
        
        # Initialize enhanced converter
        converter = EnhancedSceneConverter(
            enable_render_validation=True,
            enable_precompile_validation=True,
            verbose=True
        )
        
        print("Testing Enhanced Scene Converter with DivergentSum scene...")
        print("=" * 60)
        
        # Process the scene
        result = converter.process_scene(
            scene_name="DivergentSum",
            scene_content=scene_content,
            full_module_ast=full_ast,
            video_name="inventing-math",
            output_dir=Path("test_output")
        )
        
        # Display results
        print(f"\n🎬 Scene: {result['scene_name']}")
        print(f"✅ Overall Success: {result['success']}")
        print(f"📊 Dependencies Found:")
        deps = result['dependencies']
        print(f"   - Functions: {deps['function_count']} {deps['functions']}")
        print(f"   - Constants: {deps['constant_count']} {deps['constants']}")
        print(f"   - Classes: {deps['class_count']} {deps['classes']}")
        print(f"   - Base Classes: {deps['base_classes']}")
        
        print(f"\n🔍 Validation Results:")
        precompile = result['validation']['precompile']
        render = result['validation']['render']
        print(f"   - Precompile: {'✅' if precompile['success'] else '❌'} ({precompile.get('errors', 0)} errors)")
        print(f"   - Render: {'✅' if render['success'] else '❌'} ({render.get('render_time', 0):.2f}s)")
        
        if render.get('error'):
            print(f"   - Render Error: {render['error']}")
            
        print(f"\n📈 Metadata:")
        meta = result['metadata']
        print(f"   - Original Lines: {meta['original_lines']}")
        print(f"   - Converted Lines: {meta['converted_lines']}")
        print(f"   - Processing Time: {meta['processing_time']:.2f}s")
        
        if result['errors']:
            print(f"\n❌ Errors:")
            for error in result['errors']:
                print(f"   - {error}")
        
        # Show a sample of the generated snippet
        snippet = result['snippet']
        print(f"\n📝 Generated Snippet (first 500 chars):")
        print("-" * 50)
        print(snippet[:500] + "..." if len(snippet) > 500 else snippet)
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_with_real_scene()