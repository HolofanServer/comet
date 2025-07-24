#!/usr/bin/env python3
"""
RSSフィード取得のデバッグ用スクリプト
"""

import feedparser
import asyncio
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()

async def debug_rss_fetch():
    """RSSフィード取得のデバッグ"""
    print("=== RSSフィード取得デバッグ開始 ===")
    print(f"RSS URL: {settings.note_rss_url}")
    
    try:
        # 同期的に取得
        print("\n1. 同期的な取得テスト:")
        feed = feedparser.parse(settings.note_rss_url)
        print(f"   Status: {getattr(feed, 'status', 'N/A')}")
        print(f"   Bozo: {getattr(feed, 'bozo', 'N/A')}")
        print(f"   Entries count: {len(feed.entries) if hasattr(feed, 'entries') else 'N/A'}")
        
        if hasattr(feed, 'feed'):
            print(f"   Feed title: {getattr(feed.feed, 'title', 'N/A')}")
            print(f"   Feed link: {getattr(feed.feed, 'link', 'N/A')}")
        
        # エントリの詳細
        if hasattr(feed, 'entries') and feed.entries:
            print("\n2. エントリ詳細:")
            for i, entry in enumerate(feed.entries[:3]):
                print(f"   Entry {i+1}:")
                print(f"     Title: {getattr(entry, 'title', 'N/A')}")
                print(f"     Link: {getattr(entry, 'link', 'N/A')}")
                print(f"     Published: {getattr(entry, 'published', 'N/A')}")
        
        # 非同期での取得テスト
        print("\n3. 非同期取得テスト:")
        loop = asyncio.get_event_loop()
        feed_async = await loop.run_in_executor(None, feedparser.parse, settings.note_rss_url)
        print(f"   Status: {getattr(feed_async, 'status', 'N/A')}")
        print(f"   Entries count: {len(feed_async.entries) if hasattr(feed_async, 'entries') else 'N/A'}")
        
        # 現在のチェック条件を確認
        print("\n4. 現在の判定条件:")
        print(f"   feed is None: {feed is None}")
        print(f"   feed is False: {feed is False}")
        print(f"   not feed: {not feed}")
        print(f"   hasattr(feed, 'entries'): {hasattr(feed, 'entries')}")
        print(f"   feed.entries is None: {feed.entries is None if hasattr(feed, 'entries') else 'N/A'}")
        print(f"   not feed.entries: {not feed.entries if hasattr(feed, 'entries') else 'N/A'}")
        
        # エラーがある場合の詳細
        if hasattr(feed, 'bozo') and feed.bozo:
            print("\n5. Bozo エラー詳細:")
            print(f"   Bozo exception: {getattr(feed, 'bozo_exception', 'N/A')}")
        
        return feed
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(debug_rss_fetch())
