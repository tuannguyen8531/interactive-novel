"""Composition root for the FastAPI application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from src.application.contracts.providers import ExecutionMode, LogicalRole, ProviderRoute, ProviderRoutingConfig, ProviderTarget
from src.application.contracts.telemetry import TelemetryConfig
from src.application.ports.providers import ProviderGateway, ProviderPort
from src.application.services.branches import BranchApplicationService
from src.application.services.derived import DerivedJobApplicationService, DerivedJobWorker
from src.application.services.events import InMemoryJobEventBroker
from src.application.services.export import PlaythroughExportApplicationService
from src.application.services.feedback import FeedbackApplicationService
from src.application.services.game_states import GameStateApplicationService
from src.application.services.jobs import UowJobStore
from src.application.services.operations import RuntimeOperationsApplicationService
from src.application.services.playthroughs import PlaythroughApplicationService
from src.application.services.provider_settings import ProviderSettingsApplicationService
from src.application.services.queries import CharacterQueryApplicationService
from src.application.services.turns import TurnApplicationService
from src.application.services.world_drafts import WorldDraftApplicationService
from src.application.services.worlds import WorldApplicationService
from src.config import Settings
from src.graph.runner import GraphTurnRunner
from src.paths import get_runtime_paths
from src.services.ai.world_builder import ProviderWorldDraftGenerator
from src.services.feedback import JsonlFeedbackStore
from src.services.llm.factory import ProviderRouter
from src.services.persistence.database import Database, create_database
from src.services.persistence.migrations import upgrade_database
from src.services.persistence.uow import make_uow_factory
from src.services.provider_settings import JsonProviderSettingsStore
from src.services.telemetry import TelemetryRecorder, build_telemetry_recorder


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
    game_states: GameStateApplicationService
    exports: PlaythroughExportApplicationService
    world_drafts: WorldDraftApplicationService
    provider_settings: ProviderSettingsApplicationService
    derived_jobs: DerivedJobApplicationService
    derived_worker: DerivedJobWorker
    telemetry: TelemetryRecorder
    feedback: FeedbackApplicationService
    operations: RuntimeOperationsApplicationService

    async def start(self) -> None:
        await upgrade_database(self.database.engine)
        await self.provider_settings.initialize(_default_provider_config(self.settings))
        await self.turns.start()
        await self.derived_worker.start()

    async def shutdown(self) -> None:
        await self.derived_worker.stop()
        await self.turns.shutdown()
        await self.runner.aclose()
        await self.database.dispose()


def build_application_container(settings: Settings) -> ApplicationContainer:
    """Build the default local-first runtime without making provider calls."""
    paths = get_runtime_paths(settings.runtime_dir).ensure_directories()
    telemetry = build_telemetry_recorder(
        TelemetryConfig(
            enabled=settings.telemetry_enabled,
            output_path=str(paths.telemetry) if settings.telemetry_enabled else None,
            prompt_cost_per_1k_tokens=settings.telemetry_prompt_cost_per_1k_tokens,
            completion_cost_per_1k_tokens=settings.telemetry_completion_cost_per_1k_tokens,
            max_samples=settings.telemetry_max_samples,
        ),
        output_path=paths.telemetry,
    )
    database = create_database(
        runtime=paths,
        busy_timeout_ms=settings.database_busy_timeout_ms,
        echo=settings.database_echo,
    )
    uow_factory = make_uow_factory(database)
    events = InMemoryJobEventBroker(history_size=settings.sse_history_size)
    provider = ProviderRouter(_default_provider_config(settings))
    runner = GraphTurnRunner(
        uow_factory=uow_factory,
        provider=cast(Any, provider),
        event_sink=events,
        execution_mode=provider.config.mode,
        checkpoint_path=paths.checkpoints_db,
        telemetry=telemetry,
        input_max_chars=settings.input_max_chars,
    )
    job_store = UowJobStore(uow_factory)
    turns = TurnApplicationService(
        uow_factory,
        runner,
        job_store=job_store,
        event_broker=events,
        max_concurrency=settings.turn_max_concurrency,
    )
    game_states = GameStateApplicationService(uow_factory)
    derived_jobs = DerivedJobApplicationService(
        uow_factory,
        embedding_provider=cast(ProviderPort, provider),
        game_states=game_states,
    )
    derived_worker = DerivedJobWorker(derived_jobs)
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
        queries=CharacterQueryApplicationService(uow_factory, game_states=game_states),
        game_states=game_states,
        exports=PlaythroughExportApplicationService(uow_factory, game_states=game_states),
        world_drafts=WorldDraftApplicationService(
            uow_factory,
            generator=ProviderWorldDraftGenerator(provider),
        ),
        provider_settings=ProviderSettingsApplicationService(
            JsonProviderSettingsStore(paths.settings),
            gateway=provider,
        ),
        derived_jobs=derived_jobs,
        derived_worker=derived_worker,
        telemetry=telemetry,
        feedback=FeedbackApplicationService(JsonlFeedbackStore(paths.feedback)),
        operations=RuntimeOperationsApplicationService(paths.game_db, paths.exports),
    )


def _default_provider_config(settings: Settings) -> ProviderRoutingConfig:
    local = ProviderTarget(
        name="local",
        provider="ollama",
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )
    embedding = ProviderTarget(
        name="local-embedding",
        provider="ollama",
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
    )
    gemini = ProviderTarget(
        name="gemini",
        provider="gemini",
        model=settings.gemini_model,
        api_key_env="GEMINI_API_KEY",
    )
    openrouter = ProviderTarget(
        name="openrouter",
        provider="openrouter",
        model=settings.openrouter_model,
        api_key_env="OPENROUTER_API_KEY",
    )
    target_names = {
        "ollama": local.name,
        "gemini": gemini.name,
        "openrouter": openrouter.name,
    }
    primary_target = target_names[settings.llm_provider]
    fallback_targets = (
        (target_names[settings.fallback_provider],)
        if settings.fallback_provider and settings.fallback_provider != settings.llm_provider
        else ()
    )
    roles: dict[str, ProviderRoute] = {
        role.value: ProviderRoute(primary_target, fallback_targets)
        for role in (
            LogicalRole.PLANNER,
            LogicalRole.SIMULATOR,
            LogicalRole.CONTEXT_VALIDATOR,
            LogicalRole.WRITER,
            LogicalRole.CRITIC,
        )
    }
    roles["world_builder"] = ProviderRoute(primary_target, fallback_targets)
    roles["embedding"] = ProviderRoute("local-embedding")
    return ProviderRoutingConfig(
        targets={target.name: target for target in (local, embedding, gemini, openrouter)},
        role_routes=roles,
        mode=ExecutionMode(settings.execution_mode),
        allow_cloud=settings.allow_cloud_routing,
        story_language=settings.story_language,
    )


__all__ = ["ApplicationContainer", "build_application_container"]
