from dataclasses import dataclass, field
from enum import Enum
import openai
from solvers.solver import Solver
from utils.prompts import Prompts



class Verdict(Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    UNKNOWN = "UNKNOWN"


@dataclass
class SolutionAndVerifications:
    solution: str
    verifications: list[str] = field(default_factory=list)
    verdict: Verdict = field(default_factory=lambda: Verdict.UNKNOWN)


class FeedbackAndCondensed(Solver):
    def validate_input(self) -> None:
        if not self.problem_statement.strip():
            raise ValueError("Problem statement cannot be empty")
        if self.properties.max_reasoning_tries <= 0:
            raise ValueError("max_reasoning_tries must be positive")
        if self.properties.max_verifier_passes <= 0:
            raise ValueError("max_verifier_passes must be positive")
        if self.properties.parallel_reasoning_tries <= 0:
            raise ValueError("parallel_reasoning_tries must be positive")

    def run(self):
        file = open("output5.txt", "a")
        try:
            problem_solved = False
            self.validate_input()
            reasoner_conversation = [
                Prompts.REASONER_INITIAL_SYSTEM_PROMPT.value,
                {
                    "role": "user",
                    "content": f"Math Olympiad Problem: {self.problem_statement}",
                },
            ]
            for _ in range(self.properties.max_reasoning_tries):
                responses = self.properties.reasoner_model.send_request_times(
                    reasoner_conversation, self.properties.parallel_reasoning_tries
                )
                print("Reasoning done!")
                response_objects = [
                    SolutionAndVerifications(response) for response in responses
                ]
                for i in range(self.properties.max_verifier_passes):
                    print("Verifying..." + str(i))
                    verifier_conversations = [
                        [
                            Prompts.VERIFIER_SYSTEM_PROMPT.value,
                            {
                                "role": "user",
                                "content": f"Problem: {self.problem_statement}\nPotential Solution: {response_object.solution}",
                            },
                        ]
                        for response_object in response_objects
                        if response_object.verdict == Verdict.UNKNOWN
                    ]
                    print(len(verifier_conversations))
                    verifier_responses = (
                        self.properties.verifier_model.send_request_parallel(
                            verifier_conversations
                        )
                    )
                    verifier_index = 0
                    for response_object in response_objects:
                        if response_object.verdict == Verdict.UNKNOWN:
                            if (
                                "SOLUTION INCORRECT"
                                in verifier_responses[verifier_index]
                            ):
                                response_object.verdict = Verdict.INCORRECT
                            response_object.verifications.append(
                                verifier_responses[verifier_index]
                            )
                            verifier_index += 1

                    # Add deep check using DeepSeek R1 later

                for response_object in response_objects:
                    if response_object.verdict == Verdict.UNKNOWN:
                        response_object.verdict = Verdict.CORRECT

                print([response_object.verdict.value for response_object in response_objects])
                
                correct_responses = [
                    response_object
                    for response_object in response_objects
                    if response_object.verdict == Verdict.CORRECT
                ]

                entire_discussion = "\n\n\n".join(
                    [
                        f"Reasoner's Attempt {idx}: {response_object.solution}\nVerifications: \n"
                        + "\n\n".join(
                            [
                                f"Verification {i+1}: {s}"
                                for i, s in enumerate(response_object.verifications)
                            ]
                        )
                        for idx, response_object in enumerate(response_objects)
                    ]
                )

                file.write(entire_discussion)

                if correct_responses:
                    problem_solved = True
                    return correct_responses[0].solution

                condensed_discussion = (
                    self.properties.discussion_condenser_model.send_request(
                        [
                            Prompts.CONDENSE_ENTIRE_DISCUSSION_PROMPT.value,
                            {
                                "role": "user",
                                "content": entire_discussion,
                            },
                        ]
                    )
                )

                file.write("\n\nCondensed discussion:" + condensed_discussion + "\n\n")

                reasoner_conversation = [
                    Prompts.REASONER_CONDENSED_DISCUSSION_PROMPT.value,
                    {
                        "role": "user",
                        "content": condensed_discussion,
                    },
                ]

            return f"Couldn't solve problem. Here's a summary of what we tried:\n{condensed_discussion}"

        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
