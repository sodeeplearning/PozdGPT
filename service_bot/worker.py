from openai import AsyncOpenAI

from config import ChatBotParams, DefaultModelParams


class Chat:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=ChatBotParams.vllm_host,
            api_key=ChatBotParams.vllm_api_key,
        )

    async def stream(self, messages: list):
        stream = await self.client.chat.completions.create(
            model=ChatBotParams.vllm_model_name,
            messages=messages,
            stream=True,
            temperature=DefaultModelParams.temperature,
            max_tokens=DefaultModelParams.max_tokens,
            extra_body={
                "top_p": DefaultModelParams.top_p,
                "repetition_penalty": DefaultModelParams.repetition_penalty,
            },
        )

        async for event in stream:
            content = event.choices[0].delta.content
            if content:
                yield content

    async def non_stream(self, messages: list):
        response = await self.client.chat.completions.create(
            model=ChatBotParams.vllm_model_name,
            messages=messages,
            stream=False,
            temperature=DefaultModelParams.temperature,
            max_tokens=DefaultModelParams.max_tokens,
            extra_body={
                "top_p": DefaultModelParams.top_p,
                "repetition_penalty": DefaultModelParams.repetition_penalty,
            },
        )
        return response.choices[0].message.content


chatbot = Chat()
