#!/usr/bin/env python3
"""
Programmatic code cleaner for 3Blue1Brown dataset.
This module performs fast, deterministic cleaning by mechanically inlining imports
and creating self-contained ManimGL scripts without AI assistance.
"""

import ast
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Union
from dataclasses import dataclass
import re

# Import existing analyzers
from scene_dependency_analyzer import (
    AdvancedDependencyAnalyzer, 
    DependencyInfo,
    extract_code_for_dependencies,
    find_node_end_line
)

logger = logging.getLogger(__name__)


@dataclass 
class CleaningResult:
    """Result of programmatic cleaning attempt."""
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    scenes_processed: int = 0
    dependencies_found: int = 0
    files_inlined: int = 0
    fallback_needed: bool = False


class ProgrammaticCleaner:
    """
    Fast, deterministic code cleaner that uses AST analysis to mechanically
    inline imports and create self-contained ManimGL scripts.
    """
    
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'outputs'
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        if verbose:
            self.logger.setLevel(logging.INFO)
        
        # Track statistics
        self.stats = {
            'files_processed': 0,
            'scenes_extracted': 0,
            'scene_count': 0,
            'total_cleaning_time': 0.0,
            'dependencies_resolved': 0,
            'imports_inlined': 0,
            'duplicates_removed': 0
        }
    
    def _add_deduplicated_import(self, all_imports: Set[str], import_line: str) -> None:
        """
        Add import to set with intelligent deduplication to prevent circular references.
        
        Priority order (highest to lowest):
        1. from manim_imports_ext import *
        2. from manimlib.imports import *  
        3. from manimlib import *
        4. Specific imports (import x, from x import y)
        """
        import_line = import_line.strip()
        
        # Check if we already have a higher priority import
        existing_imports = list(all_imports)
        
        # Priority 1: manim_imports_ext (highest priority)
        if "manim_imports_ext" in import_line and "import *" in import_line:
            # Remove any conflicting manimlib imports
            conflicting = [imp for imp in existing_imports if "manimlib" in imp and "import *" in imp]
            for imp in conflicting:
                all_imports.discard(imp)
            all_imports.add(import_line)
            return
            
        # Don't add manimlib imports if we already have manim_imports_ext
        if "manimlib" in import_line and "import *" in import_line:
            has_manim_imports_ext = any("manim_imports_ext" in imp and "import *" in imp for imp in existing_imports)
            if has_manim_imports_ext:
                return
                
            # Priority 2: from manimlib.imports import * (over from manimlib import *)
            if "manimlib.imports" in import_line:
                # Remove lower priority manimlib imports
                conflicting = [imp for imp in existing_imports if imp.startswith("from manimlib import *")]
                for imp in conflicting:
                    all_imports.discard(imp)
                all_imports.add(import_line)
                return
            elif "from manimlib import *" in import_line:
                # Don't add if we already have manimlib.imports
                has_manimlib_imports = any("manimlib.imports" in imp for imp in existing_imports)
                if not has_manimlib_imports:
                    all_imports.add(import_line)
                return
        
        # For specific imports (non-wildcard), always add
        all_imports.add(import_line)
    
    def clean_video_files(self, video_id: str, caption_dir: str, match_data: Dict, year: int) -> CleaningResult:
        """
        Clean matched code files for a video using programmatic approach.
        
        Args:
            video_id: YouTube video ID
            caption_dir: Caption directory name
            match_data: Matching results from claude_match_videos
            year: Year of the video
            
        Returns:
            CleaningResult with success status and details
        """
        try:
            start_time = time.time()
            self.logger.info(f"Starting programmatic cleaning for {caption_dir}")
            
            # Get file paths
            primary_files = match_data.get('primary_files', [])
            supporting_files = match_data.get('supporting_files', [])
            all_files = primary_files + supporting_files
            
            if not all_files:
                return CleaningResult(
                    success=False,
                    error="No files to process"
                )
            
            # Early file size check - avoid processing large files
            total_size = 0
            for file_path in all_files:
                full_path = self._resolve_file_path(file_path, year)
                if full_path.exists():
                    total_size += full_path.stat().st_size
            
            # Programmatic cleaner works best on smaller files
            MAX_SIZE = 500_000  # 500KB limit
            if total_size > MAX_SIZE:
                return CleaningResult(
                    success=False,
                    error=f"Files too large for programmatic cleaning: {total_size:,} bytes > {MAX_SIZE:,} bytes",
                    fallback_needed=True
                )
            
            # Setup output paths
            video_dir = self.output_dir / str(year) / caption_dir
            video_dir.mkdir(parents=True, exist_ok=True)
            output_file = video_dir / 'monolith_manimgl.py'
            scenes_dir = video_dir / 'cleaned_scenes'
            scenes_dir.mkdir(parents=True, exist_ok=True)
            
            # Load and parse all source files
            file_contents = {}
            file_asts = {}
            
            for file_path in all_files:
                full_path = self._resolve_file_path(file_path, year)
                self.logger.debug(f"Resolving path: {file_path} -> {full_path}")
                if not full_path.exists():
                    self.logger.warning(f"File not found: {full_path}")
                    continue
                
                # Validate syntax before attempting to process
                if not self._validate_file_syntax(full_path):
                    self.logger.warning(f"Syntax error in source file: {full_path}")
                    return CleaningResult(
                        success=False,
                        error=f"Syntax error in source file: {file_path}",
                        fallback_needed=True
                    )
                    
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse AST
                    file_ast = ast.parse(content, filename=str(full_path))
                    file_contents[str(full_path)] = content.splitlines()
                    file_asts[str(full_path)] = file_ast
                    
                    self.stats['files_processed'] += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error parsing {full_path}: {e}")
                    continue
            
            if not file_contents:
                return CleaningResult(
                    success=False, 
                    error="No valid files could be parsed",
                    fallback_needed=True  # This should trigger Claude fallback
                )
            
            # Extract scenes from all files
            all_scenes = self._extract_all_scenes(file_asts, file_contents)
            
            if not all_scenes:
                # No scenes found - fall back to Claude
                return CleaningResult(
                    success=False,
                    error="No scenes found - complex file structure",
                    fallback_needed=True
                )
            
            # Process each scene individually
            scene_files = []
            total_dependencies = 0
            
            for scene_name, scene_info in all_scenes.items():
                scene_result = self._clean_single_scene(
                    scene_name, scene_info, file_asts, file_contents, scenes_dir
                )
                
                if scene_result:
                    scene_files.append(scene_result['file_path'])
                    total_dependencies += scene_result['dependencies_count']
                    self.stats['scenes_extracted'] += 1
            
            # Update aggregated statistics
            self.stats['scene_count'] += len(all_scenes)
            self.stats['total_cleaning_time'] += time.time() - start_time
            
            # Combine all scene files into monolith
            if scene_files:
                try:
                    self._combine_scene_files(scene_files, output_file, video_id, year)
                except SyntaxError as e:
                    return CleaningResult(
                        success=False,
                        error=f"Syntax error in combined output: {e}",
                        fallback_needed=True
                    )
            else:
                return CleaningResult(
                    success=False,
                    error="No scenes could be processed",
                    fallback_needed=True
                )
            
            return CleaningResult(
                success=True,
                output_path=output_file,
                scenes_processed=len(scene_files),
                dependencies_found=total_dependencies,
                files_inlined=len(file_contents)
            )
            
        except Exception as e:
            self.logger.error(f"Programmatic cleaning failed for {caption_dir}: {e}")
            return CleaningResult(
                success=False,
                error=str(e),
                fallback_needed=True
            )
    
    def _validate_file_syntax(self, file_path: Path) -> bool:
        """Validate that a file has valid Python syntax before processing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            return True
        except (SyntaxError, UnicodeDecodeError, OSError):
            return False
    
    def _resolve_file_path(self, file_path: str, year: int) -> Path:
        """Resolve relative file path to absolute path."""
        if file_path.startswith('/'):
            return Path(file_path)
        
        # Check if file_path already includes the expected prefix
        expected_prefix = f'data/videos/_{year}/'
        if file_path.startswith(expected_prefix):
            # File path already includes the full path from project root
            return self.base_dir / file_path
        elif file_path.startswith('data/videos/'):
            # File path starts with data/videos but may have different year format
            return self.base_dir / file_path
        elif file_path.startswith(f'_{year}/'):
            # File path starts with year directory directly (e.g., "_2016/eola/chapter11.py")
            return self.base_dir / 'data' / 'videos' / file_path
        else:
            # File path is relative to the year directory
            return self.base_dir / 'data' / 'videos' / f'_{year}' / file_path
    
    def _extract_all_scenes(self, file_asts: Dict[str, ast.Module], 
                           file_contents: Dict[str, List[str]]) -> Dict[str, Dict]:
        """Extract all scene classes from parsed files."""
        scenes = {}
        
        for file_path, file_ast in file_asts.items():
            for node in ast.walk(file_ast):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a scene class
                    if self._is_scene_class(node):
                        scenes[node.name] = {
                            'node': node,
                            'file_path': file_path,
                            'file_ast': file_ast,
                            'source_lines': file_contents[file_path]
                        }
        
        return scenes
    
    def _is_scene_class(self, node: ast.ClassDef) -> bool:
        """Determine if a class is a scene class."""
        # Check if class name ends with Scene
        if node.name.endswith('Scene'):
            return True
        
        # Check for common 3b1b scene types that don't follow pattern
        special_scenes = {
            'RearrangeEquation', 'TransformByGlowingDot', 'MovingCameraScene',
            'ZoomedScene', 'ReconfigurableScene', 'InteractiveScene', 
            'TeacherStudentsScene', 'PiCreatureScene', 'GraphScene',
            'ThreeDScene', 'SpecialThreeDScene', 'SampleSpaceScene',
            'ProbabilityScene', 'NumberlineScene', 'ComplexPlaneScene'
        }
        if node.name in special_scenes:
            return True
        
        # Check if it inherits from scene-like classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                if 'Scene' in base.id:
                    return True
        
        return False
    
    def _clean_single_scene(self, scene_name: str, scene_info: Dict,
                           file_asts: Dict[str, ast.Module], 
                           file_contents: Dict[str, List[str]],
                           scenes_dir: Path) -> Optional[Dict]:
        """Clean a single scene and create self-contained file."""
        try:
            scene_node = scene_info['node']
            primary_ast = scene_info['file_ast']
            primary_source = scene_info['source_lines']
            
            # Load import resolver if available
            import_resolver = None
            symbol_index_path = self.base_dir / 'data' / 'symbol_index.json'
            if symbol_index_path.exists():
                from import_resolver import ImportResolver
                import_resolver = ImportResolver(symbol_index_path)
            
            # Analyze dependencies with cross-file support
            analyzer = AdvancedDependencyAnalyzer(
                scene_node, primary_ast, file_asts, file_contents,
                import_resolver=import_resolver,
                current_file_path=scene_info['file_path']
            )
            dependencies = analyzer.analyze()
            
            # Extract scene code
            scene_start = scene_node.lineno - 1
            scene_end = find_node_end_line(scene_node, primary_source)
            scene_code = '\n'.join(primary_source[scene_start:scene_end])
            
            # Build complete file content
            output_lines = []
            
            # Add header
            output_lines.extend([
                f'"""',
                f'Self-contained scene: {scene_name}',
                f'Generated by programmatic cleaner',
                f'Dependencies: {len(dependencies.functions)} functions, {len(dependencies.classes)} classes, {len(dependencies.constants)} constants',
                f'"""',
                ''
            ])
            
            # Add imports (external only - no local imports)
            external_imports = self._extract_external_imports(primary_ast)
            if external_imports:
                output_lines.extend(external_imports)
                output_lines.append('')
            
            # Use the enhanced extract_code_for_dependencies that supports cross-file
            extracted_deps = extract_code_for_dependencies(
                primary_ast, primary_source, dependencies, file_asts, file_contents
            )
            
            # Add constants
            if extracted_deps['constants']:
                output_lines.append('# Constants')
                output_lines.extend(extracted_deps['constants'])
                output_lines.append('')
            
            # Add helper functions
            if extracted_deps['functions']:
                output_lines.append('# Helper Functions')
                output_lines.extend(extracted_deps['functions'])
                output_lines.append('')
            
            # Add helper classes
            if extracted_deps['classes']:
                output_lines.append('# Helper Classes')
                output_lines.extend(extracted_deps['classes'])
                output_lines.append('')
            
            # Add the scene itself
            output_lines.append(scene_code)
            
            # Write to file
            scene_file = scenes_dir / f'{scene_name}.py'
            with open(scene_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            
            # Validate syntax
            try:
                compile('\n'.join(output_lines), str(scene_file), 'exec')
            except SyntaxError as e:
                self.logger.warning(f"Syntax error in {scene_name}: {e}")
                return None
            
            return {
                'file_path': scene_file,
                'dependencies_count': len(dependencies.functions) + len(dependencies.classes) + len(dependencies.constants)
            }
            
        except Exception as e:
            self.logger.warning(f"Error cleaning scene {scene_name}: {e}")
            return None
    
    def _extract_external_imports(self, file_ast: ast.Module) -> List[str]:
        """Extract external imports (non-local imports)."""
        imports = []
        
        for node in file_ast.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Skip relative imports
                    if not alias.name.startswith('.'):
                        import_str = f"import {alias.name}"
                        if alias.asname:
                            import_str += f" as {alias.asname}"
                        imports.append(import_str)
                        
            elif isinstance(node, ast.ImportFrom):
                # Skip relative imports and local file imports
                if node.module and not node.module.startswith('.'):
                    # Include imports from known external libraries
                    external_modules = {
                        'numpy', 'scipy', 'matplotlib', 'sympy', 'random', 'math', 
                        'os', 'sys', 'pathlib', 'collections', 'itertools',
                        'manimlib', 'manim'  # Manim imports
                    }
                    
                    if any(node.module.startswith(ext) for ext in external_modules):
                        for alias in node.names:
                            if alias.name == '*':
                                imports.append(f"from {node.module} import *")
                            else:
                                import_str = f"from {node.module} import {alias.name}"
                                if alias.asname:
                                    import_str += f" as {alias.asname}"
                                imports.append(import_str)
        
        return imports
    
    
    def _combine_scene_files(self, scene_files: List[Path], output_file: Path,
                            video_id: str, year: int):
        """Combine individual scene files into monolithic file using simple concatenation."""
        combined_lines = []
        
        # Add header
        combined_lines.extend([
            f'"""',
            f'Combined ManimGL code for video {video_id}',
            f'Year: {year}',
            f'Generated by programmatic cleaner',
            f'Contains {len(scene_files)} scenes',
            f'"""',
            ''
        ])
        
        # Collect unique imports from all scene files
        all_imports = set()
        scene_contents = []
        
        # Track if we found any manim imports
        has_manim_import = False
        
        for scene_file in scene_files:
            with open(scene_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.splitlines()
            
            # Extract imports (only from the top of file, before any other content)
            in_header = True
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('"""'):
                    continue
                elif line.startswith(('import ', 'from ')) and in_header:
                    # Only add if it looks like a valid import (no special characters)
                    if '$' not in line and '{' not in line and '}' not in line:
                        # Keep original ManimGL imports (DO NOT convert to ManimCE)
                        if 'from manim_imports_ext import' in line or 'from manimlib' in line or 'import manimlib' in line:
                            has_manim_import = True
                        all_imports.add(line)
                elif line and not line.startswith(('import ', 'from ')):
                    # Hit non-import content, stop looking for imports
                    in_header = False
            
            # Find where the actual content starts (after imports and comments)
            content_start = 0
            in_docstring = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Handle docstrings
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                        # Single line docstring, skip it
                        continue
                    else:
                        # Multi-line docstring start/end
                        in_docstring = not in_docstring
                        continue
                
                if in_docstring:
                    continue
                    
                # Skip empty lines, comments, imports
                if (not stripped or 
                    stripped.startswith('#') or
                    stripped.startswith('import ') or
                    stripped.startswith('from ') or
                    stripped.startswith('Self-contained') or
                    stripped.startswith('Generated by') or
                    stripped.startswith('Dependencies:')):
                    continue
                
                # Found actual content (class, def, constants)
                if (stripped.startswith(('class ', 'def ')) or
                    ('=' in stripped and not stripped.startswith('#'))):
                    content_start = i
                    break
            
            # Get the content part (helper classes and scene)
            content_part = '\n'.join(lines[content_start:])
            if content_part.strip():
                scene_contents.append(content_part)
        
        # Ensure we have essential imports
        if not has_manim_import and not any('manim' in imp for imp in all_imports):
            # If no manim imports found, add the default
            all_imports.add('from manim_imports_ext import *')
        
        # Always ensure numpy is imported if used in any scene
        if any('np.' in content for content in scene_contents) and not any('numpy' in imp for imp in all_imports):
            all_imports.add('import numpy as np')
        
        # Add common standard library imports if used
        if any('it.' in content for content in scene_contents) and not any('itertools' in imp for imp in all_imports):
            all_imports.add('import itertools as it')
        
        if any('os.' in content for content in scene_contents) and not any('import os' in imp for imp in all_imports):
            all_imports.add('import os')
            
        # Build final file
        if all_imports:
            # Sort imports with manim imports first
            manim_imports = [imp for imp in all_imports if 'manim' in imp]
            other_imports = [imp for imp in all_imports if 'manim' not in imp]
            
            # Add imports in proper order
            if manim_imports:
                combined_lines.extend(sorted(manim_imports))
            if other_imports:
                combined_lines.extend(sorted(other_imports))
            combined_lines.append('')
        
        # Add all scene contents
        for content in scene_contents:
            combined_lines.append(content)
            combined_lines.append('')
        
        # Write combined file
        final_content = '\n'.join(combined_lines)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        # Validate syntax
        try:
            compile(final_content, str(output_file), 'exec')
            self.logger.info(f"Successfully created monolithic file: {output_file}")
        except SyntaxError as e:
            self.logger.error(f"Syntax error in combined file: {e}")
            # Remove the invalid file to trigger fallback
            if output_file.exists():
                output_file.unlink()
            raise SyntaxError(f"Programmatic cleaning produced invalid syntax: {e}") from e
    


def test_programmatic_cleaner():
    """Test the programmatic cleaner on a sample video."""
    cleaner = ProgrammaticCleaner('/path/to/3b1b_dataset', verbose=True)
    
    # Mock match data
    match_data = {
        'primary_files': ['some_file.py'],
        'supporting_files': ['helper.py']
    }
    
    result = cleaner.clean_video_files('test_id', 'test_video', match_data, 2015)
    print(f"Cleaning result: {result}")


if __name__ == '__main__':
    test_programmatic_cleaner()