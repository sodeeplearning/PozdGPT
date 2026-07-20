from openai import AsyncOpenAI

from config import ChatBotParams, DefaultModelParams


class NonStreamChat:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=ChatBotParams.vllm_host,
            api_key=ChatBotParams.vllm_api_key,
        )

    async def __call__(self, prompt: str):
        messages = [{"role": "user", "content": prompt}]
        response = await self.client.chat.completions.create(
            model=ChatBotParams.vllm_model_name,
            messages=messages,
            temperature=DefaultModelParams.temperature,
            max_tokens=DefaultModelParams.max_tokens,
            extra_body={
                "top_p": DefaultModelParams.top_p,
                "repetition_penalty": DefaultModelParams.repetition_penalty,
            },
        )
        content = response.choices[0].message.content
        return content
