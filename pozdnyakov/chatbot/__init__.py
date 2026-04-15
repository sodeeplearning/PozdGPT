import os
from collections import deque
import torch

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    GenerationConfig
)

from .utils import download_model
from .config import system_role, add_assistant_answers_to_history

from .config import (
    default_checkpoint,
    default_max_seq,
    default_min_seq,
    default_saving_dir,
    default_save_history,
    default_max_history_size,
    default_temperature,
    default_repetition_penalty,
    default_do_sample,
    default_confidence_threshold,
    default_top_k,
)


class PozdnyakovChatBot:
    def __init__(
        self,
        checkpoint: str | int = default_checkpoint,
        saving_dir: str = default_saving_dir,
        use_cuda: bool = True,
        model_path: str = None,
        max_seq: int = default_max_seq,
        min_seq: int = default_min_seq,
        max_history_size: int = default_max_history_size,
        confidence_threshold: float = default_confidence_threshold,
        save_history: bool = default_save_history,
        temperature: float = default_temperature,
        repetition_penalty: float = default_repetition_penalty,
        top_k: int = default_top_k,
        do_sample: bool = default_do_sample,
    ):
        """Constructor of PozdnyakovChatBot class.

        :param checkpoint: Checkpoint (weights) index.
        :param saving_dir: Path to save loaded weights.
        :param use_cuda: 'True' if you need to use GPU.
        :param model_path: Path to an existing model.
        :param max_seq: Max length of generated sequence.
        :param min_seq: Min length of generated sequence.
        :param confidence_threshold: Min probability of token to generate.
        :param save_history: 'True' if you need to save you conversations.
        :param temperature: Value of model's 'creativity'
        :param repetition_penalty: Value of penalty of repeated words.
        :param top_k: Model will choose only top-15 tokens with the bests probability.
        :param do_sample: Make generations as a sample.
        """
        use_cuda = use_cuda and torch.cuda.is_available()

        if isinstance(checkpoint, int):
            checkpoint = str(checkpoint)
        if model_path is None:
            download_model(checkpoint=checkpoint, saving_dir=saving_dir)
            model_path = os.path.join(saving_dir, f"checkpoint-{checkpoint}")

        self.save_history = save_history
        self.max_history_size = max_history_size

        self.history = deque([
            {"role": "system", "content": system_role}
        ])
        self.multy_user_history = dict()

        self.bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

        self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        self.terminators = [
            self.tokenizer.eos_token_id,
            self.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

        self.generation_config = GenerationConfig(
            temperature=temperature,
            max_new_tokens=max_seq,
            min_new_tokens=min_seq,
            eos_token_id=self.terminators,
            repetition_penalty=repetition_penalty,
            do_sample=do_sample,
            assistant_confidence_threshold=confidence_threshold,
            top_k=top_k
        )

        if use_cuda:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map="auto",
                quantization_config=self.bnb_config,
                attn_implementation=None,
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                attn_implementation="eager",
            )

    @staticmethod
    def __preprocess_input(user_prompt: str) -> str:
        return user_prompt.replace("/ask", "").replace("/ask@PozdnyakAIBot", "")

    @staticmethod
    def __postprocess_output(model_response: str) -> str:
        assistant_response = model_response[model_response.find("assistant\n") + 11:]
        cleaned = assistant_response.replace("assistant", "")

        if "_ComCallableWrapper" in cleaned:
            cleaned = cleaned[:cleaned.find("_ComCallableWrapper")]

        return cleaned

    def __update_history(self, user_id: int = None) -> None:
        if user_id is None:
            if len(self.history) > self.max_history_size:
                self.history.popleft()
                self.history.popleft()
                self.history.appendleft({"role": "system", "content": system_role})

        else:
            if len(self.multy_user_history[user_id]) > self.max_history_size:
                self.multy_user_history[user_id].popleft()
                self.multy_user_history[user_id].popleft()
                self.multy_user_history[user_id].appendleft(
                    {"role": "system", "content": system_role}
                )

    def clear_history(self, user_id: str = None) -> None:
        """Clear history of chatting.

        :return: None.
        """
        if user_id is None:
            self.history = deque([
                {"role": "system", "content": system_role}
            ])
        else:
            del self.multy_user_history[user_id]

    def __answer(self, messages: dict) -> str:
        input_ids = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(self.model.device)

        outputs = self.model.generate(
            input_ids,
            generation_config=self.generation_config
        )
        model_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        processed_response = self.__postprocess_output(model_response)

        return processed_response

    def generate(self, prompt: str = None, messages: dict = None) -> str:
        """Get answer to a prompt.

        :param prompt: Prompt to a model.
        :param messages: History of conversations.
        :return: Model's answer.
        """
        assert prompt or messages, "Input is empty."

        if messages is None:
            prompt = self.__preprocess_input(prompt)
            if not self.save_history:
                messages = [
                    {"role": "user", "content": prompt}
                ]
            else:
                self.history.append({"role": "user", "content": prompt})
                messages = self.history

        answer = self.__answer(messages=messages)

        if self.save_history:
            self.history.append({"role": "user", "content": prompt})
            if add_assistant_answers_to_history:
                self.history.append({"role": "assistant", "content": answer})
            self.__update_history()

        return answer


    def __call__(self, prompt: str, messages: dict = None) -> str:
        """Get answer to a prompt.

        :param prompt: Prompt to a model.
        :param messages: History of conversations.
        :return: Model's answer.
        """
        return self.generate(
            prompt=prompt,
            messages=messages
        )

    def multy_user_prompt(self, prompt: str, user_id: int) -> str:
        """Get answer to a prompt in a context with several users.

        :param prompt: Prompt to a model.
        :param user_id: ID of user using the model.
        :return: Model's answer.
        """
        if user_id not in self.multy_user_history:
            self.multy_user_history[user_id] = deque([
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ])
        else:
            self.multy_user_history[user_id].append(
                {"role": "user", "content": prompt}
            )

        answer = self.__answer(messages=self.multy_user_history[user_id])
        answer = answer[answer.rfind("\n") + 1:]

        self.multy_user_history[user_id].append(
            {"role": "assistant", "content": answer}
        )
        self.__update_history(user_id=user_id)

        return answer
