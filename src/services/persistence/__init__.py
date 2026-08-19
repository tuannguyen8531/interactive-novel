"""SQLite persistence adapter for the application ports."""

from .canonical import InjectedCommitFailure, SqlAlchemyCanonicalRepository
from .database import Database, create_database
from .jobs import SqlAlchemyJobRepository
from .migrations import upgrade_database
from .retrieval import SqlAlchemyEmbeddingStore, SqlAlchemyRetrievalRepository, SqlAlchemyRetrievalTraceStore
from .uow import SqlAlchemyUnitOfWork, make_uow_factory

__all__ = [
    "Database",
    "InjectedCommitFailure",
    "SqlAlchemyCanonicalRepository",
    "SqlAlchemyEmbeddingStore",
    "SqlAlchemyJobRepository",
    "SqlAlchemyRetrievalRepository",
    "SqlAlchemyRetrievalTraceStore",
    "SqlAlchemyUnitOfWork",
    "create_database",
    "make_uow_factory",
    "upgrade_database",
]
