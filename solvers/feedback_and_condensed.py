from dataclasses import dataclass, field
from enum import Enum
import openai
from concurrent.futures import ThreadPoolExecutor
from solvers.base import Solver, Verifier, VerifierOutput
from solvers.deep_check import DeepCheck
from utils.prompts import Prompts
from solvers.base import Verdict


@dataclass
class VerifiedSolution:
    solution: str
    verification: VerifierOutput


class FeedbackAndCondensed(Solver):
    def validate_input(self, problem_statement) -> None:
        if not problem_statement.strip():
            raise ValueError("Problem statement cannot be empty")
        if self.properties.max_reasoning_tries <= 0:
            raise ValueError("max_reasoning_tries must be positive")
        if self.properties.max_verifier_passes <= 0:
            raise ValueError("max_verifier_passes must be positive")
        if self.properties.parallel_reasoning_tries <= 0:
            raise ValueError("parallel_reasoning_tries must be positive")

    def run(self, problem_statement: str, light_check: bool = True) -> str:
        file = open("output7.txt", "a")
        try:
            problem_solved = False
            self.validate_input(problem_statement)
            reasoner_conversation = [
                Prompts.REASONER_INITIAL_SYSTEM_PROMPT.value,
                {
                    "role": "user",
                    "content": f"Math Olympiad Problem: {problem_statement}",
                },
            ]
            for _ in range(self.properties.max_reasoning_tries):
                responses = self.properties.reasoner_model.send_request_times(
                    reasoner_conversation, self.properties.parallel_reasoning_tries
                )
                print("Reasoning done!")
                response_objects = [
                    VerifiedSolution(solution=response, verification=VerifierOutput())
                    for response in responses
                ]
                ###
                if light_check:
                    for i in range(self.properties.max_verifier_passes):
                        print("Verifying..." + str(i))
                        verifier_conversations = [
                            [
                                Prompts.VERIFIER_SYSTEM_PROMPT.value,
                                {
                                    "role": "user",
                                    "content": f"Problem: {problem_statement}\nPotential Solution: {response_object.solution}",
                                },
                            ]
                            for response_object in response_objects
                            if response_object.verification.verdict == Verdict.UNKNOWN
                        ]
                        print(len(verifier_conversations))
                        verifier_responses = (
                            self.properties.verifier_model.send_request_parallel(
                                verifier_conversations
                            )
                        )
                        verifier_index = 0
                        for response_object in response_objects:
                            if response_object.verification.verdict == Verdict.UNKNOWN:
                                if (
                                    "SOLUTION INCORRECT"
                                    in verifier_responses[verifier_index]
                                ):
                                    response_object.verification.verdict = Verdict.INCORRECT
                                response_object.verification.verifications.append(
                                    verifier_responses[verifier_index]
                                )
                                verifier_index += 1
                ###

                for response_object in response_objects:
                    if response_object.verification.verdict == Verdict.UNKNOWN:
                        response_object.verification.verdict = Verdict.CORRECT
                # Perform deep checking in parallel for all solutions with Verdict.CORRECT
                correct_solutions = [
                    response_object for response_object in response_objects
                    if response_object.verification.verdict == Verdict.CORRECT
                ]

                if correct_solutions:
                    with ThreadPoolExecutor() as executor:
                        futures = [
                            executor.submit(
                                DeepCheck().verify,
                                problem_statement, 
                                response_object.solution
                            )
                            for response_object in correct_solutions
                        ]
                        deep_check_responses = [future.result() for future in futures]

                    # Update the response objects with the deep check results
                    deep_check_idx = 0
                    for response_object in response_objects:
                        if response_object.verification.verdict == Verdict.CORRECT:
                            deep_check_response = deep_check_responses[deep_check_idx]
                            response_object.verification.verdict = deep_check_response.verdict
                            response_object.verification.verifications.extend(
                                deep_check_response.verifications
                            )
                            response_object.verification.entire_discussion = (
                                deep_check_response.entire_discussion
                            )
                            deep_check_idx += 1
                print(
                    [
                        response_object.verification.verdict.value
                        for response_object in response_objects
                    ]
                )

                correct_responses = [
                    response_object
                    for response_object in response_objects
                    if response_object.verification.verdict == Verdict.CORRECT
                ]

                for idx, response_object in enumerate(response_objects):
                    response_object.verification.entire_discussion = (
                        f"Reasoner's Attempt {idx}: {response_object.solution}\nVerifications: \n"
                        + "\n\n".join(
                            [
                                f"Verification {i+1}: {s}"
                                for i, s in enumerate(
                                    response_object.verification.verifications
                                )
                            ]
                        )
                    ) + response_object.verification.entire_discussion

                entire_discussion = "\n\n\n".join(
                    [
                        response_object.verification.entire_discussion
                        for response_object in response_objects
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
