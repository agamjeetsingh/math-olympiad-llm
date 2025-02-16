import openai
from utils.prompts import Prompts
from . import Solver

class Feedback(Solver):
    def validate_input(self) -> None:
        if not self.problem_statement.strip():
            raise ValueError("Problem statement cannot be empty")
        if self.properties.max_reasoning_tries <= 0:
            raise ValueError("max_reasoning_tries must be positive")
        if self.properties.max_verifier_passes <= 0:
            raise ValueError("max_verifier_passes must be positive")

    def run(self):
        try:
            self.validate_input()
            reasoner_conversation = [
                Prompts.REASONER_INITIAL_SYSTEM_PROMPT.value,
                {
                    "role": "user",
                    "content": f"Math Olympiad Problem: {self.problem_statement}",
                },
            ]
            for reasoner_trial in range(self.properties.max_reasoning_tries):
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

                if not solution_incorrect:
                    break

                verifier_conversation.append(
                    Prompts.VERIFIER_PARTIAL_PROGRESS_PROMPT.value
                )
                partial_progress = self.properties.verifier_model.send_request(
                    verifier_conversation
                )
                reasoner_conversation = [
                    Prompts.REASONER_SYSTEM_PROMPT.value,
                    {
                        "role": "user",
                        "content": f"Problem: {self.problem_statement}\n\nPartial Progress: {partial_progress}",
                    },
                ]
        
            return reasoner_response

        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
