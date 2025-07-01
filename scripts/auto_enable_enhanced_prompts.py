#!/usr/bin/env python3
"""
Automatic enabler for enhanced prompts.
Add 'import auto_enable_enhanced_prompts' to any script to automatically enable enhancements.
"""

import os
import sys
from pathlib import Path

# Check if we should auto-enable (can be disabled via environment variable)
if os.environ.get('DISABLE_ENHANCED_PROMPTS', '').lower() not in ('1', 'true', 'yes'):
    # Add scripts directory to path
    scripts_dir = Path(__file__).parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    
    # Enable enhanced prompts silently
    try:
        from integrate_enhanced_prompts import upgrade_pipeline_to_enhanced
        upgrade_pipeline_to_enhanced()
        
        # Set a flag so we know it's enabled
        os.environ['ENHANCED_PROMPTS_ENABLED'] = '1'
        
    except Exception:
        # Fail silently - the pipeline will work without enhancements
        pass
else:
    # User explicitly disabled enhanced prompts
    os.environ['ENHANCED_PROMPTS_ENABLED'] = '0'