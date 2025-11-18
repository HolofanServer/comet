"""
Holodex APIクライアント
配信情報の取得を担当
"""

from typing import Optional

import aiohttp

from utils.logging import setup_logging

from .constants import (
    HOLODEX_API_BASE_URL,
    HOLODEX_API_KEY,
    MAX_UPCOMING_HOURS,
)

logger = setup_logging("D")


class HolodexClient:
    """Holodex APIとの通信を担当するクライアント"""

    def __init__(self, api_key: Optional[str] = None):
        """
        HolodexClientの初期化

        Args:
            api_key: Holodex APIキー（指定しない場合は環境変数から取得）
        """
        self.api_key = api_key or HOLODEX_API_KEY
        self.base_url = HOLODEX_API_BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリー"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのイグジット"""
        if self.session:
            await self.session.close()

    async def ensure_session(self):
        """セッションが存在しない場合は作成"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """セッションをクローズ"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_live_and_upcoming(
        self,
        org: str = "Hololive",
        max_upcoming_hours: int = MAX_UPCOMING_HOURS
    ) -> dict[str, list[dict]]:
        """
        ライブ配信とupcoming配信を取得

        Args:
            org: 組織名（デフォルト: "Hololive"）
            max_upcoming_hours: upcoming配信の取得範囲（時間）

        Returns:
            {"live": [...], "upcoming": [...]} 形式の辞書
        """
        await self.ensure_session()

        url = f"{self.base_url}/live"
        headers = {"X-APIKEY": self.api_key}
        params = {
            "org": org,
            "max_upcoming_hours": max_upcoming_hours,
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # ステータスで分類
                live_streams = []
                upcoming_streams = []

                for stream in data:
                    status = stream.get("status", "")
                    if status == "live":
                        live_streams.append(stream)
                    elif status == "upcoming":
                        upcoming_streams.append(stream)

                logger.info(
                    f"Holodex API: ライブ配信 {len(live_streams)}件、"
                    f"予定配信 {len(upcoming_streams)}件を取得"
                )

                return {
                    "live": live_streams,
                    "upcoming": upcoming_streams
                }

        except aiohttp.ClientError as e:
            logger.error(f"Holodex API通信エラー: {e}")
            return {"live": [], "upcoming": []}
        except Exception as e:
            logger.error(f"予期しないエラー: {e}", exc_info=True)
            return {"live": [], "upcoming": []}

    async def get_live_quick(self, channel_ids: list[str]) -> list[dict]:
        """
        特定チャンネルのライブ配信を高速取得

        Args:
            channel_ids: チャンネルIDのリスト

        Returns:
            ライブ配信情報のリスト
        """
        await self.ensure_session()

        url = f"{self.base_url}/users/live"
        headers = {"X-APIKEY": self.api_key}
        params = {"channels": ",".join(channel_ids)}

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                logger.info(f"Holodex API (quick): {len(data)}件のライブ配信を取得")
                return data

        except aiohttp.ClientError as e:
            logger.error(f"Holodex API通信エラー (quick): {e}")
            return []
        except Exception as e:
            logger.error(f"予期しないエラー (quick): {e}", exc_info=True)
            return []
