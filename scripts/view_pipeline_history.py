#!/usr/bin/env python3
"""
Utility script to view pipeline run history from the consolidated log.
Provides various viewing options:
- List all runs with summary
- Show details of a specific run
- Filter by date range
- Show statistics
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

def load_history(history_file: Path) -> List[Dict]:
    """Load all pipeline runs from the history file."""
    runs = []
    if history_file.exists():
        with open(history_file) as f:
            for line in f:
                try:
                    runs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    return runs

def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def print_run_summary(run: Dict):
    """Print a summary of a single pipeline run."""
    start_time = run.get('start_time', 'Unknown')
    if start_time != 'Unknown':
        start_dt = datetime.fromisoformat(start_time)
        start_time = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    duration = run.get('duration_seconds', 0)
    year = run.get('year', 'Unknown')
    
    # Get stage statuses
    stages = run.get('stages', {})
    statuses = []
    for stage_name in ['matching', 'cleaning', 'conversion', 'rendering']:
        stage = stages.get(stage_name, {})
        status = stage.get('status', 'unknown')
        if status == 'completed':
            symbol = '✓'
        elif status == 'failed':
            symbol = '✗'
        elif status == 'skipped':
            symbol = '-'
        else:
            symbol = '?'
        statuses.append(f"{stage_name[0].upper()}{symbol}")
    
    status_str = ' '.join(statuses)
    
    print(f"{start_time} | Year: {year} | Duration: {format_duration(duration)} | {status_str}")

def print_run_details(run: Dict):
    """Print detailed information about a pipeline run."""
    print("\n" + "="*80)
    print(f"Pipeline Run Details")
    print("="*80)
    
    start_time = run.get('start_time', 'Unknown')
    if start_time != 'Unknown':
        print(f"Start Time: {datetime.fromisoformat(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    end_time = run.get('end_time', 'Unknown')
    if end_time != 'Unknown':
        print(f"End Time: {datetime.fromisoformat(end_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    duration = run.get('duration_seconds', 0)
    print(f"Duration: {format_duration(duration)}")
    print(f"Year: {run.get('year', 'Unknown')}")
    
    print("\nStage Results:")
    print("-" * 40)
    
    stages = run.get('stages', {})
    for stage_name in ['matching', 'cleaning', 'conversion', 'rendering']:
        stage = stages.get(stage_name, {})
        status = stage.get('status', 'unknown')
        stats = stage.get('stats', {})
        
        print(f"\n{stage_name.capitalize()}:")
        print(f"  Status: {status}")
        
        if stats:
            for key, value in stats.items():
                print(f"  {key}: {value}")

def show_statistics(runs: List[Dict]):
    """Show overall statistics from all runs."""
    print("\n" + "="*80)
    print("Pipeline Statistics")
    print("="*80)
    
    print(f"Total runs: {len(runs)}")
    
    if not runs:
        return
    
    # Calculate statistics
    total_duration = sum(r.get('duration_seconds', 0) for r in runs)
    successful_runs = sum(1 for r in runs if all(
        r.get('stages', {}).get(s, {}).get('status') in ['completed', 'skipped'] 
        for s in ['matching', 'cleaning', 'conversion', 'rendering']
    ))
    
    print(f"Successful runs: {successful_runs}/{len(runs)} ({successful_runs/len(runs)*100:.1f}%)")
    print(f"Total processing time: {format_duration(total_duration)}")
    print(f"Average run duration: {format_duration(total_duration/len(runs))}")
    
    # Stage statistics
    print("\nStage Statistics:")
    for stage_name in ['matching', 'cleaning', 'conversion', 'rendering']:
        completed = sum(1 for r in runs if r.get('stages', {}).get(stage_name, {}).get('status') == 'completed')
        failed = sum(1 for r in runs if r.get('stages', {}).get(stage_name, {}).get('status') == 'failed')
        skipped = sum(1 for r in runs if r.get('stages', {}).get(stage_name, {}).get('status') == 'skipped')
        
        print(f"  {stage_name.capitalize()}: {completed} completed, {failed} failed, {skipped} skipped")

def main():
    parser = argparse.ArgumentParser(description='View pipeline run history')
    parser.add_argument('--last', type=int, metavar='N',
                        help='Show only the last N runs')
    parser.add_argument('--days', type=int, metavar='N',
                        help='Show runs from the last N days')
    parser.add_argument('--detail', type=int, metavar='INDEX',
                        help='Show detailed view of run at INDEX (0-based)')
    parser.add_argument('--stats', action='store_true',
                        help='Show overall statistics')
    parser.add_argument('--year', type=int,
                        help='Filter runs by year')
    
    args = parser.parse_args()
    
    # Load history
    base_dir = Path(__file__).parent.parent
    history_file = base_dir / 'output' / 'logs' / 'pipeline_history.jsonl'
    
    if not history_file.exists():
        print(f"No history file found at {history_file}")
        print("Run the migration script first: python scripts/migrate_logs.py")
        return
    
    runs = load_history(history_file)
    
    if not runs:
        print("No pipeline runs found in history")
        return
    
    # Filter by year if specified
    if args.year:
        runs = [r for r in runs if r.get('year') == args.year]
        if not runs:
            print(f"No runs found for year {args.year}")
            return
    
    # Filter by days if specified
    if args.days:
        cutoff = datetime.now() - timedelta(days=args.days)
        filtered_runs = []
        for run in runs:
            start_time = run.get('start_time')
            if start_time:
                try:
                    run_dt = datetime.fromisoformat(start_time)
                    if run_dt >= cutoff:
                        filtered_runs.append(run)
                except:
                    pass
        runs = filtered_runs
    
    # Limit to last N runs if specified
    if args.last:
        runs = runs[-args.last:]
    
    # Show detailed view if requested
    if args.detail is not None:
        if 0 <= args.detail < len(runs):
            print_run_details(runs[args.detail])
        else:
            print(f"Invalid index {args.detail}. Valid range: 0-{len(runs)-1}")
        return
    
    # Show statistics if requested
    if args.stats:
        show_statistics(runs)
        return
    
    # Default: show summary list
    print(f"\nPipeline Run History ({len(runs)} runs)")
    print("="*80)
    print("Date/Time            | Year | Duration | Status (M=Match, Cl=Clean, Co=Convert, R=Render)")
    print("-"*80)
    
    for i, run in enumerate(runs):
        print(f"[{i:3d}] ", end='')
        print_run_summary(run)
    
    print("\nUse --detail INDEX to see details of a specific run")
    print("Use --stats to see overall statistics")

if __name__ == '__main__':
    main()