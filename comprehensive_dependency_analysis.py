#!/usr/bin/env python3
"""
Comprehensive dependency analysis of the scripts directory.
This accounts for all import patterns including dynamic imports and prefixed imports.
"""

import re
from pathlib import Path
from typing import Set, Dict, List

def extract_all_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all local imports from a Python file using comprehensive regex patterns."""
    local_imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern 1: from module import ...
        from_imports = re.findall(r'from\s+(?:scripts\.)?(\w+)\s+import', content)
        local_imports.update(from_imports)
        
        # Pattern 2: import module
        direct_imports = re.findall(r'^import\s+(?:scripts\.)?(\w+)', content, re.MULTILINE)
        local_imports.update(direct_imports)
        
        # Pattern 3: dynamic imports with path joining
        dynamic_imports = re.findall(r"'(\w+)\.py'", content)
        local_imports.update(dynamic_imports)
        
        # Pattern 4: importlib or __import__ calls
        dynamic_import_calls = re.findall(r'__import__\([\'"](\w+)[\'"]', content)
        local_imports.update(dynamic_import_calls)
        
        # Pattern 5: file references in strings
        file_refs = re.findall(r"['\"](\w+)\.py['\"]", content)  
        local_imports.update(file_refs)
        
        # Filter out standard library modules and keep only potential local modules
        stdlib_modules = {'json', 'os', 'sys', 'time', 'logging', 'datetime', 'pathlib', 'typing', 
                         'collections', 'itertools', 'subprocess', 'concurrent', 'functools', 
                         'operator', 'math', 're', 'string', 'random', 'uuid', 'hashlib', 'ast',
                         'importlib', 'inspect', 'copy', 'pickle', 'shutil', 'tempfile', 'io',
                         'warnings', 'traceback', 'argparse', 'configparser', 'urllib', 'http',
                         'xml', 'html', 'email', 'multiprocessing', 'threading', 'queue', 'socket'}
        
        local_imports = {imp for imp in local_imports if imp not in stdlib_modules}
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return local_imports

def main():
    scripts_dir = Path('/Users/timholdsworth/code/3b1b_dataset/scripts')
    
    # Get all Python files
    python_files = list(scripts_dir.glob('*.py'))
    all_files = {f.stem for f in python_files}
    
    # Build dependencies
    dependencies = {}
    for file_path in python_files:
        file_name = file_path.stem
        deps = extract_all_imports_from_file(file_path)
        # Only keep dependencies that exist as actual files
        dependencies[file_name] = {d for d in deps if d in all_files}
    
    # Core files from build_dataset_pipeline.py analysis
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
        'extract_video_urls'
    }
    
    # Find all files in dependency chain recursively
    def find_deps_recursive(file_name: str, visited: Set[str]) -> Set[str]:
        if file_name in visited or file_name not in dependencies:
            return set()
        
        visited.add(file_name)
        deps = set(dependencies[file_name])
        
        for dep in dependencies[file_name]:
            deps.update(find_deps_recursive(dep, visited.copy()))
        
        return deps
    
    used_files = set(core_files)
    for core_file in core_files:
        if core_file in all_files:
            deps = find_deps_recursive(core_file, set())
            used_files.update(deps)
    
    # Only consider files that actually exist
    used_files = {f for f in used_files if f in all_files}
    unused_files = all_files - used_files
    
    print("=== COMPREHENSIVE DEPENDENCY ANALYSIS ===")
    print(f"Total Python files: {len(all_files)}")
    print(f"Files in dependency chain: {len(used_files)}")
    print(f"Unused files: {len(unused_files)}")
    
    print(f"\n=== USED FILES ===")
    print("Core files (directly imported by build_dataset_pipeline.py):")
    for file in sorted(core_files & all_files):
        print(f"  📋 {file}.py")
    
    print("\nDependency chain files:")
    dependency_files = used_files - core_files
    for file in sorted(dependency_files):
        print(f"  🔗 {file}.py")
    
    print(f"\n=== UNUSED FILES (safe to delete) ===")
    for file in sorted(unused_files):
        if file != 'build_dataset_pipeline':  # Exclude the main pipeline file
            print(f"🗑️  {file}.py")
    
    # Show specific dependencies for key files to verify correctness
    print(f"\n=== DEPENDENCY VERIFICATION ===")
    key_files = ['enhanced_scene_converter', 'systematic_api_fixer', 'validation_failure_recovery']
    for key_file in key_files:
        if key_file in dependencies:
            print(f"{key_file}.py imports: {sorted(dependencies[key_file])}")
    
    return sorted(unused_files - {'build_dataset_pipeline'})

if __name__ == '__main__':
    unused = main()
    print(f"\n=== FINAL LIST OF FILES TO DELETE ===")
    for file in unused:
        print(f"{file}.py")