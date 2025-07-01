#!/usr/bin/env python3
"""
Advanced dependency analyzer for Manim scenes.
This module provides sophisticated AST analysis to extract all dependencies
that a scene requires to function properly.
"""

import ast
from typing import Dict, Set, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Container for dependency information."""
    functions: Set[str] = field(default_factory=set)
    classes: Set[str] = field(default_factory=set)
    constants: Set[str] = field(default_factory=set)
    imports: Set[str] = field(default_factory=set)
    decorators: Set[str] = field(default_factory=set)
    config_items: Set[str] = field(default_factory=set)
    unresolved: Set[str] = field(default_factory=set)
    
    def merge(self, other: 'DependencyInfo'):
        """Merge another DependencyInfo into this one."""
        self.functions.update(other.functions)
        self.classes.update(other.classes)
        self.constants.update(other.constants)
        self.imports.update(other.imports)
        self.decorators.update(other.decorators)
        self.config_items.update(other.config_items)
        self.unresolved.update(other.unresolved)


class AdvancedDependencyAnalyzer(ast.NodeVisitor):
    """
    Sophisticated dependency analyzer that captures all code dependencies
    required for a scene to function properly.
    """
    
    def __init__(self, scene_node: ast.ClassDef, full_ast: ast.Module, 
                 file_asts: Optional[Dict[str, ast.Module]] = None,
                 file_contents: Optional[Dict[str, List[str]]] = None,
                 import_resolver: Optional[Any] = None,
                 current_file_path: Optional[str] = None):
        self.scene_node = scene_node
        self.full_ast = full_ast
        self.file_asts = file_asts or {}  # All available ASTs for cross-file analysis
        self.file_contents = file_contents or {}  # Source lines for all files
        self.import_resolver = import_resolver  # ImportResolver instance
        self.current_file_path = current_file_path  # Path of the file being analyzed
        self.dependencies = DependencyInfo()
        
        # Build symbol tables for the entire module
        self.module_functions = {}  # name -> node
        self.module_classes = {}    # name -> node
        self.module_constants = {}  # name -> node
        self.module_imports = {}    # name -> import statement
        
        # Track current scope for nested analysis
        self.current_class = None
        self.in_scene = False
        
        # Known symbols from common star imports
        self.star_import_symbols = set()
        
        # Track cross-file dependencies
        self.cross_file_symbols = {}  # name -> (file_path, node)
        
        # Build the symbol tables
        self._build_symbol_tables()
        
    def _build_symbol_tables(self):
        """Build symbol tables for the entire module."""
        # Walk only the direct children of the module (top-level nodes)
        for node in self.full_ast.body:
            if isinstance(node, ast.FunctionDef):
                self.module_functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.module_classes[node.name] = node
            elif isinstance(node, ast.Assign):
                # Extract constant assignments
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Check if it's likely a constant (UPPER_CASE or CONFIG)
                        if target.id.isupper() or target.id == 'CONFIG':
                            self.module_constants[target.id] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # Track imports
                self._record_import(node)
        
        # Build cross-file symbol tables if we have other files
        if self.file_asts:
            self._build_cross_file_symbols()
    
    
    def _record_import(self, node: ast.AST):
        """Record import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_str = f"import {alias.name}"
                if alias.asname:
                    import_str += f" as {alias.asname}"
                self.module_imports[alias.asname or alias.name] = import_str
                self.dependencies.imports.add(import_str)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                if alias.name == '*':
                    import_str = f"from {module} import *"
                    self.dependencies.imports.add(import_str)
                    # Add known symbols from common modules
                    self._add_star_import_symbols(module)
                else:
                    import_str = f"from {module} import {alias.name}"
                    if alias.asname:
                        import_str += f" as {alias.asname}"
                    self.module_imports[alias.asname or alias.name] = import_str
                    self.dependencies.imports.add(import_str)
    
    def _add_star_import_symbols(self, module: str):
        """Add known symbols from star imports."""
        # Use import resolver if available
        if self.import_resolver:
            resolved_symbols = self.import_resolver.resolve_star_import(module, self.current_file_path)
            self.star_import_symbols.update(resolved_symbols)
            return
        
        # Fallback to heuristic approach
        # Common Manim classes and functions
        if 'manim' in module.lower():
            self.star_import_symbols.update({
                'Scene', 'GraphScene', 'NumberLineScene', 'MovingCameraScene',
                'ThreeDScene', 'VGroup', 'VMobject', 'Mobject', 'Text', 'MathTex',
                'Tex', 'OldTex', 'Circle', 'Square', 'Rectangle', 'Line', 'Arrow',
                'Dot', 'Point', 'Polygon', 'RegularPolygon', 'Triangle',
                'RIGHT', 'LEFT', 'UP', 'DOWN', 'ORIGIN', 'IN', 'OUT',
                'BLUE', 'RED', 'GREEN', 'YELLOW', 'WHITE', 'BLACK',
                'PI', 'TAU', 'E', 'DEGREES',
                'FadeIn', 'FadeOut', 'Write', 'ShowCreation', 'Transform',
                'ReplacementTransform', 'ApplyMethod', 'ApplyFunction',
                'Animation', 'AnimationGroup', 'Succession', 'LaggedStart'
            })
        
        # Pi creature related symbols
        if 'pi_creature' in module or 'character' in module:
            self.star_import_symbols.update({
                'PiCreature', 'Mortimer', 'Randolph', 'Face', 'Eyes', 'Eye',
                'SpeechBubble', 'ThoughtBubble', 'Blink', 'PiCreatureClass'
            })
        
        # Custom symbols
        if 'custom' in module or 'manim_imports_ext' == module:
            self.star_import_symbols.update({
                'Face', 'SpeechBubble', 'ThoughtBubble', 'OldTex', 'SimpleTex',
                'Scene', 'GraphScene', 'NumberLineScene', 'Underbrace'
            })
        
        # Animation symbols
        if 'animation' in module:
            self.star_import_symbols.update({
                'Face', 'SpeechBubble', 'ThoughtBubble', 'Underbrace',
                'FlipThroughNumbers', 'DelayByOrder'
            })
    
    def _build_cross_file_symbols(self):
        """Build symbol tables from all available files for cross-file analysis."""
        for file_path, file_ast in self.file_asts.items():
            if file_ast == self.full_ast:  # Skip the current file
                continue
                
            for node in file_ast.body:
                if isinstance(node, ast.FunctionDef):
                    self.cross_file_symbols[node.name] = (file_path, node)
                elif isinstance(node, ast.ClassDef):
                    self.cross_file_symbols[node.name] = (file_path, node)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id.isupper() or target.id == 'CONFIG':
                                self.cross_file_symbols[target.id] = (file_path, node)
    
    def analyze(self) -> DependencyInfo:
        """Analyze the scene and return its dependencies."""
        # First, analyze the scene itself
        self.in_scene = True
        self.visit(self.scene_node)
        self.in_scene = False
        
        # Then, recursively analyze all dependencies
        self._analyze_dependencies_recursively()
        
        # Finally, analyze constant value expressions
        self._analyze_constant_expressions()
        
        return self.dependencies
    
    def _analyze_dependencies_recursively(self):
        """Recursively analyze dependencies until no new ones are found."""
        analyzed = set()
        to_analyze = self.dependencies.functions | self.dependencies.classes
        
        while to_analyze - analyzed:
            current = to_analyze - analyzed
            for name in current:
                analyzed.add(name)
                
                # Analyze function dependencies
                if name in self.module_functions:
                    func_visitor = FunctionDependencyVisitor(self)
                    func_visitor.visit(self.module_functions[name])
                    
                # Analyze class dependencies
                elif name in self.module_classes:
                    class_visitor = ClassDependencyVisitor(self)
                    class_visitor.visit(self.module_classes[name])
            
            # Update to_analyze with newly found dependencies
            to_analyze = self.dependencies.functions | self.dependencies.classes
    
    def _analyze_constant_expressions(self):
        """Analyze expressions within constant definitions to find dependencies."""
        # Analyze each constant's value expression
        for const_name in list(self.dependencies.constants):
            if const_name in self.module_constants:
                assign_node = self.module_constants[const_name]
                # Create a visitor to analyze the value expression
                const_visitor = ConstantExpressionVisitor(self)
                const_visitor.visit(assign_node.value)
    
    # Visitor methods for the scene analysis
    def visit_Name(self, node: ast.Name):
        """Track name references."""
        if not self.in_scene:
            return
            
        name = node.id
        
        # Check if it's a known function
        if name in self.module_functions:
            self.dependencies.functions.add(name)
        # Check if it's a known class
        elif name in self.module_classes:
            self.dependencies.classes.add(name)
        # Check if it's a known constant
        elif name in self.module_constants:
            self.dependencies.constants.add(name)
        # Check if it's in cross-file symbols
        elif name in self.cross_file_symbols:
            file_path, symbol_node = self.cross_file_symbols[name]
            if isinstance(symbol_node, ast.FunctionDef):
                self.dependencies.functions.add(name)
            elif isinstance(symbol_node, ast.ClassDef):
                self.dependencies.classes.add(name)
            elif isinstance(symbol_node, ast.Assign):
                self.dependencies.constants.add(name)
        # Check if it's from an import
        elif name in self.module_imports:
            # Already tracked in imports
            pass
        # Check if it's from a star import
        elif name in self.star_import_symbols:
            # Don't track as unresolved - it's from a star import
            pass
        # Check common Manim/math names that don't need tracking
        elif name in {'self', 'True', 'False', 'None', 'PI', 'TAU', 'E', 
                      'UP', 'DOWN', 'LEFT', 'RIGHT', 'ORIGIN', 'OUT', 'IN'}:
            pass
        else:
            # Track as unresolved
            self.dependencies.unresolved.add(name)
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Track attribute access, especially for CONFIG."""
        if not self.in_scene:
            return
            
        # Check for CONFIG.item access
        if isinstance(node.value, ast.Name) and node.value.id == 'CONFIG':
            self.dependencies.config_items.add(node.attr)
            self.dependencies.constants.add('CONFIG')
        
        self.generic_visit(node)
    
    def visit_Subscript(self, node: ast.Subscript):
        """Track subscript access, especially for CONFIG[key]."""
        if not self.in_scene:
            return
            
        # Check for CONFIG[key] or self.CONFIG[key] access
        if isinstance(node.value, ast.Name) and node.value.id == 'CONFIG':
            # Direct CONFIG[key] access
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                self.dependencies.config_items.add(node.slice.value)
                self.dependencies.constants.add('CONFIG')
        elif (isinstance(node.value, ast.Attribute) and 
              node.value.attr == 'CONFIG' and
              isinstance(node.value.value, ast.Name) and
              node.value.value.id == 'self'):
            # self.CONFIG[key] access
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                self.dependencies.config_items.add(node.slice.value)
                self.dependencies.constants.add('CONFIG')
        elif (isinstance(node.value, ast.Attribute) and 
              node.value.attr == 'CONFIG'):
            # SomeClass.CONFIG[key] access
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                self.dependencies.config_items.add(node.slice.value)
                self.dependencies.constants.add('CONFIG')
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class definitions and their base classes."""
        if not self.in_scene:
            return
            
        # Track base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                if base_name in self.module_classes:
                    self.dependencies.classes.add(base_name)
                elif base_name in self.cross_file_symbols:
                    self.dependencies.classes.add(base_name)
            elif isinstance(base, ast.Attribute):
                # Handle cases like module.ClassName
                pass
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Track function calls."""
        if not self.in_scene:
            return
            
        # Handle direct function calls
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in self.module_functions:
                self.dependencies.functions.add(name)
            elif name in self.module_classes:
                self.dependencies.classes.add(name)
        
        # Handle decorators
        for decorator in getattr(node, 'decorator_list', []):
            if isinstance(decorator, ast.Name):
                self.dependencies.decorators.add(decorator.id)
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                self.dependencies.decorators.add(decorator.func.id)
        
        self.generic_visit(node)


class FunctionDependencyVisitor(ast.NodeVisitor):
    """Visitor for analyzing dependencies within a function."""
    
    def __init__(self, parent_analyzer: AdvancedDependencyAnalyzer):
        self.parent = parent_analyzer
        self.dependencies = DependencyInfo()
    
    def visit_Call(self, node: ast.Call):
        """Track function/class calls within the function."""
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in self.parent.module_functions:
                self.dependencies.functions.add(name)
                self.parent.dependencies.functions.add(name)
            elif name in self.parent.module_classes:
                self.dependencies.classes.add(name)
                self.parent.dependencies.classes.add(name)
            elif name in self.parent.cross_file_symbols:
                file_path, symbol_node = self.parent.cross_file_symbols[name]
                if isinstance(symbol_node, ast.ClassDef):
                    self.dependencies.classes.add(name)
                    self.parent.dependencies.classes.add(name)
                elif isinstance(symbol_node, ast.FunctionDef):
                    self.dependencies.functions.add(name)
                    self.parent.dependencies.functions.add(name)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Track names used in the function."""
        name = node.id
        
        if name in self.parent.module_functions and name != self.parent.current_class:
            self.dependencies.functions.add(name)
            self.parent.dependencies.functions.add(name)
        elif name in self.parent.module_classes:
            self.dependencies.classes.add(name)
            self.parent.dependencies.classes.add(name)
        elif name in self.parent.module_constants:
            self.dependencies.constants.add(name)
            self.parent.dependencies.constants.add(name)
        
        self.generic_visit(node)


class ClassDependencyVisitor(ast.NodeVisitor):
    """Visitor for analyzing dependencies within a class."""
    
    def __init__(self, parent_analyzer: AdvancedDependencyAnalyzer):
        self.parent = parent_analyzer
        self.dependencies = DependencyInfo()
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class definitions and their base classes."""
        # Track base classes - this is crucial for inheritance chains
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                if base_name in self.parent.module_classes:
                    self.dependencies.classes.add(base_name)
                    self.parent.dependencies.classes.add(base_name)
                elif base_name in self.parent.cross_file_symbols:
                    self.dependencies.classes.add(base_name)
                    self.parent.dependencies.classes.add(base_name)
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Track function/class calls within the class."""
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in self.parent.module_functions:
                self.dependencies.functions.add(name)
                self.parent.dependencies.functions.add(name)
            elif name in self.parent.module_classes:
                self.dependencies.classes.add(name)
                self.parent.dependencies.classes.add(name)
            elif name in self.parent.cross_file_symbols:
                file_path, symbol_node = self.parent.cross_file_symbols[name]
                if isinstance(symbol_node, ast.ClassDef):
                    self.dependencies.classes.add(name)
                    self.parent.dependencies.classes.add(name)
                elif isinstance(symbol_node, ast.FunctionDef):
                    self.dependencies.functions.add(name)
                    self.parent.dependencies.functions.add(name)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Track names used in the class."""
        name = node.id
        
        if name in self.parent.module_functions:
            self.dependencies.functions.add(name)
            self.parent.dependencies.functions.add(name)
        elif name in self.parent.module_classes and name != self.parent.current_class:
            self.dependencies.classes.add(name)
            self.parent.dependencies.classes.add(name)
        elif name in self.parent.module_constants:
            self.dependencies.constants.add(name)
            self.parent.dependencies.constants.add(name)
        
        self.generic_visit(node)


class ConstantExpressionVisitor(ast.NodeVisitor):
    """Visitor for analyzing dependencies within constant value expressions."""
    
    def __init__(self, parent_analyzer: AdvancedDependencyAnalyzer):
        self.parent = parent_analyzer
    
    def visit_Name(self, node: ast.Name):
        """Track names used in the constant expression."""
        if isinstance(node.ctx, ast.Load):
            name = node.id
            
            # Skip built-ins
            if name in {'reduce', 'op', 'str', 'len', 'range', 'int', 'float', 
                       'list', 'dict', 'set', 'tuple', 'True', 'False', 'None'}:
                self.generic_visit(node)
                return
            
            # Check if it's a known function
            if name in self.parent.module_functions:
                self.parent.dependencies.functions.add(name)
            # Check if it's a known class
            elif name in self.parent.module_classes:
                self.parent.dependencies.classes.add(name)
            # Check if it's a known constant
            elif name in self.parent.module_constants:
                self.parent.dependencies.constants.add(name)
            # Check if it's in cross-file symbols
            elif name in self.parent.cross_file_symbols:
                file_path, symbol_node = self.parent.cross_file_symbols[name]
                if isinstance(symbol_node, ast.FunctionDef):
                    self.parent.dependencies.functions.add(name)
                elif isinstance(symbol_node, ast.ClassDef):
                    self.parent.dependencies.classes.add(name)
                elif isinstance(symbol_node, ast.Assign):
                    self.parent.dependencies.constants.add(name)
            # Check if it's from an import
            elif name in self.parent.module_imports:
                # Already tracked in imports
                pass
            # Check if it's from a star import
            elif name in self.parent.star_import_symbols:
                # Don't track as unresolved - it's from a star import
                pass
            else:
                # Track as unresolved if not a common name
                if name not in {'self', 'PI', 'TAU', 'E', 'UP', 'DOWN', 'LEFT', 
                               'RIGHT', 'ORIGIN', 'OUT', 'IN'}:
                    self.parent.dependencies.unresolved.add(name)
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Track function calls within the constant expression."""
        if isinstance(node.func, ast.Name):
            name = node.func.id
            
            # Skip built-ins
            if name in {'reduce', 'sum', 'len', 'str', 'int', 'float', 'list', 
                       'dict', 'set', 'tuple', 'range', 'zip', 'map', 'filter',
                       'min', 'max', 'abs', 'round', 'sorted', 'enumerate'}:
                self.generic_visit(node)
                return
                
            if name in self.parent.module_functions:
                self.parent.dependencies.functions.add(name)
            elif name in self.parent.module_classes:
                self.parent.dependencies.classes.add(name)
            elif name in self.parent.cross_file_symbols:
                file_path, symbol_node = self.parent.cross_file_symbols[name]
                if isinstance(symbol_node, ast.FunctionDef):
                    self.parent.dependencies.functions.add(name)
                elif isinstance(symbol_node, ast.ClassDef):
                    self.parent.dependencies.classes.add(name)
        
        self.generic_visit(node)


def extract_code_for_dependencies(full_ast: ast.Module, source_lines: List[str], 
                                 dependencies: DependencyInfo,
                                 file_asts: Optional[Dict[str, ast.Module]] = None,
                                 file_contents: Optional[Dict[str, List[str]]] = None) -> Dict[str, str]:
    """
    Extract the actual code for all dependencies.
    Returns a dict mapping dependency type to code string.
    """
    extracted = {
        'imports': [],
        'constants': [],
        'functions': [],
        'classes': []
    }
    
    file_asts = file_asts or {}
    file_contents = file_contents or {}
    
    # Extract imports
    for import_stmt in dependencies.imports:
        extracted['imports'].append(import_stmt)
    
    # Helper function to extract from any AST/source pair
    def extract_from_ast(ast_tree, source_lines, name, node_type):
        for node in ast.walk(ast_tree):
            if node_type == 'constant' and isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        start_line = node.lineno - 1
                        # Use find_node_end_line for constants to handle multi-line properly
                        end_line = find_node_end_line(node, source_lines)
                        return '\n'.join(source_lines[start_line:end_line])
            elif node_type == 'function' and isinstance(node, ast.FunctionDef) and node.name == name:
                start_line = node.lineno - 1
                end_line = find_node_end_line(node, source_lines)
                return '\n'.join(source_lines[start_line:end_line])
            elif node_type == 'class' and isinstance(node, ast.ClassDef) and node.name == name:
                start_line = node.lineno - 1
                end_line = find_node_end_line(node, source_lines)
                return '\n'.join(source_lines[start_line:end_line])
        return None
    
    # Extract constants
    for const_name in dependencies.constants:
        # Try current file first
        code = extract_from_ast(full_ast, source_lines, const_name, 'constant')
        if code:
            extracted['constants'].append(code)
        else:
            # Try other files
            for file_path, file_ast in file_asts.items():
                if file_path in file_contents:
                    code = extract_from_ast(file_ast, file_contents[file_path], const_name, 'constant')
                    if code:
                        extracted['constants'].append(f"# From {file_path}\n{code}")
                        break
    
    # Extract functions
    for func_name in dependencies.functions:
        # Try current file first
        code = extract_from_ast(full_ast, source_lines, func_name, 'function')
        if code:
            extracted['functions'].append(code)
        else:
            # Try other files
            for file_path, file_ast in file_asts.items():
                if file_path in file_contents:
                    code = extract_from_ast(file_ast, file_contents[file_path], func_name, 'function')
                    if code:
                        extracted['functions'].append(f"# From {file_path}\n{code}")
                        break
    
    # Extract classes
    for class_name in dependencies.classes:
        # Try current file first
        code = extract_from_ast(full_ast, source_lines, class_name, 'class')
        if code:
            extracted['classes'].append(code)
        else:
            # Try other files
            for file_path, file_ast in file_asts.items():
                if file_path in file_contents:
                    code = extract_from_ast(file_ast, file_contents[file_path], class_name, 'class')
                    if code:
                        extracted['classes'].append(f"# From {file_path}\n{code}")
                        break
    
    return extracted


def convert_parameterized_construct(scene_node: ast.ClassDef, source_lines: List[str]) -> Optional[str]:
    """
    Convert scenes with parameterized construct(self, mode) to standard format.
    Returns the converted scene code or None if not parameterized.
    """
    # Check if construct method has parameters beyond self
    construct_method = None
    for node in scene_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'construct':
            if len(node.args.args) > 1:  # More than just 'self'
                construct_method = node
                break
    
    if not construct_method:
        return None  # Not a parameterized scene
    
    # Extract parameter names and defaults
    params = []
    defaults = []
    args = construct_method.args
    
    # Get positional args (skip 'self')
    for arg in args.args[1:]:
        params.append(arg.arg)
    
    # Get defaults (aligned to the end of args)
    if args.defaults:
        # Pad with None for args without defaults
        defaults = [None] * (len(params) - len(args.defaults)) + args.defaults
    else:
        defaults = [None] * len(params)
    
    # Build the converted scene
    converted_lines = []
    
    # Add __init__ method
    converted_lines.append("    def __init__(self, **kwargs):")
    converted_lines.append("        # Convert parameterized construct to instance attributes")
    
    # Add parameter assignments
    for param, default in zip(params, defaults):
        if default is not None:
            # Convert AST node to source
            default_str = ast.unparse(default) if hasattr(ast, 'unparse') else str(default)
            converted_lines.append(f"        self.{param} = kwargs.get('{param}', {default_str})")
        else:
            converted_lines.append(f"        self.{param} = kwargs.get('{param}')")
    
    converted_lines.append("        super().__init__(**kwargs)")
    converted_lines.append("")
    
    # Now modify the construct method to remove parameters
    construct_start = construct_method.lineno - 1
    construct_end = find_node_end_line(construct_method, source_lines)
    
    # Replace the construct definition line
    old_construct_line = source_lines[construct_start]
    indent = len(old_construct_line) - len(old_construct_line.lstrip())
    new_construct_line = " " * indent + "def construct(self):"
    
    # Build the complete scene
    scene_start = scene_node.lineno - 1
    scene_end = find_node_end_line(scene_node, source_lines)
    
    result_lines = []
    
    # Add everything before construct
    for i in range(scene_start, construct_start):
        result_lines.append(source_lines[i])
    
    # Add the __init__ method before construct
    result_lines.extend(converted_lines)
    
    # Add the modified construct method
    result_lines.append(new_construct_line)
    
    # Add the rest of construct body
    for i in range(construct_start + 1, construct_end):
        # Replace parameter references with self.param
        line = source_lines[i]
        for param in params:
            # Simple replacement - could be more sophisticated with AST
            line = re.sub(r'\b' + param + r'\b', f'self.{param}', line)
        result_lines.append(line)
    
    # Add everything after construct
    for i in range(construct_end, scene_end):
        result_lines.append(source_lines[i])
    
    return '\n'.join(result_lines)


def validate_scene_self_containment(scene_code: str, scene_name: str = "UnknownScene") -> Tuple[bool, List[str]]:
    """
    Validate that a scene is truly self-contained with all dependencies included.
    Returns (is_valid, list_of_missing_dependencies).
    """
    missing_deps = []
    
    try:
        # Parse the scene code
        tree = ast.parse(scene_code)
        
        # Track what's defined in this code
        defined_names = set()
        defined_classes = set()
        imported_names = set()
        
        # First pass: collect all definitions and imports
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_classes.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        if alias.name == '*':
                            # Star imports - add common known names
                            if 'manim' in node.module:
                                imported_names.update({
                                    'Scene', 'VMobject', 'VGroup', 'Text', 'MathTex', 'Tex',
                                    'Circle', 'Square', 'Rectangle', 'Line', 'Arrow', 'Dot',
                                    'FadeIn', 'FadeOut', 'Write', 'Transform', 'Create',
                                    'UP', 'DOWN', 'LEFT', 'RIGHT', 'ORIGIN', 'PI', 'TAU',
                                    'BLUE', 'RED', 'GREEN', 'WHITE', 'BLACK', 'YELLOW'
                                })
                            if 'animation' in node.module or 'custom' in node.module:
                                imported_names.update({
                                    'Face', 'SpeechBubble', 'ThoughtBubble', 'Underbrace',
                                    'FlipThroughNumbers', 'DelayByOrder'
                                })
                        else:
                            imported_names.add(alias.asname or alias.name)
        
        # Second pass: check for undefined names
        class UndefinedNameChecker(ast.NodeVisitor):
            def __init__(self):
                self.undefined = set()
                self.in_function = False
                self.local_vars = set()
            
            def visit_FunctionDef(self, node):
                old_in_function = self.in_function
                old_locals = self.local_vars.copy()
                self.in_function = True
                
                # Add function parameters to local vars
                for arg in node.args.args:
                    self.local_vars.add(arg.arg)
                
                self.generic_visit(node)
                
                self.in_function = old_in_function
                self.local_vars = old_locals
            
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    name = node.id
                    # Skip common built-ins and special names
                    if name in {'self', 'super', 'True', 'False', 'None', 'print', 'len', 
                               'range', 'list', 'dict', 'set', 'tuple', 'str', 'int', 
                               'float', 'bool', 'type', 'isinstance', 'hasattr', 'getattr',
                               'setattr', 'zip', 'enumerate', 'map', 'filter', 'sum', 'min',
                               'max', 'abs', 'round', 'sorted', 'reversed', 'all', 'any',
                               'property', 'staticmethod', 'classmethod', '__name__',
                               'Exception', 'ValueError', 'TypeError', 'AttributeError'}:
                        return
                    
                    # Skip if it's a local variable
                    if name in self.local_vars:
                        return
                    
                    # Check if it's defined or imported
                    if (name not in defined_names and 
                        name not in defined_classes and 
                        name not in imported_names):
                        self.undefined.add(name)
                
                self.generic_visit(node)
            
            def visit_Assign(self, node):
                # Add assigned names to local vars if in function
                if self.in_function:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.local_vars.add(target.id)
                self.generic_visit(node)
        
        # Check for undefined names
        checker = UndefinedNameChecker()
        
        # Find the scene class and check it specifically
        scene_found = False
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (node.name == scene_name or 
                                                   node.name.endswith('Scene')):
                scene_found = True
                checker.visit(node)
        
        # If no specific scene found, check the whole file
        if not scene_found:
            checker.visit(tree)
        
        missing_deps = list(checker.undefined)
        
        # Additional validation: try to compile
        try:
            compile(scene_code, f"{scene_name}.py", 'exec')
        except NameError as e:
            # Extract the undefined name from the error
            import re
            match = re.search(r"name '(\w+)' is not defined", str(e))
            if match and match.group(1) not in missing_deps:
                missing_deps.append(match.group(1))
        except Exception:
            # Other compilation errors don't indicate missing dependencies
            pass
        
        return len(missing_deps) == 0, missing_deps
        
    except Exception as e:
        return False, [f"Validation error: {str(e)}"]


def find_node_end_line(node: ast.AST, source_lines: List[str]) -> int:
    """
    Find the actual end line of a node, including its body.
    This is more accurate than the simple approach in the current code.
    
    FIXED (June 27, 2025): For ast.Assign nodes (constants), trust AST's end_lineno 
    directly without additional processing to handle multi-line constants properly.
    """
    if hasattr(node, 'end_lineno') and node.end_lineno:
        # For assignments (constants), trust the AST's end_lineno directly
        # This fixes issues with multi-line constant expressions like reduce()
        if isinstance(node, ast.Assign):
            return node.end_lineno
            
        # Start with AST's end line
        end_line = node.end_lineno
        
        # For functions and classes, we need to check indentation
        # to ensure we capture the entire body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            # Get the indentation of the definition line
            def_line = source_lines[node.lineno - 1]
            base_indent = len(def_line) - len(def_line.lstrip())
            
            # Look for where indentation returns to base level or less
            current_line = end_line
            while current_line < len(source_lines):
                line = source_lines[current_line]
                
                # Skip empty lines
                if not line.strip():
                    current_line += 1
                    continue
                
                # Check indentation
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= base_indent:
                    # Found the end
                    break
                
                current_line += 1
            
            end_line = current_line
    else:
        # Fallback for older Python versions using AST walking
        end_line = node.lineno
        
        # Walk through all child nodes to find the furthest line
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                end_line = max(end_line, child.lineno)
            if hasattr(child, 'end_lineno') and child.end_lineno:
                end_line = max(end_line, child.end_lineno)
    
    # Safety check: ensure we don't go beyond the file
    end_line = min(end_line, len(source_lines))
    
    return end_line