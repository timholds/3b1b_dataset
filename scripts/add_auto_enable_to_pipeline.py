#!/usr/bin/env python3
"""
Script to permanently add auto-enable to build_dataset_pipeline.py
Run this once to modify the pipeline to always use enhanced prompts.
"""

import sys
from pathlib import Path

def add_auto_enable():
    """Add auto-enable import to build_dataset_pipeline.py"""
    
    pipeline_file = Path(__file__).parent / 'build_dataset_pipeline.py'
    
    if not pipeline_file.exists():
        print("❌ build_dataset_pipeline.py not found!")
        return False
    
    # Read the current content
    with open(pipeline_file, 'r') as f:
        content = f.read()
    
    # Check if already modified
    if 'auto_enable_enhanced_prompts' in content:
        print("✅ Pipeline already has auto-enable!")
        return True
    
    # Find the right place to insert (after the docstring and before other imports)
    lines = content.split('\n')
    insert_index = 0
    in_docstring = False
    docstring_count = 0
    
    for i, line in enumerate(lines):
        # Track docstring state
        if '"""' in line:
            docstring_count += line.count('"""')
            if docstring_count % 2 == 1:
                in_docstring = True
            else:
                in_docstring = False
        
        # Find first import after docstring
        if not in_docstring and (line.startswith('import ') or line.startswith('from ')):
            insert_index = i
            break
    
    # Insert the auto-enable import
    auto_enable_lines = [
        "",
        "# Automatically enable enhanced prompts for better performance",
        "try:",
        "    import auto_enable_enhanced_prompts",
        "except ImportError:",
        "    # Enhanced prompts not available, continue with standard prompts",
        "    pass",
        ""
    ]
    
    # Insert the lines
    for j, new_line in enumerate(auto_enable_lines):
        lines.insert(insert_index + j, new_line)
    
    # Write back
    with open(pipeline_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print("✅ Successfully added auto-enable to build_dataset_pipeline.py!")
    print("   Enhanced prompts will now be automatically enabled every time.")
    print("   To disable: set environment variable DISABLE_ENHANCED_PROMPTS=1")
    
    return True

def create_launcher_script():
    """Create a launcher script that ensures enhanced prompts are enabled."""
    
    launcher_file = Path(__file__).parent / 'run_pipeline.py'
    
    launcher_content = '''#!/usr/bin/env python3
"""
Launcher script for the 3Blue1Brown pipeline with enhanced prompts.
This ensures enhanced prompts are always enabled.
"""

import sys
import os

# Force enable enhanced prompts
os.environ.pop('DISABLE_ENHANCED_PROMPTS', None)

# Enable enhanced prompts
import enable_enhanced_prompts
enable_enhanced_prompts.enable_enhanced_prompts()

# Run the main pipeline
from build_dataset_pipeline import main

if __name__ == '__main__':
    main()
'''
    
    with open(launcher_file, 'w') as f:
        f.write(launcher_content)
    
    # Make it executable
    launcher_file.chmod(0o755)
    
    print("✅ Created run_pipeline.py launcher script")
    print("   Use: python scripts/run_pipeline.py --year 2015")
    
    return launcher_file

def create_shell_alias():
    """Create shell alias suggestions."""
    
    print("\n📝 Shell Alias Suggestions:")
    print("\nFor bash (~/.bashrc or ~/.bash_profile):")
    print("alias 3b1b-pipeline='python scripts/build_dataset_pipeline_enhanced.py'")
    print("\nFor zsh (~/.zshrc):")
    print("alias 3b1b-pipeline='python scripts/build_dataset_pipeline_enhanced.py'")
    print("\nFor fish (~/.config/fish/config.fish):")
    print("alias 3b1b-pipeline 'python scripts/build_dataset_pipeline_enhanced.py'")
    print("\nThen you can just run: 3b1b-pipeline --year 2015")

def main():
    """Main function offering different automation options."""
    
    print("🚀 Enhanced Prompts Automation Setup")
    print("=" * 50)
    print("\nChoose automation method:")
    print("1. Modify build_dataset_pipeline.py permanently (recommended)")
    print("2. Create a launcher script (run_pipeline.py)")
    print("3. Use build_dataset_pipeline_enhanced.py instead")
    print("4. Set up shell alias")
    print("5. All of the above")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice in ('1', '5'):
        add_auto_enable()
    
    if choice in ('2', '5'):
        create_launcher_script()
    
    if choice in ('3', '5'):
        print("\n✅ build_dataset_pipeline_enhanced.py already exists")
        print("   Use: python scripts/build_dataset_pipeline_enhanced.py --year 2015")
    
    if choice in ('4', '5'):
        create_shell_alias()
    
    print("\n✨ Setup complete!")
    print("\n📝 Additional Options:")
    print("- To temporarily disable: DISABLE_ENHANCED_PROMPTS=1 python scripts/build_dataset_pipeline.py")
    print("- To check if enabled: echo $ENHANCED_PROMPTS_ENABLED")

if __name__ == '__main__':
    main()