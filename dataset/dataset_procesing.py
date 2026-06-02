import argparse
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import traceback
from typing import List, Literal
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from openai import AsyncOpenAI
from pydantic import BaseModel


load_dotenv()


DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_SEMAPHORE = 50


def __process_single_dataset(dataset_path: str) -> list[dict]:
    with open(dataset_path, "r", encoding="utf-8") as json_file:
        messages = json.load(json_file)["messages"]

    obtained_data = []
    for message in messages:
        if message["type"] == "message" and len(message["text"]) >= 100:
            obtained_data.append({
                "text": message["text"],
                "date": message["date"],
            })

    return obtained_data


def merge_datasets(
        datasets_paths: list[str],
        output_path: str,
):
    merge_result = []
    for current_path in tqdm(datasets_paths, desc="Merging datasets"):
        current_dataset = __process_single_dataset(current_path)
        merge_result.extend(current_dataset)

    merge_result.sort(key=lambda x: datetime.fromisoformat(x["date"]))

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(merge_result, output_file, ensure_ascii=False, indent=2)


class DialogMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class DatasetSample(BaseModel):
    system_prompt: str
    dialog: List[DialogMessage]


async def __process_single_post(post: dict, model_name: str) -> DatasetSample:
    system_prompt = f"""Ты — эксперт по точному воспроизведению стиля Владислава Позднякова.
У тебя есть его реальный пост от {post["date"]}.
Задачи (выполняй строго по порядку):
1. Придумай один реалистичный вопрос от обычного подписчика, на который этот пост звучал бы как естественный и прямой ответ.
    - Вопрос старайся сделать более повседневным, незаурядным и натуральным. Прояви креативность
    - Если пост про какую-то новость, то лучше использовать фразы по типу
    "Как относишься..", "Что думаешь.." и дальше очень кратко про новость (старайся такие вопросы делать покороче)
2. Сформируй ответ ассистента, который должен быть максимально близок к оригинальному посту:
    - сохрани по максимум оригинального текста (80 плюс процентов). Сохрани весь характер, все эмоции и всю экспрессию
    - запрещается убирать маты, нецензурщину, оскорбления и т.д.
    - разрешается усиливать эмоции для предания экспрессии
    - старайся адаптировать ответ под вопрос пользователя, чтобы был полноценный диалог
    - если ответ совсем не имеет смысла, то можешь перефразировать пост, убрать детали, но главное - сохранить характер поста
    - можно убирать текст после слов по типу UPD, если он звучит как бред.
    - можно убирать ссылки на фото и сторонние ресурсы
    - если ответ получается больше 100 слов, урежь его, оставив самое главное и сохранив всю нецензурную лексику!
3. Создай **один короткий и универсальный system prompt** (2–4 предложения), который будет использоваться для всей будущей модели. Он должен максимально точно передавать: уровень и тип мата, любимые конструкции, сарказм, иронию, длину предложений, мировоззрение и все речевые привычки Позднякова.
Никогда не придумывай ничего от себя. Не смягчай мат. Не улучшай стиль.

4. Теперь собери диалог между пользователем и ассистентом на 5–7 сообщений (считая только user/assistant), где:
   - первое сообщение user = вопрос из пункта 1
   - первое сообщение assistant = ответ из пункта 2 (максимально близкий к посту)
   - затем добавь ещё 2–3 пары реплик (user → assistant), чтобы диалог звучал натурально:
       * пользователь уточняет/спорит/просит пример/спрашивает «и что делать?»
       * ассистент отвечает в том же стиле и не добавляет фактов, которых нет в посте (кроме общих рассуждений без конкретики)
   - все ответы ассистента должны сохранять характер, экспрессию и лексику.
Верни результат строго в формате JSON по схеме DatasetSample: system_prompt, dialog (массив сообщений role/content)."""

    response = await client.responses.parse(
        model=model_name,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": post["text"]},
        ],
        text_format=DatasetSample,
    )

    sample: DatasetSample = response.output_parsed
    sample.system_prompt = sample.system_prompt + f"\nСегодня {post['date']}"
    return sample


async def __process_all_posts(posts: list[dict], model_name: str, semaphore_num: int):
    semaphore = asyncio.Semaphore(semaphore_num)

    async def process_single_post_by_index(index: int):
        async with semaphore:
            try:
                processing_result: DatasetSample = await __process_single_post(posts[index], model_name)
                return index, processing_result, None
            except Exception as e:
                traceback.print_exc()
                return index, None, str(e)

    tasks = [
        process_single_post_by_index(i)
        for i in range(len(posts))
    ]

    results = await tqdm_asyncio.gather(*tasks)

    processed = []
    errored = []
    samples = []

    for post_index, result, error in results:
        if error is None:
            processed.append(post_index)
            samples.append(result.model_dump())
        else:
            errored.append((post_index, error))

    return {
        "processed_posts": processed,
        "posts_with_errors": errored,
        "samples": samples,
    }


async def process_all_posts_and_save(
        posts_path: str,
        output_path: str = "dataset_result.json",
        model_name: str = DEFAULT_MODEL,
        semaphore_num: int = DEFAULT_SEMAPHORE,
):
    with open(posts_path, "r") as posts_file:
        posts = json.load(posts_file)

    result = await __process_all_posts(
        posts=posts,
        model_name=model_name,
        semaphore_num=semaphore_num,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


async def __continue_posts_processing(
        last_result_path: str,
        posts: list[dict],
        model_name: str,
        semaphore_num: int,
) -> dict[str, list]:

    with open(last_result_path, "r", encoding="utf-8") as json_file:
        last_dataset = json.load(json_file)

    indexes_to_process = [post[0] for post in last_dataset["posts_with_errors"]]
    posts_to_process = [posts[ind] for ind in indexes_to_process]

    result = await __process_all_posts(
        posts=posts_to_process,
        model_name=model_name,
        semaphore_num=semaphore_num,
    )

    indexes_to_insert = [indexes_to_process[i] for i in result["processed_posts"]]

    merge_result = []
    all_processed_ids = sorted(set(last_dataset["processed_posts"]) | set(indexes_to_insert))

    current_insert_index = 0
    for old_processed_ind, old_sample in zip(last_dataset["processed_posts"], last_dataset["samples"]):
        while (
            current_insert_index < len(indexes_to_insert)
            and indexes_to_insert[current_insert_index] < old_processed_ind
        ):
            merge_result.append(result["samples"][current_insert_index])
            current_insert_index += 1
        merge_result.append(old_sample)

    while current_insert_index < len(indexes_to_insert):
        merge_result.append(result["samples"][current_insert_index])
        current_insert_index += 1

    return {
        "processed_posts": all_processed_ids,
        "posts_with_errors": result["posts_with_errors"],
        "samples": merge_result,
    }


async def continue_posts_processing_and_save(
        last_result_path: str,
        posts_path: str,
        output_path: str = "dataset_result.json",
        model_name: str = DEFAULT_MODEL,
        semaphore_num: int = DEFAULT_SEMAPHORE,
):
    with open(posts_path, "r") as posts_file:
        posts = json.load(posts_file)

    try:
        result = await __continue_posts_processing(
            last_result_path=last_result_path,
            posts=posts,
            model_name=model_name,
            semaphore_num=semaphore_num,
        )

        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(result, json_file, ensure_ascii=False, indent=2)

    except Exception as e:
        traceback.print_exc()
        print(f"Exception {e} occurred")


client = AsyncOpenAI(
    api_key=os.environ.get("OPENROUTER_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

parser = argparse.ArgumentParser()
parser.add_argument(
    "--model",
    default=DEFAULT_MODEL,
)
parser.add_argument(
    "--semaphore",
    type=int,
    default=DEFAULT_SEMAPHORE,
)

sub_parsers = parser.add_subparsers(
    dest="command",
    required=True,
)

merging_parser = sub_parsers.add_parser("merge")
merging_parser.add_argument(
    "--paths",
    nargs="+",
    required=True,
)
merging_parser.add_argument(
    "--output_path",
    default="merge_result.json",
)

processing_parser = sub_parsers.add_parser("process")
processing_parser.add_argument(
    "--posts_path",
    required=True,
)
processing_parser.add_argument(
    "--output_path",
    default="dataset_result.json",
)

continuing_parser = sub_parsers.add_parser("continue_processing")
continuing_parser.add_argument(
    "--last_result_path",
    required=True,
)
continuing_parser.add_argument(
    "--posts_path",
    required=True,
)
continuing_parser.add_argument(
    "--output_path",
    default="continued_dataset_result.json",
)

args: argparse.Namespace = parser.parse_args()

match args.command:
    case "merge":
        merge_datasets(
            datasets_paths=args.paths,
            output_path=args.output_path,
        )
    case "process":
        asyncio.run(process_all_posts_and_save(
            posts_path=args.posts_path,
            output_path=args.output_path,
            model_name=args.model,
            semaphore_num=args.semaphore,
        ))
    case "continue_processing":
        asyncio.run(continue_posts_processing_and_save(
            last_result_path=args.last_result_path,
            posts_path=args.posts_path,
            output_path=args.output_path,
            model_name=args.model,
            semaphore_num=args.semaphore,
        ))
