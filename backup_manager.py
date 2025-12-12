#!/usr/bin/env python3
"""
Database Backup Manager for Hammy the Hire Tracker
Handles automatic and manual backups of the SQLite database.
"""
import os
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Manages database backups with automatic cleanup."""

    def __init__(self, db_path: Path, backup_dir: Path = None, max_backups: int = 10):
        """
        Initialize the backup manager.

        Args:
            db_path: Path to the SQLite database file
            backup_dir: Directory to store backups (default: ./backups)
            max_backups: Maximum number of backups to retain (default: 10)
        """
        self.db_path = Path(db_path)
        self.backup_dir = backup_dir or (self.db_path.parent / 'backups')
        self.max_backups = max_backups

        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, backup_name: str = None) -> Path:
        """
        Create a backup of the database.

        Args:
            backup_name: Optional custom backup name (default: timestamp-based)

        Returns:
            Path to the created backup file
        """
        if not self.db_path.exists():
            logger.warning(f"Database file {self.db_path} does not exist, skipping backup")
            return None

        # Generate backup filename with timestamp
        if backup_name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"jobs_backup_{timestamp}.db"

        backup_path = self.backup_dir / backup_name

        try:
            # Use SQLite's backup API for safe backup (handles WAL mode)
            src_conn = sqlite3.connect(str(self.db_path))
            dst_conn = sqlite3.connect(str(backup_path))

            with dst_conn:
                src_conn.backup(dst_conn)

            src_conn.close()
            dst_conn.close()

            logger.info(f"✅ Database backup created: {backup_path}")

            # Clean up old backups
            self._cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            # Fallback to simple file copy if backup API fails
            try:
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"✅ Database backup created (fallback method): {backup_path}")
                self._cleanup_old_backups()
                return backup_path
            except Exception as e2:
                logger.error(f"❌ Fallback backup also failed: {e2}")
                return None

    def _cleanup_old_backups(self):
        """Remove old backups, keeping only the most recent max_backups files."""
        try:
            # Get all backup files sorted by modification time (newest first)
            backups = sorted(
                self.backup_dir.glob('jobs_backup_*.db'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Remove old backups beyond max_backups
            for old_backup in backups[self.max_backups:]:
                old_backup.unlink()
                logger.info(f"🗑️  Removed old backup: {old_backup.name}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to clean up old backups: {e}")

    def list_backups(self):
        """List all available backups with their sizes and dates."""
        backups = []
        for backup_file in sorted(self.backup_dir.glob('jobs_backup_*.db'), reverse=True):
            stat = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
        return backups

    def restore_backup(self, backup_filename: str) -> bool:
        """
        Restore database from a backup file.

        Args:
            backup_filename: Name of the backup file to restore

        Returns:
            True if successful, False otherwise
        """
        backup_path = self.backup_dir / backup_filename

        if not backup_path.exists():
            logger.error(f"❌ Backup file not found: {backup_filename}")
            return False

        try:
            # Create a safety backup of current database first
            safety_backup = self.db_path.parent / f"jobs_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            if self.db_path.exists():
                shutil.copy2(self.db_path, safety_backup)
                logger.info(f"🔒 Safety backup created: {safety_backup}")

            # Restore the backup
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"✅ Database restored from: {backup_filename}")
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False

    def get_backup_stats(self) -> dict:
        """Get statistics about backups."""
        backups = list(self.backup_dir.glob('jobs_backup_*.db'))

        if not backups:
            return {
                'count': 0,
                'total_size_mb': 0,
                'oldest': None,
                'newest': None
            }

        sizes = [b.stat().st_size for b in backups]
        times = [b.stat().st_mtime for b in backups]

        return {
            'count': len(backups),
            'total_size_mb': round(sum(sizes) / (1024 * 1024), 2),
            'oldest': datetime.fromtimestamp(min(times)).strftime('%Y-%m-%d %H:%M:%S'),
            'newest': datetime.fromtimestamp(max(times)).strftime('%Y-%m-%d %H:%M:%S')
        }


def backup_on_startup(db_path: Path, max_backups: int = 10) -> bool:
    """
    Convenience function to create a backup on application startup.

    Args:
        db_path: Path to the database file
        max_backups: Maximum number of backups to retain

    Returns:
        True if backup successful, False otherwise
    """
    manager = BackupManager(db_path, max_backups=max_backups)
    backup_path = manager.create_backup()
    return backup_path is not None


if __name__ == '__main__':
    # Test the backup manager
    import sys

    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        db_path = Path(__file__).parent / 'jobs.db'

    logging.basicConfig(level=logging.INFO)

    print(f"🐷 Hammy's Backup Manager")
    print(f"Database: {db_path}")
    print()

    manager = BackupManager(db_path)

    # Create backup
    print("Creating backup...")
    backup_path = manager.create_backup()
    print()

    # Show stats
    stats = manager.get_backup_stats()
    print("📊 Backup Statistics:")
    print(f"  Total backups: {stats['count']}")
    print(f"  Total size: {stats['total_size_mb']} MB")
    if stats['oldest']:
        print(f"  Oldest: {stats['oldest']}")
        print(f"  Newest: {stats['newest']}")
    print()

    # List backups
    print("📁 Available Backups:")
    for backup in manager.list_backups():
        print(f"  • {backup['filename']} ({backup['size_mb']} MB) - {backup['created']}")
