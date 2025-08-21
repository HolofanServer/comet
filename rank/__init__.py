"""
Rank System Package - Cogs

Discord.py レベリングシステム統合パッケージ
メッセージXP・音声XP・AI設定・カスタム公式・品質分析を含む包括的システム
"""

__version__ = "1.0.0"
__author__ = "HFS Homepage Management Bot"

# パッケージメタデータ
PACKAGE_INFO = {
    "name": "rank_system_cogs", 
    "description": "Discord.py レベリングシステム - コマンド群",
    "version": __version__,
    "components": [
        "rank - メインレベリングシステム",
        "rank_config - AI自然言語設定管理",
        "formula_config - カスタムレベル公式管理",
        "voice_config - 音声XP設定管理", 
        "voice_tracker - 音声状態追跡・統計"
    ]
}
