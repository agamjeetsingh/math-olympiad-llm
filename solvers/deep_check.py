import openai
from solvers.solver import Solver
from utils.model import Model, ModelName
from utils.prompts import Prompts


class DeepCheck:
    def check(self, solution: str) -> bool:
        try:
            proof_divider_conversation = [
                Prompts.PROOF_DIVIDER_SYSTEM_PROMPT.value,
                {
                    "role": "user",
                    "content": f"Solution to fragment: {solution}",
                },
            ]
            proof_divider_response = Model(ModelName.O3_MINI_HIGH).send_request(
                proof_divider_conversation
            )
            proof_fragments = (
                []
            )  # TODO: Extract proof fragments from proof_divider_response
            proof_progression_list = [
                "\n".join(proof_fragments[: (i + 1)])
                for i in range(len(proof_fragments))
            ]
            proof_segment_verifier_conversations = [
                [
                    Prompts.PROOF_SEGMENT_VERIFIER_SYSTEMP_PROMPT.value,
                    {
                        "role": "user",
                        "content": proof_progression,
                    },
                ]
                for proof_progression in proof_progression_list
            ]

            responses = Model(ModelName.DEEPSEEK).send_request_parallel(
                proof_segment_verifier_conversations
            )

            if any("SOLUTION INCORRECT" in response for response in responses):
                return False
            
            return True

        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
