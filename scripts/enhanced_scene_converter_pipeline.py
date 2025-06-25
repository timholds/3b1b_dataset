#!/usr/bin/env python3
"""
Enhanced Scene Converter Pipeline - Integrates dependency analysis and validation

This module replaces the basic scene-by-scene conversion with an enhanced version
that includes real-time dependency analysis and scene-level render validation.
"""

import ast
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import our enhanced converter
from enhanced_scene_converter import EnhancedSceneConverter

logger = logging.getLogger(__name__)


class EnhancedScenePipeline:
    """
    Enhanced scene conversion pipeline that integrates dependency analysis,
    conversion, and validation into a unified workflow.
    """
    
    def __init__(self, verbose: bool = False, enable_render_validation: bool = True,
                 enable_precompile_validation: bool = True, render_timeout: int = 30,
                 enable_claude_fixes: bool = True, max_fix_attempts: int = 3):
        self.verbose = verbose
        self.enable_render_validation = enable_render_validation
        self.enable_precompile_validation = enable_precompile_validation
        self.render_timeout = render_timeout
        self.enable_claude_fixes = enable_claude_fixes
        self.max_fix_attempts = max_fix_attempts
        
        # Initialize enhanced converter
        self.converter = EnhancedSceneConverter(
            enable_render_validation=enable_render_validation,
            enable_precompile_validation=enable_precompile_validation,
            verbose=verbose,
            render_timeout=render_timeout,
            enable_claude_fixes=enable_claude_fixes,
            max_fix_attempts=max_fix_attempts
        )
        
        logger.info(f"Enhanced Scene Pipeline initialized (render={enable_render_validation}, precompile={enable_precompile_validation}, claude_fixes={enable_claude_fixes})")
    
    def process_video_scenes(self, video_dir: Path, full_code_content: str, 
                           video_name: str = "") -> Dict[str, Any]:
        """
        Process all scenes in a video directory with enhanced conversion.
        
        Args:
            video_dir: Directory containing cleaned scene files
            full_code_content: Complete cleaned code for dependency analysis
            video_name: Name of the video for metadata
            
        Returns:
            Dict with comprehensive processing results
        """
        start_time = time.time()
        
        # Find scene files
        cleaned_scenes_dir = video_dir / 'cleaned_scenes'
        if not cleaned_scenes_dir.exists():
            logger.error(f"No cleaned_scenes directory found in {video_dir}")
            return {'status': 'error', 'message': 'No cleaned scenes found'}
        
        scene_files = list(cleaned_scenes_dir.glob('*.py'))
        if not scene_files:
            logger.error(f"No scene files found in {cleaned_scenes_dir}")
            return {'status': 'error', 'message': 'No scene files found'}
        
        logger.info(f"Found {len(scene_files)} scene files in {video_name}")
        
        # Parse full code AST for dependency analysis
        try:
            full_ast = ast.parse(full_code_content)
        except SyntaxError as e:
            logger.error(f"Failed to parse full code AST: {e}")
            return {'status': 'error', 'message': f'AST parse error: {str(e)}'}
        
        # Process each scene
        scene_results = {}
        successful_scenes = 0
        failed_scenes = 0
        total_dependencies = {'functions': 0, 'classes': 0, 'constants': 0}
        
        # Create output directory for validation artifacts
        validation_output_dir = video_dir / 'enhanced_validation'
        validation_output_dir.mkdir(exist_ok=True)
        
        for scene_file in sorted(scene_files):
            scene_name = scene_file.stem
            logger.info(f"Processing scene: {scene_name}")
            
            try:
                # Read scene content
                with open(scene_file, 'r', encoding='utf-8') as f:
                    scene_content = f.read()
                
                # Process scene with enhanced converter
                result = self.converter.process_scene(
                    scene_name=scene_name,
                    scene_content=scene_content,
                    full_module_ast=full_ast,
                    video_name=video_name,
                    output_dir=validation_output_dir
                )
                
                scene_results[scene_name] = result
                
                # Update counters
                if result['success']:
                    successful_scenes += 1
                else:
                    failed_scenes += 1
                
                # Aggregate dependency counts
                deps = result['dependencies']
                total_dependencies['functions'] += deps['function_count']
                total_dependencies['classes'] += deps['class_count']
                total_dependencies['constants'] += deps['constant_count']
                
                # Log results
                status = "✅" if result['success'] else "❌"
                precompile_status = "✅" if result['validation']['precompile']['success'] else "❌"
                render_status = "✅" if result['validation']['render']['success'] else "❌"
                
                logger.info(f"{status} {scene_name}: {deps['function_count']}f, {deps['constant_count']}c, {deps['class_count']}cl | Precompile: {precompile_status} | Render: {render_status}")
                
            except Exception as e:
                logger.error(f"Failed to process scene {scene_name}: {e}")
                scene_results[scene_name] = {
                    'scene_name': scene_name,
                    'success': False,
                    'error': str(e)
                }
                failed_scenes += 1
        
        # Generate enhanced snippets directory
        snippets_dir = video_dir / 'enhanced_snippets'
        snippets_dir.mkdir(exist_ok=True)
        
        # Save self-contained snippets
        for scene_name, result in scene_results.items():
            if result.get('snippet'):
                snippet_file = snippets_dir / f"{scene_name}.py"
                with open(snippet_file, 'w', encoding='utf-8') as f:
                    f.write(result['snippet'])
                
                # Save metadata
                metadata_file = snippets_dir / f"{scene_name}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(result.get('metadata', {}), f, indent=2)
        
        # Combine successful scenes (if any)
        combined_success = False
        combined_content = ""
        
        if successful_scenes > 0:
            combined_content = self._combine_converted_scenes(scene_results, video_name)
            if combined_content:
                combined_file = video_dir / 'manimce_code_enhanced.py'
                with open(combined_file, 'w', encoding='utf-8') as f:
                    f.write(combined_content)
                combined_success = True
                logger.info(f"Combined {successful_scenes} scenes into manimce_code_enhanced.py")
        
        # Generate comprehensive report
        total_time = time.time() - start_time
        
        report = {
            'status': 'completed',
            'video_name': video_name,
            'processing_time': total_time,
            'scene_summary': {
                'total_scenes': len(scene_files),
                'successful_scenes': successful_scenes,
                'failed_scenes': failed_scenes,
                'success_rate': successful_scenes / len(scene_files) if scene_files else 0
            },
            'dependency_summary': total_dependencies,
            'validation_summary': {
                'precompile_passed': sum(1 for r in scene_results.values() 
                                       if r.get('validation', {}).get('precompile', {}).get('success', False)),
                'render_passed': sum(1 for r in scene_results.values() 
                                   if r.get('validation', {}).get('render', {}).get('success', False))
            },
            'scene_results': scene_results,
            'combined_success': combined_success,
            'output_files': {
                'snippets_dir': str(snippets_dir),
                'validation_dir': str(validation_output_dir),
                'combined_file': str(video_dir / 'manimce_code_enhanced.py') if combined_success else None
            }
        }
        
        # Save report
        report_file = video_dir / 'enhanced_conversion_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Enhanced processing complete: {successful_scenes}/{len(scene_files)} scenes successful")
        logger.info(f"Dependencies found: {total_dependencies['functions']} functions, {total_dependencies['constants']} constants, {total_dependencies['classes']} classes")
        
        return report
    
    def _combine_converted_scenes(self, scene_results: Dict[str, Any], video_name: str) -> str:
        """Combine successful scene conversions into a single file."""
        try:
            parts = []
            
            # Header
            parts.append(f"# Enhanced ManimCE conversion for {video_name}")
            parts.append(f"# Generated by Enhanced Scene Converter Pipeline")
            parts.append(f"# Includes dependency analysis and validation")
            parts.append("")
            
            # Collect all imports, functions, constants, and classes
            all_imports = set(['from manim import *'])
            all_constants = {}
            all_functions = {}
            all_classes = {}
            scene_contents = []
            
            for scene_name, result in scene_results.items():
                if not result.get('success', False):
                    continue
                
                snippet = result.get('snippet', '')
                if not snippet:
                    continue
                
                # Parse snippet to extract components
                try:
                    snippet_ast = ast.parse(snippet)
                    for node in snippet_ast.body:
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            import_str = ast.unparse(node)
                            if 'from manim import' not in import_str:
                                all_imports.add(import_str)
                        elif isinstance(node, ast.FunctionDef):
                            all_functions[node.name] = ast.unparse(node)
                        elif isinstance(node, ast.ClassDef):
                            if not node.name.endswith('Scene'):  # Don't include scene classes here
                                all_classes[node.name] = ast.unparse(node)
                            else:
                                scene_contents.append(ast.unparse(node))
                        elif isinstance(node, ast.Assign):
                            # Constants
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    all_constants[target.id] = ast.unparse(node)
                
                except Exception as e:
                    logger.warning(f"Failed to parse snippet for {scene_name}: {e}")
                    # Fallback: just include the converted content
                    converted_content = result.get('converted_content', '')
                    if converted_content:
                        scene_contents.append(converted_content)
            
            # Build combined file
            # Imports
            for import_stmt in sorted(all_imports):
                parts.append(import_stmt)
            parts.append("")
            
            # Constants
            if all_constants:
                parts.append("# Constants")
                for const_code in all_constants.values():
                    parts.append(const_code)
                parts.append("")
            
            # Functions
            if all_functions:
                parts.append("# Helper functions")
                for func_code in all_functions.values():
                    parts.append(func_code)
                    parts.append("")
            
            # Classes (non-scene)
            if all_classes:
                parts.append("# Helper classes")
                for class_code in all_classes.values():
                    parts.append(class_code)
                    parts.append("")
            
            # Scenes
            if scene_contents:
                parts.append("# Scenes")
                for scene_code in scene_contents:
                    parts.append(scene_code)
                    parts.append("")
            
            return '\n'.join(parts)
            
        except Exception as e:
            logger.error(f"Failed to combine scenes: {e}")
            return ""


def test_enhanced_pipeline():
    """Test the enhanced pipeline with inventing-math data."""
    
    # Set up paths
    video_dir = Path("outputs/2015/inventing-math")
    if not video_dir.exists():
        print(f"Video directory not found: {video_dir}")
        return
    
    # Read full cleaned code
    cleaned_code_file = video_dir / "cleaned_code.py"
    if not cleaned_code_file.exists():
        print(f"Cleaned code file not found: {cleaned_code_file}")
        return
    
    with open(cleaned_code_file, 'r', encoding='utf-8') as f:
        full_code = f.read()
    
    # Initialize pipeline
    pipeline = EnhancedScenePipeline(
        verbose=True,
        enable_render_validation=True,
        enable_precompile_validation=True
    )
    
    print("Testing Enhanced Scene Pipeline...")
    print("=" * 60)
    
    # Process scenes
    result = pipeline.process_video_scenes(
        video_dir=video_dir,
        full_code_content=full_code,
        video_name="inventing-math"
    )
    
    # Display results
    print(f"\n🎬 Video: {result['video_name']}")
    print(f"⏱️  Processing Time: {result['processing_time']:.2f}s")
    
    summary = result['scene_summary']
    print(f"📊 Scene Summary:")
    print(f"   - Total: {summary['total_scenes']}")
    print(f"   - Successful: {summary['successful_scenes']}")
    print(f"   - Failed: {summary['failed_scenes']}")
    print(f"   - Success Rate: {summary['success_rate']:.1%}")
    
    deps = result['dependency_summary']
    print(f"🔗 Dependencies Found:")
    print(f"   - Functions: {deps['functions']}")
    print(f"   - Constants: {deps['constants']}")
    print(f"   - Classes: {deps['classes']}")
    
    validation = result['validation_summary']
    print(f"✅ Validation Results:")
    print(f"   - Precompile Passed: {validation['precompile_passed']}/{summary['total_scenes']}")
    print(f"   - Render Passed: {validation['render_passed']}/{summary['total_scenes']}")
    
    print(f"📁 Output Files:")
    outputs = result['output_files']
    for key, path in outputs.items():
        if path:
            print(f"   - {key}: {path}")
    
    return result


if __name__ == "__main__":
    test_enhanced_pipeline()