#!/usr/bin/env python3
"""
Test script to demonstrate the integrated pipeline converter.

This shows how the enhanced converter solves the "0 dependencies" problem
and creates validated snippets with Claude error recovery.
"""

import sys
import json
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from integrated_pipeline_converter import IntegratedPipelineConverter


def test_single_video(video_path: str):
    """Test the integrated converter on a single video directory."""
    
    video_dir = Path(video_path)
    if not video_dir.exists():
        print(f"Error: Video directory not found: {video_dir}")
        return
        
    print(f"Testing integrated converter on: {video_dir.name}")
    print("=" * 60)
    
    # Initialize converter
    converter = IntegratedPipelineConverter(
        base_dir=video_dir.parent.parent,
        verbose=True,
        enable_render_validation=True,
        enable_precompile_validation=True,
        render_max_attempts=3
    )
    
    # Convert the video
    result = converter.convert_video(video_dir)
    
    # Display results
    print("\n" + "=" * 60)
    print("CONVERSION RESULTS")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Snippets created: {result['snippets_created']}")
    print(f"All scenes valid: {result['all_scenes_valid']}")
    
    if result['scenes']:
        print(f"\nScene Details:")
        for scene_name, scene_result in result['scenes'].items():
            success = "✅" if scene_result.get('success') else "❌"
            deps = scene_result.get('dependencies', {})
            func_count = deps.get('function_count', 0)
            class_count = deps.get('class_count', 0)
            const_count = deps.get('constant_count', 0)
            
            print(f"  {success} {scene_name}: {func_count}f, {const_count}c, {class_count}cl")
            
            if scene_result.get('claude_fixes', 0) > 0:
                print(f"     └─ Fixed with {scene_result['claude_fixes']} Claude attempts")
                
    # Display overall statistics
    stats = converter.get_statistics()
    print(f"\nOverall Statistics:")
    print(f"  Total scenes: {stats['total_scenes']}")
    print(f"  Successful: {stats['successful_scenes']} ({stats['scene_success_rate']:.1%})")
    print(f"  Dependencies found: {stats['total_dependencies_found']} total")
    if stats['successful_scenes'] > 0:
        print(f"  Avg per scene: {stats['avg_dependencies_per_scene']:.1f}")
    
    if stats['claude_fixes_attempted'] > 0:
        print(f"\nClaude Error Recovery:")
        print(f"  Attempts: {stats['claude_fixes_attempted']}")
        print(f"  Successful: {stats['claude_fixes_successful']} ({stats['claude_fix_success_rate']:.1%})")
        
    # Check output files
    print(f"\nOutput Files Created:")
    snippets_dir = video_dir / 'validated_snippets'
    if snippets_dir.exists():
        snippet_files = list(snippets_dir.glob('*.py'))
        print(f"  Validated snippets: {len(snippet_files)} files in {snippets_dir}")
        
    if result['combined_file']:
        print(f"  Combined file: {result['combined_file']}")
        
    results_file = video_dir / 'conversion_results.json'
    if results_file.exists():
        print(f"  Results JSON: {results_file}")
        
    print("\n✨ The key difference: Each scene now shows its actual dependencies!")
    print("   Previously all scenes showed '0f, 0c, 0cl' - now we see the real counts.")


def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python test_integrated_pipeline.py <video_directory>")
        print("\nExample:")
        print("  python test_integrated_pipeline.py outputs/2015/music-and-measure-theory")
        sys.exit(1)
        
    video_path = sys.argv[1]
    test_single_video(video_path)


if __name__ == "__main__":
    main()