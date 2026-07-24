import json
import redis

from config import TelegramBotParams


class ChatMemory:
    def __init__(self):
        self.client = redis.Redis(
            host=TelegramBotParams.redis_host,
            port=TelegramBotParams.redis_port,
            decode_responses=True
        )

    def add_qa(self, user_id: int, user_message: str, assistant_message: str):
        db_key = f"history:{user_id}"
        adding_messages = [
            json.dumps({"role": "user", "content": user_message}, ensure_ascii=False),
            json.dumps({"role": "assistant", "content": assistant_message}, ensure_ascii=False),
        ]
        self.client.rpush(db_key, *adding_messages)
        self.client.ltrim(db_key, -TelegramBotParams.history_size, -1)
        self.client.expire(db_key, TelegramBotParams.expiration_date * 60 * 60 * 24)

    def read_history(self, user_id: int) -> list[dict[str, str]]:
        db_key = f"history:{user_id}"
        messages = [json.loads(m) for m in self.client.lrange(db_key, 0, -1)]
        return messages

    def clear_history(self, user_id: int):
        db_key = f"history:{user_id}"
        self.client.delete(db_key)


memory = ChatMemory()
