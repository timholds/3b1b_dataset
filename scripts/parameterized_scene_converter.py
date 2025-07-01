#!/usr/bin/env python3
"""
Parameterized Scene Converter

Automatically converts parameterized scenes (construct methods with parameters)
to standard ManimCE pattern using __init__ and instance attributes.

This eliminates the need for manual Claude conversion of these patterns.
"""

import ast
import re
from typing import Tuple, List, Optional, Dict, Any
import logging

class ParameterizedSceneConverter:
    """Automatically convert parameterized scenes during cleaning stage."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
    def is_parameterized_scene(self, code: str) -> bool:
        """Check if code contains a parameterized construct method."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if (isinstance(node, ast.FunctionDef) and 
                    node.name == 'construct' and
                    len(node.args.args) > 1):  # More than just 'self'
                    return True
            return False
        except SyntaxError:
            return False
    
    def extract_scene_parameters(self, construct_node: ast.FunctionDef) -> List[str]:
        """Extract parameter names from construct method (excluding 'self')."""
        params = []
        for arg in construct_node.args.args[1:]:  # Skip 'self'
            params.append(arg.arg)
        return params
    
    def create_init_method(self, params: List[str], defaults: List[Any] = None) -> ast.FunctionDef:
        """Create an __init__ method that stores parameters as instance attributes."""
        if defaults is None:
            defaults = []
            
        # Create function arguments: self + parameters
        args = [ast.arg(arg='self', annotation=None)]
        for param in params:
            args.append(ast.arg(arg=param, annotation=None))
        
        # Create function body: self.param = param for each parameter
        body = []
        for param in params:
            assign = ast.Assign(
                targets=[ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), 
                                     attr=param, ctx=ast.Store())],
                value=ast.Name(id=param, ctx=ast.Load())
            )
            body.append(assign)
        
        # Create the __init__ method
        init_method = ast.FunctionDef(
            name='__init__',
            args=ast.arguments(
                posonlyargs=[],
                args=args,
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=defaults
            ),
            body=body,
            decorator_list=[],
            returns=None
        )
        
        # Fix AST nodes for unparsing
        ast.fix_missing_locations(init_method)
        
        return init_method
    
    def modify_construct_body(self, construct_node: ast.FunctionDef, params: List[str]) -> ast.FunctionDef:
        """Modify construct method body to use self.param instead of param."""
        
        class ParameterReplacer(ast.NodeTransformer):
            def __init__(self, param_names: List[str]):
                self.param_names = param_names
                
            def visit_Name(self, node):
                # Replace parameter references with self.parameter
                if (isinstance(node.ctx, ast.Load) and 
                    node.id in self.param_names):
                    return ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr=node.id,
                        ctx=ast.Load()
                    )
                return node
        
        # Create new construct method with modified body
        replacer = ParameterReplacer(params)
        new_body = [replacer.visit(stmt) for stmt in construct_node.body]
        
        # Create new construct method with just 'self' parameter
        new_construct = ast.FunctionDef(
            name='construct',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self', annotation=None)],  # Only self
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]
            ),
            body=new_body,
            decorator_list=construct_node.decorator_list,
            returns=construct_node.returns
        )
        
        # Fix AST nodes for unparsing
        ast.fix_missing_locations(new_construct)
        
        return new_construct
    
    def convert_scene_class(self, class_node: ast.ClassDef) -> Tuple[ast.ClassDef, bool]:
        """Convert a single scene class if it has parameterized construct."""
        converted = False
        new_body = []
        construct_node = None
        params = []
        
        # Find construct method and extract parameters
        for node in class_node.body:
            if (isinstance(node, ast.FunctionDef) and 
                node.name == 'construct' and
                len(node.args.args) > 1):
                construct_node = node
                params = self.extract_scene_parameters(node)
                converted = True
                break
        
        if not converted:
            return class_node, False
        
        # Build new class body
        has_init = False
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                if node.name == '__init__':
                    has_init = True
                    # Keep existing __init__ - assume it's compatible
                    new_body.append(node)
                elif node.name == 'construct':
                    # Replace with modified construct
                    new_construct = self.modify_construct_body(node, params)
                    new_body.append(new_construct)
                else:
                    # Keep other methods as-is
                    new_body.append(node)
            else:
                # Keep non-method nodes (class variables, etc.)
                new_body.append(node)
        
        # Add __init__ method if not present
        if not has_init:
            init_method = self.create_init_method(params)
            new_body.insert(0, init_method)  # Add at beginning of class
        
        # Create new class with modified body
        new_class = ast.ClassDef(
            name=class_node.name,
            bases=class_node.bases,
            keywords=class_node.keywords,
            body=new_body,
            decorator_list=class_node.decorator_list
        )
        
        return new_class, True
    
    def convert_parameterized_scene(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """Convert construct(self, param) to standard pattern."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return code, False, {'error': f'Syntax error: {e}'}
        
        converted = False
        conversion_info = {
            'converted_classes': [],
            'total_parameters': 0
        }
        
        class SceneConverter(ast.NodeTransformer):
            def __init__(self, converter_instance):
                self.converter = converter_instance
                
            def visit_ClassDef(self, node):
                # Check if this class has Scene in its inheritance or name
                is_scene_class = (
                    'Scene' in node.name or
                    node.name.endswith('Scene') or  # Handle classes ending with Scene
                    any('Scene' in base.id if isinstance(base, ast.Name) else False 
                        for base in node.bases) or
                    any(base.id.endswith('Scene') if isinstance(base, ast.Name) else False 
                        for base in node.bases)  # Handle inheritance from *Scene classes
                )
                
                if is_scene_class:
                    new_class, class_converted = self.converter.convert_scene_class(node)
                    if class_converted:
                        nonlocal converted
                        converted = True
                        conversion_info['converted_classes'].append(node.name)
                        
                        # Count parameters
                        for method in node.body:
                            if (isinstance(method, ast.FunctionDef) and 
                                method.name == 'construct' and
                                len(method.args.args) > 1):
                                conversion_info['total_parameters'] += len(method.args.args) - 1
                    
                    return new_class
                
                return node
        
        converter = SceneConverter(self)
        new_tree = converter.visit(tree)
        
        if converted:
            try:
                # Fix missing locations for the entire tree
                ast.fix_missing_locations(new_tree)
                converted_code = ast.unparse(new_tree)
                if self.verbose:
                    self.logger.info(f"Converted parameterized scenes: {conversion_info['converted_classes']}")
                return converted_code, True, conversion_info
            except Exception as e:
                return code, False, {'error': f'Failed to unparse: {e}'}
        
        return code, False, conversion_info
    
    def convert_file_content(self, file_content: str, file_path: str = '') -> Tuple[str, bool, Dict[str, Any]]:
        """Convert parameterized scenes in file content."""
        if not self.is_parameterized_scene(file_content):
            return file_content, False, {'message': 'No parameterized scenes found'}
        
        if self.verbose:
            self.logger.info(f"Found parameterized scene(s) in {file_path or 'content'}")
        
        return self.convert_parameterized_scene(file_content)
    
    def validate_conversion(self, original_code: str, converted_code: str) -> Dict[str, Any]:
        """Validate that the conversion was successful."""
        validation_result = {
            'syntax_valid': False,
            'has_init': False,
            'construct_params_removed': False,
            'issues': []
        }
        
        try:
            # Check syntax
            ast.parse(converted_code)
            validation_result['syntax_valid'] = True
        except SyntaxError as e:
            validation_result['issues'].append(f'Syntax error: {e}')
            return validation_result
        
        try:
            # Find which classes were parameterized in the original code
            original_tree = ast.parse(original_code)
            parameterized_classes = set()
            
            for node in ast.walk(original_tree):
                if isinstance(node, ast.ClassDef):
                    # Check if this class has parameterized construct
                    for method in node.body:
                        if (isinstance(method, ast.FunctionDef) and 
                            method.name == 'construct' and
                            len(method.args.args) > 1):
                            parameterized_classes.add(node.name)
                            break
            
            # Now validate only the converted classes
            converted_tree = ast.parse(converted_code)
            
            for node in ast.walk(converted_tree):
                if isinstance(node, ast.ClassDef) and node.name in parameterized_classes:
                    has_init = False
                    construct_has_params = False
                    
                    for method in node.body:
                        if isinstance(method, ast.FunctionDef):
                            if method.name == '__init__':
                                has_init = True
                            elif method.name == 'construct':
                                if len(method.args.args) > 1:
                                    construct_has_params = True
                    
                    validation_result['has_init'] = has_init
                    validation_result['construct_params_removed'] = not construct_has_params
                    
                    if not has_init:
                        validation_result['issues'].append(f'No __init__ method found in converted scene {node.name}')
                    if construct_has_params:
                        validation_result['issues'].append(f'construct method still has parameters in {node.name}')
            
        except Exception as e:
            validation_result['issues'].append(f'Validation error: {e}')
        
        return validation_result


def test_parameterized_converter():
    """Test the parameterized scene converter with sample code."""
    
    # Test case 1: Simple parameterized scene
    sample_code = """
class TestScene(Scene):
    def construct(self, mode="normal"):
        if mode == "fast":
            self.play(Write(Text("Fast mode")))
        else:
            self.play(Write(Text("Normal mode")))
"""
    
    converter = ParameterizedSceneConverter(verbose=True)
    
    print("Original code:")
    print(sample_code)
    print("\n" + "="*50 + "\n")
    
    converted_code, success, info = converter.convert_file_content(sample_code)
    
    if success:
        print("Converted code:")
        print(converted_code)
        print(f"\nConversion info: {info}")
        
        # Validate conversion
        validation = converter.validate_conversion(sample_code, converted_code)
        print(f"\nValidation: {validation}")
    else:
        print("No conversion needed or failed")
        print(f"Info: {info}")


if __name__ == '__main__':
    test_parameterized_converter()