from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from utils.model import Model, ModelName

@dataclass
class Properties:
    max_reasoning_tries: Optional[int] = 4
    max_verifier_passes: Optional[int] = 4
    parallel_reasoning_tries: Optional[int] = 4 # Used in feedback_and_condensed
    reasoner_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)
    verifier_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)
    discussion_condenser_model: Optional[Model] = Model(ModelName.O3_MINI_HIGH)

class Solver(ABC):
    def __init__(self, problem_statement: str, properties: Properties = Properties()):
        self.problem_statement = problem_statement
        self.properties = properties

    @abstractmethod
    def run(self):
        pass