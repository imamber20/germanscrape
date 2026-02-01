"""
Checkpoint Manager for Resume Functionality
Saves progress every N businesses to prevent losing work on interruption
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set


class CheckpointManager:
    """Manages scraping progress and checkpoints for resume functionality"""

    def __init__(self, checkpoint_file: str = "progress.json"):
        """Initialize checkpoint manager"""
        self.checkpoint_file = Path(checkpoint_file)
        self.processed_place_ids: Set[str] = set()
        self.stats = {
            'start_time': None,
            'last_checkpoint': None,
            'total_processed': 0,
            'total_cost': 0.0,
            'api_calls': {
                'geocoding': 0,
                'nearby_search': 0,
                'place_details': 0,
                'place_details_skipped': 0
            },
            'leads_by_category': {}
        }
        self.load()

    def load(self) -> bool:
        """Load existing checkpoint if available"""
        if not self.checkpoint_file.exists():
            return False

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.processed_place_ids = set(data.get('processed_place_ids', []))
            self.stats = data.get('stats', self.stats)

            print(f"\n✓ Loaded checkpoint: {len(self.processed_place_ids)} businesses already processed")
            print(f"  Last checkpoint: {self.stats.get('last_checkpoint', 'N/A')}")
            print(f"  Total cost so far: ${self.stats.get('total_cost', 0):.2f}")

            return True

        except Exception as e:
            print(f"⚠️  Failed to load checkpoint: {e}")
            return False

    def save(self) -> None:
        """Save current progress to checkpoint file"""
        try:
            data = {
                'processed_place_ids': list(self.processed_place_ids),
                'stats': self.stats
            }

            # Update last checkpoint time
            self.stats['last_checkpoint'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Write to temp file first, then rename (atomic operation)
            temp_file = self.checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.checkpoint_file)

        except Exception as e:
            print(f"⚠️  Failed to save checkpoint: {e}")

    def is_processed(self, place_id: str) -> bool:
        """Check if a business has already been processed"""
        return place_id in self.processed_place_ids

    def mark_processed(self, place_id: str) -> None:
        """Mark a business as processed"""
        self.processed_place_ids.add(place_id)
        self.stats['total_processed'] += 1

    def update_api_call(self, call_type: str) -> None:
        """Track API call for cost calculation"""
        if call_type in self.stats['api_calls']:
            self.stats['api_calls'][call_type] += 1

    def update_cost(self, cost: float) -> None:
        """Update total cost"""
        self.stats['total_cost'] += cost

    def update_category_count(self, category: str) -> None:
        """Track leads by category"""
        if category not in self.stats['leads_by_category']:
            self.stats['leads_by_category'][category] = 0
        self.stats['leads_by_category'][category] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return self.stats.copy()

    def clear(self) -> None:
        """Clear checkpoint (start fresh)"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()

        self.processed_place_ids.clear()
        self.stats = {
            'start_time': None,
            'last_checkpoint': None,
            'total_processed': 0,
            'total_cost': 0.0,
            'api_calls': {
                'geocoding': 0,
                'nearby_search': 0,
                'place_details': 0,
                'place_details_skipped': 0
            },
            'leads_by_category': {}
        }

    def print_summary(self) -> None:
        """Print checkpoint statistics"""
        print("\n" + "=" * 60)
        print("CHECKPOINT STATISTICS")
        print("=" * 60)
        print(f"Total businesses processed: {self.stats['total_processed']}")
        print(f"Total cost: ${self.stats['total_cost']:.2f}")
        print(f"\nAPI Calls:")
        print(f"  Geocoding: {self.stats['api_calls']['geocoding']}")
        print(f"  Nearby Search: {self.stats['api_calls']['nearby_search']}")
        print(f"  Place Details: {self.stats['api_calls']['place_details']}")
        print(f"  Place Details Skipped: {self.stats['api_calls']['place_details_skipped']}")

        if self.stats['leads_by_category']:
            print(f"\nLeads by Category:")
            for category, count in sorted(self.stats['leads_by_category'].items()):
                print(f"  {category}: {count}")

        print("=" * 60 + "\n")
