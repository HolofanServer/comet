#!/usr/bin/env python3
"""
RSSフィードの構造詳細調査用スクリプト
"""

import feedparser
import sys
import os
import pprint

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.setting import get_settings

settings = get_settings()

def debug_rss_structure():
    """RSSフィードの詳細構造を調査"""
    print("=== RSSフィードの構造調査 ===")
    
    try:
        feed = feedparser.parse(settings.note_rss_url)
        
        if feed.entries:
            entry = feed.entries[0]  # 最初のエントリを詳しく調査
            
            print("=== エントリの全属性 ===")
            for attr in dir(entry):
                if not attr.startswith('_'):
                    try:
                        value = getattr(entry, attr)
                        print(f"{attr}: {type(value)} = {repr(value)}")
                    except:
                        print(f"{attr}: (取得エラー)")
            
            print("\n=== media_thumbnail詳細 ===")
            if hasattr(entry, 'media_thumbnail'):
                print(f"Type: {type(entry.media_thumbnail)}")
                print(f"Value: {repr(entry.media_thumbnail)}")
                if isinstance(entry.media_thumbnail, list):
                    for i, item in enumerate(entry.media_thumbnail):
                        print(f"  Item {i}: {type(item)} = {repr(item)}")
                        if hasattr(item, '__dict__'):
                            print(f"    Attributes: {item.__dict__}")
            
            print("\n=== tags詳細 ===")
            if hasattr(entry, 'tags'):
                print(f"Tags type: {type(entry.tags)}")
                print(f"Tags length: {len(entry.tags) if hasattr(entry.tags, '__len__') else 'N/A'}")
                for i, tag in enumerate(entry.tags):
                    print(f"  Tag {i}: {type(tag)} = {repr(tag)}")
                    if hasattr(tag, '__dict__'):
                        print(f"    Attributes: {tag.__dict__}")
            
            print("\n=== enclosures詳細 ===")
            if hasattr(entry, 'enclosures'):
                print(f"Enclosures type: {type(entry.enclosures)}")
                print(f"Enclosures length: {len(entry.enclosures) if hasattr(entry.enclosures, '__len__') else 'N/A'}")
                for i, enc in enumerate(entry.enclosures):
                    print(f"  Enclosure {i}: {type(enc)} = {repr(enc)}")
                    if hasattr(enc, '__dict__'):
                        print(f"    Attributes: {enc.__dict__}")

            print("\n=== 特殊な属性詳細 ===")
            special_attrs = ['media_thumbnail', 'media_content', 'links', 'summary_detail']
            for attr in special_attrs:
                if hasattr(entry, attr):
                    value = getattr(entry, attr)
                    print(f"{attr}: {type(value)}")
                    if isinstance(value, (list, tuple)):
                        for i, item in enumerate(value):
                            print(f"  [{i}]: {type(item)} = {repr(item)}")
                    elif hasattr(value, '__dict__'):
                        print(f"  Attributes: {value.__dict__}")
                    else:
                        print(f"  Value: {repr(value)}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_rss_structure()
