from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import openai
from dotenv import load_dotenv
import os
import json
import requests
import time
import random
from dataclasses import dataclass
from typing import Optional, List, Any, Union, Dict, Tuple


class ModelName(Enum):
    O3_MINI_HIGH = "cline/o3-mini:high"
    O3_MINI_MEDIUM = "cline/o3-mini:medium"
    O3_MINI_LOW = "cline/o3-mini:low"
    DEEPSEEK = "deepseek-reasoner"
    DEEPSEEK_OPENROUTER = "deepseek/deepseek-r1"


@dataclass
class ModelConfig:
    name: ModelName
    base_url: str
    api_key_env: str
    requires_conversation_fix: bool = (
        False  # Some models like DeepSeek do not handle system messages well
    )
    has_reasoning: bool = False


class ModelRegistry:
    _registry = {
        ModelName.O3_MINI_HIGH: ModelConfig(
            name=ModelName.O3_MINI_HIGH,
            base_url="https://router.requesty.ai/v1",
            api_key_env="ROUTER_API_KEY",
        ),
        ModelName.O3_MINI_MEDIUM: ModelConfig(
            name=ModelName.O3_MINI_MEDIUM,
            base_url="https://router.requesty.ai/v1",
            api_key_env="ROUTER_API_KEY",
        ),
        ModelName.DEEPSEEK: ModelConfig(
            name=ModelName.DEEPSEEK,
            base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            has_reasoning=True,
            requires_conversation_fix=True,
        ),
        ModelName.DEEPSEEK_OPENROUTER: ModelConfig(
            name=ModelName.DEEPSEEK_OPENROUTER,
            base_url="https://openrouter.ai/api/v1/chat/completions",
            api_key_env="OPENROUTER_API_KEY",
            has_reasoning=True,
            requires_conversation_fix=True,
        ),
    }

    @classmethod
    def get_config(cls, model_name: ModelName) -> ModelConfig:
        return cls._registry.get(model_name)


class Model:
    def __init__(self, model_type: ModelName) -> None:
        self.model_name = model_type
        self.config = ModelRegistry.get_config(model_type)
        self.base_url = self.config.base_url
        # Flag that can be set from outside to cancel streaming requests
        self.cancel_stream = False

    def fix_conversation(self, conversation):
        if (
            self.config.requires_conversation_fix
            and conversation[0]["role"] == "system"
        ):
            system_message = conversation.pop(0)
            user_message = conversation.pop(0)
            new_message = {
                "role": "user",
                "content": system_message["content"] + "\n\n" + user_message["content"],
            }
            conversation.insert(0, new_message)
        return conversation

    def send_request(
        self,
        conversation,
        use_backoff=True,
        max_retries=3,
        initial_delay=1,
        backoff_factor=2,
    ):
        """
        Send a request to the model API with optional exponential backoff for retrying failed requests.

        Args:
            conversation: The conversation to send to the model
            use_backoff: Whether to use exponential backoff on retryable errors
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry
            backoff_factor: Factor by which to increase delay on each retry

        Returns:
            The model's response content
        """
        load_dotenv()
        api_key = os.getenv(self.config.api_key_env)
        client = openai.OpenAI(api_key=api_key, base_url=self.base_url)

        if self.config.requires_conversation_fix:
            conversation = self.fix_conversation(conversation)

        retryable_errors = (
            openai.APIError,
            openai.APIConnectionError,
            openai.RateLimitError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            json.JSONDecodeError,
        )

        attempts = 0
        delay = initial_delay

        while True:
            try:
                # Special handling for OpenRouter
                if "openrouter" in self.base_url:

                    headers = {
                        "Authorization": f"Bearer {os.getenv("OPENROUTER_API_KEY")}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": self.model_name.value,
                        "messages": conversation,
                        "include_reasoning": self.config.has_reasoning,
                    }

                    response = requests.post(self.base_url, headers=headers, data=json.dumps(payload))
                    reasoning_content = response.json()['choices'][0]['message']['reasoning']
                    content = response.json()['choices'][0]['message']['content']

                    content = f"<thinking>{reasoning_content}</thinking>\n\n{content}"
                elif "deepseek" in self.base_url:
                    # Direct API call to DeepSeek
                    api_url = f"{self.base_url}/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {os.getenv(self.config.api_key_env)}"
                    }

                    payload = {
                        "model": self.model_name.value,
                        "messages": conversation,
                        "stream": False
                    }

                    response = requests.post(api_url, headers=headers, json=payload)
                    response.raise_for_status()

                    data = response.json()
                    content = data['choices'][0]['message']['content']

                    if self.config.has_reasoning and 'reasoning_content' in data['choices'][0]['message']:
                        reasoning = data['choices'][0]['message']['reasoning_content']
                        content = f"<thinking>{reasoning}</thinking>\n\n{content}"

                else:
                    # Standard OpenAI API handling
                    response = client.chat.completions.create(
                        model=self.model_name.value, messages=conversation
                    )

                    content = response.choices[0].message.content
                    if self.config.has_reasoning and hasattr(
                        response.choices[0].message, "reasoning_content"
                    ):
                        content = f"<thinking>{response.choices[0].message.reasoning_content}</thinking>\n\n{content}"

                return content

            except retryable_errors as e:
                attempts += 1

                # Log the error
                print(
                    f"API request failed (attempt {attempts}/{max_retries}): {str(e)}"
                )

                # If we've reached max retries or backoff is disabled, raise the exception
                if attempts >= max_retries or not use_backoff:
                    print(
                        f"Maximum retries reached, giving up after {attempts} attempts"
                    )
                    raise

                # Calculate backoff delay with jitter (±20% randomness)
                jitter = random.uniform(0.8, 1.2)
                sleep_time = delay * jitter

                print(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)

                # Increase delay for next retry
                delay *= backoff_factor

            except Exception as e:
                # For non-retryable errors, just raise immediately
                print(f"Non-retryable error in API request: {str(e)}")
                raise

    def send_request_times(
        self,
        conversation,
        num_requests,
        use_backoff=True,
        max_retries=3,
        initial_delay=1,
        backoff_factor=2,
    ):
        """Send the same conversation request multiple times in parallel with backoff support"""
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self.send_request,
                    conversation,
                    use_backoff,
                    max_retries,
                    initial_delay,
                    backoff_factor,
                )
                for _ in range(num_requests)
            ]
            results = [future.result() for future in futures]
        return results

    def send_request_streaming(
        self,
        conversation,
        use_backoff=True,
        max_retries=3,
        initial_delay=1,
        backoff_factor=2,
    ):
        """
        Send a request in streaming mode that can be canceled mid-generation
        
        Returns the response so far if canceled, or the complete response if not canceled
        """
        load_dotenv()
        api_key = os.getenv(self.config.api_key_env)

        if self.config.requires_conversation_fix:
            conversation = self.fix_conversation(conversation)

        # Reset cancel flag before starting
        self.cancel_stream = False

        if "openrouter" in self.base_url:
            headers = {
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name.value,
                "messages": conversation,
                "include_reasoning": self.config.has_reasoning,
                "stream": True,
            }

            response_text = ""
            reasoning_text = ""

            try:
                with requests.post(self.base_url, headers=headers, json=payload, stream=True) as response:
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if self.cancel_stream:
                            print("Streaming request canceled")
                            break

                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data:'):
                                line = line[5:].strip()
                                if line == "[DONE]":
                                    break

                                try:
                                    chunk = json.loads(line)
                                    delta = chunk['choices'][0].get('delta', {})

                                    if 'content' in delta and delta['content'] is not None:
                                        response_text += delta['content']
                                        # print(delta['content'], end="") #####
                                    if 'reasoning' in delta and delta['reasoning'] is not None:
                                        reasoning_text += delta['reasoning']
                                        # print(delta['reasoning'], end="") #####
                                except json.JSONDecodeError:
                                    continue

                if reasoning_text:
                    return f"<thinking>{reasoning_text}</thinking>\n\n{response_text}"
                return response_text

            except Exception as e:
                print(f"Error during streaming: {e}")
                # Return what we have so far if there's any content
                if reasoning_text:
                    return f"<thinking>{reasoning_text}</thinking>\n\n{response_text}" if response_text else f"[Error: {e}]"
                return response_text if response_text else f"[Error: {e}]"

        elif "deepseek" in self.base_url:
            api_url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.getenv(self.config.api_key_env)}"
            }

            payload = {
                "model": self.model_name.value,
                "messages": conversation,
                "stream": True
            }

            response_text = ""
            reasoning_text = ""

            try:
                with requests.post(api_url, headers=headers, json=payload, stream=True) as response:
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if self.cancel_stream:
                            print("Streaming request canceled")
                            break

                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data:'):
                                line = line[5:].strip()
                                if line == "[DONE]":
                                    break

                                try:
                                    chunk = json.loads(line)
                                    delta = chunk['choices'][0].get('delta', {})

                                    if 'content' in delta and delta['content'] is not None:
                                        response_text += delta['content']
                                        # print(delta['content'], end="") #####
                                    if 'reasoning_content' in delta and delta['reasoning_content'] is not None:
                                        reasoning_text += delta['reasoning_content']
                                        # print(delta['reasoning_content'], end="") #####
                                except json.JSONDecodeError:
                                    continue

                if reasoning_text:
                    return f"<thinking>{reasoning_text}</thinking>\n\n{response_text}"
                return response_text

            except Exception as e:
                print(f"Error during streaming: {e}")
                # Return what we have so far if there's any content
                if reasoning_text:
                    return f"<thinking>{reasoning_text}</thinking>\n\n{response_text}" if response_text else f"[Error: {e}]"
                return response_text if response_text else f"[Error: {e}]"

        else:
            # Standard OpenAI streaming
            client = openai.OpenAI(api_key=api_key, base_url=self.base_url)
            response_text = ""
            reasoning_text = ""

            try:
                stream = client.chat.completions.create(
                    model=self.model_name.value, 
                    messages=conversation,
                    stream=True
                )

                for chunk in stream:
                    if self.cancel_stream:
                        stream.close()
                        print("Streaming request canceled")
                        break

                    if chunk.choices[0].delta.content is not None:
                        response_text += chunk.choices[0].delta.content

                    # OpenAI doesn't typically stream reasoning but adding for completeness
                    if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content is not None:
                        reasoning_text += chunk.choices[0].delta.reasoning_content

                if reasoning_text:
                    return f"<thinking>{reasoning_text}</thinking>\n\n{response_text}"
                return response_text

            except Exception as e:
                print(f"Error during streaming: {e}")
                return response_text if response_text else f"[Error: {e}]"

    def send_request_parallel(
        self,
        conversations,
        use_backoff=True,
        max_retries=3,
        initial_delay=1,
        backoff_factor=2,
    ):
        """Send different conversations in parallel with backoff support"""
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self.send_request,
                    conversation,
                    use_backoff,
                    max_retries,
                    initial_delay,
                    backoff_factor,
                )
                for conversation in conversations
            ]
            results = [future.result() for future in futures]
        return results
