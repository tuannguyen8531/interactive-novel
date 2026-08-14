"""SQLAlchemy mappings for the Phase 2 persistence foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Metadata root owned by the persistence adapter."""


class WorldModel(Base):
    __tablename__ = "worlds"
    __table_args__ = (UniqueConstraint("name", name="uq_worlds_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False, default="")
    genre: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    tone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    canon_rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    content_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaythroughModel(Base):
    __tablename__ = "playthroughs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(String(36), ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False, index=True)
    player_character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True
    )
    root_branch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    provider_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    world_clock_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_seed: Mapped[str] = mapped_column(String(160), nullable=False)
    rng_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BranchModel(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    fork_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    head_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    head_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TurnModel(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    final_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_patch: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    world_time_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    world_time_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CharacterModel(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(String(36), ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False, index=True)
    playthrough_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CharacterStateModel(Base):
    __tablename__ = "character_states"
    __table_args__ = (UniqueConstraint("character_id", "playthrough_id", "branch_id", name="uq_character_states_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_active_turn_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "Base",
    "BranchModel",
    "CharacterModel",
    "CharacterStateModel",
    "PlaythroughModel",
    "TurnModel",
    "WorldModel",
]
