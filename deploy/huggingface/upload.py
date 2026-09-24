"""Push the staged Space folder to Hugging Face (used by .github/workflows/deploy-hf.yml).

Creates the Docker Space on first use and replaces its files on every deploy; the
Space then rebuilds itself. Needs HF_TOKEN (a write token) and HF_SPACE (owner/name).
"""
import os
import sys

from huggingface_hub import HfApi


def main(folder):
    token, space = os.environ.get("HF_TOKEN"), os.environ.get("HF_SPACE")
    if not token or not space:
        sys.exit("Set the HF_TOKEN secret and the HF_SPACE variable in the GitHub repository settings.")
    api = HfApi(token=token)
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    commit = os.environ.get("GITHUB_SHA", "local")[:7]
    api.upload_folder(folder_path=folder, repo_id=space, repo_type="space",
                      delete_patterns="*", commit_message=f"Deploy {commit}")
    host = space.lower().replace("/", "-").replace("_", "-").replace(".", "-")
    print(f"Deployed. The Space is rebuilding; the app will be at https://{host}.hf.space")


if __name__ == "__main__":
    main(sys.argv[1])
