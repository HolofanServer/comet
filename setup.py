import json
import subprocess
import os

from utils.auth import get_auth

from utils.logging import setup_logging

logger = setup_logging("D")

async def main():
    await get_auth()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

# def get_second_last_commit_message():
#     logger.debug("Fetching the first last commit message.")
#     result = subprocess.run(["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True)
#     messages = result.stdout.strip().split("\n\n")
#     logger.debug(f"Commit messages fetched: {messages}")
#     return messages[-1]

# def update_version(major_change=False):
#     logger.debug("Updating version in config/version.json.")
#     with open("config/version.json", "r") as file:
#         data = json.load(file)
#         logger.debug(f"Current version: {data['version']}")

#     version_parts = data["version"].split(".")
#     if major_change:
#         version_parts[1] = str(int(version_parts[1]) + 1)
#         version_parts[2] = "0"
#         logger.debug("Major change detected. Incrementing minor version and resetting patch version.")
#     else:
#         version_parts[2] = str(int(version_parts[2]) + 1)
#         logger.debug("Minor change detected. Incrementing patch version.")

#     data["version"] = ".".join(version_parts)
#     logger.debug(f"New version: {data['version']}")

#     with open("config/version.json", "w") as file:
#         json.dump(data, file, indent=4)
#         logger.debug("Version updated in config/version.json.")

# commit_message = get_second_last_commit_message()
# logger.debug(f"Second last commit message: {commit_message}")
# if "fix" in commit_message:
#     update_version(major_change=False)
#     logger.info("fix found in commit message.")
# elif "add" in commit_message:
#     update_version(major_change=True)
#     logger.info("add found in commit message.")
# elif "update" in commit_message:
#     update_version(major_change=True)
#     logger.info("update found in commit message.")
# elif "rm" in commit_message:
#     update_version(major_change=True)
#     logger.info("rm found in commit message.")
# else:
#     update_version(major_change=False)
#     logger.info("No BREAKING CHANGE found in commit message.")
