from dataclasses import dataclass
from dotenv import load_dotenv
from os import environ


load_dotenv()


@dataclass
class TelegramBotParams:
    bot_token = environ["BOT_TOKEN"]
    redis_port = int(environ.get("REDIS_PORT", 6379))
    redis_host = environ.get("REDIS_HOST", "redis")
    history_size = int(environ.get("HISTORY_SIZE", 20))
    expiration_date = int(environ.get("EXPIRATION_DATE", 7))
    max_pool_connections = int(environ.get("MAX_POOL_CONNECTIONS", 20))
    db_host = environ.get("DB_HOST", "postgres")
    db_user = environ.get("DB_USER", "bot")
    db_password = environ["DB_PASSWORD"]
    db_name = environ.get("DB_NAME", "botdb")
    db_port = int(environ.get("DB_PORT", 5432))
    telegram_channel_id = environ["TELEGRAM_CHANNEL_ID"]
    admins_ids = [int(aid) for aid in environ["ADMINS"].split(",")]


@dataclass
class Payment:
    packages = {  # package_name: commentaries amount - price in telegram stars
        "package_100": {"messages_amount": 100, "price": 3}
    }
    default_user_messages = 50
    subscribed_addition_percent = 20

@dataclass
class ChatBotParams:
    vllm_host = environ.get("VLLM_HOST", f"http://vllm:{environ.get("VLLM_PORT", 8148)}/v1")
    vllm_api_key = environ.get("VLLM_API_KEY", "key")
    vllm_model_name = environ.get("VLLM_MODEL_NAME", "pozdgpt")


@dataclass
class DefaultModelParams:
    temperature = 0.4
    max_tokens = 1024
    top_p = 0.9
    repetition_penalty = 1.1
