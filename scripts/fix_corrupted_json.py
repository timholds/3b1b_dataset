#!/usr/bin/env python3
"""
Script to find and fix corrupted JSON files in the 3Blue1Brown dataset pipeline.
This handles common JSON corruption issues like incomplete writes, truncated files, etc.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
import argparse
import shutil

def find_json_files(base_dir: Path, pattern: str = "*.json") -> list[Path]:
    """Find all JSON files matching the pattern."""
    return list(base_dir.rglob(pattern))

def check_json_file(file_path: Path) -> tuple[bool, str]:
    """Check if a JSON file is valid. Returns (is_valid, error_message)."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if not content.strip():
                return False, "Empty file"
            json.loads(content)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def backup_file(file_path: Path) -> Path:
    """Create a backup of the file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = file_path.with_suffix(f'.json.backup_{timestamp}')
    shutil.copy2(file_path, backup_path)
    return backup_path

def fix_logs_json(file_path: Path) -> bool:
    """Attempt to fix a corrupted logs.json file."""
    # For logs.json files, we can safely create an empty structure
    if file_path.name == 'logs.json':
        try:
            # Backup the corrupted file
            backup_path = backup_file(file_path)
            print(f"  Backed up to: {backup_path}")
            
            # Create empty logs structure
            empty_logs = {}
            with open(file_path, 'w') as f:
                json.dump(empty_logs, f, indent=2)
            
            print(f"  ✓ Fixed: Created empty logs.json")
            return True
        except Exception as e:
            print(f"  ✗ Failed to fix: {e}")
            return False
    return False

def fix_matches_json(file_path: Path) -> bool:
    """Attempt to fix a corrupted matches.json file."""
    # For matches.json, we can't recreate the data, but we can create a placeholder
    if file_path.name == 'matches.json':
        try:
            # Backup the corrupted file
            backup_path = backup_file(file_path)
            print(f"  Backed up to: {backup_path}")
            
            # Create placeholder structure
            placeholder = {
                "status": "corrupted_recovered",
                "error": "Original file was corrupted",
                "recovered_at": datetime.now().isoformat(),
                "primary_files": [],
                "confidence_score": 0.0
            }
            with open(file_path, 'w') as f:
                json.dump(placeholder, f, indent=2)
            
            print(f"  ✓ Fixed: Created placeholder matches.json")
            return True
        except Exception as e:
            print(f"  ✗ Failed to fix: {e}")
            return False
    return False

def main():
    parser = argparse.ArgumentParser(description='Find and fix corrupted JSON files in the pipeline')
    parser.add_argument('--base-dir', type=Path, default=Path.cwd(),
                        help='Base directory to search (default: current directory)')
    parser.add_argument('--fix', action='store_true',
                        help='Attempt to fix corrupted files (default: only report)')
    parser.add_argument('--pattern', default='*.json',
                        help='File pattern to search (default: *.json)')
    
    args = parser.parse_args()
    
    print(f"Scanning for JSON files in: {args.base_dir}")
    print(f"Pattern: {args.pattern}")
    print()
    
    json_files = find_json_files(args.base_dir, args.pattern)
    print(f"Found {len(json_files)} JSON files")
    print()
    
    corrupted_files = []
    
    for file_path in json_files:
        is_valid, error = check_json_file(file_path)
        if not is_valid:
            corrupted_files.append((file_path, error))
            
    if not corrupted_files:
        print("✓ All JSON files are valid!")
        return 0
        
    print(f"Found {len(corrupted_files)} corrupted JSON files:")
    print()
    
    for file_path, error in corrupted_files:
        print(f"✗ {file_path}")
        print(f"  Error: {error}")
        
        if args.fix:
            fixed = False
            if file_path.name == 'logs.json':
                fixed = fix_logs_json(file_path)
            elif file_path.name == 'matches.json':
                fixed = fix_matches_json(file_path)
            else:
                print(f"  ⚠ No automatic fix available for {file_path.name}")
                
    if not args.fix and corrupted_files:
        print()
        print("To attempt automatic fixes, run with --fix flag")
        print("WARNING: This will backup and modify corrupted files!")
        
    return len(corrupted_files)

if __name__ == '__main__':
    sys.exit(main())