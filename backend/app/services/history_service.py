from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.testing_persistence import (
    AnalyticsRecordDB,
    FailureAnalysisRecord,
    SelfHealingRecord,
    TestExecutionRecord,
)


class TestingHistoryService:

    async def executions(
        self,
        db: AsyncSession,
        repository_path: str | None = None,
        limit: int = 50,
    ):
        stmt = select(TestExecutionRecord).order_by(
            TestExecutionRecord.created_at.desc()
        )

        if repository_path:
            stmt = stmt.where(
                TestExecutionRecord.repository_path == repository_path
            )

        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def failures(
        self,
        db: AsyncSession,
        repository_path: str | None = None,
        limit: int = 50,
    ):
        stmt = select(FailureAnalysisRecord).order_by(
            FailureAnalysisRecord.created_at.desc()
        )

        if repository_path:
            stmt = stmt.where(
                FailureAnalysisRecord.repository_path == repository_path
            )

        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def self_healing(
        self,
        db: AsyncSession,
        repository_path: str | None = None,
        limit: int = 50,
    ):
        stmt = select(SelfHealingRecord).order_by(
            SelfHealingRecord.created_at.desc()
        )

        if repository_path:
            stmt = stmt.where(
                SelfHealingRecord.repository_path == repository_path
            )

        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def analytics(
        self,
        db: AsyncSession,
        repository_path: str | None = None,
        limit: int = 50,
    ):
        stmt = select(AnalyticsRecordDB).order_by(
            AnalyticsRecordDB.created_at.desc()
        )

        if repository_path:
            stmt = stmt.where(
                AnalyticsRecordDB.repository_path == repository_path
            )

        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())


testing_history_service = TestingHistoryService()
