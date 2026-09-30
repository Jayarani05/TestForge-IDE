from app.agents.self_healing import (
    SelfHealingAgent,
    SelfHealingRequest,
    SelfHealingResult,
)


class SelfHealingService:

    def __init__(self) -> None:
        self.agent = SelfHealingAgent()

    def repair(
        self,
        request: SelfHealingRequest,
    ) -> SelfHealingResult:
        return self.agent.repair(request)