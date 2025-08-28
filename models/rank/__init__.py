"""
Rank System Package - Models

Discord.py レベリングシステム データモデルパッケージ
Pydanticモデル・設定構造・データ検証を含む
"""

__version__ = "1.0.0"
__author__ = "HFS Homepage Management Bot"

# パッケージメタデータ
PACKAGE_INFO = {
    "name": "rank_system_models",
    "description": "Discord.py レベリングシステム - データモデル",
    "version": __version__,
    "components": [
        "level_config - AI設定システム用モデル",
        "level_formula - カスタムレベル公式モデル",
        "quality_analysis - AI品質分析用モデル",
        "voice_activity - 音声XP・トラック管理モデル"
    ]
}
