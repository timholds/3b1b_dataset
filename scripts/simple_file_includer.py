#!/usr/bin/env python3
"""
Simple file includer that replaces complex dependency analysis.
Instead of trying to analyze cross-file dependencies, this simply includes
all content from matched files and lets Python handle the imports.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
import re
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class SimpleIncludeResult:
    """Result of simple file inclusion."""
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    files_included: int = 0
    total_lines: int = 0
    duplicates_removed: int = 0
    syntax_valid: bool = True
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


class SimpleFileIncluder:
    """
    Simple file includer that just concatenates all matched files
    without complex dependency analysis.
    """
    
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        if verbose:
            self.logger.setLevel(logging.INFO)
    
    def _resolve_file_path(self, file_path: str, year: int) -> Path:
        """Resolve file path relative to base directory."""
        if isinstance(file_path, dict):
            file_path = file_path['file_path']
        
        file_path = str(file_path)
        
        # Convert relative paths to absolute
        if not file_path.startswith('/'):
            file_path = self.base_dir / file_path
        else:
            file_path = Path(file_path)
        
        return file_path
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements from file content."""
        imports = []
        
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            imports.append(f"import {alias.name} as {alias.asname}")
                        else:
                            imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    if node.names:
                        if len(node.names) == 1 and node.names[0].name == '*':
                            imports.append(f"from {module} import *")
                        else:
                            names = []
                            for alias in node.names:
                                if alias.asname:
                                    names.append(f"{alias.name} as {alias.asname}")
                                else:
                                    names.append(alias.name)
                            imports.append(f"from {module} import {', '.join(names)}")
        except SyntaxError:
            # If we can't parse, extract imports using regex
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)
        
        return imports
    
    def _extract_non_import_content(self, content: str) -> str:
        """Extract everything except import statements."""
        lines = content.split('\n')
        non_import_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import lines but keep everything else
            if not (stripped.startswith('import ') or stripped.startswith('from ')):
                non_import_lines.append(line)
        
        return '\n'.join(non_import_lines)
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute a hash of normalized content for duplicate detection."""
        # Normalize by removing comments and extra whitespace
        lines = content.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Remove inline comments
            if '#' in line:
                line = line[:line.index('#')]
            # Remove trailing whitespace
            line = line.rstrip()
            # Skip empty lines
            if line:
                normalized_lines.append(line)
        
        normalized_content = '\n'.join(normalized_lines)
        return hashlib.md5(normalized_content.encode()).hexdigest()
    
    def _extract_code_blocks(self, content: str) -> Dict[str, List[Tuple[str, int, int]]]:
        """
        Extract significant code blocks (classes and functions) with their line ranges.
        Returns dict mapping block type to list of (name, start_line, end_line).
        """
        blocks = {'class': [], 'function': []}
        
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Find the end line of the class
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    blocks['class'].append((node.name, node.lineno, end_line))
                elif isinstance(node, ast.FunctionDef):
                    # Only top-level functions (not methods)
                    if node.col_offset == 0:
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                        blocks['function'].append((node.name, node.lineno, end_line))
        except:
            # If AST parsing fails, we'll skip block detection
            pass
        
        return blocks
    
    def _remove_duplicate_blocks(self, content_sections: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], int]:
        """
        Remove duplicate code blocks across files.
        Returns (deduplicated_sections, duplicates_removed_count).
        """
        seen_hashes = set()
        seen_blocks = {}  # block_name -> content_hash
        deduplicated = []
        duplicates_removed = 0
        
        for file_path, content in content_sections:
            # First check if entire file is duplicate
            file_hash = self._compute_content_hash(content)
            if file_hash in seen_hashes:
                duplicates_removed += 1
                continue
            seen_hashes.add(file_hash)
            
            # Extract code blocks
            blocks = self._extract_code_blocks(content)
            lines = content.split('\n')
            keep_lines = set(range(len(lines)))  # Track which lines to keep
            
            # Check for duplicate classes and functions
            for block_type, block_list in blocks.items():
                for name, start_line, end_line in block_list:
                    # Extract block content
                    block_lines = lines[start_line-1:end_line]
                    block_content = '\n'.join(block_lines)
                    block_hash = self._compute_content_hash(block_content)
                    
                    # Check if we've seen this block before
                    block_key = f"{block_type}:{name}"
                    if block_key in seen_blocks and seen_blocks[block_key] == block_hash:
                        # Remove this duplicate block
                        for i in range(start_line-1, min(end_line, len(lines))):
                            keep_lines.discard(i)
                        duplicates_removed += 1
                    else:
                        seen_blocks[block_key] = block_hash
            
            # Reconstruct content without duplicate blocks
            if len(keep_lines) < len(lines):
                kept_lines = [lines[i] for i in sorted(keep_lines)]
                content = '\n'.join(kept_lines)
            
            deduplicated.append((file_path, content))
        
        return deduplicated, duplicates_removed
    
    def _validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate Python syntax of the combined code.
        Returns (is_valid, list_of_errors).
        """
        errors = []
        
        try:
            # First try to parse as AST
            ast.parse(code)
            
            # Then try to compile
            compile(code, '<string>', 'exec')
            
            return True, []
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.strip()}"
            errors.append(error_msg)
        except Exception as e:
            errors.append(f"Compilation error: {str(e)}")
        
        return False, errors
    
    def _categorize_import(self, import_line: str) -> Tuple[int, str]:
        """
        Categorize import by type for better organization.
        Returns (priority, category) where lower priority comes first.
        """
        import_line = import_line.strip()
        
        # Standard library imports (priority 0)
        stdlib_modules = {
            'os', 'sys', 'math', 'random', 'json', 'time', 'datetime', 
            'collections', 'itertools', 'functools', 'copy', 're', 'ast',
            'pathlib', 'typing', 'dataclasses', 'abc', 'enum', 'warnings',
            'logging', 'subprocess', 'multiprocessing', 'threading'
        }
        
        # Check if it's a standard library import
        if import_line.startswith('import '):
            module = import_line.split()[1].split('.')[0]
            if module in stdlib_modules:
                return (0, 'stdlib')
        elif import_line.startswith('from '):
            module = import_line.split()[1].split('.')[0]
            if module in stdlib_modules:
                return (0, 'stdlib')
        
        # Third-party imports (priority 1)
        if any(pkg in import_line for pkg in ['numpy', 'scipy', 'matplotlib', 'PIL', 'cv2', 'pygame']):
            return (1, 'third_party')
        
        # Manim imports (priority 2)
        if 'manim' in import_line:
            return (2, 'manim')
        
        # Local/project imports (priority 3)
        return (3, 'local')
    
    def _organize_imports(self, imports: List[str]) -> List[str]:
        """Organize imports by category with proper spacing."""
        # First deduplicate
        unique_imports = list(set(imports))
        
        # Categorize imports
        categorized = {}
        for imp in unique_imports:
            priority, category = self._categorize_import(imp)
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(imp)
        
        # Build organized import list
        organized = []
        categories = ['stdlib', 'third_party', 'manim', 'local']
        
        for i, category in enumerate(categories):
            if category in categorized:
                # Sort imports within category
                category_imports = sorted(categorized[category])
                organized.extend(category_imports)
                # Add blank line between categories (except after last)
                if i < len(categories) - 1 and any(cat in categorized for cat in categories[i+1:]):
                    organized.append("")
        
        return organized
    
    def _standardize_imports(self, imports: List[str]) -> List[str]:
        """Standardize, deduplicate and organize imports."""
        standardized = []
        
        for imp in imports:
            # Convert manimlib imports to standard form
            if 'manimlib' in imp:
                # Convert to manim_imports_ext which is the standard entry point
                if 'import *' in imp:
                    standardized.append('from manim_imports_ext import *')
                else:
                    standardized.append(imp)
            else:
                standardized.append(imp)
        
        # Organize imports by category
        return self._organize_imports(standardized)
    
    def include_all_files(self, video_id: str, caption_dir: str, match_data: Dict, year: int) -> SimpleIncludeResult:
        """
        Include all content from matched files without dependency analysis.
        
        Args:
            video_id: YouTube video ID
            caption_dir: Caption directory name
            match_data: Matching results
            year: Year of the video
            
        Returns:
            SimpleIncludeResult with success status and details
        """
        try:
            self.logger.info(f"Including all files for {caption_dir}")
            
            # Get all files to include
            primary_files = match_data.get('primary_files', [])
            supporting_files = match_data.get('supporting_files', [])
            all_files = primary_files + supporting_files
            
            if not all_files:
                return SimpleIncludeResult(
                    success=False,
                    error="No files to include"
                )
            
            # Set up output directory
            output_dir = self.base_dir / 'outputs' / str(year) / caption_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Collect all imports and content
            all_imports = []
            content_sections = []  # List of (file_path, content) tuples
            files_included = 0
            total_lines = 0
            
            for file_path in all_files:
                full_path = self._resolve_file_path(file_path, year)
                
                if not full_path.exists():
                    self.logger.warning(f"File not found: {full_path}")
                    continue
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract imports and content separately
                    file_imports = self._extract_imports(content)
                    file_content = self._extract_non_import_content(content)
                    
                    all_imports.extend(file_imports)
                    content_sections.append((str(full_path), file_content))
                    
                    files_included += 1
                    total_lines += len(content.split('\n'))
                    
                    line_count = len(content.split('\n'))
                    self.logger.info(f"Included {full_path} ({line_count} lines)")
                    
                except Exception as e:
                    self.logger.warning(f"Error reading {full_path}: {e}")
                    continue
            
            if files_included == 0:
                return SimpleIncludeResult(
                    success=False,
                    error="No files could be read"
                )
            
            # Remove duplicate code blocks
            deduplicated_sections, duplicates_removed = self._remove_duplicate_blocks(content_sections)
            
            if duplicates_removed > 0:
                self.logger.info(f"Removed {duplicates_removed} duplicate code blocks")
            
            # Standardize and organize imports
            standardized_imports = self._standardize_imports(all_imports)
            
            # Combine everything
            final_content = []
            final_content.append("#!/usr/bin/env python3")
            final_content.append('"""')
            final_content.append(f"Combined ManimGL code for {caption_dir}")
            final_content.append(f"Generated by enhanced simple file includer")
            final_content.append(f"Files included: {files_included}, Duplicates removed: {duplicates_removed}")
            final_content.append('"""')
            final_content.append("")
            
            # Add organized imports at the top
            final_content.extend(standardized_imports)
            final_content.append("")
            
            # Add all deduplicated content
            for file_path, content in deduplicated_sections:
                if content.strip():  # Only add non-empty content
                    final_content.append(f"# Content from {file_path}")
                    final_content.append(content)
                    final_content.append("")  # Add blank line between files
            
            # Create the final code string
            final_code = '\n'.join(final_content)
            
            # Validate syntax
            syntax_valid, validation_errors = self._validate_syntax(final_code)
            
            if not syntax_valid:
                self.logger.warning(f"Combined code has syntax errors: {validation_errors}")
            
            # Write output file
            output_path = output_dir / 'monolith_manimgl.py'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_code)
            
            self.logger.info(f"Created combined file: {output_path}")
            
            return SimpleIncludeResult(
                success=True,
                output_path=output_path,
                files_included=files_included,
                total_lines=total_lines,
                duplicates_removed=duplicates_removed,
                syntax_valid=syntax_valid,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            self.logger.error(f"Error in simple file inclusion: {e}")
            return SimpleIncludeResult(
                success=False,
                error=str(e)
            )