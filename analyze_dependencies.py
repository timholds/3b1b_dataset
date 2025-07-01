#!/usr/bin/env python3
"""
Analyze dependencies in the scripts directory to identify which files are not part of the main pipeline.
"""

import ast
import re
from pathlib import Path
from typing import Set, Dict, List, Tuple

def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all local imports from a Python file."""
    local_imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse with AST for proper imports
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Only consider imports that could be local scripts
                        if not alias.name.startswith(('json', 'os', 'sys', 'time', 'logging', 'datetime', 
                                                     'pathlib', 'typing', 'collections', 'itertools',
                                                     'subprocess', 'concurrent', 'functools', 'operator',
                                                     'math', 're', 'string', 'random', 'uuid', 'hashlib')):
                            local_imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not node.module.startswith(('json', 'os', 'sys', 'time', 'logging', 'datetime', 
                                                                  'pathlib', 'typing', 'collections', 'itertools',
                                                                  'subprocess', 'concurrent', 'functools', 'operator',
                                                                  'math', 're', 'string', 'random', 'uuid', 'hashlib')):
                        local_imports.add(node.module)
        except SyntaxError:
            # Fallback to regex if AST parsing fails
            pass
        
        # Also use regex as fallback for dynamic imports
        regex_imports = re.findall(r'^(?:from\s+(\w+)\s+import|import\s+(\w+))', content, re.MULTILINE)
        for match in regex_imports:
            module = match[0] or match[1]
            if module and not module.startswith(('json', 'os', 'sys', 'time', 'logging', 'datetime', 
                                               'pathlib', 'typing', 'collections', 'itertools',
                                               'subprocess', 'concurrent', 'functools', 'operator',
                                               'math', 're', 'string', 'random', 'uuid', 'hashlib')):
                local_imports.add(module)
                
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return local_imports

def build_dependency_graph() -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build a dependency graph of all Python files in scripts/."""
    scripts_dir = Path('/Users/timholdsworth/code/3b1b_dataset/scripts')
    dependencies = {}
    all_files = set()
    
    # Get all Python files
    python_files = list(scripts_dir.glob('*.py'))
    
    for file_path in python_files:
        file_name = file_path.stem
        all_files.add(file_name)
        dependencies[file_name] = extract_imports_from_file(file_path)
    
    return dependencies, all_files

def find_dependencies_recursive(module: str, dependencies: Dict[str, Set[str]], 
                               visited: Set[str]) -> Set[str]:
    """Recursively find all dependencies of a module."""
    if module in visited:
        return set()
    
    visited.add(module)
    all_deps = set()
    
    if module in dependencies:
        direct_deps = dependencies[module]
        all_deps.update(direct_deps)
        
        for dep in direct_deps:
            all_deps.update(find_dependencies_recursive(dep, dependencies, visited.copy()))
    
    return all_deps

def main():
    print("Analyzing Python file dependencies in scripts/...")
    
    # Build dependency graph
    dependencies, all_files = build_dependency_graph()
    
    # Core files directly imported by build_dataset_pipeline.py
    core_files = {
        'claude_match_videos',
        'hybrid_cleaner', 
        'parameterized_scene_converter',
        'render_videos',
        'manimce_precompile_validator',
        'conversion_error_collector',
        'generate_comparison_report',
        'scene_validator',
        'systematic_pipeline_converter',
        'integrated_pipeline_converter',
        'extract_video_urls'  # called via subprocess
    }
    
    # Find all files in the dependency chain
    used_files = set(core_files)
    
    for core_file in core_files:
        deps = find_dependencies_recursive(core_file, dependencies, set())
        used_files.update(deps)
    
    # Remove any that don't exist as actual files
    used_files = {f for f in used_files if f in all_files}
    
    # Find unused files
    unused_files = all_files - used_files
    
    print(f"\n=== DEPENDENCY ANALYSIS ===")
    print(f"Total Python files: {len(all_files)}")
    print(f"Files in dependency chain: {len(used_files)}")
    print(f"Unused files: {len(unused_files)}")
    
    print(f"\n=== CORE FILES (directly imported by build_dataset_pipeline.py) ===")
    for file in sorted(core_files):
        if file in all_files:
            print(f"✓ {file}.py")
        else:
            print(f"✗ {file}.py (missing)")
    
    print(f"\n=== DEPENDENCY CHAIN (used by core files) ===")
    dependency_chain = used_files - core_files
    for file in sorted(dependency_chain):
        print(f"  {file}.py")
    
    print(f"\n=== UNUSED FILES (safe to delete) ===")
    for file in sorted(unused_files):
        print(f"🗑️  {file}.py")
    
    # Show dependencies for some key files
    print(f"\n=== KEY DEPENDENCIES ===")
    key_files = ['systematic_pipeline_converter', 'hybrid_cleaner', 'enhanced_scene_converter']
    for key_file in key_files:
        if key_file in dependencies:
            deps = dependencies[key_file]
            deps_exist = {d for d in deps if d in all_files}
            if deps_exist:
                print(f"{key_file}.py depends on:")
                for dep in sorted(deps_exist):
                    print(f"  → {dep}.py")
    
    return unused_files

if __name__ == '__main__':
    unused = main()