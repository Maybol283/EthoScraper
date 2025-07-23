#!/usr/bin/env python3
"""
EthoScraper CLI - Main command line interface
"""

import sys
import argparse
from pathlib import Path


def main():
    """Main CLI entry point for EthoScraper."""
    parser = argparse.ArgumentParser(
        prog='ethoscraper',
        description='Ethical web scraper with GDPR compliance tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ethoscraper setup                    # Create new project with LIA wizard
  ethoscraper analyze                  # Analyze compliance.yaml in current dir
  ethoscraper analyze --model o3       # Use specific model for analysis
  ethoscraper scrape                   # Run scraper (uses target.yaml in current dir)
  ethoscraper scrape --force           # Bypass LIA validation (not recommended)
  ethoscraper scrape custom.yaml      # Use specific target file
  
  # Or use specific commands:
  ethoscraper-setup                    # Project setup
  ethoscraper-analyze                  # Compliance analysis  
  ethoscraper-scrape                   # Web scraping (auto-detects target.yaml)
        """
    )
    
    parser.add_argument('command', nargs='?', choices=['setup', 'analyze', 'scrape'], 
                        help='Command to run')
    parser.add_argument('target_file', nargs='?', 
                        help='Target YAML file (optional - defaults to target.yaml in current directory)')
    parser.add_argument('--max-pages', type=int, 
                        help='Maximum pages to scrape')
    parser.add_argument('--model', type=str, default='gpt-4.1',
                        help='Model to use for analysis (default: gpt-4.1). Options: gpt-4.1, o3, o3-mini, etc.')
    parser.add_argument('--force', action='store_true',
                        help='Bypass LIA validation requirements for scraping (not recommended)')
    parser.add_argument('--version', action='version', version='EthoScraper 0.1.0')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'setup':
            from ethoscraper.core.setup import main as setup_main
            setup_main()
            
        elif args.command == 'analyze':
            from ethoscraper.core.analysis import main as analyze_main
            analyze_main(model=args.model)
            
        elif args.command == 'scrape':
            # Auto-detect target.yaml if not specified
            if not args.target_file:
                target_path = Path("target.yaml")
                if target_path.exists():
                    target_file = "target.yaml"
                    print(f"🎯 Using target.yaml from current directory")
                else:
                    print("❌ Error: No target.yaml found in current directory")
                    print("   Please ensure you're in a project directory with target.yaml")
                    print("   Or specify the target file: ethoscraper scrape path/to/target.yaml")
                    sys.exit(1)
            else:
                target_file = args.target_file
            
            from ethoscraper.core.scraper import run_ethical_scraper
            run_ethical_scraper(target_file, args.max_pages, args.force)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 