import httpx
import json
import os

with open('config/bot.json', 'r') as f:
    bot_config = json.load(f)

async def get_auth():
    """
    FastAPIの認証APIから新しい認証情報を取得する。
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://auth.frwi.net/generate?label={bot_config['name']}")
        try:
            if response.status_code == 200:
                auth_data = response.json()
                if auth_data:
                    save_auth(auth_data)
                    return auth_data
                else:
                    raise Exception("認証情報が空です。")
            else:
                raise Exception("認証情報の取得に失敗しました。")
        except Exception as e:
            raise Exception(f"認証情報の取得に失敗しました。: {e}")

def save_auth(auth: dict):
    """
    認証情報をconfig/auth.jsonに保存する。
    """
    auth_path = 'config/auth.json'
    os.makedirs(os.path.dirname(auth_path), exist_ok=True)
    with open(auth_path, 'w') as f:
        json.dump(auth, f, indent=4)

def load_auth():
    """
    保存済みの認証情報を読み込む。
    """
    if os.path.exists('config/auth.json'):
        with open('config/auth.json', 'r') as f:
            return json.load(f)
    else:
        raise FileNotFoundError("auth.jsonが見つかりません。認証情報を取得してください。")

async def verify_auth(auth: dict):
    """
    FastAPIの認証APIに対して認証情報を送信し、認証チェックを行う。
    """
    auth = load_auth()
    auth_code = auth["auth_code"]
    auth_id = auth["id"]

    async with httpx.AsyncClient() as client:
        response = await client.post("http://auth.frwi.net/verify", json={"id": auth_id, "auth_code": auth_code})
        if response.status_code == 200:
            return response.json().get("result", False)
        else:
            return False
