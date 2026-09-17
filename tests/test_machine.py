import pytest

from agenty.machine import (
    Action, AgentEvent, AgentState, AgentyMachine, Environment, Goal, InvalidAgentTransition, Reward,
)


def test_agent_machine_lifecycle():
    machine = AgentyMachine(Goal(goal_id="g1", description="test"), Environment(environment_id="e1", working_directory="/tmp"))
    machine.apply(AgentEvent.CONTEXT_RESOLUTION_STARTED)
    machine.apply(AgentEvent.CONTEXT_RESOLVED)
    machine.apply(AgentEvent.PLAN_CREATED, action=Action(action_id="a1", strategy="inspect"))
    machine.apply(AgentEvent.EXECUTION_STARTED)
    machine.apply(AgentEvent.RESULT_COLLECTED, reward=Reward(success=True, value=1.0))
    machine.apply(AgentEvent.CLOSED)
    assert machine.state is AgentState.CLOSED


def test_plan_requires_action():
    machine = AgentyMachine(Goal(goal_id="g1", description="test"), Environment(environment_id="e1", working_directory="/tmp"))
    machine.apply(AgentEvent.CONTEXT_RESOLUTION_STARTED)
    machine.apply(AgentEvent.CONTEXT_RESOLVED)
    with pytest.raises(InvalidAgentTransition, match="action"):
        machine.apply(AgentEvent.PLAN_CREATED)
