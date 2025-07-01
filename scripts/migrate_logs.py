#!/usr/bin/env python3
"""
Migrate logs.json files from .pipeline/logs/ to the video root directory.

This script fixes the path mismatch where:
- build_dataset_pipeline.py saves to: video_dir/.pipeline/logs/logs.json
- render_videos.py reads from: video_dir/logs.json
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def migrate_logs(base_dir: Path, dry_run: bool = False):
    """Migrate logs.json files from .pipeline/logs/ to video root directory."""
    outputs_dir = base_dir / 'outputs'
    
    if not outputs_dir.exists():
        print("No outputs directory found.")
        return
    
    migrated_count = 0
    already_exists_count = 0
    error_count = 0
    
    # Iterate through all year directories
    for year_dir in outputs_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
            
        print(f"\nProcessing year {year_dir.name}...")
        
        # Iterate through all video directories
        for video_dir in year_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            # Check for logs in old location
            old_log_path = video_dir / '.pipeline' / 'logs' / 'logs.json'
            new_log_path = video_dir / 'logs.json'
            
            if old_log_path.exists():
                if new_log_path.exists():
                    # Both exist - need to merge
                    print(f"  {video_dir.name}: Both old and new logs exist, merging...")
                    
                    if not dry_run:
                        try:
                            # Load both log files
                            with open(old_log_path, 'r') as f:
                                old_logs = json.load(f)
                            with open(new_log_path, 'r') as f:
                                new_logs = json.load(f)
                            
                            # Merge logs (old logs take precedence for duplicate keys)
                            merged_logs = {**new_logs, **old_logs}
                            
                            # Save merged logs
                            with open(new_log_path, 'w') as f:
                                json.dump(merged_logs, f, indent=2)
                            
                            # Remove old log file
                            old_log_path.unlink()
                            
                            print(f"    ✓ Merged and migrated")
                            migrated_count += 1
                            
                        except Exception as e:
                            print(f"    ✗ Error merging logs: {e}")
                            error_count += 1
                    else:
                        print(f"    [DRY RUN] Would merge logs")
                        migrated_count += 1
                        
                else:
                    # Only old exists - simple move
                    print(f"  {video_dir.name}: Migrating logs...")
                    
                    if not dry_run:
                        try:
                            # Move the file
                            shutil.move(str(old_log_path), str(new_log_path))
                            print(f"    ✓ Migrated")
                            migrated_count += 1
                            
                        except Exception as e:
                            print(f"    ✗ Error migrating: {e}")
                            error_count += 1
                    else:
                        print(f"    [DRY RUN] Would migrate")
                        migrated_count += 1
                        
            elif new_log_path.exists():
                # Only new exists - nothing to do
                already_exists_count += 1
            
    # Summary
    print(f"\n{'='*60}")
    print("Migration Summary:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Already in correct location: {already_exists_count}")
    print(f"  Errors: {error_count}")
    
    if dry_run:
        print("\n[DRY RUN] No files were actually moved. Run without --dry-run to perform migration.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate logs.json files from .pipeline/logs/ to video root directory'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually moving files')
    
    args = parser.parse_args()
    
    # Get base directory
    base_dir = Path(__file__).parent.parent
    
    print("Migrating logs.json files...")
    print(f"Base directory: {base_dir}")
    
    migrate_logs(base_dir, dry_run=args.dry_run)


if __name__ == '__main__':
    main()