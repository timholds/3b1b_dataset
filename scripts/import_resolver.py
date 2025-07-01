#!/usr/bin/env python3
"""
Import resolver for the 3b1b dataset pipeline.
Resolves star imports and module imports using the symbol index.
"""

import ast
import json
import logging
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ImportResolver:
    """Resolve star imports and module imports using symbol index."""
    
    def __init__(self, symbol_index_path: Optional[Path] = None):
        """
        Initialize the import resolver.
        
        Args:
            symbol_index_path: Path to the symbol index JSON file
        """
        self.symbol_index = {}
        self.resolved_imports_cache = {}
        
        if symbol_index_path and symbol_index_path.exists():
            with open(symbol_index_path, 'r') as f:
                self.symbol_index = json.load(f)
        else:
            logger.warning("No symbol index provided - using heuristic resolution only")
    
    def resolve_star_import(self, module_name: str, file_path: Optional[str] = None) -> Set[str]:
        """
        Resolve `from module import *` to actual symbols.
        
        Args:
            module_name: The module being imported from
            file_path: Current file path (for relative imports)
            
        Returns:
            Set of symbol names exported by the module
        """
        # Check cache first
        cache_key = f"{module_name}:{file_path or ''}"
        if cache_key in self.resolved_imports_cache:
            return self.resolved_imports_cache[cache_key]
        
        symbols = set()
        
        # Special handling for key modules
        if module_name == 'manim_imports_ext':
            symbols = self._resolve_manim_imports_ext()
        elif module_name and module_name.startswith('.'):
            # Relative import
            symbols = self._resolve_relative_import(module_name, file_path)
        else:
            # Check symbol index
            symbols = self._resolve_from_index(module_name)
        
        # Fallback to heuristics if needed
        if not symbols:
            symbols = self._get_heuristic_symbols(module_name)
        
        # Cache the result
        self.resolved_imports_cache[cache_key] = symbols
        return symbols
    
    def _resolve_manim_imports_ext(self) -> Set[str]:
        """
        Special handling for manim_imports_ext.py which re-exports many things.
        """
        symbols = set()
        
        # First, get direct exports from manim_imports_ext
        manim_ext_path = "data/videos/manim_imports_ext.py"
        if manim_ext_path in self.symbol_index.get('modules', {}):
            symbols.update(self.symbol_index['modules'][manim_ext_path])
        
        # Then, analyze its imports to find re-exports
        if manim_ext_path in self.symbol_index.get('imports', {}):
            imports = self.symbol_index['imports'][manim_ext_path]
            for import_stmt in imports:
                if 'from manimlib' in import_stmt and 'import *' in import_stmt:
                    # Add common manimlib exports
                    symbols.update(self._get_manimlib_symbols())
                elif 'from custom' in import_stmt and 'import *' in import_stmt:
                    # Add custom module exports
                    symbols.update(self._get_custom_symbols())
        
        # Add known symbols that are commonly used
        symbols.update({
            'Scene', 'GraphScene', 'NumberLineScene', 'MovingCameraScene',
            'ThreeDScene', 'VGroup', 'VMobject', 'Mobject', 'Text', 'MathTex',
            'Tex', 'OldTex', 'Circle', 'Square', 'Rectangle', 'Line', 'Arrow',
            'Dot', 'Point', 'Polygon', 'RegularPolygon', 'Triangle',
            'RIGHT', 'LEFT', 'UP', 'DOWN', 'ORIGIN', 'IN', 'OUT',
            'BLUE', 'RED', 'GREEN', 'YELLOW', 'WHITE', 'BLACK',
            'PI', 'TAU', 'E', 'DEGREES',
            'FadeIn', 'FadeOut', 'Write', 'ShowCreation', 'Transform',
            'ReplacementTransform', 'ApplyMethod', 'ApplyFunction',
            'Face', 'SpeechBubble', 'ThoughtBubble', 'PiCreature'
        })
        
        return symbols
    
    def _resolve_relative_import(self, module_name: str, file_path: Optional[str]) -> Set[str]:
        """Resolve relative imports like 'from .other_file import *'."""
        if not file_path:
            return set()
        
        # Convert relative import to absolute path
        current_dir = Path(file_path).parent
        
        # Handle different relative import patterns
        if module_name == '.':
            # from . import something
            target_module = str(current_dir / '__init__.py')
        else:
            # from .module import something
            module_parts = module_name.split('.')
            # Count leading dots
            level = len(module_name) - len(module_name.lstrip('.'))
            
            # Go up directories based on level
            target_dir = current_dir
            for _ in range(level - 1):
                target_dir = target_dir.parent
            
            # Get the module name after dots
            if len(module_parts) > level:
                module_file = module_parts[-1] + '.py'
                target_module = str(target_dir / module_file)
            else:
                target_module = str(target_dir / '__init__.py')
        
        # Look up in symbol index
        if target_module in self.symbol_index.get('modules', {}):
            return set(self.symbol_index['modules'][target_module])
        
        return set()
    
    def _resolve_from_index(self, module_name: str) -> Set[str]:
        """Resolve imports using the symbol index."""
        symbols = set()
        
        # Check direct module match
        module_patterns = [
            f"data/videos/{module_name}.py",
            f"data/videos/{module_name}/__init__.py",
            f"data/videos/custom/{module_name}.py",
            f"data/videos/once_useful_constructs/{module_name}.py"
        ]
        
        for pattern in module_patterns:
            if pattern in self.symbol_index.get('modules', {}):
                symbols.update(self.symbol_index['modules'][pattern])
                break
        
        # Check for partial matches (e.g., 'custom.characters.pi_creature')
        if '.' in module_name:
            path_like = module_name.replace('.', '/') + '.py'
            for module_path in self.symbol_index.get('modules', {}):
                if module_path.endswith(path_like):
                    symbols.update(self.symbol_index['modules'][module_path])
                    break
        
        return symbols
    
    def _get_heuristic_symbols(self, module_name: str) -> Set[str]:
        """Get symbols based on heuristic patterns when index lookup fails."""
        symbols = set()
        
        # Manim-related modules
        if 'manim' in module_name.lower():
            symbols.update(self._get_manimlib_symbols())
        
        # Custom modules
        if 'custom' in module_name:
            symbols.update(self._get_custom_symbols())
        
        # Pi creature modules
        if 'pi_creature' in module_name or 'character' in module_name:
            symbols.update({
                'PiCreature', 'Mortimer', 'Randolph', 'Face', 'Eyes', 'Eye',
                'SpeechBubble', 'ThoughtBubble', 'Blink', 'PiCreatureClass'
            })
        
        # Animation modules
        if 'animation' in module_name:
            symbols.update({
                'Animation', 'AnimationGroup', 'Succession', 'LaggedStart',
                'FadeIn', 'FadeOut', 'Write', 'ShowCreation', 'Transform',
                'FlipThroughNumbers', 'DelayByOrder'
            })
        
        return symbols
    
    def _get_manimlib_symbols(self) -> Set[str]:
        """Get common symbols from manimlib."""
        return {
            # Scene types
            'Scene', 'GraphScene', 'NumberLineScene', 'MovingCameraScene',
            'ThreeDScene', 'VectorScene', 'LinearTransformationScene',
            
            # Mobjects
            'VMobject', 'Mobject', 'VGroup', 'Group',
            
            # Text
            'Text', 'MathTex', 'Tex', 'OldTex', 'OldTexText', 'Title',
            
            # Shapes
            'Circle', 'Square', 'Rectangle', 'Line', 'Arrow', 'DoubleArrow',
            'Dot', 'Point', 'Polygon', 'RegularPolygon', 'Triangle',
            'Ellipse', 'Arc', 'ArcBetweenPoints', 'CurvedArrow',
            
            # Constants
            'RIGHT', 'LEFT', 'UP', 'DOWN', 'ORIGIN', 'IN', 'OUT',
            'UR', 'UL', 'DR', 'DL',  # Diagonal directions
            'BLUE', 'RED', 'GREEN', 'YELLOW', 'WHITE', 'BLACK', 'PURPLE',
            'ORANGE', 'PINK', 'GREY', 'GRAY', 'TEAL', 'GOLD',
            'PI', 'TAU', 'E', 'DEGREES', 'RADIANS',
            'SMALL_BUFF', 'MED_SMALL_BUFF', 'MED_LARGE_BUFF', 'LARGE_BUFF',
            
            # Animations
            'Animation', 'AnimationGroup', 'Succession', 'LaggedStart',
            'FadeIn', 'FadeOut', 'Write', 'ShowCreation', 'Create',
            'Transform', 'ReplacementTransform', 'TransformFromCopy',
            'ApplyMethod', 'ApplyFunction', 'ApplyMatrix',
            'Rotate', 'Shift', 'Scale', 'ShrinkToCenter', 'GrowFromCenter',
            'SpinInFromNothing', 'Indicate', 'Flash', 'ShowPassingFlash',
            
            # Functions
            'interpolate', 'smooth', 'there_and_back', 'wiggle',
            'rate_func', 'bezier', 'straight_path', 'path_arc',
            
            # Number line and graph
            'NumberLine', 'NumberPlane', 'Axes', 'ThreeDAxes',
            'ParametricFunction', 'FunctionGraph'
        }
    
    def _get_custom_symbols(self) -> Set[str]:
        """Get symbols from custom modules."""
        symbols = set()
        
        # Scan custom directory in symbol index
        for module_path in self.symbol_index.get('modules', {}):
            if 'custom/' in module_path:
                symbols.update(self.symbol_index['modules'][module_path])
        
        # Add known custom symbols
        symbols.update({
            'Face', 'SpeechBubble', 'ThoughtBubble', 'PiCreature',
            'Mortimer', 'Randolph', 'Teacher', 'Student',
            'OldTex', 'OldTexText', 'SimpleTex', 'Underbrace'
        })
        
        return symbols
    
    def get_all_imports_for_file(self, file_ast: ast.Module, file_path: str) -> Dict[str, Set[str]]:
        """
        Get all imported symbols for a file.
        
        Returns:
            Dict mapping import type to set of symbols:
            - 'direct': Directly imported names
            - 'star': Names from star imports
            - 'modules': Imported module names
        """
        result = {
            'direct': set(),
            'star': set(),
            'modules': set()
        }
        
        for node in ast.walk(file_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    result['modules'].add(name)
                    
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                
                for alias in node.names:
                    if alias.name == '*':
                        # Star import
                        star_symbols = self.resolve_star_import(module, file_path)
                        result['star'].update(star_symbols)
                    else:
                        # Direct import
                        name = alias.asname or alias.name
                        result['direct'].add(name)
        
        return result