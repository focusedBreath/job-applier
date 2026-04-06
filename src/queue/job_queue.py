import sqlite3
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum

from ..utils.logger import log


class JobStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class QueuedJob:
    id: str
    title: str
    company: str
    location: str
    url: str
    platform: str
    posted_date: Optional[str] = None
    salary: Optional[str] = None
    status: str = "pending"
    applied_at: Optional[str] = None
    error: Optional[str] = None
    scraped_at: str = None

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()


class JobQueue:
    DB_PATH = Path(__file__).parent.parent.parent / "data" / "jobs.db"

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self.DB_PATH

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    url TEXT UNIQUE NOT NULL,
                    platform TEXT,
                    posted_date TEXT,
                    salary TEXT,
                    status TEXT DEFAULT 'pending',
                    applied_at TEXT,
                    error TEXT,
                    scraped_at TEXT,
                    UNIQUE(url)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_platform ON jobs(platform)
            """)

    def add_job(self, job: QueuedJob) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs 
                    (id, title, company, location, url, platform, posted_date, salary, status, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job.id,
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.platform,
                        job.posted_date,
                        job.salary,
                        job.status,
                        job.scraped_at,
                    ),
                )
                return conn.total_changes > 0
        except Exception as e:
            log.error(f"Error adding job: {e}")
            return False

    def add_jobs(self, jobs: list[QueuedJob]) -> int:
        count = 0
        for job in jobs:
            if self.add_job(job):
                count += 1
        log.info(f"Added {count} new jobs to queue (total: {self.count()})")
        return count

    def get_pending(
        self, limit: int = 50, platform: Optional[str] = None
    ) -> list[QueuedJob]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM jobs WHERE status = 'pending'"
            params = []

            if platform:
                query += " AND platform = ?"
                params.append(platform)

            query += " ORDER BY scraped_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [QueuedJob(**dict(row)) for row in rows]

    def mark_applied(self, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET status = 'applied', applied_at = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), job_id),
            )

    def mark_failed(self, job_id: str, error: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET status = 'failed', error = ?
                WHERE id = ?
            """,
                (error, job_id),
            )

    def mark_skipped(self, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET status = 'skipped'
                WHERE id = ?
            """,
                (job_id,),
            )

    def count(self, status: Optional[str] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            if status:
                return conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)
                ).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
            ).fetchone()[0]
            applied = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
            ).fetchone()[0]

            platforms = conn.execute("""
                SELECT platform, COUNT(*) FROM jobs GROUP BY platform
            """).fetchall()

            return {
                "total": total,
                "pending": pending,
                "applied": applied,
                "failed": failed,
                "by_platform": dict(platforms),
            }

    def clear_applied(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('applied', 'skipped')")
        log.info("Cleared applied/skipped jobs from queue")

    def export_pending(self, filepath: str):
        jobs = self.get_pending(limit=10000)
        with open(filepath, "w") as f:
            json.dump([asdict(job) for job in jobs], f, indent=2)
        log.info(f"Exported {len(jobs)} pending jobs to {filepath}")
