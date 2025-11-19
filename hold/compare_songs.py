#!/usr/bin/env python3
"""Smart comparison of song files with different naming conventions."""
import os
import re
from pathlib import Path


def normalize_filename(filename):
    """Normalize filename for comparison."""
    # Remove .mp3 extension
    name = filename.replace('.mp3', '')

    # Replace underscores with spaces
    name = name.replace('_', ' ')

    # Remove common extra info in parentheses
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)

    # Remove common words
    words_to_remove = [
        'Official', 'Video', 'Audio', 'Music', 'Lyric', 'Lyrics',
        'ft.', 'feat.', 'featuring', 'ft', 'feat',
        'Explicit', 'HD', 'HQ', '4K', 'Remix', 'Official Video',
        'Official Music Video', 'Official Audio', 'Lyric Video'
    ]

    for word in words_to_remove:
        name = re.sub(r'\b' + re.escape(word) + r'\b', '', name, flags=re.IGNORECASE)

    # Remove extra dashes and spaces
    name = re.sub(r'\s*-\s*', ' - ', name)  # Normalize dashes
    name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single
    name = name.strip(' -')

    # Convert to lowercase for case-insensitive comparison
    name = name.lower()

    return name


def extract_core_info(filename):
    """Extract artist and song title from filename."""
    normalized = normalize_filename(filename)

    # Try to split by dash to get artist and title
    parts = normalized.split(' - ')

    if len(parts) >= 2:
        artist = parts[0].strip()
        # Join remaining parts as title (in case title has dashes)
        title = ' '.join(parts[1:]).strip()
        return f"{artist}|||{title}"

    return normalized


def main():
    hold1_dir = Path('hold1')
    hold2_dir = Path('hold2')

    # Get all mp3 files
    hold1_files = [f.name for f in hold1_dir.glob('*.mp3')]
    hold2_files = [f.name for f in hold2_dir.glob('*.mp3')]

    print(f"Hold1 files: {len(hold1_files)}")
    print(f"Hold2 files: {len(hold2_files)}")
    print()

    # Create normalized mappings
    hold1_normalized = {}
    for f in hold1_files:
        core = extract_core_info(f)
        hold1_normalized[core] = f

    hold2_normalized = {}
    for f in hold2_files:
        core = extract_core_info(f)
        hold2_normalized[core] = f

    # Find files in hold1 not in hold2
    missing_from_hold2 = []
    matched = []

    for core, original_name in hold1_normalized.items():
        if core not in hold2_normalized:
            missing_from_hold2.append((original_name, core))
        else:
            matched.append((original_name, hold2_normalized[core]))

    # Write results
    with open('SMART_COMPARISON_REPORT.txt', 'w') as f:
        f.write("SMART SONG COMPARISON REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total hold1 files: {len(hold1_files)}\n")
        f.write(f"Total hold2 files: {len(hold2_files)}\n")
        f.write(f"Matched songs: {len(matched)}\n")
        f.write(f"Missing from hold2: {len(missing_from_hold2)}\n\n")

        f.write("=" * 80 + "\n")
        f.write("MATCHED SONGS (already in both folders)\n")
        f.write("=" * 80 + "\n\n")

        for hold1_name, hold2_name in sorted(matched):
            f.write(f"✓ MATCH:\n")
            f.write(f"  hold1: {hold1_name}\n")
            f.write(f"  hold2: {hold2_name}\n\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("MISSING FROM HOLD2 (need to copy these)\n")
        f.write("=" * 80 + "\n\n")

        for original_name, normalized in sorted(missing_from_hold2):
            f.write(f"✗ MISSING: {original_name}\n")
            f.write(f"  Normalized: {normalized}\n\n")

    # Also create a simple list for easy copying
    with open('FILES_TO_COPY.txt', 'w') as f:
        f.write("Files to copy from hold1 to hold2:\n")
        f.write("=" * 80 + "\n\n")
        for original_name, _ in sorted(missing_from_hold2):
            f.write(f"{original_name}\n")

    print(f"✓ Created SMART_COMPARISON_REPORT.txt")
    print(f"✓ Created FILES_TO_COPY.txt")
    print()
    print(f"📊 Summary:")
    print(f"   Matched: {len(matched)} songs")
    print(f"   Missing: {len(missing_from_hold2)} songs")
    print()

    if missing_from_hold2:
        print("🎵 Top 10 missing songs:")
        for original_name, _ in sorted(missing_from_hold2)[:10]:
            print(f"   - {original_name}")


if __name__ == '__main__':
    main()
