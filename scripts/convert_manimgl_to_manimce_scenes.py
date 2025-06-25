#!/usr/bin/env python3
"""
Scene-level ManimGL to ManimCE converter.
This module extends the base converter to support scene-by-scene conversion,
allowing for better error isolation and parallel processing.
"""

import os
import ast
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile

# Import base converter
from convert_manimgl_to_manimce import ManimConverter

# Set up logging
logger = logging.getLogger(__name__)


class SceneConversionTask:
    """Container for a scene conversion task."""
    def __init__(self, scene_name: str, scene_path: Path, video_context: Optional[Dict] = None):
        self.scene_name = scene_name
        self.scene_path = scene_path
        self.video_context = video_context or {}
        self.result = None
        self.error = None


class SceneLevelConverter(ManimConverter):
    """Extended converter that processes scenes individually."""
    
    def __init__(self, source_dir: str, output_dir: str, verbose: bool = False,
                 enable_render_validation: bool = True, render_max_attempts: int = 3,
                 use_advanced_converter: bool = True, intelligent_parsing: bool = True):
        super().__init__(source_dir, output_dir, verbose, enable_render_validation,
                        render_max_attempts, use_advanced_converter, intelligent_parsing)
        
        # Additional setup for scene-level conversion
        self.scene_conversion_log = []
        
    def convert_scene(self, scene_path: Path, scene_name: str, 
                     video_context: Optional[Dict] = None) -> Tuple[str, bool, Dict]:
        """Convert a single scene with focused context.
        
        Returns: (converted_content, success, metadata)
        """
        logger.info(f"Converting scene {scene_name} from {scene_path}")
        
        # Read scene content
        try:
            with open(scene_path, 'r') as f:
                scene_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read scene file: {e}")
            return "", False, {"error": str(e)}
        
        # Use base converter's convert_file logic but with scene-specific content
        # Create a temporary file for conversion
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp.write(scene_content)
            tmp_path = Path(tmp.name)
        
        try:
            # Convert using base converter
            converted_content, success = self.convert_file(tmp_path)
            
            # Add scene-specific metadata
            metadata = {
                "scene_name": scene_name,
                "original_lines": len(scene_content.splitlines()),
                "converted_lines": len(converted_content.splitlines()),
                "conversion_log": self.conversion_log.copy(),
                "issues": [i for i in self.issues if scene_name in str(i.get('file', ''))]
            }
            
            # If video context provided, add it to conversion prompt
            if video_context and self.enable_render_validation:
                metadata["video_context"] = video_context
            
            return converted_content, success, metadata
            
        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
    
    def create_scene_conversion_prompt(self, scene_content: str, scene_name: str,
                                     video_context: Optional[Dict] = None) -> str:
        """Create a focused conversion prompt for a single scene."""
        context_info = ""
        if video_context:
            context_info = f"""
Video Context:
- Video Title: {video_context.get('title', 'Unknown')}
- Video ID: {video_context.get('video_id', 'Unknown')}
- Description: {video_context.get('description', 'N/A')}
- This scene appears at: {video_context.get('timestamp', 'Unknown')}
"""
        
        return f"""Convert this single ManimGL scene to ManimCE.
{context_info}
Scene: {scene_name}

## Key Conversions Required:
1. Import changes: from manimlib → from manim
2. Class renames: TextMobject→Text, TexMobject→MathTex, ShowCreation→Create
3. Method updates: get_width()→.width, get_height()→.height
4. Pi Creatures: Comment out with explanation
5. CONFIG dict: Convert to class attributes or __init__ parameters

## Scene Code:
```python
{scene_content}
```

Convert this scene ensuring it will work independently in ManimCE.
Focus on making the scene render correctly."""
    
    def parallel_convert_scenes(self, scene_tasks: List[SceneConversionTask], 
                              max_workers: int = 4) -> Dict[str, Dict]:
        """Convert multiple scenes in parallel.
        
        Returns dict mapping scene_name to conversion result.
        """
        results = {}
        total_scenes = len(scene_tasks)
        
        logger.info(f"Starting parallel conversion of {total_scenes} scenes with {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._convert_scene_task, task): task 
                for task in scene_tasks
            }
            
            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed += 1
                
                try:
                    result = future.result()
                    results[task.scene_name] = result
                    
                    if result['success']:
                        logger.info(f"[{completed}/{total_scenes}] Successfully converted {task.scene_name}")
                    else:
                        logger.warning(f"[{completed}/{total_scenes}] Failed to convert {task.scene_name}: {result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"[{completed}/{total_scenes}] Exception converting {task.scene_name}: {e}")
                    results[task.scene_name] = {
                        'success': False,
                        'error': str(e),
                        'content': ''
                    }
        
        return results
    
    def _convert_scene_task(self, task: SceneConversionTask) -> Dict:
        """Worker function to convert a single scene task."""
        try:
            converted_content, success, metadata = self.convert_scene(
                task.scene_path, 
                task.scene_name,
                task.video_context
            )
            
            return {
                'success': success,
                'content': converted_content,
                'metadata': metadata,
                'scene_name': task.scene_name
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'content': '',
                'scene_name': task.scene_name
            }
    
    def load_cleaned_scenes(self, video_dir: Path) -> List[SceneConversionTask]:
        """Load all cleaned scenes from a video directory."""
        scenes_dir = video_dir / 'cleaned_scenes'
        if not scenes_dir.exists():
            logger.warning(f"No cleaned_scenes directory found in {video_dir}")
            return []
        
        # Load video context if available
        video_context = {}
        matches_file = video_dir / 'matches.json'
        if matches_file.exists():
            with open(matches_file, 'r') as f:
                match_data = json.load(f)
                video_context = {
                    'video_id': match_data.get('video_id'),
                    'title': match_data.get('title'),
                    'description': match_data.get('description', '')[:200]  # First 200 chars
                }
        
        # Create tasks for each scene file
        tasks = []
        for scene_file in sorted(scenes_dir.glob('*.py')):
            task = SceneConversionTask(
                scene_name=scene_file.stem,
                scene_path=scene_file,
                video_context=video_context
            )
            tasks.append(task)
        
        logger.info(f"Found {len(tasks)} scenes to convert in {video_dir.name}")
        return tasks
    
    def combine_converted_scenes(self, converted_scenes: Dict[str, Dict], 
                               output_file: Path) -> bool:
        """Intelligently combine converted scenes into a single file."""
        if not converted_scenes:
            logger.error("No converted scenes to combine")
            return False
        
        # Separate successful and failed scenes
        successful_scenes = {
            name: data for name, data in converted_scenes.items() 
            if data.get('success') and data.get('content')
        }
        
        if not successful_scenes:
            logger.error("No successfully converted scenes to combine")
            return False
        
        logger.info(f"Combining {len(successful_scenes)} successfully converted scenes")
        
        # Build combined content
        combined_lines = []
        imports_section = set()
        
        # Header
        combined_lines.append("# Combined ManimCE scenes")
        combined_lines.append(f"# Converted on: {datetime.now().isoformat()}")
        combined_lines.append(f"# Total scenes: {len(successful_scenes)}")
        combined_lines.append("")
        
        # First pass: collect all imports
        for scene_name, data in successful_scenes.items():
            content = data['content']
            lines = content.split('\n')
            
            for line in lines:
                if line.strip().startswith(('import ', 'from ')):
                    # Skip module-specific imports that might conflict
                    if 'manimlib' not in line:  # Already converted
                        # Also skip invalid manim imports
                        if ('manim.imports' not in line and 
                            'manim.mobject.svg.old_tex_mobject' not in line and
                            'old_tex_mobject' not in line):
                            imports_section.add(line.strip())
        
        # Always ensure manim import is present
        imports_section.add('from manim import *')
        
        # Add sorted imports
        for imp in sorted(imports_section):
            combined_lines.append(imp)
        
        # Add custom imports if needed
        all_content = '\n'.join(data['content'] for data in successful_scenes.values())
        if 'FlipThroughNumbers' in all_content or 'DelayByOrder' in all_content:
            combined_lines.append("from manimce_custom_animations import *")
        
        combined_lines.append("")
        combined_lines.append("")
        
        # Second pass: add scene content (excluding imports)
        for scene_name, data in sorted(successful_scenes.items()):
            combined_lines.append(f"# {'='*60}")
            combined_lines.append(f"# Scene: {scene_name}")
            if data.get('metadata', {}).get('issues'):
                combined_lines.append(f"# Issues: {len(data['metadata']['issues'])} found during conversion")
            combined_lines.append(f"# {'='*60}")
            combined_lines.append("")
            
            content = data['content']
            lines = content.split('\n')
            
            # Skip imports and empty lines at the beginning
            content_started = False
            for line in lines:
                if not content_started:
                    if line.strip() and not line.strip().startswith(('import ', 'from ', '#')):
                        content_started = True
                
                if content_started or (line.strip() and not line.strip().startswith(('import ', 'from '))):
                    combined_lines.append(line)
            
            combined_lines.append("")
            combined_lines.append("")
        
        # Write combined file
        try:
            combined_content = '\n'.join(combined_lines)
            
            # Validate syntax before writing
            try:
                compile(combined_content, str(output_file), 'exec')
            except SyntaxError as e:
                logger.error(f"Combined content has syntax errors: {e}")
                # Still write it for debugging
            
            with open(output_file, 'w') as f:
                f.write(combined_content)
            
            logger.info(f"Successfully wrote combined file: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write combined file: {e}")
            return False
    
    def convert_video_by_scenes(self, video_dir: Path, max_workers: int = 4) -> Dict:
        """Convert all scenes in a video directory."""
        logger.info(f"Starting scene-by-scene conversion for {video_dir.name}")
        
        # Load scene tasks
        tasks = self.load_cleaned_scenes(video_dir)
        if not tasks:
            return {
                'status': 'no_scenes',
                'error': 'No cleaned scenes found to convert'
            }
        
        # Create output directory for converted scenes
        converted_scenes_dir = video_dir / 'manimce_scenes'
        converted_scenes_dir.mkdir(exist_ok=True)
        
        # Convert scenes in parallel
        conversion_results = self.parallel_convert_scenes(tasks, max_workers)
        
        # Save individual converted scenes
        for scene_name, result in conversion_results.items():
            if result.get('success') and result.get('content'):
                scene_file = converted_scenes_dir / f"{scene_name}.py"
                with open(scene_file, 'w') as f:
                    f.write(result['content'])
        
        # Combine into single file
        output_file = video_dir / 'manimce_code.py'
        combine_success = self.combine_converted_scenes(conversion_results, output_file)
        
        # Generate summary
        successful_scenes = sum(1 for r in conversion_results.values() if r.get('success'))
        failed_scenes = len(conversion_results) - successful_scenes
        
        summary = {
            'status': 'completed' if combine_success else 'partial',
            'total_scenes': len(tasks),
            'successful_scenes': successful_scenes,
            'failed_scenes': failed_scenes,
            'combine_success': combine_success,
            'scene_results': conversion_results,
            'conversion_mode': 'scene'
        }
        
        # Save conversion report
        report_file = converted_scenes_dir / 'conversion_report.json'
        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary


def main():
    """Main entry point for scene-level conversion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert ManimGL code to ManimCE scene by scene')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--video', type=str, required=True,
                        help='Video directory name to convert')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--max-workers', type=int, default=4,
                        help='Maximum parallel workers (default: 4)')
    parser.add_argument('--no-render-validation', action='store_true',
                        help='Disable render validation')
    
    args = parser.parse_args()
    
    # Set up paths
    base_dir = Path(__file__).parent.parent
    video_dir = base_dir / 'outputs' / str(args.year) / args.video
    
    if not video_dir.exists():
        print(f"Video directory not found: {video_dir}")
        return
    
    # Create converter
    converter = SceneLevelConverter(
        source_dir=str(video_dir),
        output_dir=str(video_dir),
        verbose=args.verbose,
        enable_render_validation=not args.no_render_validation,
        use_advanced_converter=True
    )
    
    # Run conversion
    result = converter.convert_video_by_scenes(video_dir, max_workers=args.max_workers)
    
    print(f"\nConversion Summary:")
    print(f"Status: {result['status']}")
    print(f"Total scenes: {result.get('total_scenes', 0)}")
    print(f"Successful: {result.get('successful_scenes', 0)}")
    print(f"Failed: {result.get('failed_scenes', 0)}")
    print(f"Combined file created: {result.get('combine_success', False)}")


if __name__ == '__main__':
    main()