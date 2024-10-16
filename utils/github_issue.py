import httpx
import os
import json

from utils.logging import setup_logging

logger = setup_logging("D")

GITHUB_TOKEN = os.getenv("GITHUB_PAT")
GITHUB_AUTHOR = os.getenv("GITHUB_AUTHOR")
GITHUB_REPO = os.getenv("GITHUB_REPO")

with open('config/bot.json', 'r') as f:
    bot_config = json.load(f)
with open('config/version.json', 'r') as f:
    version_config = json.load(f)

bot_name = bot_config['name']
bot_version = version_config['version']

async def create_github_issue(issue_title, issue_body):
    url = f"https://api.github.com/repos/{GITHUB_AUTHOR}/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    json_data = {
        "title": issue_title,
        "body": issue_body,
        "labels": [f"{bot_name}", f"{bot_version}", "error"],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=json_data)
        try:
            if response.status_code != 201:
                error_message = (
                    f"Issue作成に失敗しました: {response.status_code} - {response.text}\n"
                    f"リクエストURL: {response.url}\n"
                    f"リクエストヘッダー: {response.headers}\n"
                    f"リクエストボディ: {issue_body}"
                )
                raise Exception(error_message)
        except Exception as e:
            logger.error(e)
