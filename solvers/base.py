from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from utils.model import Model, ModelName


@dataclass
class SolverProperties:
    max_reasoning_tries: Optional[int] = 4
    max_verifier_passes: Optional[int] = 4
    parallel_reasoning_tries: Optional[int] = 4  # Used in feedback_and_condensed
    reasoner_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)
    verifier_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)
    discussion_condenser_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)


class Solver(ABC):
    def __init__(
        self, properties: SolverProperties = SolverProperties()
    ):
        self.properties = properties

    @abstractmethod
    def run(self, problem_statement: str):
        pass

class Reasoner(ABC):
    def __init__(self, problem_statement: str):
        self.problem_statement = problem_statement

    @abstractmethod
    def reason(self) -> str:
        pass
    
    @abstractmethod
    def reason_parallel(self, parallel_tries: int) -> list[str]:
        pass

class Verdict(Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    UNKNOWN = "UNKNOWN"
    
@dataclass
class VerifierOutput:
    verifications: List[str] = field(default_factory=list)
    verdict: Verdict = Verdict.UNKNOWN
    entire_discussion: str = ""
    error: Optional[str] = None


class Verifier(ABC):
    @abstractmethod
    def verify(self) -> VerifierOutput:
        pass
