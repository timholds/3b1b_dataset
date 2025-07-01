#!/usr/bin/env python3
"""
Scene Combiner - Intelligently combines validated snippets into a complete file.

This module handles the combination of individually validated scene snippets
into a single ManimCE file, deduplicating imports and helper code.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import logging
logger = logging.getLogger(__name__)


class SceneCombiner:
    """Combines validated scene snippets into a cohesive ManimCE file."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
    def combine_snippets(self, snippets: Dict[str, str], video_name: str = "") -> str:
        """
        Combine multiple validated snippets into a single file.
        
        Args:
            snippets: Dictionary mapping scene names to snippet content
            video_name: Name of the video for documentation
            
        Returns:
            Combined ManimCE code with deduplicated imports and helpers
        """
        if not snippets:
            return ""
            
        # Parse all snippets
        parsed_snippets = {}
        for scene_name, content in snippets.items():
            try:
                parsed = self._parse_snippet(content, scene_name)
                parsed_snippets[scene_name] = parsed
            except Exception as e:
                logger.error(f"Failed to parse snippet {scene_name}: {e}")
                
        if not parsed_snippets:
            return ""
            
        # Build combined file
        combined_parts = []
        
        # Header
        combined_parts.append("#!/usr/bin/env python3")
        combined_parts.append('"""')
        combined_parts.append(f"Combined ManimCE code for: {video_name}")
        combined_parts.append("Auto-generated from individually validated scene snippets")
        combined_parts.append('"""')
        combined_parts.append("")
        
        # Collect and deduplicate imports
        all_imports = self._collect_imports(parsed_snippets)
        combined_parts.extend(all_imports)
        combined_parts.append("")
        
        # Collect and deduplicate constants
        all_constants = self._collect_constants(parsed_snippets)
        if all_constants:
            combined_parts.append("# Constants")
            combined_parts.extend(all_constants)
            combined_parts.append("")
            
        # Collect and deduplicate helper functions
        all_functions = self._collect_functions(parsed_snippets)
        if all_functions:
            combined_parts.append("# Helper functions")
            combined_parts.extend(all_functions)
            combined_parts.append("")
            
        # Collect and deduplicate helper classes
        all_classes = self._collect_helper_classes(parsed_snippets)
        if all_classes:
            combined_parts.append("# Helper classes")
            combined_parts.extend(all_classes)
            combined_parts.append("")
            
        # Add all scene classes
        combined_parts.append("# Scene classes")
        for scene_name in sorted(parsed_snippets.keys()):
            parsed = parsed_snippets[scene_name]
            if 'scene_class' in parsed:
                combined_parts.append(f"# From validated snippet: {scene_name}")
                combined_parts.append(parsed['scene_class'])
                combined_parts.append("")
                
        return '\n'.join(combined_parts)
        
    def _parse_snippet(self, content: str, scene_name: str) -> Dict[str, any]:
        """Parse a snippet into its components."""
        result = {
            'imports': [],
            'constants': [],
            'functions': [],
            'helper_classes': [],
            'scene_class': None,
            'other': []
        }
        
        # Split content into logical sections
        lines = content.split('\n')
        current_section = []
        in_class = False
        in_function = False
        class_indent = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Skip empty lines and comments at module level
            if not in_class and not in_function and (not stripped or stripped.startswith('#')):
                if stripped.startswith('#') and not any(
                    marker in stripped for marker in ['Constants', 'Helper', 'Main scene', 'From validated']
                ):
                    current_section.append(line)
                i += 1
                continue
                
            # Handle imports
            if stripped.startswith(('import ', 'from ')) and not in_class and not in_function:
                result['imports'].append(line)
                i += 1
                continue
                
            # Handle class definitions
            if re.match(r'^class\s+\w+', stripped) and not in_class:
                # Check if this is the scene class
                class_match = re.match(r'^class\s+(\w+)', stripped)
                if class_match:
                    class_name = class_match.group(1)
                    
                    # Collect the entire class
                    class_lines = [line]
                    i += 1
                    class_indent = len(line) - len(line.lstrip())
                    
                    while i < len(lines):
                        next_line = lines[i]
                        next_stripped = next_line.strip()
                        
                        # Check if we're still in the class
                        if next_stripped and not next_line.startswith(' ' * (class_indent + 1)):
                            # Check if it's another class or function at same level
                            if re.match(r'^(class|def)\s+', next_stripped):
                                break
                                
                        class_lines.append(next_line)
                        i += 1
                        
                    class_content = '\n'.join(class_lines).rstrip()
                    
                    # Determine if it's the scene class or a helper
                    if class_name == scene_name or 'Scene' in class_name:
                        result['scene_class'] = class_content
                    else:
                        result['helper_classes'].append(class_content)
                continue
                
            # Handle function definitions
            if re.match(r'^def\s+\w+', stripped) and not in_class:
                # Collect the entire function
                func_lines = [line]
                i += 1
                func_indent = len(line) - len(line.lstrip())
                
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    
                    # Check if we're still in the function
                    if next_stripped and not next_line.startswith(' ' * (func_indent + 1)):
                        # Check if it's another function or class at same level
                        if re.match(r'^(class|def)\s+', next_stripped):
                            break
                            
                    func_lines.append(next_line)
                    i += 1
                    
                func_content = '\n'.join(func_lines).rstrip()
                result['functions'].append(func_content)
                continue
                
            # Handle constants (simple assignments at module level)
            if '=' in stripped and not in_class and not in_function:
                # Check if it looks like a constant (but exclude indented code)
                if ((re.match(r'^[A-Z_]+\s*=', stripped) or re.match(r'^\w+\s*=\s*[\[\{\(]', stripped)) and
                    not line.startswith((' ', '\t'))):  # Exclude indented code
                    result['constants'].append(line)
                    i += 1
                    continue
                    
            # Everything else
            result['other'].append(line)
            i += 1
            
        return result
        
    def _collect_imports(self, parsed_snippets: Dict[str, Dict]) -> List[str]:
        """Collect and deduplicate imports from all snippets."""
        seen_imports = set()
        ordered_imports = []
        
        # Always start with manim import
        manim_import = "from manim import *"
        seen_imports.add(manim_import)
        ordered_imports.append(manim_import)
        
        # Collect all other imports
        for parsed in parsed_snippets.values():
            for import_line in parsed['imports']:
                normalized = import_line.strip()
                if normalized and normalized not in seen_imports:
                    # Skip redundant manim imports
                    if 'manim' in normalized and any(
                        pattern in normalized for pattern in ['from manim', 'import manim']
                    ):
                        continue
                    seen_imports.add(normalized)
                    ordered_imports.append(normalized)
                    
        # Sort imports (standard library first, then third party)
        std_imports = []
        third_party = []
        
        for imp in ordered_imports[1:]:  # Skip the manim import
            if imp.startswith('import ') and '.' not in imp.split()[1]:
                std_imports.append(imp)
            else:
                third_party.append(imp)
                
        final_imports = [manim_import]
        if std_imports:
            final_imports.extend(sorted(std_imports))
        if third_party:
            final_imports.extend(sorted(third_party))
            
        return final_imports
        
    def _collect_constants(self, parsed_snippets: Dict[str, Dict]) -> List[str]:
        """Collect and deduplicate constants from all snippets."""
        seen_constants = {}
        
        for parsed in parsed_snippets.values():
            for const in parsed['constants']:
                # Extract constant name
                match = re.match(r'^(\w+)\s*=', const.strip())
                if match:
                    const_name = match.group(1)
                    if const_name not in seen_constants:
                        seen_constants[const_name] = const
                        
        return list(seen_constants.values())
        
    def _collect_functions(self, parsed_snippets: Dict[str, Dict]) -> List[str]:
        """Collect and deduplicate helper functions from all snippets."""
        seen_functions = {}
        
        for parsed in parsed_snippets.values():
            for func in parsed['functions']:
                # Extract function name
                match = re.search(r'^def\s+(\w+)', func, re.MULTILINE)
                if match:
                    func_name = match.group(1)
                    if func_name not in seen_functions:
                        seen_functions[func_name] = func
                        
        return list(seen_functions.values())
        
    def _collect_helper_classes(self, parsed_snippets: Dict[str, Dict]) -> List[str]:
        """Collect and deduplicate helper classes from all snippets."""
        seen_classes = {}
        
        for parsed in parsed_snippets.values():
            for cls in parsed['helper_classes']:
                # Extract class name
                match = re.search(r'^class\s+(\w+)', cls, re.MULTILINE)
                if match:
                    class_name = match.group(1)
                    if class_name not in seen_classes:
                        seen_classes[class_name] = cls
                        
        return list(seen_classes.values())


def test_scene_combiner():
    """Test the scene combiner with sample snippets."""
    
    snippet1 = """from manim import *
import numpy as np

# Constants
SCALE_FACTOR = 2

def helper_func():
    return Circle()

class HelperClass:
    pass

class Scene1(Scene):
    def construct(self):
        self.add(Circle())
"""

    snippet2 = """from manim import *
import numpy as np
import math

# Constants
SCALE_FACTOR = 2
ANOTHER_CONST = 3

def helper_func():
    return Circle()
    
def another_helper():
    return Square()

class Scene2(Scene):
    def construct(self):
        self.add(Square())
"""
    
    combiner = SceneCombiner(verbose=True)
    
    snippets = {
        'Scene1': snippet1,
        'Scene2': snippet2
    }
    
    combined = combiner.combine_snippets(snippets, "test_video")
    
    print("Combined output:")
    print("=" * 60)
    print(combined)
    
    # Verify no duplicate imports or functions
    lines = combined.split('\n')
    import_count = sum(1 for line in lines if 'import numpy' in line)
    func_count = sum(1 for line in lines if 'def helper_func' in line)
    const_count = sum(1 for line in lines if 'SCALE_FACTOR = 2' in line)
    
    print("\n" + "=" * 60)
    print(f"Import numpy count: {import_count} (should be 1)")
    print(f"helper_func count: {func_count} (should be 1)")
    print(f"SCALE_FACTOR count: {const_count} (should be 1)")
    

if __name__ == "__main__":
    test_scene_combiner()