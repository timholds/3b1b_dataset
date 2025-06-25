#!/usr/bin/env python3
"""
Extract self-contained training snippets from ManimCE code.

This script analyzes converted ManimCE files and extracts individual scenes
as self-contained snippets suitable for supervised fine-tuning.
"""

import ast
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
import argparse
from collections import defaultdict
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.manimce_conversion_utils import extract_scenes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FunctionDependencyVisitor(ast.NodeVisitor):
    """Helper visitor to analyze function bodies for dependencies."""
    
    def __init__(self):
        self.used_names = set()
        self.used_functions = set()
    
    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.used_functions.add(node.func.id)
        self.generic_visit(node)


class DependencyAnalyzer(ast.NodeVisitor):
    """Analyze AST to find dependencies for a given scene."""
    
    def __init__(self, module_ast: ast.Module, scene_name: str):
        self.module_ast = module_ast
        self.scene_name = scene_name
        self.scene_node = None
        
        # Dependencies to track
        self.used_functions: Set[str] = set()
        self.used_names: Set[str] = set()
        self.used_classes: Set[str] = set()
        self.used_imports: Set[str] = set()
        
        # Module-level definitions
        self.module_functions: Dict[str, ast.FunctionDef] = {}
        self.module_classes: Dict[str, ast.ClassDef] = {}
        self.module_constants: Dict[str, ast.AST] = {}
        self.module_imports: List[ast.AST] = []
        
        # Current context
        self.current_class = None
        self.in_scene = False
        
        # Analyze module first
        self._analyze_module()
        
    def _analyze_module(self):
        """Extract module-level definitions."""
        for node in self.module_ast.body:
            if isinstance(node, ast.FunctionDef):
                self.module_functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.module_classes[node.name] = node
                if node.name == self.scene_name:
                    self.scene_node = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.module_imports.append(node)
            elif isinstance(node, ast.Assign):
                # Track module-level constants
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.module_constants[target.id] = node
    
    def analyze_scene(self) -> Dict[str, Any]:
        """Analyze the scene and return its dependencies."""
        if not self.scene_node:
            return {}
        
        # Find base classes
        base_classes = []
        for base in self.scene_node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
        
        # Visit the scene node
        self.in_scene = True
        self.visit(self.scene_node)
        self.in_scene = False
        
        # Collect all dependencies
        dependencies = {
            'functions': self._collect_function_dependencies(),
            'classes': self._collect_class_dependencies(base_classes),
            'constants': self._collect_constant_dependencies(),
            'imports': self._collect_import_dependencies(),
            'base_classes': base_classes
        }
        
        return dependencies
    
    def visit_Call(self, node: ast.Call):
        """Track function calls."""
        if self.in_scene:
            if isinstance(node.func, ast.Name):
                self.used_functions.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                # Track method calls that might be module functions
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    # Skip self.method() calls
                    pass
                else:
                    # Could be a function from an imported module
                    self.used_functions.add(ast.unparse(node.func))
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Track name references."""
        if self.in_scene and isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        
        self.generic_visit(node)
    
    def _collect_function_dependencies(self) -> Dict[str, ast.FunctionDef]:
        """Collect all functions used by the scene."""
        result = {}
        to_process = list(self.used_functions)
        processed = set()
        
        while to_process:
            func_name = to_process.pop(0)
            if func_name in processed or func_name not in self.module_functions:
                continue
                
            processed.add(func_name)
            result[func_name] = self.module_functions[func_name]
            
            # Analyze function body for more dependencies
            func_analyzer = FunctionDependencyVisitor()
            func_analyzer.visit(self.module_functions[func_name])
            
            # Add newly found dependencies
            for name in func_analyzer.used_names:
                if name in self.module_functions and name not in processed:
                    to_process.append(name)
                # Also track constants used by functions
                if name in self.module_constants:
                    self.used_names.add(name)
        
        return result
    
    def _collect_class_dependencies(self, base_classes: List[str]) -> Dict[str, ast.ClassDef]:
        """Collect all classes used by the scene."""
        result = {}
        to_process = list(base_classes) + [name for name in self.used_names if name in self.module_classes]
        processed = set()
        
        while to_process:
            class_name = to_process.pop(0)
            if class_name in processed or class_name not in self.module_classes or class_name == 'Scene':
                continue
                
            processed.add(class_name)
            result[class_name] = self.module_classes[class_name]
            
            # Analyze class body for dependencies
            class_analyzer = FunctionDependencyVisitor()
            class_analyzer.visit(self.module_classes[class_name])
            
            # Add dependencies found in class
            for name in class_analyzer.used_names:
                if name in self.module_classes and name not in processed:
                    to_process.append(name)
                # Track constants used by classes
                if name in self.module_constants:
                    self.used_names.add(name)
            
            # Check base classes of this class
            class_node = self.module_classes[class_name]
            for base in class_node.bases:
                if isinstance(base, ast.Name) and base.id in self.module_classes:
                    if base.id not in processed:
                        to_process.append(base.id)
        
        return result
    
    def _collect_constant_dependencies(self) -> Dict[str, ast.AST]:
        """Collect all constants used by the scene."""
        result = {}
        
        for name in self.used_names:
            if name in self.module_constants:
                result[name] = self.module_constants[name]
        
        return result
    
    def _collect_import_dependencies(self) -> List[ast.AST]:
        """Determine which imports are needed."""
        # For now, include all imports (conservative approach)
        # TODO: Smart import filtering based on usage
        return self.module_imports


class SceneSnippetExtractor:
    """Extract self-contained snippets from ManimCE files."""
    
    def __init__(self, manimce_code_path: str):
        self.code_path = Path(manimce_code_path)
        self.video_name = self.code_path.parent.name
        self.year = self.code_path.parent.parent.name
        
        # Read the code
        with open(self.code_path, 'r', encoding='utf-8') as f:
            self.code = f.read()
        
        # Parse AST
        try:
            self.ast_tree = ast.parse(self.code)
        except SyntaxError as e:
            logger.error(f"Syntax error in {self.code_path}: {e}")
            self.ast_tree = None
    
    def extract_snippets(self) -> List[Dict[str, Any]]:
        """Extract all scenes as self-contained snippets."""
        if not self.ast_tree:
            return []
        
        snippets = []
        
        # Find all scene classes
        scene_classes = self._find_scene_classes()
        logger.info(f"Found {len(scene_classes)} scenes in {self.video_name}")
        
        for idx, scene_name in enumerate(scene_classes):
            logger.info(f"Processing scene {idx+1}/{len(scene_classes)}: {scene_name}")
            
            # Analyze dependencies
            analyzer = DependencyAnalyzer(self.ast_tree, scene_name)
            dependencies = analyzer.analyze_scene()
            
            # Build snippet
            snippet_code = self._build_snippet(scene_name, dependencies)
            
            # Create metadata
            metadata = {
                'video_name': self.video_name,
                'video_year': self.year,
                'scene_name': scene_name,
                'scene_index': idx,
                'snippet_hash': hashlib.md5(snippet_code.encode()).hexdigest(),
                'dependencies_included': {
                    'functions': list(dependencies['functions'].keys()),
                    'classes': list(dependencies['classes'].keys()),
                    'constants': list(dependencies['constants'].keys()),
                    'base_classes': dependencies['base_classes']
                }
            }
            
            # Validate snippet
            is_valid = self._validate_snippet(snippet_code)
            metadata['validated'] = is_valid
            
            snippets.append({
                'code': snippet_code,
                'metadata': metadata
            })
        
        return snippets
    
    def _find_scene_classes(self) -> List[str]:
        """Find all classes that inherit from Scene."""
        scene_classes = []
        
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from Scene
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_name = base.id
                        if 'Scene' in base_name or base_name in self._get_known_scene_bases():
                            scene_classes.append(node.name)
                            break
        
        return scene_classes
    
    def _get_known_scene_bases(self) -> Set[str]:
        """Return known scene base classes."""
        return {
            'MovingCameraScene', 'ZoomedScene', 'ThreeDScene',
            'VectorScene', 'LinearTransformationScene', 'SpecialThreeDScene',
            'GraphScene', 'NumberLineScene', 'IntervalScene'
        }
    
    def _build_snippet(self, scene_name: str, dependencies: Dict[str, Any]) -> str:
        """Build a self-contained snippet for the scene."""
        parts = []
        
        # Header with metadata
        parts.append(f"# Video: {self.video_name}")
        parts.append(f"# Scene: {scene_name}")
        parts.append(f"# Description: Scene from {self.video_name}")
        parts.append("")
        
        # Imports
        parts.append("from manim import *")
        
        # Collect unique imports
        seen_imports = {'from manim import *', 'import manim'}
        import_lines = []
        
        for import_node in dependencies['imports']:
            import_str = ast.unparse(import_node)
            # Skip duplicates and manim imports
            if import_str not in seen_imports and 'from manim import' not in import_str and 'import manim' not in import_str:
                seen_imports.add(import_str)
                import_lines.append(import_str)
        
        # Add unique imports
        for import_line in sorted(import_lines):
            parts.append(import_line)
        
        parts.append("")
        
        # Add ManimGL compatibility functions if needed
        if self._needs_compatibility_functions(scene_name, dependencies):
            parts.append("# ManimGL compatibility functions")
            parts.append(self._get_compatibility_functions())
            parts.append("")
        
        # Constants
        if dependencies['constants']:
            parts.append("# Constants")
            for const_name, const_node in dependencies['constants'].items():
                parts.append(ast.unparse(const_node))
            parts.append("")
        
        # Helper functions
        if dependencies['functions']:
            parts.append("# Helper functions")
            for func_name, func_node in dependencies['functions'].items():
                parts.append(ast.unparse(func_node))
                parts.append("")
        
        # Base classes
        if dependencies['classes']:
            parts.append("# Required classes")
            for class_name, class_node in dependencies['classes'].items():
                parts.append(ast.unparse(class_node))
                parts.append("")
        
        # The scene itself
        parts.append("# Main scene")
        scene_node = self._get_scene_node(scene_name)
        if scene_node:
            parts.append(ast.unparse(scene_node))
        
        return '\n'.join(parts)
    
    def _get_scene_node(self, scene_name: str) -> Optional[ast.ClassDef]:
        """Get the AST node for a specific scene."""
        for node in self.ast_tree.body:
            if isinstance(node, ast.ClassDef) and node.name == scene_name:
                return node
        return None
    
    def _validate_snippet(self, snippet_code: str) -> bool:
        """Validate that the snippet is syntactically correct."""
        try:
            ast.parse(snippet_code)
            return True
        except SyntaxError:
            return False
    
    def _needs_compatibility_functions(self, scene_name: str, dependencies: Dict[str, Any]) -> bool:
        """Check if compatibility functions are needed."""
        # Check if digest_config is used
        all_code = ast.unparse(self._get_scene_node(scene_name))
        for class_node in dependencies['classes'].values():
            all_code += ast.unparse(class_node)
        
        return 'digest_config' in all_code
    
    def _get_compatibility_functions(self) -> str:
        """Return ManimGL compatibility functions."""
        return """def digest_config(obj, kwargs):
    \"\"\"ManimGL compatibility function to process CONFIG dictionaries.\"\"\"
    if hasattr(obj, 'CONFIG'):
        for key, value in obj.CONFIG.items():
            setattr(obj, key, kwargs.get(key, value))
    for key, value in kwargs.items():
        setattr(obj, key, value)"""
    
    def save_snippets(self, output_dir: Path):
        """Save snippets to individual files."""
        snippets = self.extract_snippets()
        
        # Create output directory
        snippet_dir = output_dir / self.year / self.video_name / "snippets"
        snippet_dir.mkdir(parents=True, exist_ok=True)
        
        # Save each snippet
        for snippet in snippets:
            scene_name = snippet['metadata']['scene_name']
            snippet_path = snippet_dir / f"{scene_name}.py"
            
            with open(snippet_path, 'w', encoding='utf-8') as f:
                f.write(snippet['code'])
            
            # Save metadata
            metadata_path = snippet_dir / f"{scene_name}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(snippet['metadata'], f, indent=2)
        
        # Save summary
        summary = {
            'video_name': self.video_name,
            'year': self.year,
            'total_scenes': len(snippets),
            'validated_scenes': sum(1 for s in snippets if s['metadata']['validated']),
            'snippets': [s['metadata'] for s in snippets]
        }
        
        summary_path = snippet_dir / "extraction_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved {len(snippets)} snippets to {snippet_dir}")
        
        return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Extract training snippets from ManimCE code")
    parser.add_argument('--year', type=str, required=True, help='Year to process')
    parser.add_argument('--video', type=str, help='Specific video to process')
    parser.add_argument('--output-dir', type=str, default='outputs', help='Output directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Find videos to process
    output_dir = Path(args.output_dir)
    year_dir = output_dir / args.year
    
    if not year_dir.exists():
        logger.error(f"Year directory does not exist: {year_dir}")
        return 1
    
    # Get video directories
    if args.video:
        video_dirs = [year_dir / args.video]
        if not video_dirs[0].exists():
            logger.error(f"Video directory does not exist: {video_dirs[0]}")
            return 1
    else:
        video_dirs = [d for d in year_dir.iterdir() if d.is_dir()]
    
    # Process each video
    total_snippets = 0
    successful_videos = 0
    
    for video_dir in sorted(video_dirs):
        manimce_path = video_dir / "manimce_code.py"
        
        if not manimce_path.exists():
            logger.warning(f"No manimce_code.py found in {video_dir.name}, skipping")
            continue
        
        logger.info(f"\nProcessing {video_dir.name}...")
        
        try:
            extractor = SceneSnippetExtractor(str(manimce_path))
            summary = extractor.save_snippets(output_dir)
            
            total_snippets += summary['total_scenes']
            successful_videos += 1
            
            logger.info(f"Successfully extracted {summary['total_scenes']} snippets "
                       f"({summary['validated_scenes']} validated)")
            
        except Exception as e:
            logger.error(f"Failed to process {video_dir.name}: {e}")
            continue
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Extraction complete!")
    logger.info(f"Processed {successful_videos} videos")
    logger.info(f"Total snippets extracted: {total_snippets}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())