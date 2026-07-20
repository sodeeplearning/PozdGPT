from dotenv import load_dotenv
from os import environ, listdir
from os.path import isdir, join

from huggingface_hub import HfApi


weights_path = "./weights"
repo_id = "sodeeplearning/pozdgpt"

load_dotenv()
api = HfApi(token=environ.get("HF_TOKEN"))


for filename in listdir(weights_path):
    current_path = join(weights_path, filename)
    if isdir(current_path) and "awq" in current_path:
        api.upload_folder(
            folder_path=current_path,
            repo_id=repo_id,
            path_in_repo=filename,
        )
    elif filename.endswith(".gguf"):
        api.upload_file(
            path_or_fileobj=current_path,
            repo_id=repo_id,
            path_in_repo=filename,
        )
