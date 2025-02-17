from dataclasses import dataclass
from datetime import datetime
import itertools
from typing import Optional, List
from enum import Enum
import json

from solvers import Feedback
from solvers import NoFeedback
import sqlite3

class SolutionType(Enum):
    REASONING = "reasoning"
    VERIFICATION = "verification"
    PARTIAL_SOLUTION = "partial solution"
    FINAL_SOLUTION = "final solution"
    OTHER = "other"


@dataclass
class SolvingStep:
    type: SolutionType
    content: str
    timestamp: datetime
    model: str
    time_taken: float
    metadata: dict = None  # For additional info like model used, confidence, etc.
    
@dataclass
class SolvingProcess:
    steps: List[SolvingStep]

    def to_json(self) -> str:
        return json.dumps(
            {
                "steps": [
                    {
                        "type": step.type,
                        "content": step.content,
                        "timestamp": step.timestamp.isoformat(),
                        "model": step.model,
                        "time_taken": step.time_taken,
                        "metadata": step.metadata,
                    }
                    for step in self.steps
                ],
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SolvingProcess":
        data = json.loads(json_str)
        steps = [
            SolvingStep(
                type=step["type"],
                content=step["content"],
                timestamp=datetime.fromisoformat(step["timestamp"]),
                model=step["model"],
                time_taken=step["time_taken"],
                metadata=step["metadata"],
            )
            for step in data["steps"]
        ]
        return cls(steps=steps)

def split_list(lst, is_delimiter):
    result = []
    current = []
    for item in lst:
        if is_delimiter(item):
            if current:  # if current is non-empty, append it to the result
                result.append(current)
                current = []
        else:
            current.append(item)
    if current:  # add the last group if any
        result.append(current)
    return result

@dataclass
class Solution:
    problem: str
    problem_id: str # Like: "IMO-2021-P1"
    solution: str
    solver_type: NoFeedback | Feedback
    success: bool = None
    timestamp: datetime
    solving_process: SolvingProcess
    error: Optional[str] = None
    
    def total_time(self):
        return sum(step.time_taken for step in self.solving_process.steps)
    
    def total_reasoning_attempts(self):
        return len([step for step in self.solving_process.steps if step.type == SolutionType.REASONING])
    
    def total_verification_attempts(self) -> List[int]:
        return list(map(lambda listOfVerifiers: len(listOfVerifiers) ,list(map(lambda lst: list(filter(lambda step: step.type == SolutionType.VERIFICATION, lst)), split_list(self.solving_process.steps, lambda step: step.type == SolutionType.REASONING)))))
        
class ResearchDatabase:
    def __init__(self, db_path: str = "research_results.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS solutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem TEXT NOT NULL,
                    solution TEXT,
                    solver_type TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    timestamp DATETIME NOT NULL,
                    solving_process JSON NOT NULL,
                    error TEXT,
                    experiment_version TEXT NOT NULL
                )
            """)

    def save_solution(self, solution: Solution, experiment_version: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO solutions 
                (problem, solution, solver_type, attempts, success, 
                 timestamp, solving_process, error, experiment_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                solution.problem,
                solution.solution,
                solution.solver_type,
                solution.attempts,
                solution.success,
                solution.timestamp,
                solution.solving_process.to_json(),  # Store as JSON
                solution.error,
                experiment_version
            ))