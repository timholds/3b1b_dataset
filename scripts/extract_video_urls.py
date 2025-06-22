#!/usr/bin/env python3
"""
Extract YouTube video URLs from the captions repository for a given year.
Creates a mapping between caption directories and video IDs.
"""

import os
import json
import re
import argparse
from pathlib import Path

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'youtu\.be/([a-zA-Z0-9_-]+)',
        r'youtube\.com/embed/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def process_year_captions(captions_dir, year):
    """Process all caption directories for a given year and extract video information."""
    year_dir = os.path.join(captions_dir, str(year))
    
    if not os.path.exists(year_dir):
        print(f"{year} directory not found at {year_dir}")
        return {}
    
    video_mappings = {}
    
    # Process each video directory in the year
    for video_dir in os.listdir(year_dir):
        video_path = os.path.join(year_dir, video_dir)
        
        if not os.path.isdir(video_path):
            continue
            
        # Look for video_url.txt
        url_file = os.path.join(video_path, 'video_url.txt')
        
        if os.path.exists(url_file):
            try:
                with open(url_file, 'r') as f:
                    url = f.read().strip()
                    video_id = extract_video_id(url)
                    
                    if video_id:
                        # Check if English captions exist
                        english_dir = os.path.join(video_path, 'english')
                        has_english = os.path.exists(english_dir)
                        
                        video_mappings[video_dir] = {
                            'video_id': video_id,
                            'url': url,
                            'caption_dir': video_dir,
                            'has_english_captions': has_english,
                            'year': year
                        }
                        
                        print(f"Found: {video_dir} -> {video_id}")
                    else:
                        print(f"Could not extract video ID from {url}")
                        
            except Exception as e:
                print(f"Error reading {url_file}: {e}")
        else:
            print(f"No video_url.txt found in {video_dir}")
    
    return video_mappings

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Extract YouTube video URLs from the captions repository for a given year'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    args = parser.parse_args()
    
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    captions_dir = os.path.join(base_dir, 'data', 'captions')
    output_dir = os.path.join(base_dir, 'data', 'youtube_metadata')
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if captions repository exists
    if not os.path.exists(captions_dir):
        print(f"Captions repository not found at {captions_dir}")
        print("Please clone the captions repository first")
        return
    
    # Process captions for the given year
    print(f"Processing {args.year} captions...")
    video_mappings = process_year_captions(captions_dir, args.year)
    
    # Save mappings
    output_file = os.path.join(output_dir, f'{args.year}_video_mappings.json')
    with open(output_file, 'w') as f:
        json.dump(video_mappings, f, indent=2)
    
    print(f"\nFound {len(video_mappings)} videos in {args.year}")
    print(f"Mappings saved to {output_file}")
    
    # Summary
    print(f"\nSummary of {args.year} videos:")
    for caption_dir, info in video_mappings.items():
        english = "✓" if info['has_english_captions'] else "✗"
        print(f"  {caption_dir}: {info['video_id']} [English: {english}]")

if __name__ == '__main__':
    main()