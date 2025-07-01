#!/usr/bin/env python3
"""
Pipeline wrapper that reads .env file for configuration.
Automatically enables enhanced prompts based on environment settings.
"""

import os
import sys
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent.parent / '.env'
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        print(f"✅ Loaded configuration from {env_file}")

# Load .env file first
load_env_file()

# Check if enhanced prompts should be enabled
if os.environ.get('ENABLE_ENHANCED_PROMPTS', '').lower() in ('1', 'true', 'yes'):
    import enable_enhanced_prompts
    enable_enhanced_prompts.enable_enhanced_prompts()
elif os.environ.get('DISABLE_ENHANCED_PROMPTS', '').lower() not in ('1', 'true', 'yes'):
    # Default to enabled if not explicitly disabled
    import enable_enhanced_prompts
    enable_enhanced_prompts.enable_enhanced_prompts()

# Run the main pipeline
from build_dataset_pipeline import main

if __name__ == '__main__':
    main()