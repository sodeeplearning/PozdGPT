from dataclasses import dataclass
from dotenv import load_dotenv
from os import environ


load_dotenv()


@dataclass
class TelegramBotParams:
    bot_token = environ["BOT_TOKEN"]
    redis_port = environ.get("REDIS_PORT")


@dataclass
class ChatBotParams:
    vllm_host = f"http://localhost:{environ.get("VLLM_PORT", 8148)}/v1"
    vllm_api_key = environ.get("VLLM_API_KEY", "key")
    vllm_model_name = environ.get("VLLM_MODEL_NAME", "pozdgpt")


@dataclass
class DefaultModelParams:
    temperature = 0.4
    max_tokens = 1024
    top_p = 0.9
    repetition_penalty = 1.1

