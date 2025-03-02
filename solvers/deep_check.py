from concurrent.futures import ThreadPoolExecutor, as_completed
import openai
from solvers.base import Solver, Verdict, Verifier, VerifierOutput
from utils.model import Model, ModelName
from utils.prompts import Prompts
import re


class DeepCheck(Verifier):
    
    def verify(self, problem: str, solution: str) -> VerifierOutput:
        try:
            proof_divider_conversation = [
                Prompts.PROOF_DIVIDER_SYSTEM_PROMPT.value,
                {
                    "role": "user",
                    "content": f"Problem: {problem}\n\nSolution to fragment: {solution}",
                },
            ]
            proof_divider_response = Model(ModelName.O3_MINI_HIGH).send_request(
                proof_divider_conversation
            )
            print("Proof divider response: ", proof_divider_response)

            proof_fragments: list[str] = re.findall(
                r"Segment \d+:\s*(.*?)\s*(?=Segment \d+:|$)",
                proof_divider_response,
                re.DOTALL,
            )

            proof_progression_list = (
                [
                    f"Problem Statement: {problem}\n\nFirst segment to verify:\n\n{proof_fragments[0]}"
                ]
                + [
                    f"Problem Statement: {problem}\n\n"
                    + f"Assume that the following segments are correct and fully rigorous (1 to {i + 1}):\n\n"
                    + "\n\n".join(
                        [
                            f"Segment {j + 1}: " + proof_segment
                            for j, proof_segment in enumerate(
                                proof_fragments[: (i + 1)]
                            )
                        ]
                    )
                    + f"\n\nDetermine whether the following logically segment follows from all the segments above:\n\nSegment {i+2}: "
                    + proof_fragments[i + 1]
                    for i in range(len(proof_fragments) - 1)
                ]
                + [
                    f"Problem Statement: {problem}\n\n"
                    + "\n\n".join(
                        [
                            f"Segment {j + 1}: " + proof_segment
                            for j, proof_segment in enumerate(
                                proof_fragments[: (len(proof_fragments) - 1)]
                            )
                        ]
                    )
                    + f"\n\nSegment {len(proof_fragments)}: "
                    + proof_fragments[len(proof_fragments) - 1]
                ]
            )

            proof_segment_verifier_conversations = (
                [
                    [
                        Prompts.PROOF_SEGMENT_VERIFIER_INITIAL_SYSTEM_PROMPT.value,
                        {
                            "role": "user",
                            "content": proof_progression_list[0],
                        },
                    ]
                ]
                + [
                    [
                        Prompts.PROOF_SEGMENT_VERIFIER_SYSTEMP_PROMPT.value,
                        {
                            "role": "user",
                            "content": proof_progression,
                        },
                    ]
                    for proof_progression in proof_progression_list[
                        1 : len(proof_progression_list) - 1
                    ]
                ]
                + [
                    [
                        Prompts.PROOF_ACHEIVES_GOAL_SYSTEM_PROMPT.value,
                        {
                            "role": "user",
                            "content": proof_progression_list[
                                len(proof_progression_list) - 1
                            ],
                        },
                    ]
                ]
            )

            # Use ThreadPoolExecutor with early termination pattern
            model = Model(ModelName.DEEPSEEK)
            responses = [None] * len(proof_segment_verifier_conversations)
            verdict = Verdict.CORRECT
            
            # Helper function to check if a response indicates incorrect solution
            def is_incorrect(response):
                return ("SOLUTION INCORRECT" in response) or ("SEGMENT INCORRECT" in response)
            
            # Process conversations in parallel with streaming to allow cancellation mid-generation
            with ThreadPoolExecutor() as executor:
                # Map each future to its index in the original list
                future_to_idx = {
                    executor.submit(model.send_request_streaming, conv): idx
                    for idx, conv in enumerate(proof_segment_verifier_conversations)
                }
                
                # Process results as they complete
                completed_count = 0
                total_count = len(future_to_idx)
                
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    completed_count += 1
                    
                    try:
                        response = future.result()
                        responses[idx] = response
                        print(f"Completed verification {idx+1}/{total_count}")
                        
                        # If this segment is incorrect, cancel remaining tasks
                        if is_incorrect(response):
                            print(f"Verification {idx+1} failed. Stopping early.")
                            verdict = Verdict.INCORRECT
                            
                            # Set the cancel flag on the model to stop streaming
                            model.cancel_stream = True
                            
                            # Cancel any pending futures
                            for fut in future_to_idx:
                                if not fut.done() and not fut.cancelled():
                                    fut.cancel()
                                    
                            # Fill any None responses with placeholder
                            for i, resp in enumerate(responses):
                                if resp is None:
                                    responses[i] = "[Verification cancelled]"
                                    
                            break
                            
                    except Exception as e:
                        print(f"Error in verification {idx+1}: {e}")
                        responses[idx] = f"[Error: {e}]"
            
            # If any responses are None (shouldn't happen but just in case)
            for i, resp in enumerate(responses):
                if resp is None:
                    responses[i] = "[No response]"
            
            entire_conversation = "DEEP CHECK:\n\n" + "\n\n".join(
                [
                    f"Verification {i + 1}:\n\n{proof_progression_list[i]}\n\n{responses[i]}"
                    for i in range(len(proof_fragments))
                ]
                + [
                    f"Checking whether Goal of Problem if Met:\n\n{proof_progression_list[len(proof_fragments)]}\n\n{responses[len(proof_fragments)]}"
                ]
            )
            return VerifierOutput(responses, verdict, entire_conversation)

        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
            return VerifierOutput(error=f"{e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            return VerifierOutput(error=f"{e}")


    def verify_parallel(self, problems: str, solutions: str) -> list[bool]:
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.check, problems[i], solutions[i])
                for i in range(len(problems))
            ]
            results = [future.result() for future in futures]
        return results
