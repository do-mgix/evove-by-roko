"""SQLAlchemy ORM models.

One row in `users` per profile. All other tables FK to `users.id` and
include a per-user logical id (`action_id`, `attr_id`, etc) preserved from
the JSON era for compatibility with existing IDs and frontend.

Names map: JSON shape → table. Empty/unused JSON keys (parameters,
statuses, shop_items, tags) are not modeled until needed.
"""
from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    state: Mapped["UserState"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    tutorial: Mapped[list["UserTutorial"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sequences_state: Mapped["SequencesState"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    actions: Mapped[list["Action"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    attributes: Mapped[list["Attribute"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    skills: Mapped[list["AcquiredSkill"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    agenda_items: Mapped[list["AgendaItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    logs: Mapped[list["Log"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserState(Base):
    __tablename__ = "user_state"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    build_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skill_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="progressive", nullable=False)
    days_until_next_checkpoint: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    last_checkpoint_check: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_token_refill: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_refill: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    user: Mapped[User] = relationship(back_populates="state")


class UserTutorial(Base):
    __tablename__ = "user_tutorial"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="tutorial")


class SequencesState(Base):
    __tablename__ = "sequences_state"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    first_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    consecutive_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="sequences_state")


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("user_id", "action_id", name="uq_actions_user_action"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[int] = mapped_column(Integer, nullable=False)
    diff: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    logic_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sub_logic_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="actions")


class Attribute(Base):
    __tablename__ = "attributes"
    __table_args__ = (UniqueConstraint("user_id", "attr_id", name="uq_attributes_user_attr"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attr_id: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    user: Mapped[User] = relationship(back_populates="attributes")
    related_actions: Mapped[list["AttributeAction"]] = relationship(cascade="all, delete-orphan")


class AttributeAction(Base):
    """Link table: attribute → action (per-user attribute id refers to per-user action id)."""
    __tablename__ = "attribute_actions"

    attribute_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey("attributes.id", ondelete="CASCADE"), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(16), primary_key=True)


class AcquiredSkill(Base):
    __tablename__ = "skills_acquired"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="skills")


class AgendaItem(Base):
    __tablename__ = "agenda_items"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_agenda_user_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(16), nullable=False)
    day: Mapped[str | None] = mapped_column(String(8), nullable=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    label_kind: Mapped[str] = mapped_column(String(16), default="text", nullable=False)
    label_id: Mapped[str | None] = mapped_column(String(16), nullable=True)

    user: Mapped[User] = relationship(back_populates="agenda_items")


class Log(Base):
    __tablename__ = "logs"
    __table_args__ = (UniqueConstraint("user_id", "log_id", name="uq_logs_user_log"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    log_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="[CLOUD]", nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    day_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    order_in_day: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="logs")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_projects_user_project"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="projects")
    related_actions: Mapped[list["ProjectAction"]] = relationship(cascade="all, delete-orphan")
    related_attributes: Mapped[list["ProjectAttribute"]] = relationship(cascade="all, delete-orphan")


class ProjectAction(Base):
    __tablename__ = "project_actions"

    project_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(16), primary_key=True)


class ProjectAttribute(Base):
    __tablename__ = "project_attributes"

    project_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    attr_id: Mapped[str] = mapped_column(String(16), primary_key=True)
