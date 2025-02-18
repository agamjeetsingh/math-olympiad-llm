from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import openai
from dotenv import load_dotenv
import os


class ModelName(Enum):
    O3_MINI_HIGH = "cline/o3-mini:high"
    O3_MINI_MEDIUM = "cline/o3-mini:medium"
    DEEPSEEK = "deepseek/deepseek-r1"


class Model:
    def __init__(self, model_type: ModelName) -> None:
        self.model_name = model_type
        if (
            self.model_name == ModelName.O3_MINI_HIGH
            or self.model_name == ModelName.O3_MINI_MEDIUM
        ):
            self.base_url = "https://router.requesty.ai/v1"
        else:
            self.base_url = "https://openrouter.ai/api/v1"
            
    def deepseek_fix_conversation(self, conversation):
        if conversation[0]["role"] == "system":
            system_message = conversation.pop(0)
            user_message = conversation.pop(0)
            new_message = {
                "role": "user",
                "content": system_message["content"] + "\n\n" + user_message["content"],
            }
            conversation.insert(0, new_message)
        return conversation

    def send_request(self, conversation):
        load_dotenv()
        if self.base_url == "https://router.requesty.ai/v1":
            api_key = os.getenv("ROUTER_API_KEY")
        else:
            api_key = os.getenv("OPENROUTER_API_KEY")
        client = openai.OpenAI(api_key=api_key, base_url=self.base_url)
        
        if ModelName.DEEPSEEK in self.model_name:
            conversation = self.deepseek_fix_conversation(conversation)
        
        response = client.chat.completions.create(
            model=self.model_name.value, messages=conversation
        )
        content = response.choices[0].message.content
        if self.model_name == ModelName.DEEPSEEK:
            reasoning_content = response.choices[0].message.reasoning_content
            return (reasoning_content, content)
        return content

    def send_request_times(self, conversation, num_requests):
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.send_request, conversation)
                for _ in range(num_requests)
            ]
            results = [future.result() for future in futures]
        return results

    def send_request_parallel(self, conversations):
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.send_request, conversation)
                for conversation in conversations
            ]
            results = [future.result() for future in futures]
        return results
