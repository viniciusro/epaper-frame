import logging
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path('data/history.db')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_path TEXT NOT NULL,
    source TEXT NOT NULL,
    shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shown_at ON history(shown_at);
CREATE INDEX IF NOT EXISTS idx_path ON history(photo_path);
CREATE INDEX IF NOT EXISTS idx_source ON history(source);
"""

# Sources that use a finite local cache — show every photo once before repeating.
_CACHE_SOURCES = {'nga', 'nextcloud'}

# When remaining unshown photos for a cache source drop to this count, trigger sync.
SYNC_AHEAD_THRESHOLD = 10


class Shuffler:
    def __init__(self, config, sources, db_path=None):
        self.config = config
        self.sources = sources
        self._db_path = Path(db_path) if db_path else _DB_PATH
        self._init_db()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def next(self) -> Path:
        eligible = self._eligible_photos()
        if not eligible:
            logger.warning('History reset — all photos shown')
            self._reset_exhausted_sources()
            eligible = self._eligible_photos()
            if not eligible:
                raise RuntimeError('No photos available from any source')

        source_buckets = {}
        for path, source_name in eligible:
            source_buckets.setdefault(source_name, []).append(path)

        # Uploaded photos always jump the queue regardless of mode.
        if 'upload' in source_buckets:
            chosen_source = 'upload'

        # NGA mode: exclusive — only NGA photos.
        elif 'nga' in source_buckets:
            chosen_source = 'nga'

        # Nextcloud mode: exclusive — only Nextcloud photos.
        elif 'nextcloud' in source_buckets:
            chosen_source = 'nextcloud'

        # Local mode: local folder only (upload already handled above).
        else:
            chosen_source = random.choice(list(source_buckets.keys()))

        chosen_path = random.choice(source_buckets[chosen_source])
        self._record(chosen_path, chosen_source)
        return chosen_path

    def remaining_count(self, source_name: str) -> int:
        """Return how many unshown photos remain for the given source."""
        eligible = self._eligible_photos()
        return sum(1 for _, s in eligible if s == source_name)

    def history_count(self) -> int:
        with self._connect() as conn:
            return conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]

    def reset_history(self):
        with self._connect() as conn:
            conn.execute('DELETE FROM history')

    def reset_history_for_source(self, source_name: str):
        with self._connect() as conn:
            conn.execute('DELETE FROM history WHERE source = ?', (source_name,))
        logger.info('Shuffler: history reset for source %s', source_name)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self):
        return sqlite3.connect(str(self._db_path))

    def _shown_paths_for_source(self, source_name: str) -> set:
        """All photo paths ever shown for this source (no time limit)."""
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT photo_path FROM history WHERE source = ?',
                (source_name,),
            ).fetchall()
        return {row[0] for row in rows}

    def _recently_shown_paths(self) -> set:
        no_repeat_days = self.config.get('display', {}).get('no_repeat_days', 7)
        cutoff = datetime.now() - timedelta(days=no_repeat_days)
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT photo_path FROM history WHERE shown_at >= ?',
                (cutoff.isoformat(),),
            ).fetchall()
        return {row[0] for row in rows}

    def _eligible_photos(self) -> list:
        """Return list of (Path, source_name) not yet shown in this cycle.

        For cache sources (NGA, Nextcloud): exclude any photo shown since the
        last per-source reset — each photo shown exactly once per cycle.
        For other sources: use the time-based no_repeat_days window.
        """
        recent_shown = self._recently_shown_paths()

        # Build per-cache-source shown sets (only fetched if needed)
        cache_shown: dict[str, set] = {}

        eligible = []
        for source in self.sources:
            if source.name in _CACHE_SOURCES:
                if source.name not in cache_shown:
                    cache_shown[source.name] = self._shown_paths_for_source(source.name)
                shown = cache_shown[source.name]
            else:
                shown = recent_shown

            for path in source.list_photos():
                if str(path) not in shown:
                    eligible.append((path, source.name))

        return eligible

    def _reset_exhausted_sources(self):
        """Reset history for any source whose entire pool has been shown."""
        for source in self.sources:
            if source.name in _CACHE_SOURCES:
                all_paths = {str(p) for p in source.list_photos()}
                if not all_paths:
                    continue
                shown = self._shown_paths_for_source(source.name)
                if all_paths <= shown:
                    self.reset_history_for_source(source.name)
            else:
                # For non-cache sources, fall through to global reset below
                pass

        # If still nothing after per-source resets, do a full reset as fallback
        # (handles local source exhaustion)
        recent_shown = self._recently_shown_paths()
        local_sources = [s for s in self.sources if s.name not in _CACHE_SOURCES]
        for source in local_sources:
            remaining = [p for p in source.list_photos() if str(p) not in recent_shown]
            if not remaining:
                with self._connect() as conn:
                    conn.execute('DELETE FROM history WHERE source = ?', (source.name,))
                logger.info('Shuffler: history reset for exhausted local source %s', source.name)

    def _record(self, path: Path, source_name: str):
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO history (photo_path, source) VALUES (?, ?)',
                (str(path), source_name),
            )
