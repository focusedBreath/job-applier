import aiosqlite
from datetime import datetime

from src.queue.models import JobListing, JobStats, JobStatus, Platform


DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    platform    TEXT NOT NULL,
    description TEXT DEFAULT '',
    salary      TEXT DEFAULT '',
    posted_date TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    added_at    TEXT NOT NULL,
    applied_at  TEXT,
    skip_reason TEXT DEFAULT '',
    error       TEXT DEFAULT '',
    ai_reason   TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
"""


class JobStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(DDL)
            await db.commit()

    # ── Write ────────────────────────────────────────────────────

    async def add_jobs(self, jobs: list[JobListing]) -> int:
        """Insert new jobs, skip duplicates. Returns count inserted."""
        inserted = 0
        async with aiosqlite.connect(self._db_path) as db:
            for job in jobs:
                try:
                    await db.execute(
                        """
                        INSERT INTO jobs
                            (title, company, location, url, platform, description,
                             salary, posted_date, status, added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.title,
                            job.company,
                            job.location,
                            job.url,
                            job.platform,
                            job.description,
                            job.salary,
                            job.posted_date,
                            JobStatus.PENDING,
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    inserted += 1
                except aiosqlite.IntegrityError:
                    pass  # duplicate URL — skip
            await db.commit()
        return inserted

    async def update_status(
        self,
        job_id: int,
        status: JobStatus,
        *,
        skip_reason: str = "",
        error: str = "",
        ai_reason: str = "",
    ) -> None:
        applied_at = datetime.utcnow().isoformat() if status == JobStatus.APPLIED else None
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE jobs
                SET status = ?, applied_at = COALESCE(?, applied_at),
                    skip_reason = ?, error = ?, ai_reason = ?
                WHERE id = ?
                """,
                (status, applied_at, skip_reason, error, ai_reason, job_id),
            )
            await db.commit()

    # ── Read ─────────────────────────────────────────────────────

    async def get_pending(
        self, platforms: list[Platform] | None = None, limit: int = 50
    ) -> list[JobListing]:
        placeholders = ""
        params: list = [JobStatus.PENDING, limit]
        if platforms:
            placeholders = f"AND platform IN ({','.join('?' * len(platforms))})"
            params = [JobStatus.PENDING, *[p.value for p in platforms], limit]
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT * FROM jobs WHERE status = ? {placeholders} ORDER BY added_at LIMIT ?",
                params,
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_job(r) for r in rows]

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        platform: Platform | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobListing], int]:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if platform:
            conditions.append("platform = ?")
            params.append(platform.value)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT COUNT(*) FROM jobs {where}", params
            ) as cur:
                row = await cur.fetchone()
                total = row[0] if row else 0
            async with db.execute(
                f"SELECT * FROM jobs {where} ORDER BY added_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ) as cur:
                rows = await cur.fetchall()
        return [_row_to_job(r) for r in rows], total

    async def stats(self) -> JobStats:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT status, platform, COUNT(*) as n FROM jobs GROUP BY status, platform"
            ) as cur:
                rows = await cur.fetchall()

        counts: dict[str, int] = {}
        by_platform: dict[str, int] = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + row["n"]
            by_platform[row["platform"]] = by_platform.get(row["platform"], 0) + row["n"]

        return JobStats(
            total=sum(counts.values()),
            pending=counts.get("pending", 0),
            applied=counts.get("applied", 0),
            skipped=counts.get("skipped", 0),
            failed=counts.get("failed", 0),
            by_platform=by_platform,
        )


def _row_to_job(row: aiosqlite.Row) -> JobListing:
    d = dict(row)
    for dt_field in ("added_at", "applied_at"):
        if d.get(dt_field):
            try:
                d[dt_field] = datetime.fromisoformat(d[dt_field])
            except ValueError:
                d[dt_field] = None
    return JobListing(**d)
