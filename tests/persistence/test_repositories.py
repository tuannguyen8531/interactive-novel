from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.application.contracts.persistence import PlaythroughRecord, WorldRecord
from src.application.errors import ResourceNotFoundError
from src.application.services.playthroughs import PlaythroughApplicationService
from src.application.services.worlds import WorldApplicationService
from src.services.persistence.database import Database
from src.services.persistence.uow import make_uow_factory


async def test_world_and_playthrough_application_services_round_trip(database: Database) -> None:
    uow_factory = make_uow_factory(database)
    worlds = WorldApplicationService(uow_factory)
    playthroughs = PlaythroughApplicationService(uow_factory)

    world = await worlds.create_world(
        name="School of Moonlight",
        premise="A quiet school hides a changing constellation.",
        genre="school_romance",
        tone="warm",
        canon_rules={"schema_version": 1, "public_fact": "the observatory is locked"},
        content_policy={"rating": "14+"},
    )
    playthrough = await playthroughs.create_playthrough(
        world_id=world.id,
        provider_config_snapshot={"mode": "fake"},
        world_clock_minutes=12,
        rng_seed="fixture-seed",
        rng_state={"position": 0},
    )

    assert await worlds.load_world(world.id) == world
    assert await playthroughs.load_playthrough(playthrough.id) == playthrough


async def test_playthrough_creation_requires_an_existing_world(database: Database) -> None:
    playthroughs = PlaythroughApplicationService(make_uow_factory(database))

    with pytest.raises(ResourceNotFoundError):
        await playthroughs.create_playthrough(world_id="missing-world")


async def test_failed_transaction_rolls_back_prior_world_insert(database: Database) -> None:
    world = WorldRecord.new(name="Rolled Back World")
    invalid_playthrough = PlaythroughRecord.new(world_id="missing-world")
    uow_factory = make_uow_factory(database)

    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.worlds.add(world)
            await uow.playthroughs.add(invalid_playthrough)
            await uow.commit()

    async with uow_factory() as uow:
        assert await uow.worlds.get(world.id) is None
