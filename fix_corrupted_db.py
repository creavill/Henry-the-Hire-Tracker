#!/usr/bin/env python3
"""
Emergency Database Fix Script
Deletes corrupted database files and creates a fresh one.
"""
import os
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / 'jobs.db'
DB_SHM = SCRIPT_DIR / 'jobs.db-shm'
DB_WAL = SCRIPT_DIR / 'jobs.db-wal'

print("🔧 Hammy's Database Repair Tool")
print("=" * 60)
print(f"Working directory: {SCRIPT_DIR}")
print()

# Check for corrupted files
corrupted_files = []
if DB_PATH.exists():
    corrupted_files.append(DB_PATH)
if DB_SHM.exists():
    corrupted_files.append(DB_SHM)
if DB_WAL.exists():
    corrupted_files.append(DB_WAL)

if not corrupted_files:
    print("✅ No corrupted database files found!")
    print("Database will be created fresh on next app startup.")
    sys.exit(0)

print("⚠️  Found potentially corrupted database files:")
for f in corrupted_files:
    print(f"   - {f.name}")
print()

response = input("Delete these files and start fresh? (yes/no): ").strip().lower()

if response == 'yes':
    print("\n🗑️  Deleting corrupted files...")
    for f in corrupted_files:
        try:
            f.unlink()
            print(f"   ✓ Deleted {f.name}")
        except Exception as e:
            print(f"   ✗ Failed to delete {f.name}: {e}")

    print("\n✅ Corrupted files removed!")
    print("🔄 Now run: python local_app.py")
    print("   The database will be created fresh automatically.")
else:
    print("\n❌ Cancelled. Database not modified.")
    sys.exit(1)
