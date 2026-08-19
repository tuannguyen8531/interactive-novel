"""Composition root for the FastAPI application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from src.application.contracts.providers import LogicalRole, ProviderRoute, ProviderRoutingConfig, ProviderTarget
from src.application.ports.providers import ProviderGateway
from src.application.services.branches import BranchApplicationService
from src.application.services.events import InMemoryJobEventBroker
from src.application.services.export import PlaythroughExportApplicationService
from src.application.services.jobs import UowJobStore
from src.application.services.playthroughs import PlaythroughApplicationService
from src.application.services.provider_settings import InMemoryProviderSettingsStore, ProviderSettingsApplicationService
from src.application.services.queries import CharacterQueryApplicationService
from src.application.services.turns import TurnApplicationService
from src.application.services.worlds import WorldApplicationService
from src.config import Settings
from src.graph.runner import GraphTurnRunner
from src.paths import get_runtime_paths
from src.services.llm.factory import ProviderRouter
from src.services.persistence.database import Database, create_database
from src.services.persistence.migrations import upgrade_database
from src.services.persistence.uow import make_uow_factory


@dataclass(slots=True)
class ApplicationContainer:
    """All application services owned by one API process."""

    settings: Settings
    database: Database
    uow_factory: Any
    events: InMemoryJobEventBroker
    provider: ProviderGateway
    runner: GraphTurnRunner
    turns: TurnApplicationService
    worlds: WorldApplicationService
    playthroughs: PlaythroughApplicationService
    branches: BranchApplicationService
    queries: CharacterQueryApplicationService
    exports: PlaythroughExportApplicationService
    provider_settings: ProviderSettingsApplicationService

    async def start(self) -> None:
        await upgrade_database(self.database.engine)
        await self.turns.start()

    async def shutdown(self) -> None:
        await self.turns.shutdown()
        await self.runner.aclose()
        await self.database.dispose()


def build_application_container(settings: Settings) -> ApplicationContainer:
    """Build the default local-first runtime without making provider calls."""
    paths = get_runtime_paths(settings.runtime_dir).ensure_directories()
    database = create_database(
        runtime=paths,
        busy_timeout_ms=settings.database_busy_timeout_ms,
        echo=settings.database_echo,
    )
    uow_factory = make_uow_factory(database)
    events = InMemoryJobEventBroker(history_size=settings.sse_history_size)
    provider = ProviderRouter(_default_provider_config())
    runner = GraphTurnRunner(
        uow_factory=uow_factory,
        provider=cast(Any, provider),
        event_sink=events,
        execution_mode=provider.config.mode,
        checkpoint_path=paths.checkpoints_db,
    )
    job_store = UowJobStore(uow_factory)
    turns = TurnApplicationService(
        uow_factory,
        runner,
        job_store=job_store,
        event_broker=events,
        max_concurrency=settings.turn_max_concurrency,
    )
    return ApplicationContainer(
        settings=settings,
        database=database,
        uow_factory=uow_factory,
        events=events,
        provider=provider,
        runner=runner,
        turns=turns,
        worlds=WorldApplicationService(uow_factory),
        playthroughs=PlaythroughApplicationService(uow_factory),
        branches=BranchApplicationService(uow_factory),
        queries=CharacterQueryApplicationService(uow_factory),
        exports=PlaythroughExportApplicationService(uow_factory),
        provider_settings=ProviderSettingsApplicationService(
            InMemoryProviderSettingsStore(),
            gateway=provider,
        ),
    )


def _default_provider_config() -> ProviderRoutingConfig:
    target = ProviderTarget(name="local", provider="ollama", model="llama3.2")
    roles: dict[str, ProviderRoute] = {
        role.value: ProviderRoute("local")
        for role in (
            LogicalRole.PLANNER,
            LogicalRole.SIMULATOR,
            LogicalRole.CONTEXT_VALIDATOR,
            LogicalRole.WRITER,
            LogicalRole.CRITIC,
        )
    }
    return ProviderRoutingConfig(targets={target.name: target}, role_routes=roles)


__all__ = ["ApplicationContainer", "build_application_container"]
