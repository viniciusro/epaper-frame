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
"""


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
            self.reset_history()
            eligible = self._eligible_photos()
            if not eligible:
                raise RuntimeError('No photos available from any source')

        # Weighted random: equal weight per source.
        # If NGA is enabled and has photos, pick exclusively from NGA.
        source_buckets = {}
        for path, source_name in eligible:
            source_buckets.setdefault(source_name, []).append(path)

        if 'nga' in source_buckets:
            chosen_source = 'nga'
        else:
            chosen_source = random.choice(list(source_buckets.keys()))
        chosen_path = random.choice(source_buckets[chosen_source])

        self._record(chosen_path, chosen_source)
        return chosen_path

    def history_count(self) -> int:
        with self._connect() as conn:
            return conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]

    def reset_history(self):
        with self._connect() as conn:
            conn.execute('DELETE FROM history')

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self):
        return sqlite3.connect(str(self._db_path))

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
        """Return list of (Path, source_name) not shown within no_repeat_days."""
        shown = self._recently_shown_paths()
        eligible = []
        for source in self.sources:
            for path in source.list_photos():
                if str(path) not in shown:
                    eligible.append((path, source.name))
        return eligible

    def _record(self, path: Path, source_name: str):
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO history (photo_path, source) VALUES (?, ?)',
                (str(path), source_name),
            )
