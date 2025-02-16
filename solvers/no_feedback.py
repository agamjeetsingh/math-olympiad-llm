import openai
from utils.prompts import Prompts
from . import Solver

class NoFeedback(Solver):
    def validate_input(self) -> None:
        """Validate input parameters before solving."""
        if not self.problem_statement.strip():
            raise ValueError("Problem statement cannot be empty")
        if self.properties.max_reasoning_tries <= 0:
            raise ValueError("max_reasoning_tries must be positive")
        if self.properties.max_verifier_passes <= 0:
            raise ValueError("max_verifier_passes must be positive")

    def run(self):
        try:
            self.validate_input()
            for reasoner_trial in range(self.properties.max_reasoning_tries):
                reasoner_conversation = [
                    Prompts.REASONER_INITIAL_SYSTEM_PROMPT.value,
                    {
                        "role": "user",
                        "content": f"Math Olympiad Problem: {self.problem_statement}",
                    },
                ]
                reasoner_response = self.properties.reasoner_model.send_request(
                    reasoner_conversation
                )
                verifier_conversation = [
                    Prompts.VERIFIER_SYSTEM_PROMPT.value,
                    {
                        "role": "user",
                        "content": f"Problem: {self.problem_statement}\nPotential Solution: {reasoner_response}",
                    },
                ]
                solution_incorrect = False
                for i in range(self.properties.max_verifier_passes):
                    verifier_response = self.properties.verifier_model.send_request(
                        verifier_conversation
                    )
                    if "SOLUTION INCORRECT" in verifier_response:
                        solution_incorrect = True
                        break

                if solution_incorrect:
                    continue

                break
            print(reasoner_response)

        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")