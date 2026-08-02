"""Rename Kikuyu Bible MP3s in canonical Bible book order."""
import re
from pathlib import Path

BIBLE_ORDER = {
    "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
    "Joshua": 6, "Judges": 7, "Ruth": 8, "1 Samuel": 9, "2 Samuel": 10,
    "1 Kings": 11, "2 Kings": 12, "1 Chronicles": 13, "2 Chronicles": 14,
    "Ezra": 15, "Nehemiah": 16, "Esther": 17, "Job": 18, "Psalms": 19,
    "Proverbs": 20, "Ecclesiastes": 21, "Song of Songs": 22, "Isaiah": 23,
    "Jeremiah": 24, "Lamentations": 25, "Ezekiel": 26, "Daniel": 27,
    "Hosea": 28, "Joel": 29, "Amos": 30, "Obadiah": 31, "Jonah": 32,
    "Micah": 33, "Nahum": 34, "Habakkuk": 35, "Zephaniah": 36, "Haggai": 37,
    "Zechariah": 38, "Malachi": 39,
    "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44,
    "Romans": 45, "1 Corinthians": 46, "2 Corinthians": 47, "Galatians": 48,
    "Ephesians": 49, "Philippians": 50, "Colossians": 51,
    "1 Thessalonians": 52, "2 Thessalonians": 53,
    "1 Timothy": 54, "2 Timothy": 55, "Titus": 56, "Philemon": 57,
    "Hebrews": 58, "James": 59, "1 Peter": 60, "2 Peter": 61,
    "1 John": 62, "2 John": 63, "3 John": 64, "Jude": 65, "Revelation": 66,
}

temp_dir = Path("./temp")
files = list(temp_dir.glob("*.mp3"))
renamed = 0
skipped = []

for f in files:
    # Extract English book name from parentheses
    match = re.search(r'\(([^)]+)\)', f.name)
    if not match:
        skipped.append(f.name)
        continue

    english_name = match.group(1)
    book_num = BIBLE_ORDER.get(english_name)

    if book_num is None:
        skipped.append(f"{f.name} — unknown book: '{english_name}'")
        continue

    # New name: "01 - Kĩambĩrĩria (Genesis).mp3"
    kikuyu_part = f.name.split(" - ")[2].split(" Kikuyu")[0].strip()
    new_name = f"{book_num:02d} - {kikuyu_part}.mp3"
    new_path = temp_dir / new_name

    f.rename(new_path)
    print(f"{book_num:02d}. {new_name}")
    renamed += 1

print(f"\nRenamed {renamed}/66 files.")
if skipped:
    print("Skipped:")
    for s in skipped:
        print(f"  - {s}")
