from app.agents.tasks import AgentTask


class LLMRoutingStrategy:
    """
    Determine the preferred provider sequence for
    different TestForge agent tasks.
    """

    DEFAULT_ROUTE = [
        "gpt",
        "gemini",
        "llama",
        "deepseek",
        "mock",
    ]

    TASK_ROUTES: dict[AgentTask, list[str]] = {
        AgentTask.ANALYZE_REPOSITORY: [
            "gpt",
            "gemini",
            "llama",
            "deepseek",
            "mock",
        ],
        AgentTask.GENERATE_TESTS: [
            "gpt",
            "gemini",
            "deepseek",
            "llama",
            "mock",
        ],
        AgentTask.GENERATE_AUTOMATION: [
            "gpt",
            "gemini",
            "llama",
            "deepseek",
            "mock",
        ],
        AgentTask.ANALYZE_FAILURE: [
            "gpt",
            "deepseek",
            "gemini",
            "llama",
            "mock",
        ],
        AgentTask.SELF_HEAL: [
            "gpt",
            "deepseek",
            "gemini",
            "llama",
            "mock",
        ],
    }

    @classmethod
    def get_route(
        cls,
        task: AgentTask,
    ) -> list[str]:
        return list(
            cls.TASK_ROUTES.get(
                task,
                cls.DEFAULT_ROUTE,
            )
        )