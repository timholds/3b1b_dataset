#!/usr/bin/env python3
"""
One-time migration script to organize existing logs into the new structure.
This script:
1. Moves pipeline logs to output/logs/
2. Archives old pipeline report JSONs to output/logs/archive/
3. Keeps only the latest pipeline report JSON in the main output directory
4. Creates a consolidated history from existing reports
"""

import json
from pathlib import Path
from datetime import datetime
import shutil

def migrate_logs(base_dir: Path):
    """Migrate existing logs to the new organized structure."""
    output_dir = base_dir / 'output'
    
    # Create new directories
    logs_dir = output_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    archive_dir = logs_dir / 'archive'
    archive_dir.mkdir(exist_ok=True)
    
    print("Starting log migration...")
    
    # 1. Move pipeline_logs directory contents to logs/
    old_pipeline_logs = output_dir / 'pipeline_logs'
    if old_pipeline_logs.exists():
        print(f"Moving pipeline logs from {old_pipeline_logs} to {logs_dir}")
        for log_file in old_pipeline_logs.glob('*.log'):
            new_path = logs_dir / log_file.name
            shutil.move(str(log_file), str(new_path))
            print(f"  Moved: {log_file.name}")
        
        # Remove empty directory
        old_pipeline_logs.rmdir()
        print("  Removed old pipeline_logs directory")
    
    # 2. Find all pipeline report JSON files
    report_files = list(output_dir.glob('pipeline_report_*_*.json'))
    
    if report_files:
        print(f"\nFound {len(report_files)} pipeline report JSON files")
        
        # Sort by modification time
        report_files.sort(key=lambda p: p.stat().st_mtime)
        
        # Create consolidated history from all reports
        consolidated_file = logs_dir / 'pipeline_history.jsonl'
        print(f"Creating consolidated history at {consolidated_file}")
        
        with open(consolidated_file, 'w') as f:
            for report_file in report_files:
                try:
                    with open(report_file) as rf:
                        data = json.load(rf)
                        # Add filename for reference
                        data['_original_file'] = report_file.name
                        f.write(json.dumps(data) + '\n')
                except Exception as e:
                    print(f"  Warning: Could not read {report_file.name}: {e}")
        
        # Archive all but the most recent report
        latest_report = report_files[-1]
        print(f"\nKeeping latest report: {latest_report.name}")
        
        # Rename latest to standard name
        year_match = latest_report.name.split('_')[2]  # Extract year from filename
        new_latest_path = output_dir / f'pipeline_report_{year_match}_latest.json'
        shutil.copy2(str(latest_report), str(new_latest_path))
        print(f"  Created: {new_latest_path.name}")
        
        # Archive all old reports
        print("\nArchiving old reports...")
        for report_file in report_files:
            archive_path = archive_dir / report_file.name
            shutil.move(str(report_file), str(archive_path))
            print(f"  Archived: {report_file.name}")
    
    # 3. Move cleaning logs to logs/ subdirectory
    cleaning_logs_dir = output_dir / 'cleaning_logs'
    if cleaning_logs_dir.exists():
        new_cleaning_logs = logs_dir / 'cleaning'
        new_cleaning_logs.mkdir(exist_ok=True)
        
        print(f"\nMoving cleaning logs to {new_cleaning_logs}")
        for item in cleaning_logs_dir.iterdir():
            new_path = new_cleaning_logs / item.name
            shutil.move(str(item), str(new_path))
            print(f"  Moved: {item.name}")
        
        cleaning_logs_dir.rmdir()
        print("  Removed old cleaning_logs directory")
    
    print("\nMigration complete!")
    print(f"New structure:")
    print(f"  - Logs: {logs_dir}/")
    print(f"  - Archive: {archive_dir}/")
    print(f"  - History: {logs_dir / 'pipeline_history.jsonl'}")

if __name__ == '__main__':
    base_dir = Path(__file__).parent.parent
    migrate_logs(base_dir)