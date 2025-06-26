#!/usr/bin/env python3
"""
Scene-aware cleaning for matched code files.
This module extends the base CodeCleaner to support scene-by-scene cleaning,
allowing for more focused Claude calls and better error handling.
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import logging
from datetime import datetime

# Import base cleaner
from clean_matched_code import CodeCleaner
# Import advanced dependency analyzer
from scene_dependency_analyzer import (
    AdvancedDependencyAnalyzer, 
    DependencyInfo,
    extract_code_for_dependencies,
    find_node_end_line
)
# Import scene relationship analyzer
from scene_relationship_analyzer import SceneRelationshipAnalyzer


class SceneInfo:
    """Container for scene information."""
    def __init__(self, name: str, code: str, start_line: int, end_line: int,
                 dependency_info: Optional[DependencyInfo] = None,
                 dependency_code: Optional[Dict[str, List[str]]] = None):
        self.name = name
        self.code = code
        self.start_line = start_line
        self.end_line = end_line
        self.dependency_info = dependency_info or DependencyInfo()
        self.dependency_code = dependency_code or {}


class SceneAwareCleaner(CodeCleaner):
    """Extended cleaner that can process files scene by scene."""
    
    def __init__(self, base_dir: str, verbose: bool = False, 
                 timeout_multiplier: float = 1.0, max_retries: int = 3):
        super().__init__(base_dir, verbose, timeout_multiplier, max_retries)
    
    def _make_progress_bar(self, current: int, total: int, width: int = 20) -> str:
        """Create a simple ASCII progress bar."""
        if total == 0:
            return "[" + " " * width + "]"
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
        
    def extract_scenes_from_files(self, files: List[Union[str, Dict]], year: int) -> List[SceneInfo]:
        """Extract all Scene classes from a list of files."""
        scenes = []
        
        for file_info in files:
            # Handle both string file names and dictionary file info
            if isinstance(file_info, dict):
                # Path in dict already includes 'data/videos/...' so use base_dir
                file_path = self.base_dir / file_info['path']
                file_name = file_info['path']
            else:
                # String file names - check if they include a path
                if '/' in file_info:
                    # Path already included (e.g., data/videos/_2016/...)
                    file_path = self.base_dir / file_info
                    file_name = file_info
                else:
                    # Just a filename (common in 2015 data)
                    videos_dir = self.data_dir / 'videos' / f'_{year}'
                    file_path = videos_dir / file_info
                    file_name = file_info
                
            if not file_path.exists():
                self.logger.warning(f"File not found: {file_path}")
                continue
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Parse AST to find scenes
                tree = ast.parse(content)
                file_scenes = self._extract_scenes_from_ast(tree, content, file_name)
                scenes.extend(file_scenes)
                
            except Exception as e:
                self.logger.error(f"Error extracting scenes from {file_name}: {e}")
                
        return scenes
    
    def _extract_scenes_from_ast(self, tree: ast.AST, content: str, file_name: str) -> List[SceneInfo]:
        """Extract Scene classes from AST with proper dependency analysis."""
        scenes = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if this class inherits from Scene
                if self._inherits_from_scene(node):
                    # Get the full class code using improved boundary detection
                    start_line = node.lineno - 1
                    end_line = find_node_end_line(node, lines)
                    
                    class_code = '\n'.join(lines[start_line:end_line])
                    
                    # Use advanced dependency analyzer
                    analyzer = AdvancedDependencyAnalyzer(node, tree)
                    dependency_info = analyzer.analyze()
                    
                    # Extract the actual code for dependencies
                    dependency_code = extract_code_for_dependencies(tree, lines, dependency_info)
                    
                    scene = SceneInfo(
                        name=node.name,
                        code=class_code,
                        start_line=start_line,
                        end_line=end_line,
                        dependency_info=dependency_info,
                        dependency_code=dependency_code
                    )
                    
                    scenes.append(scene)
                    # Simplify scene found message
                    deps_str = f"{len(dependency_info.functions)}f/{len(dependency_info.classes)}c/{len(dependency_info.constants)}const"
                    self.logger.info(f"  • {node.name} ({end_line - start_line} lines, deps: {deps_str})")
        
        return scenes
    
    def _inherits_from_scene(self, node: ast.ClassDef) -> bool:
        """Check if a class inherits from Scene or its subclasses."""
        # Known scene base classes that don't end with "Scene"
        special_scene_classes = {
            'RearrangeEquation', 'TeacherStudentsScene', 'PiCreatureScene'
        }
        
        for base in node.bases:
            # Check for direct inheritance (e.g., GraphScene, NumberLineScene)
            if isinstance(base, ast.Name):
                if base.id.endswith('Scene') or base.id in special_scene_classes:
                    return True
            # Handle attribute access (e.g., manimlib.GraphScene)
            elif isinstance(base, ast.Attribute):
                if base.attr.endswith('Scene') or base.attr in special_scene_classes:
                    return True
                
        return False
    
    
    def create_scene_cleaning_prompt(self, scene: SceneInfo, all_files: List[str], 
                                   video_id: str, caption_dir: str, year: int) -> str:
        """Create a focused cleaning prompt for a single scene with extracted dependencies."""
        output_path = self.output_dir / str(year) / caption_dir / 'cleaned_scenes' / f'{scene.name}.py'
        
        # Build dependency code section
        dependency_code_section = ""
        
        if scene.dependency_code.get('constants'):
            dependency_code_section += "\n# Required Constants:\n"
            dependency_code_section += '\n'.join(scene.dependency_code['constants'])
            dependency_code_section += "\n"
        
        if scene.dependency_code.get('functions'):
            dependency_code_section += "\n# Required Functions:\n"
            dependency_code_section += '\n\n'.join(scene.dependency_code['functions'])
            dependency_code_section += "\n"
            
        if scene.dependency_code.get('classes'):
            dependency_code_section += "\n# Required Classes:\n"
            dependency_code_section += '\n\n'.join(scene.dependency_code['classes'])
            dependency_code_section += "\n"
        
        return f"""You are cleaning and inlining code for a single Manim scene.

Scene Information:
- Scene Name: {scene.name}
- From Video: {video_id} ({caption_dir})
- Year: {year}
- Function dependencies: {', '.join(sorted(scene.dependency_info.functions))}
- Class dependencies: {', '.join(sorted(scene.dependency_info.classes))}
- Constants used: {', '.join(sorted(scene.dependency_info.constants))}
- Unresolved references: {', '.join(sorted(scene.dependency_info.unresolved)[:10])}

The scene code to clean:
```python
{scene.code}
```

Dependencies already extracted for this scene:
```python
{dependency_code_section}
```

Available files that may contain additional dependencies:
{json.dumps(all_files, indent=2)}

Your task:
1. The scene's direct dependencies have already been extracted above
2. Check if any unresolved references need to be found in the listed files
3. Read files ONLY if needed for unresolved references
4. Inline the provided dependencies and any additional ones you find
5. Keep external imports (numpy, manim, etc.) but inline local imports
6. Create a self-contained scene file that can run independently

CRITICAL INSTRUCTIONS:
- Keep the ORIGINAL ManimGL code (DO NOT convert to ManimCE)
- Use the already-extracted dependencies provided above
- Only search for additional code if there are unresolved references
- Preserve the exact scene functionality
- Add clear comments showing where inlined code came from
- Ensure the output is syntactically valid Python
- If you see 'from manimlib import *' or 'from manim_imports_ext import *', keep it exactly as is
- Place helper functions and constants BEFORE the scene class

IMPORTANT: Do NOT create any additional files. Only save the cleaned scene to the specified path.
Do not create separate dependency files or any other auxiliary files.
If dependencies are missing, include them directly in the cleaned scene file.

Save the cleaned scene to: {output_path}

Include this header:
```python
# Scene: {scene.name}
# From Video: {video_id}
# Cleaned on: {datetime.now().isoformat()}
# Original lines: {scene.start_line+1}-{scene.end_line}
```"""
    
    def clean_scenes_individually(self, scenes: List[SceneInfo], match_data: Dict, 
                                video_id: str, caption_dir: str, year: int) -> Dict:
        """Clean each scene individually with focused Claude calls."""
        all_files = match_data.get('primary_files', []) + match_data.get('supporting_files', [])
        
        # Create output directory for cleaned scenes
        scenes_output_dir = self.output_dir / str(year) / caption_dir / 'cleaned_scenes'
        scenes_output_dir.mkdir(parents=True, exist_ok=True)
        
        cleaning_results = {
            'scenes': {},
            'total_scenes': len(scenes),
            'cleaned_scenes': 0,
            'failed_scenes': 0
        }
        
        for i, scene in enumerate(scenes, 1):
            self.logger.info(f"Processing scene {i}/{len(scenes)}: '{scene.name}' from {video_id} ({len(scene.code)} chars, {len(scene.dependency_info.functions)} deps)")
            
            # Create focused prompt for this scene
            prompt = self.create_scene_cleaning_prompt(
                scene, all_files, video_id, caption_dir, year
            )
            
            # More specific scene context logging
            self.logger.info(f"Claude cleaning: scene '{scene.name}' ({len(scene.code)} chars, deps: {len(scene.dependency_info.functions)}f/{len(scene.dependency_info.classes)}c)")
            
            # Run Claude cleaning with smaller context
            result = self.run_claude_cleaning(
                prompt, f"{video_id}_{scene.name}", caption_dir, year,
                file_size=len(scene.code), max_retries=self.max_retries
            )
            
            if result['status'] == 'completed':
                # Validate the cleaned scene
                cleaned_file = scenes_output_dir / f'{scene.name}.py'
                if cleaned_file.exists():
                    is_valid, error = self.validate_cleaned_code(cleaned_file)
                    if is_valid:
                        self.logger.info(f"✓ Scene '{scene.name}' cleaned successfully")
                        cleaning_results['cleaned_scenes'] += 1
                        result['validation'] = 'passed'
                    else:
                        self.logger.warning(f"✗ Scene '{scene.name}' validation failed: {error[:100]}...")
                        result['validation'] = 'failed'
                        result['validation_error'] = error
                        cleaning_results['failed_scenes'] += 1
                else:
                    self.logger.error(f"✗ Scene '{scene.name}' - output file not created")
                    result['validation'] = 'file_not_created'
                    cleaning_results['failed_scenes'] += 1
            else:
                cleaning_results['failed_scenes'] += 1
                
            cleaning_results['scenes'][scene.name] = result
            
            # Small delay between API calls
            time.sleep(2)
        
        return cleaning_results
    
    def clean_scenes_individually_with_context(self, scenes: List[SceneInfo], match_data: Dict,
                                             video_id: str, caption_dir: str, year: int,
                                             relationship_analysis: Dict) -> Dict:
        """Clean scenes with awareness of their relationships and context."""
        all_files = match_data.get('primary_files', []) + match_data.get('supporting_files', [])
        
        # Create output directory for cleaned scenes
        scenes_output_dir = self.output_dir / str(year) / caption_dir / 'cleaned_scenes'
        scenes_output_dir.mkdir(parents=True, exist_ok=True)
        
        cleaning_results = {
            'scenes': {},
            'total_scenes': len(scenes),
            'cleaned_scenes': 0,
            'failed_scenes': 0
        }
        
        # Create a map for quick scene lookup
        scene_map = {scene.name: scene for scene in scenes}
        
        # Process scenes in optimal order
        scene_order = relationship_analysis['scene_order']
        ordered_scenes = [scene_map[name] for name in scene_order if name in scene_map]
        
        for i, scene in enumerate(ordered_scenes, 1):
            # Add visual separator between scenes with progress
            if self.verbose:
                print("\n" + "-"*60)
                progress_bar = self._make_progress_bar(i - 1, len(ordered_scenes))
                progress_pct = ((i-1) / len(ordered_scenes) * 100) if len(ordered_scenes) > 0 else 0
                print(f"Scene {i}/{len(ordered_scenes)} {progress_bar} ({progress_pct:.0f}%)")
            self.logger.info(f"Processing '{scene.name}' ({len(scene.code)} chars)")
            
            # Get context for this scene
            scene_context = relationship_analysis['contexts'].get(scene.name, {})
            scene_dependencies = [r for r in relationship_analysis['relationships'] 
                                if r.from_scene == scene.name]
            
            # Create enhanced prompt with relationship context
            prompt = self.create_context_aware_cleaning_prompt(
                scene, all_files, video_id, caption_dir, year,
                scene_context, scene_dependencies, relationship_analysis
            )
            
            # Scene context info - more concise
            relation_count = len(scene_dependencies)
            rel_str = f" ({relation_count} rel)" if relation_count > 0 else ""
            self.logger.info(f"  Claude API: '{scene.name}'{rel_str}")
            result = self.run_claude_cleaning(
                prompt, f"{video_id}_{scene.name}", caption_dir, year,
                file_size=len(scene.code), max_retries=self.max_retries
            )
            
            if result['status'] == 'completed':
                # Validate the cleaned scene
                cleaned_file = scenes_output_dir / f'{scene.name}.py'
                if cleaned_file.exists():
                    is_valid, error = self.validate_cleaned_code(cleaned_file)
                    if is_valid:
                        self.logger.info(f"  ✓ {scene.name} cleaned")
                        cleaning_results['cleaned_scenes'] += 1
                        result['validation'] = 'passed'
                    else:
                        self.logger.warning(f"  ✗ {scene.name} validation failed: {error[:50]}...")
                        result['validation'] = 'failed'
                        result['validation_error'] = error
                        cleaning_results['failed_scenes'] += 1
                else:
                    self.logger.error(f"  ✗ {scene.name} - file not created")
                    result['validation'] = 'file_not_created'
                    
                    # Try progressive recovery
                    recovery_result = self.progressive_scene_recovery(
                        scene, "Cleaned file not created", 
                        all_files, video_id, caption_dir, year
                    )
                    
                    if recovery_result and recovery_result.get('validation') == 'passed':
                        self.logger.info(f"🔧 Scene '{scene.name}' recovered successfully")
                        result = recovery_result
                        cleaning_results['cleaned_scenes'] += 1
                    else:
                        cleaning_results['failed_scenes'] += 1
            else:
                # Initial cleaning failed - try recovery
                error_msg = result.get('error', 'Unknown error')
                recovery_result = self.progressive_scene_recovery(
                    scene, error_msg, all_files, video_id, caption_dir, year
                )
                
                if recovery_result and recovery_result['status'] == 'completed':
                    self.logger.info(f"🔧 Scene '{scene.name}' recovery completed")
                    result = recovery_result
                    cleaning_results['cleaned_scenes'] += 1
                else:
                    cleaning_results['failed_scenes'] += 1
                
            cleaning_results['scenes'][scene.name] = result
            
            # Small delay between API calls
            time.sleep(2)
        
        return cleaning_results
    
    def create_context_aware_cleaning_prompt(self, scene: SceneInfo, all_files: List[str],
                                           video_id: str, caption_dir: str, year: int,
                                           scene_context: Dict, scene_dependencies: List,
                                           relationship_analysis: Dict) -> str:
        """Create a cleaning prompt that includes relationship context."""
        output_path = self.output_dir / str(year) / caption_dir / 'cleaned_scenes' / f'{scene.name}.py'
        
        # Build dependency code section
        dependency_code_section = ""
        
        if scene.dependency_code.get('constants'):
            dependency_code_section += "\n# Required Constants:\n"
            dependency_code_section += '\n'.join(scene.dependency_code['constants'])
            dependency_code_section += "\n"
        
        if scene.dependency_code.get('functions'):
            dependency_code_section += "\n# Required Functions:\n"
            dependency_code_section += '\n\n'.join(scene.dependency_code['functions'])
            dependency_code_section += "\n"
            
        if scene.dependency_code.get('classes'):
            dependency_code_section += "\n# Required Classes:\n"
            dependency_code_section += '\n\n'.join(scene.dependency_code['classes'])
            dependency_code_section += "\n"
        
        # Build relationship context
        relationship_context = ""
        if scene_dependencies:
            relationship_context = "\n\nScene Relationships:\n"
            for dep in scene_dependencies:
                relationship_context += f"- {dep.relationship_type} {dep.to_scene}: {dep.evidence[0] if dep.evidence else 'N/A'}\n"
        
        # Determine if this scene is part of a sequence
        flow = relationship_analysis['flow_analysis']
        if scene.name in flow['introduction_scenes']:
            scene_role = "This is an INTRODUCTION scene that sets up initial concepts."
        elif scene.name in flow['development_scenes']:
            scene_role = "This is a DEVELOPMENT scene that builds on previous concepts."
        elif scene.name in flow['conclusion_scenes']:
            scene_role = "This is a CONCLUSION scene that wraps up the demonstration."
        else:
            scene_role = "This is an INDEPENDENT scene."
        
        return f"""You are cleaning and inlining code for a single Manim scene with full context awareness.

Scene Information:
- Scene Name: {scene.name}
- From Video: {video_id} ({caption_dir})
- Year: {year}
- Scene Role: {scene_role}
- Mathematical Objects Used: {', '.join(scene_context.mathematical_objects if hasattr(scene_context, 'mathematical_objects') else [])}
- Function dependencies: {', '.join(sorted(scene.dependency_info.functions))}
- Class dependencies: {', '.join(sorted(scene.dependency_info.classes))}
- Constants used: {', '.join(sorted(scene.dependency_info.constants))}
{relationship_context}

The scene code to clean:
```python
{scene.code}
```

Dependencies already extracted for this scene:
```python
{dependency_code_section}
```

Available files that may contain additional dependencies:
{json.dumps(all_files, indent=2)}

Your task:
1. The scene's direct dependencies have already been extracted above
2. Consider the scene's role in the video when cleaning
3. Preserve any mathematical continuity with related scenes
4. Check if any unresolved references need to be found in the listed files
5. Inline the provided dependencies and any additional ones you find
6. Create a self-contained scene file that maintains its educational purpose

CRITICAL INSTRUCTIONS:
- Keep the ORIGINAL ManimGL code (DO NOT convert to ManimCE)
- Preserve the mathematical narrative and educational flow
- Use the already-extracted dependencies provided above
- Ensure the scene can work independently while maintaining its context
- Place helper functions and constants BEFORE the scene class
- Add comments explaining the scene's purpose if not already present

IMPORTANT: Do NOT create any additional files. Only save the cleaned scene to the specified path.
Do not create separate dependency files or any other auxiliary files.
If dependencies are missing, include them directly in the cleaned scene file.

Save the cleaned scene to: {output_path}

Include this header:
```python
# Scene: {scene.name}
# From Video: {video_id}
# Scene Role: {scene_role}
# Cleaned on: {datetime.now().isoformat()}
# Original lines: {scene.start_line+1}-{scene.end_line}
```"""
    
    def combine_cleaned_scenes_with_context(self, scenes_dir: Path, output_file: Path,
                                          relationship_analysis: Dict) -> bool:
        """Combine cleaned scenes intelligently using relationship analysis."""
        if not scenes_dir.exists():
            self.logger.error(f"Scenes directory not found: {scenes_dir}")
            return False
            
        scene_files = sorted(scenes_dir.glob('*.py'))
        if not scene_files:
            self.logger.error(f"No scene files found in {scenes_dir}")
            return False
        
        # Order scenes according to the optimal order from relationship analysis
        scene_order = relationship_analysis['scene_order']
        ordered_files = []
        
        # Create a map of scene names to files
        file_map = {f.stem: f for f in scene_files}
        
        # Order files according to scene_order
        for scene_name in scene_order:
            if scene_name in file_map:
                ordered_files.append(file_map[scene_name])
        
        # Add any files not in the order (shouldn't happen, but just in case)
        for f in scene_files:
            if f not in ordered_files:
                ordered_files.append(f)
        
        combined_content = []
        imports_section = set()
        shared_utilities = set()
        
        # First pass: collect all imports and shared utilities
        for scene_file in ordered_files:
            with open(scene_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
                for line in lines:
                    if line.strip().startswith(('import ', 'from ')):
                        imports_section.add(line.strip())
        
        # Build combined file
        combined_content.append("# Combined cleaned scenes with preserved relationships")
        combined_content.append(f"# Generated on: {datetime.now().isoformat()}")
        combined_content.append(f"# Total scenes: {len(ordered_files)}")
        combined_content.append(f"# Processing order preserves mathematical flow")
        combined_content.append("")
        
        # Add grouped imports
        combined_content.append("# ========== Imports ==========")
        stdlib_imports = sorted([i for i in imports_section if not i.startswith('from manim')])
        manim_imports = sorted([i for i in imports_section if i.startswith('from manim')])
        
        for imp in stdlib_imports:
            combined_content.append(imp)
        if stdlib_imports and manim_imports:
            combined_content.append("")
        for imp in manim_imports:
            combined_content.append(imp)
        combined_content.append("")
        combined_content.append("")
        
        # Extract and add shared utilities first
        flow = relationship_analysis['flow_analysis']
        shared_objects = relationship_analysis['shared_objects']
        
        if shared_objects:
            combined_content.append("# ========== Shared Utilities and Objects ==========")
            combined_content.append(f"# These are used across multiple scenes")
            combined_content.append("")
        
        # Add scenes in optimal order with section headers
        sections = [
            ("Introduction Scenes", flow['introduction_scenes']),
            ("Development Scenes", flow['development_scenes']),
            ("Conclusion Scenes", flow['conclusion_scenes']),
            ("Independent Scenes", flow['independent_scenes'])
        ]
        
        for section_name, section_scenes in sections:
            if not section_scenes:
                continue
                
            combined_content.append(f"\n# {'='*20} {section_name} {'='*20}")
            
            for scene_file in ordered_files:
                if scene_file.stem not in section_scenes:
                    continue
                    
                combined_content.append(f"\n# ========== Scene: {scene_file.stem} ==========")
                
                # Add relationship info as comment
                scene_deps = [r for r in relationship_analysis['relationships'] 
                            if r.from_scene == scene_file.stem]
                if scene_deps:
                    combined_content.append(f"# Relationships: {', '.join(f'{d.relationship_type} {d.to_scene}' for d in scene_deps)}")
                
                with open(scene_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                    # Skip imports and headers, add the rest
                    in_header = True
                    for line in lines:
                        if in_header and line.strip() and not line.startswith('#'):
                            in_header = False
                        
                        if not in_header and not line.strip().startswith(('import ', 'from ')):
                            combined_content.append(line)
                
                combined_content.append("")
        
        # Write combined file
        try:
            with open(output_file, 'w') as f:
                f.write('\n'.join(combined_content))
            
            # Validate the combined file
            is_valid, error = self.validate_cleaned_code(output_file)
            if is_valid:
                self.logger.info(f"✓ Combined {len(scene_files)} scenes into single file with preserved relationships")
                return True
            else:
                self.logger.error(f"Combined file has syntax errors: {error}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error writing combined file: {e}")
            return False
    
    def progressive_scene_recovery(self, scene: SceneInfo, error: str, 
                                  all_files: List[str], video_id: str, 
                                  caption_dir: str, year: int, attempt: int = 1) -> Optional[Dict]:
        """Try progressive recovery strategies for a failed scene."""
        self.logger.info(f"🔧 Attempting recovery for scene '{scene.name}' (attempt {attempt}/{len(recovery_strategies)})")
        
        recovery_strategies = [
            ('expand_dependencies', self._recovery_expand_dependencies),
            ('add_missing_imports', self._recovery_add_missing_imports),
            ('simplify_scene', self._recovery_simplify_scene),
            ('fallback_monolithic', self._recovery_fallback_monolithic)
        ]
        
        if attempt > len(recovery_strategies):
            self.logger.error(f"All recovery attempts exhausted for scene '{scene.name}'")
            return None
        
        strategy_name, strategy_func = recovery_strategies[attempt - 1]
        self.logger.info(f"🔧 Using recovery strategy: {strategy_name}")
        
        # Apply the recovery strategy
        enhanced_scene = strategy_func(scene, error, all_files, year)
        
        if enhanced_scene:
            # Create a recovery prompt
            prompt = self.create_recovery_cleaning_prompt(
                enhanced_scene, all_files, video_id, caption_dir, year, 
                strategy_name, error
            )
            
            # Try cleaning again with enhanced context
            result = self.run_claude_cleaning(
                prompt, f"{video_id}_{scene.name}_recovery{attempt}", 
                caption_dir, year, file_size=len(enhanced_scene.code), 
                max_retries=2  # Fewer retries for recovery
            )
            
            if result['status'] == 'completed':
                # Validate the recovered scene
                scenes_output_dir = self.output_dir / str(year) / caption_dir / 'cleaned_scenes'
                cleaned_file = scenes_output_dir / f'{scene.name}.py'
                
                if cleaned_file.exists():
                    is_valid, validation_error = self.validate_cleaned_code(cleaned_file)
                    if is_valid:
                        self.logger.info(f"✓ Recovery successful for scene '{scene.name}' using {strategy_name}")
                        result['recovery_strategy'] = strategy_name
                        result['recovery_attempt'] = attempt
                        return result
                    else:
                        self.logger.warning(f"✗ Recovery attempt {attempt} failed validation: {validation_error[:100]}...")
            
            # If this attempt failed, try the next strategy
            if attempt < len(recovery_strategies):
                return self.progressive_scene_recovery(
                    scene, f"{error}\nPrevious recovery failed: {result.get('error', 'Unknown')}", 
                    all_files, video_id, caption_dir, year, attempt + 1
                )
        
        return None
    
    def _recovery_expand_dependencies(self, scene: SceneInfo, error: str, 
                                    all_files: List[str], year: int) -> Optional[SceneInfo]:
        """Expand dependencies by including more context."""
        # Re-analyze with broader scope
        enhanced_scene = SceneInfo(
            name=scene.name,
            code=scene.code,
            start_line=scene.start_line,
            end_line=scene.end_line,
            dependency_info=scene.dependency_info,
            dependency_code=scene.dependency_code.copy()
        )
        
        # Add any unresolved references as potential dependencies
        if scene.dependency_info.unresolved:
            self.logger.info(f"Expanding search for unresolved: {scene.dependency_info.unresolved}")
            # This would require reading files to find the unresolved references
            # For now, we just mark them for Claude to handle
            enhanced_scene.dependency_info.unresolved = scene.dependency_info.unresolved
        
        return enhanced_scene
    
    def _recovery_add_missing_imports(self, scene: SceneInfo, error: str,
                                    all_files: List[str], year: int) -> Optional[SceneInfo]:
        """Add commonly missing imports based on error patterns."""
        enhanced_scene = SceneInfo(
            name=scene.name,
            code=scene.code,
            start_line=scene.start_line,
            end_line=scene.end_line,
            dependency_info=scene.dependency_info,
            dependency_code=scene.dependency_code.copy()
        )
        
        # Common missing imports based on error patterns
        if 'numpy' in error.lower() or 'np' in error:
            enhanced_scene.dependency_info.imports.add('import numpy as np')
        if 'CONFIG' in error:
            enhanced_scene.dependency_info.constants.add('CONFIG')
        if 'PI' in error or 'TAU' in error:
            enhanced_scene.dependency_info.imports.add('from manimlib.constants import *')
        
        return enhanced_scene
    
    def _recovery_simplify_scene(self, scene: SceneInfo, error: str,
                                all_files: List[str], year: int) -> Optional[SceneInfo]:
        """Try to simplify the scene by focusing on core functionality."""
        # This is a placeholder - in practice, this might involve
        # removing complex dependencies or simplifying the scene structure
        return scene
    
    def _recovery_fallback_monolithic(self, scene: SceneInfo, error: str,
                                     all_files: List[str], year: int) -> Optional[SceneInfo]:
        """Fall back to including entire file context."""
        self.logger.warning(f"Falling back to monolithic context for scene '{scene.name}'")
        
        # Create a scene with full file context
        # This would require reading the original file
        enhanced_scene = SceneInfo(
            name=scene.name,
            code=scene.code,
            start_line=0,
            end_line=-1,  # Signal to include entire file
            dependency_info=scene.dependency_info,
            dependency_code=scene.dependency_code
        )
        
        return enhanced_scene
    
    def create_recovery_cleaning_prompt(self, scene: SceneInfo, all_files: List[str],
                                      video_id: str, caption_dir: str, year: int,
                                      strategy_name: str, previous_error: str) -> str:
        """Create a cleaning prompt for recovery attempts."""
        output_path = self.output_dir / str(year) / caption_dir / 'cleaned_scenes' / f'{scene.name}.py'
        
        # Build dependency code section
        dependency_code_section = ""
        if scene.dependency_code:
            for dep_type, deps in scene.dependency_code.items():
                if deps:
                    dependency_code_section += f"\n# {dep_type.title()}:\n"
                    dependency_code_section += '\n'.join(deps) + "\n"
        
        return f"""You are attempting to recover a failed scene cleaning using the {strategy_name} strategy.

Previous Error:
{previous_error}

Scene Information:
- Scene Name: {scene.name}
- From Video: {video_id} ({caption_dir})
- Recovery Strategy: {strategy_name}

The scene code:
```python
{scene.code}
```

Dependencies and context:
```python
{dependency_code_section}
```

Unresolved references that need attention: {', '.join(scene.dependency_info.unresolved)}

Available files:
{json.dumps(all_files, indent=2)}

RECOVERY INSTRUCTIONS:
1. Focus on making the scene syntactically valid and self-contained
2. If dependencies are missing, read the files to find them
3. Add any missing imports at the top
4. Inline all necessary helper functions and constants
5. Ensure the scene can run independently
6. Keep the ORIGINAL ManimGL code (DO NOT convert to ManimCE)

Common issues to check:
- Missing imports (numpy, manimlib, etc.)
- Undefined helper functions
- Missing CONFIG dictionary
- Unresolved color constants (BLUE_A, RED_B, etc.)

IMPORTANT: Do NOT create any additional files. Only save the cleaned scene to the specified path.
Do not create separate dependency files or any other auxiliary files.
If dependencies are missing, include them directly in the cleaned scene file.

Save the recovered scene to: {output_path}"""
    
    def combine_cleaned_scenes(self, scenes_dir: Path, output_file: Path) -> bool:
        """Combine individually cleaned scenes into a single file."""
        if not scenes_dir.exists():
            self.logger.error(f"Scenes directory not found: {scenes_dir}")
            return False
            
        scene_files = sorted(scenes_dir.glob('*.py'))
        if not scene_files:
            self.logger.error(f"No scene files found in {scenes_dir}")
            return False
            
        combined_content = []
        imports_section = set()
        
        # First pass: collect all imports
        for scene_file in scene_files:
            with open(scene_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
                for line in lines:
                    if line.strip().startswith(('import ', 'from ')):
                        imports_section.add(line.strip())
        
        # Build combined file
        combined_content.append("# Combined cleaned scenes")
        combined_content.append(f"# Generated on: {datetime.now().isoformat()}")
        combined_content.append(f"# From {len(scene_files)} individual scenes")
        combined_content.append("")
        
        # Add sorted imports
        for imp in sorted(imports_section):
            combined_content.append(imp)
        combined_content.append("")
        
        # Add non-import content from each scene
        for scene_file in scene_files:
            combined_content.append(f"\n# ========== Scene: {scene_file.stem} ==========")
            
            with open(scene_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
                # Skip imports and headers, add the rest
                in_header = True
                for line in lines:
                    if in_header and line.strip() and not line.startswith('#'):
                        in_header = False
                    
                    if not in_header and not line.strip().startswith(('import ', 'from ')):
                        combined_content.append(line)
        
        # Write combined file
        try:
            with open(output_file, 'w') as f:
                f.write('\n'.join(combined_content))
            
            # Validate the combined file
            is_valid, error = self.validate_cleaned_code(output_file)
            if is_valid:
                self.logger.info(f"✓ Combined {len(scene_files)} scenes into single file")
                return True
            else:
                self.logger.error(f"Combined file has syntax errors: {error}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error writing combined file: {e}")
            return False
    
    def clean_video_by_scenes(self, video_id: str, caption_dir: str, 
                            match_data: Dict, year: int) -> Dict:
        """Clean a video using scene-by-scene approach with relationship analysis."""
        self.logger.info(f"Starting scene-by-scene cleaning for {caption_dir}")
        
        # Extract all files
        all_files = match_data.get('primary_files', []) + match_data.get('supporting_files', [])
        
        # Extract scenes from files
        scenes = self.extract_scenes_from_files(all_files, year)
        
        if not scenes:
            self.logger.warning(f"No scenes found in {caption_dir}")
            return {
                'status': 'no_scenes_found',
                'error': 'No Scene classes found in files'
            }
        
        # Scene extraction summary
        if self.verbose:
            print(f"\nExtracted {len(scenes)} scenes from {len(all_files)} files:")
        
        # Analyze scene relationships before cleaning
        self.logger.info(f"Analyzing scene relationships...")
        relationship_analyzer = SceneRelationshipAnalyzer(scenes)
        relationship_analysis = relationship_analyzer.analyze_all_relationships()
        
        # Summary of relationships
        n_rels = len(relationship_analysis['relationships'])
        n_shared = len(relationship_analysis['shared_objects'])
        flow = relationship_analysis['flow_analysis']
        flow_str = f"{len(flow['introduction_scenes'])}i/{len(flow['development_scenes'])}d/{len(flow['conclusion_scenes'])}c/{len(flow['independent_scenes'])}x"
        self.logger.info(f"  Relationships: {n_rels}, Shared objects: {n_shared}, Flow: {flow_str}")
        
        # Store relationship analysis for use during cleaning
        self.current_relationship_analysis = relationship_analysis
        
        # Clean each scene individually with relationship context
        cleaning_results = self.clean_scenes_individually_with_context(
            scenes, match_data, video_id, caption_dir, year, relationship_analysis
        )
        
        # Combine cleaned scenes into single file using smart merging
        scenes_dir = self.output_dir / str(year) / caption_dir / 'cleaned_scenes'
        output_file = self.output_dir / str(year) / caption_dir / 'cleaned_code.py'
        
        combine_success = self.combine_cleaned_scenes_with_context(
            scenes_dir, output_file, relationship_analysis
        )
        
        cleaning_results['combine_success'] = combine_success
        cleaning_results['status'] = 'completed' if combine_success else 'partial'
        cleaning_results['relationship_analysis'] = {
            'total_relationships': len(relationship_analysis['relationships']),
            'shared_objects': len(relationship_analysis['shared_objects']),
            'flow_analysis': relationship_analysis['flow_analysis']
        }
        
        # Print completion summary for this video
        if self.verbose:
            success_bar = self._make_progress_bar(cleaning_results['cleaned_scenes'], cleaning_results['total_scenes'], width=15)
            print(f"\n  Summary: {success_bar} {cleaning_results['cleaned_scenes']}/{cleaning_results['total_scenes']} scenes cleaned")
            if cleaning_results['failed_scenes'] > 0:
                print(f"  ⚠️  {cleaning_results['failed_scenes']} scenes failed")
            if combine_success:
                print(f"  ✅ Combined into cleaned_code.py")
            else:
                print(f"  ❌ Combination failed")
        
        return cleaning_results


def main():
    """Main entry point for scene-aware cleaning."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean matched code scene by scene')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--video', type=str,
                        help='Clean a specific video by caption directory name')
    parser.add_argument('--timeout-multiplier', type=float, default=1.0,
                        help='Multiply all timeouts by this factor (default: 1.0)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum number of retry attempts for timeouts (default: 3)')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    cleaner = SceneAwareCleaner(base_dir, verbose=args.verbose, 
                              timeout_multiplier=args.timeout_multiplier,
                              max_retries=args.max_retries)
    
    if args.video:
        # Test on a specific video
        match_results = cleaner.load_match_results(args.year)
        if args.video in match_results:
            match_data = match_results[args.video]
            video_id = match_data.get('video_id', 'unknown')
            
            result = cleaner.clean_video_by_scenes(video_id, args.video, match_data, args.year)
            print(f"Scene cleaning result: {json.dumps(result, indent=2)}")
        else:
            print(f"No match data found for video: {args.video}")
    else:
        print("Please specify a video to clean with --video")


if __name__ == '__main__':
    main()