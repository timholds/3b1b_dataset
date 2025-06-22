#!/usr/bin/env python3
"""
Fetch transcripts directly from YouTube videos using youtube-transcript-api.
This will help us get transcripts for all videos, including those with empty caption files.
"""

import os
import json
import argparse
from youtube_transcript_api import YouTubeTranscriptApi

def fetch_transcript(video_id, languages=['en']):
    """
    Fetch transcript for a YouTube video.
    
    Returns:
        (transcript_text, transcript_data, error_message)
    """
    try:
        # Get transcript - this automatically tries to get the best available transcript
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        
        # Format as plain text by joining all text segments
        transcript_text = ' '.join(entry['text'] for entry in transcript_data)
        
        return transcript_text, transcript_data, None
        
    except Exception as e:
        return None, None, f"Error fetching transcript: {str(e)}"

def save_transcript(output_dir, video_id, caption_dir, transcript_text, transcript_data):
    """Save transcript in both text and JSON formats."""
    video_dir = os.path.join(output_dir, caption_dir)
    os.makedirs(video_dir, exist_ok=True)
    
    # Save plain text version
    text_path = os.path.join(video_dir, 'youtube_transcript.txt')
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(transcript_text)
    
    # Save JSON version with timestamps
    json_path = os.path.join(video_dir, 'youtube_transcript.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, indent=2, ensure_ascii=False)
    
    return text_path, json_path

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Fetch YouTube transcripts for videos from a given year'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    args = parser.parse_args()
    
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metadata_file = os.path.join(base_dir, 'data', 'youtube_metadata', f'{args.year}_video_mappings.json')
    output_dir = os.path.join(base_dir, 'data', 'youtube_transcripts', str(args.year))
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load video mappings
    if not os.path.exists(metadata_file):
        print(f"Video mappings not found at {metadata_file}")
        print(f"Please run extract_video_urls.py --year {args.year} first")
        return
    
    with open(metadata_file, 'r') as f:
        video_mappings = json.load(f)
    
    print(f"Fetching YouTube transcripts for {args.year} videos")
    print("=" * 60)
    
    # Track results
    results = {
        'success': [],
        'failed': []
    }
    
    # Process each video
    for caption_dir, video_info in video_mappings.items():
        video_id = video_info['video_id']
        print(f"\nProcessing {caption_dir} ({video_id})...", end='')
        
        # Fetch transcript
        transcript_text, transcript_data, error = fetch_transcript(video_id)
        
        if transcript_text:
            # Save transcript
            text_path, json_path = save_transcript(output_dir, video_id, caption_dir, 
                                                   transcript_text, transcript_data)
            
            # Calculate statistics
            word_count = len(transcript_text.split())
            duration = sum(item['duration'] for item in transcript_data)
            
            results['success'].append({
                'caption_dir': caption_dir,
                'video_id': video_id,
                'word_count': word_count,
                'duration_seconds': duration,
                'text_path': text_path,
                'json_path': json_path
            })
            
            print(f" ✓ ({word_count} words, {duration:.1f}s)")
        else:
            results['failed'].append({
                'caption_dir': caption_dir,
                'video_id': video_id,
                'error': error
            })
            print(f" ✗ ({error})")
    
    # Save results summary
    summary_file = os.path.join(base_dir, 'data', 'youtube_transcripts', f'{args.year}_transcript_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TRANSCRIPT FETCH SUMMARY")
    print("=" * 60)
    print(f"Successfully fetched: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    
    if results['failed']:
        print("\nFailed videos:")
        for item in results['failed']:
            print(f"  - {item['caption_dir']}: {item['error']}")
    
    print(f"\nTranscripts saved to: {output_dir}")
    print(f"Summary saved to: {summary_file}")

if __name__ == '__main__':
    main()