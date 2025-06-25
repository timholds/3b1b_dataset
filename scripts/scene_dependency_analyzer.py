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
    
    def __init__(self, scene_node: ast.ClassDef, full_ast: ast.Module):
        self.scene_node = scene_node
        self.full_ast = full_ast
        self.dependencies = DependencyInfo()
        
        # Build symbol tables for the entire module
        self.module_functions = {}  # name -> node
        self.module_classes = {}    # name -> node
        self.module_constants = {}  # name -> node
        self.module_imports = {}    # name -> import statement
        
        # Track current scope for nested analysis
        self.current_class = None
        self.in_scene = False
        
        # Build the symbol tables
        self._build_symbol_tables()
        
    def _build_symbol_tables(self):
        """Build symbol tables for the entire module."""
        for node in ast.walk(self.full_ast):
            if isinstance(node, ast.FunctionDef) and self._is_top_level(node):
                self.module_functions[node.name] = node
            elif isinstance(node, ast.ClassDef) and self._is_top_level(node):
                self.module_classes[node.name] = node
            elif isinstance(node, ast.Assign) and self._is_top_level(node):
                # Extract constant assignments
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Check if it's likely a constant (UPPER_CASE or CONFIG)
                        if target.id.isupper() or target.id == 'CONFIG':
                            self.module_constants[target.id] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # Track imports
                self._record_import(node)
    
    def _is_top_level(self, node: ast.AST) -> bool:
        """Check if a node is at module top level."""
        # This is a simplified check - in practice, we'd track scope more carefully
        for parent in ast.walk(self.full_ast):
            if parent == self.full_ast:
                continue
            if isinstance(parent, (ast.FunctionDef, ast.ClassDef)):
                if any(child == node for child in ast.walk(parent)):
                    return False
        return True
    
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
                else:
                    import_str = f"from {module} import {alias.name}"
                    if alias.asname:
                        import_str += f" as {alias.asname}"
                    self.module_imports[alias.asname or alias.name] = import_str
                    self.dependencies.imports.add(import_str)
    
    def analyze(self) -> DependencyInfo:
        """Analyze the scene and return its dependencies."""
        # First, analyze the scene itself
        self.in_scene = True
        self.visit(self.scene_node)
        self.in_scene = False
        
        # Then, recursively analyze all dependencies
        self._analyze_dependencies_recursively()
        
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
        # Check if it's from an import
        elif name in self.module_imports:
            # Already tracked in imports
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


def extract_code_for_dependencies(full_ast: ast.Module, source_lines: List[str], 
                                 dependencies: DependencyInfo) -> Dict[str, str]:
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
    
    # Extract imports
    for import_stmt in dependencies.imports:
        extracted['imports'].append(import_stmt)
    
    # Extract constants
    for const_name in dependencies.constants:
        for node in ast.walk(full_ast):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == const_name:
                        # Extract the assignment
                        start_line = node.lineno - 1
                        end_line = node.end_lineno or node.lineno
                        code = '\n'.join(source_lines[start_line:end_line])
                        extracted['constants'].append(code)
    
    # Extract functions
    for func_name in dependencies.functions:
        for node in ast.walk(full_ast):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                start_line = node.lineno - 1
                # Find the end of the function
                end_line = find_node_end_line(node, source_lines)
                code = '\n'.join(source_lines[start_line:end_line])
                extracted['functions'].append(code)
    
    # Extract classes
    for class_name in dependencies.classes:
        for node in ast.walk(full_ast):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                start_line = node.lineno - 1
                # Find the end of the class
                end_line = find_node_end_line(node, source_lines)
                code = '\n'.join(source_lines[start_line:end_line])
                extracted['classes'].append(code)
    
    return extracted


def find_node_end_line(node: ast.AST, source_lines: List[str]) -> int:
    """
    Find the actual end line of a node, including its body.
    This is more accurate than the simple approach in the current code.
    """
    if hasattr(node, 'end_lineno') and node.end_lineno:
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
        # Fallback for older Python versions
        end_line = node.lineno
        
        # Walk through all child nodes to find the furthest line
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                end_line = max(end_line, child.lineno)
    
    return end_line