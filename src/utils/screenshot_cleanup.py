#!/usr/bin/env python3
"""
Screenshot Cleanup Script - Manage screenshot storage
"""
import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.screenshot_manager import screenshot_manager


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description='Manage screenshot storage')
    parser.add_argument('--stats', action='store_true', help='Show storage statistics')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Remove screenshots older than N days')
    parser.add_argument('--category', type=str, help='Show/clean specific category only')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats(args.category)
    elif args.cleanup is not None:
        cleanup_old(args.cleanup, args.category)
    else:
        parser.print_help()


def show_stats(category=None):
    """Show screenshot statistics"""
    stats = screenshot_manager.get_stats()
    
    print("📸 Screenshot Storage Statistics")
    print("=" * 40)
    print(f"Total Files: {stats['total_files']}")
    print(f"Total Size: {stats['total_size_mb']:.2f} MB")
    print()
    
    if category:
        if category in stats['by_category']:
            cat_stats = stats['by_category'][category]
            print(f"Category: {category}")
            print(f"  Files: {cat_stats['files']}")
            print(f"  Size: {cat_stats['size_mb']:.2f} MB")
        else:
            print(f"Category '{category}' not found")
            print("Available categories:")
            for cat in stats['by_category'].keys():
                print(f"  - {cat}")
    else:
        print("By Category:")
        for cat_name, cat_stats in stats['by_category'].items():
            print(f"  {cat_name:15} {cat_stats['files']:4} files  {cat_stats['size_mb']:6.2f} MB")


def cleanup_old(days, category=None):
    """Clean up old screenshots"""
    print(f"🧹 Cleaning up screenshots older than {days} days...")
    
    if category:
        print(f"   Category: {category}")
        # Custom cleanup for specific category
        import time
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        removed_count = 0
        
        category_dir = screenshot_manager.base_dir / category
        if category_dir.exists():
            for screenshot in category_dir.glob("*.png"):
                if screenshot.stat().st_mtime < cutoff_time:
                    screenshot.unlink()
                    removed_count += 1
                    
            print(f"✅ Removed {removed_count} screenshots from {category}")
        else:
            print(f"❌ Category '{category}' not found")
    else:
        # Clean all categories
        screenshot_manager.cleanup_old_screenshots(days)
        print("✅ Cleanup complete")


if __name__ == "__main__":
    main()