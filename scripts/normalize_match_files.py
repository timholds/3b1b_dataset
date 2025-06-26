#!/usr/bin/env python3
"""
Normalize all matches.json files to use consistent format.
Converts dictionary entries with 'path' keys to simple string paths.
"""

import json
from pathlib import Path
import sys


def normalize_file_list(files):
    """Convert file list to consistent string format."""
    normalized = []
    for file_entry in files:
        if isinstance(file_entry, dict):
            # Extract path from dictionary format
            if 'path' in file_entry:
                normalized.append(file_entry['path'])
            else:
                print(f"Warning: Dictionary entry without 'path' key: {file_entry}")
        elif isinstance(file_entry, str):
            # Already in correct format
            normalized.append(file_entry)
        else:
            print(f"Warning: Unknown file entry type: {type(file_entry)}")
    return normalized


def normalize_matches_file(matches_path):
    """Normalize a single matches.json file."""
    try:
        with open(matches_path, 'r') as f:
            data = json.load(f)
        
        modified = False
        
        # Normalize primary_files
        if 'primary_files' in data:
            normalized_primary = normalize_file_list(data['primary_files'])
            if normalized_primary != data['primary_files']:
                data['primary_files'] = normalized_primary
                modified = True
                print(f"  Normalized primary_files in {matches_path}")
        
        # Normalize supporting_files
        if 'supporting_files' in data:
            normalized_supporting = normalize_file_list(data['supporting_files'])
            if normalized_supporting != data['supporting_files']:
                data['supporting_files'] = normalized_supporting
                modified = True
                print(f"  Normalized supporting_files in {matches_path}")
        
        # Save if modified
        if modified:
            with open(matches_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {matches_path}: {e}")
        return False


def main():
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        year = 2016
    
    base_dir = Path(__file__).parent.parent
    outputs_dir = base_dir / 'outputs' / str(year)
    
    if not outputs_dir.exists():
        print(f"No outputs directory for year {year}")
        return
    
    print(f"Normalizing matches.json files for year {year}...")
    
    total_files = 0
    normalized_files = 0
    
    # Find all matches.json files
    for video_dir in outputs_dir.iterdir():
        if video_dir.is_dir():
            matches_file = video_dir / 'matches.json'
            if matches_file.exists():
                total_files += 1
                if normalize_matches_file(matches_file):
                    normalized_files += 1
    
    print(f"\nProcessed {total_files} matches.json files")
    print(f"Normalized {normalized_files} files")
    
    # Also update the summary file
    summary_file = base_dir / 'outputs' / f'matching_summary_{year}.json'
    if summary_file.exists():
        print(f"\nUpdating summary file: {summary_file}")
        try:
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            modified = False
            for video_name, video_data in summary.get('results', {}).items():
                if 'match_data' in video_data:
                    match_data = video_data['match_data']
                    
                    # Normalize primary_files
                    if 'primary_files' in match_data:
                        normalized = normalize_file_list(match_data['primary_files'])
                        if normalized != match_data['primary_files']:
                            match_data['primary_files'] = normalized
                            modified = True
                            print(f"  Normalized {video_name} primary_files")
                    
                    # Normalize supporting_files
                    if 'supporting_files' in match_data:
                        normalized = normalize_file_list(match_data['supporting_files'])
                        if normalized != match_data['supporting_files']:
                            match_data['supporting_files'] = normalized
                            modified = True
                            print(f"  Normalized {video_name} supporting_files")
            
            if modified:
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                print("Summary file updated")
            else:
                print("Summary file already normalized")
                
        except Exception as e:
            print(f"Error updating summary file: {e}")


if __name__ == '__main__':
    main()