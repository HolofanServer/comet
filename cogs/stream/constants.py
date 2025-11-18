"""
配信通知システムの定数定義
ホロライブメンバーの絵文字マッピング、ブランチ設定など
"""

import json
import os
from pathlib import Path
from typing import Optional

from config.setting import get_settings

settings = get_settings()

# Holodex API設定
HOLODEX_API_KEY: str = os.getenv("HOLODEX_API_KEY", "")
HOLODEX_API_BASE_URL: str = "https://holodex.net/api/v2"

# ブランチ別チャンネル設定
STREAM_CHANNELS: dict[str, dict] = {
    "jp": {
        "channel_id": int(os.getenv("HOLODEX_STREAM_JP_CHANNEL_ID", 0)),
        "webhook_url": os.getenv("HOLODEX_WEBHOOK_JP", ""),
        "idle_name": "配信中のライバーはいません",
        "emoji": "🇯🇵",
        "color": 0xFF4444,  # 赤
        "upcoming_title": "📅 JP配信予定 | Upcoming Streams"
    },
    "en": {
        "channel_id": int(os.getenv("HOLODEX_STREAM_EN_CHANNEL_ID", 0)),
        "webhook_url": os.getenv("HOLODEX_WEBHOOK_EN", ""),
        "idle_name": "配信中のライバーはいません",
        "emoji": "🇺🇸",
        "color": 0x4444FF,  # 青
        "upcoming_title": "📅 EN配信予定 | Upcoming Streams"
    },
    "id": {
        "channel_id": int(os.getenv("HOLODEX_STREAM_ID_CHANNEL_ID", 0)),
        "webhook_url": os.getenv("HOLODEX_WEBHOOK_ID", ""),
        "idle_name": "配信中のライバーはいません",
        "emoji": "🇮🇩",
        "color": 0xFF44FF,  # マゼンタ
        "upcoming_title": "📅 ID配信予定 | Upcoming Streams"
    },
    "dev_is": {
        "channel_id": int(os.getenv("HOLODEX_STREAM_DEV_IS_CHANNEL_ID", 0)),
        "webhook_url": os.getenv("HOLODEX_WEBHOOK_DEV_IS", ""),
        "idle_name": "配信中のライバーはいません",
        "emoji": "🌟",
        "color": 0xFFAA44,  # オレンジ
        "upcoming_title": "📅 DEV_IS配信予定 | Upcoming Streams"
    }
}

# ホロライブメンバーデータの読み込み
def load_member_data() -> dict:
    """hololive_members_complete.jsonからメンバーデータを読み込む"""
    json_path = Path(__file__).parent.parent.parent / "hololive_members_complete.json"

    with open(json_path, encoding='utf-8') as f:
        return json.load(f)

# メンバーデータから絵文字マッピングとブランチマッピングを生成
def generate_mappings() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """
    メンバーデータから各種マッピングを生成

    Returns:
        (name_to_emoji, name_to_branch, name_to_name_ja)のタプル
    """
    members = load_member_data()

    name_to_emoji: dict[str, str] = {}
    name_to_branch: dict[str, str] = {}
    name_to_name_ja: dict[str, str] = {}

    for member in members:
        if not member.get("is_active", True):
            # 非アクティブなメンバーはスキップ
            continue

        name_en = member["name_en"]
        emoji = member["emoji_unicode"]
        branch = member["branch"]
        name_ja = member["name_ja"]

        name_to_emoji[name_en] = emoji
        name_to_branch[name_en] = branch
        name_to_name_ja[name_en] = name_ja

    return name_to_emoji, name_to_branch, name_to_name_ja

# マッピングデータの生成
MEMBER_NAME_TO_EMOJI, MEMBER_NAME_TO_BRANCH, MEMBER_NAME_TO_NAME_JA = generate_mappings()

# Holodex APIのパラメータ
MAX_UPCOMING_HOURS: int = 48  # upcoming配信の取得範囲（時間）
MAX_DISPLAY_UPCOMING: int = 10  # 各ブランチで表示するupcoming配信の最大数
MAX_CHANNEL_NAME_EMOJIS: int = 5  # チャンネル名に表示する絵文字の最大数

# チェック間隔（秒）
CHECK_INTERVAL_SECONDS: int = 300  # 5分

def get_emoji_for_member(channel_name: str) -> Optional[str]:
    """
    チャンネル名からメンバーの絵文字を取得

    Args:
        channel_name: Holodex APIから取得したチャンネル名

    Returns:
        絵文字文字列、見つからない場合はNone
    """
    # チャンネル名からメンバー名を推測して絵文字を返す
    for member_name, emoji in MEMBER_NAME_TO_EMOJI.items():
        if member_name in channel_name:
            return emoji
    return None

def get_branch_for_member(channel_name: str) -> Optional[str]:
    """
        チャンネル名からメンバーのブランチを取得

    Args:
        channel_name: Holodex APIから取得したチャンネル名

    Returns:
        ブランチ名（jp/en/id/dev_is）、見つからない場合はNone
    """
    for member_name, branch in MEMBER_NAME_TO_BRANCH.items():
        if member_name in channel_name:
            return branch
    return None
