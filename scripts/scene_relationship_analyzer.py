#!/usr/bin/env python3
"""
Scene relationship analyzer for understanding connections between scenes.
This helps preserve the mathematical and educational flow when processing scenes.
"""

import ast
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class SceneRelationship:
    """Represents a relationship between two scenes."""
    from_scene: str
    to_scene: str
    relationship_type: str  # 'references', 'inherits', 'follows', 'transforms'
    evidence: List[str] = field(default_factory=list)


@dataclass
class SceneContext:
    """Context information for a scene."""
    scene_name: str
    mathematical_objects: Set[str] = field(default_factory=set)
    created_objects: Set[str] = field(default_factory=set)
    referenced_scenes: Set[str] = field(default_factory=set)
    position_in_video: int = 0
    educational_purpose: str = ""
    shared_utilities: Set[str] = field(default_factory=set)


class SceneRelationshipAnalyzer:
    """Analyzes relationships between scenes to preserve context and flow."""
    
    def __init__(self, scenes: List['SceneInfo']):
        self.scenes = {scene.name: scene for scene in scenes}
        self.relationships: List[SceneRelationship] = []
        self.scene_contexts: Dict[str, SceneContext] = {}
        
    def analyze_all_relationships(self) -> Dict[str, any]:
        """Analyze relationships between all scenes."""
        # First pass: build context for each scene
        for scene_name, scene in self.scenes.items():
            context = self._analyze_scene_context(scene)
            self.scene_contexts[scene_name] = context
        
        # Second pass: find relationships
        for scene_name, scene in self.scenes.items():
            self._find_scene_relationships(scene)
        
        # Analyze the flow
        flow_analysis = self._analyze_educational_flow()
        
        return {
            'contexts': self.scene_contexts,
            'relationships': self.relationships,
            'flow_analysis': flow_analysis,
            'shared_objects': self._find_shared_objects(),
            'scene_order': self._determine_optimal_order()
        }
    
    def _analyze_scene_context(self, scene: 'SceneInfo') -> SceneContext:
        """Extract context information from a scene."""
        context = SceneContext(scene_name=scene.name)
        
        try:
            tree = ast.parse(scene.code)
        except SyntaxError:
            logger.warning(f"Could not parse scene {scene.name} for context analysis")
            return context
        
        # Find mathematical objects and concepts
        class ContextVisitor(ast.NodeVisitor):
            def __init__(self, context: SceneContext):
                self.context = context
                
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    
                    # Track mathematical object creation
                    if func_name in ['Circle', 'Square', 'Line', 'Arrow', 'Dot', 
                                     'Text', 'TexMobject', 'TextMobject', 'Axes',
                                     'NumberPlane', 'FunctionGraph', 'ParametricFunction']:
                        self.context.mathematical_objects.add(func_name)
                    
                    # Track scene references
                    if 'Scene' in func_name and func_name != 'Scene':
                        self.context.referenced_scenes.add(func_name)
                
                self.generic_visit(node)
            
            def visit_Assign(self, node):
                # Track object creation
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.context.created_objects.add(target.id)
                self.generic_visit(node)
        
        visitor = ContextVisitor(context)
        visitor.visit(tree)
        
        # Extract educational purpose from docstrings or comments
        context.educational_purpose = self._extract_purpose(scene.code)
        
        # Track shared utilities from dependencies
        if hasattr(scene, 'dependency_info'):
            context.shared_utilities = scene.dependency_info.functions.copy()
        
        return context
    
    def _find_scene_relationships(self, scene: 'SceneInfo'):
        """Find relationships between this scene and others."""
        context = self.scene_contexts[scene.name]
        
        # Check for inheritance relationships
        try:
            tree = ast.parse(scene.code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == scene.name:
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id in self.scenes:
                            self.relationships.append(SceneRelationship(
                                from_scene=scene.name,
                                to_scene=base.id,
                                relationship_type='inherits',
                                evidence=[f"class {scene.name}({base.id})"]
                            ))
        except SyntaxError:
            pass
        
        # Check for references in code
        for other_scene in self.scenes:
            if other_scene != scene.name:
                if other_scene in scene.code:
                    # Find the context of the reference
                    evidence = self._find_reference_context(scene.code, other_scene)
                    if evidence:
                        self.relationships.append(SceneRelationship(
                            from_scene=scene.name,
                            to_scene=other_scene,
                            relationship_type='references',
                            evidence=evidence
                        ))
        
        # Check for shared mathematical objects (indicates flow)
        for other_name, other_context in self.scene_contexts.items():
            if other_name != scene.name:
                shared_objects = context.mathematical_objects & other_context.mathematical_objects
                if shared_objects:
                    self.relationships.append(SceneRelationship(
                        from_scene=scene.name,
                        to_scene=other_name,
                        relationship_type='transforms',
                        evidence=[f"Shared objects: {', '.join(shared_objects)}"]
                    ))
    
    def _find_reference_context(self, code: str, referenced_scene: str) -> List[str]:
        """Find context lines where a scene is referenced."""
        evidence = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines):
            if referenced_scene in line:
                # Get surrounding context
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = lines[start:end]
                evidence.append(' | '.join(line.strip() for line in context if line.strip()))
        
        return evidence
    
    def _extract_purpose(self, code: str) -> str:
        """Extract educational purpose from docstrings or comments."""
        lines = code.split('\n')
        
        # Look for docstrings
        in_docstring = False
        docstring_lines = []
        
        for line in lines:
            if '"""' in line or "'''" in line:
                if in_docstring:
                    docstring_lines.append(line)
                    in_docstring = False
                    break
                else:
                    in_docstring = True
                    docstring_lines.append(line)
            elif in_docstring:
                docstring_lines.append(line)
        
        if docstring_lines:
            return ' '.join(docstring_lines).strip()
        
        # Look for leading comments
        for line in lines[:5]:
            if line.strip().startswith('#') and len(line.strip()) > 10:
                return line.strip()[1:].strip()
        
        return ""
    
    def _find_shared_objects(self) -> Dict[str, Set[str]]:
        """Find objects shared between multiple scenes."""
        shared = {}
        
        # Find objects that appear in multiple scenes
        object_scenes = {}  # object -> set of scenes using it
        
        for scene_name, context in self.scene_contexts.items():
            for obj in context.created_objects:
                if obj not in object_scenes:
                    object_scenes[obj] = set()
                object_scenes[obj].add(scene_name)
        
        # Filter to only shared objects
        for obj, scenes in object_scenes.items():
            if len(scenes) > 1:
                shared[obj] = scenes
        
        return shared
    
    def _analyze_educational_flow(self) -> Dict[str, any]:
        """Analyze the educational flow through scenes."""
        flow = {
            'introduction_scenes': [],
            'development_scenes': [],
            'conclusion_scenes': [],
            'independent_scenes': []
        }
        
        # Identify scene types based on relationships and content
        for scene_name, context in self.scene_contexts.items():
            incoming = [r for r in self.relationships if r.to_scene == scene_name]
            outgoing = [r for r in self.relationships if r.from_scene == scene_name]
            
            # Introduction scenes: few dependencies, create many objects
            if len(incoming) == 0 and len(context.created_objects) > 2:
                flow['introduction_scenes'].append(scene_name)
            # Development scenes: both incoming and outgoing relationships
            elif len(incoming) > 0 and len(outgoing) > 0:
                flow['development_scenes'].append(scene_name)
            # Conclusion scenes: many dependencies, few dependents
            elif len(incoming) > 1 and len(outgoing) == 0:
                flow['conclusion_scenes'].append(scene_name)
            # Independent scenes: no relationships
            elif len(incoming) == 0 and len(outgoing) == 0:
                flow['independent_scenes'].append(scene_name)
        
        return flow
    
    def _determine_optimal_order(self) -> List[str]:
        """Determine the optimal order for processing scenes."""
        # Start with topological sort based on dependencies
        ordered = []
        visited = set()
        
        def visit(scene_name):
            if scene_name in visited:
                return
            visited.add(scene_name)
            
            # Visit dependencies first
            for rel in self.relationships:
                if rel.from_scene == scene_name and rel.relationship_type in ['inherits', 'references']:
                    visit(rel.to_scene)
            
            ordered.append(scene_name)
        
        # Visit all scenes
        for scene_name in self.scenes:
            visit(scene_name)
        
        return ordered
    
    def get_scene_dependencies(self, scene_name: str) -> Set[str]:
        """Get all scenes that this scene depends on."""
        dependencies = set()
        
        for rel in self.relationships:
            if rel.from_scene == scene_name and rel.relationship_type in ['inherits', 'references']:
                dependencies.add(rel.to_scene)
        
        return dependencies
    
    def get_processing_groups(self) -> List[List[str]]:
        """Group scenes that can be processed together."""
        groups = []
        processed = set()
        
        # Process in dependency order
        optimal_order = self._determine_optimal_order()
        
        for scene in optimal_order:
            if scene in processed:
                continue
            
            # Find all scenes that can be processed with this one
            group = [scene]
            processed.add(scene)
            
            # Add scenes that have no dependencies on unprocessed scenes
            for other_scene in optimal_order:
                if other_scene in processed:
                    continue
                
                deps = self.get_scene_dependencies(other_scene)
                if deps.issubset(processed):
                    group.append(other_scene)
                    processed.add(other_scene)
            
            groups.append(group)
        
        return groups