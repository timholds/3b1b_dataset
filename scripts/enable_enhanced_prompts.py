#!/usr/bin/env python3
"""
Simple script to enable enhanced prompts in the existing pipeline.
Run this before running the pipeline to activate all improvements.
"""

import sys
from pathlib import Path

def enable_enhanced_prompts():
    """Enable enhanced prompts by modifying Python path and imports."""
    
    # Add scripts directory to Python path if not already there
    scripts_dir = Path(__file__).parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    
    print("🚀 Enabling Enhanced Prompts for 3Blue1Brown Pipeline")
    print("=" * 60)
    
    # Import the integration module which will auto-patch everything
    try:
        import integrate_enhanced_prompts
        print("✅ Enhanced prompts integration loaded")
    except ImportError as e:
        print(f"❌ Failed to load integration module: {e}")
        return False
    
    # Import and patch specific modules
    try:
        # These imports will trigger the monkey patching
        import claude_match_videos
        import clean_matched_code
        import claude_api_helper
        
        # Replace with enhanced versions
        from claude_match_videos_enhanced import EnhancedClaudeVideoMatcher
        from clean_matched_code_enhanced import EnhancedCodeCleaner  
        from claude_api_helper_enhanced import EnhancedClaudeAPIHelper
        
        # Monkey patch the modules
        claude_match_videos.ClaudeVideoMatcher = EnhancedClaudeVideoMatcher
        clean_matched_code.CodeCleaner = EnhancedCodeCleaner
        claude_api_helper.ClaudeAPIHelper = EnhancedClaudeAPIHelper
        
        print("✅ Modules patched successfully")
        
    except ImportError as e:
        print(f"⚠️  Some modules could not be patched: {e}")
        print("   The pipeline will still work but may not have all enhancements")
    
    print("\n📋 Enhanced Features Enabled:")
    print("  ✓ Few-shot examples in prompts")
    print("  ✓ Adaptive learning from successes/failures")
    print("  ✓ Automatic timeout adjustment")
    print("  ✓ Progressive model selection for retries")
    print("  ✓ Performance tracking and reporting")
    print("  ✓ Learned error fix patterns")
    
    print("\n📊 Optimization data will be saved to:")
    print("  - outputs/prompt_optimization/")
    print("  - outputs/prompt_feedback/")
    print("  - outputs/logs/*_optimization_*.txt")
    
    print("\n✨ Enhanced prompts are now active!")
    print("=" * 60)
    
    return True

def main():
    """Main function when run as a script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Enable enhanced prompts for the 3Blue1Brown pipeline'
    )
    parser.add_argument('--test', action='store_true',
                       help='Run a test to verify enhancement is working')
    
    args = parser.parse_args()
    
    # Enable enhancements
    success = enable_enhanced_prompts()
    
    if args.test and success:
        print("\n🧪 Running enhancement test...")
        
        # Test that modules are properly patched
        import claude_match_videos
        import clean_matched_code
        
        if hasattr(claude_match_videos.ClaudeVideoMatcher, 'optimizer'):
            print("✅ Video matcher has optimizer attribute")
        else:
            print("❌ Video matcher not properly enhanced")
            
        if hasattr(clean_matched_code.CodeCleaner, 'feedback_system'):
            print("✅ Code cleaner has feedback system")  
        else:
            print("❌ Code cleaner not properly enhanced")
            
        print("\n✅ Enhancement test complete")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())