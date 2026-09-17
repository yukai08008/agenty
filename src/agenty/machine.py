"""Minimal provider-neutral AgentyMachine lifecycle."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentState(str, Enum):
    CREATED = "created"
    RESOLVING_CONTEXT = "resolving_context"
    READY = "ready"
    PLANNING = "planning"
    EXECUTING = "executing"
    COLLECTING_RESULT = "collecting_result"
    AWAITING_HUMAN = "awaiting_human"
    CLOSED = "closed"
    BLOCKED = "blocked"


class AgentEvent(str, Enum):
    CONTEXT_RESOLUTION_STARTED = "context_resolution_started"
    CONTEXT_RESOLVED = "context_resolved"
    CONTEXT_REJECTED = "context_rejected"
    PLAN_CREATED = "plan_created"
    EXECUTION_STARTED = "execution_started"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    RESULT_COLLECTED = "result_collected"
    CLOSED = "closed"


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: str
    description: str


class Environment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: str
    working_directory: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    strategy: str
    requires_approval: bool = True


class Reward(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    success: bool
    evidence_refs: list[str] = Field(default_factory=list)


class AgentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: AgentState = AgentState.CREATED
    goal: Goal
    environment: Environment
    action: Action | None = None
    reward: Reward | None = None
    events: list[AgentEvent] = Field(default_factory=list)
    failure: str | None = None


class InvalidAgentTransition(RuntimeError):
    pass


class AgentyMachine:
    def __init__(self, goal: Goal, environment: Environment, snapshot: AgentSnapshot | None = None) -> None:
        if snapshot is not None and (snapshot.goal != goal or snapshot.environment != environment):
            raise ValueError("snapshot belongs to another goal or environment")
        self._data = snapshot or AgentSnapshot(goal=goal, environment=environment)

    @property
    def state(self) -> AgentState:
        return self._data.state

    @property
    def data(self) -> AgentSnapshot:
        return self._data

    def apply(self, event: AgentEvent, *, action: Action | None = None, reward: Reward | None = None, failure: str | None = None) -> AgentState:
        transitions = {
            (AgentState.CREATED, AgentEvent.CONTEXT_RESOLUTION_STARTED): AgentState.RESOLVING_CONTEXT,
            (AgentState.RESOLVING_CONTEXT, AgentEvent.CONTEXT_RESOLVED): AgentState.READY,
            (AgentState.RESOLVING_CONTEXT, AgentEvent.CONTEXT_REJECTED): AgentState.BLOCKED,
            (AgentState.READY, AgentEvent.PLAN_CREATED): AgentState.PLANNING,
            (AgentState.PLANNING, AgentEvent.EXECUTION_STARTED): AgentState.EXECUTING,
            (AgentState.EXECUTING, AgentEvent.HUMAN_DECISION_REQUIRED): AgentState.AWAITING_HUMAN,
            (AgentState.EXECUTING, AgentEvent.RESULT_COLLECTED): AgentState.COLLECTING_RESULT,
            (AgentState.COLLECTING_RESULT, AgentEvent.CLOSED): AgentState.CLOSED,
            (AgentState.AWAITING_HUMAN, AgentEvent.EXECUTION_STARTED): AgentState.EXECUTING,
        }
        next_state = transitions.get((self.state, event))
        if next_state is None:
            raise InvalidAgentTransition(f"cannot apply {event.value!r} from {self.state.value!r}")
        if event is AgentEvent.PLAN_CREATED:
            if action is None:
                raise InvalidAgentTransition("plan requires an action")
            self._data.action = action
        if event is AgentEvent.RESULT_COLLECTED:
            if reward is None:
                raise InvalidAgentTransition("result requires a reward")
            self._data.reward = reward
        self._data.failure = failure
        self._data.state = next_state
        self._data.events.append(event)
        return next_state

    def snapshot(self) -> AgentSnapshot:
        return self._data.model_copy(deep=True)
