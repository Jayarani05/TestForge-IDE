from enum import Enum


class AgentTask(str, Enum):
    """Tasks supported by the TestForge agent layer."""

    ANALYZE_REPOSITORY = "analyze_repository"

    GENERATE_TESTS = "generate_tests"

    GENERATE_AUTOMATION = "generate_automation"

    ANALYZE_FAILURE = "analyze_failure"

    SELF_HEAL = "self_heal"