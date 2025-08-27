# 起動ユーティリティ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットの起動ユーティリティは、ボットの初期化プロセスを支援し、システムの健全性チェック、依存関係の確認、環境設定の検証を行います。安全で確実な起動を保証するための包括的なツールセットを提供します。

## 起動ユーティリティアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                起動ユーティリティアーキテクチャ               │
├─────────────────────────────────────────────────────────────┤
│  初期化管理層 (Initialization Management)                   │
│  ├── 起動シーケンス制御                                      │
│  ├── 依存関係チェック                                        │
│  ├── 環境検証                                                │
│  └── 設定読み込み                                            │
├─────────────────────────────────────────────────────────────┤
│  システムチェック層 (System Check)                          │
│  ├── ハードウェア要件確認                                    │
│  ├── ソフトウェア依存関係                                    │
│  ├── ネットワーク接続性                                      │
│  └── 権限確認                                                │
├─────────────────────────────────────────────────────────────┤
│  データ準備層 (Data Preparation)                            │
│  ├── データベース初期化                                      │
│  ├── キャッシュ準備                                          │
│  ├── ファイルシステム確認                                    │
│  └── バックアップ確認                                        │
├─────────────────────────────────────────────────────────────┤
│  サービス起動層 (Service Startup)                           │
│  ├── コアサービス起動                                        │
│  ├── 外部サービス接続                                        │
│  ├── 監視システム開始                                        │
│  └── 通知システム起動                                        │
└─────────────────────────────────────────────────────────────┘
```

## 起動シーケンス管理

### 1. 起動マネージャー

```python
import asyncio
import sys
import os
import platform
import psutil
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class StartupPhase:
    def __init__(self, name: str, description: str, handler: Callable, required: bool = True):
        self.name = name
        self.description = description
        self.handler = handler
        self.required = required
        self.completed = False
        self.error = None
        self.start_time = None
        self.end_time = None
        self.duration = None

class StartupManager:
    def __init__(self):
        self.phases = []
        self.startup_start_time = None
        self.startup_end_time = None
        self.total_duration = None
        self.failed_phases = []
        self.warnings = []
        
    def add_phase(self, name: str, description: str, handler: Callable, required: bool = True):
        """起動フェーズの追加"""
        phase = StartupPhase(name, description, handler, required)
        self.phases.append(phase)
        logger.debug(f"Added startup phase: {name}")
    
    async def execute_startup(self) -> bool:
        """起動シーケンスの実行"""
        self.startup_start_time = datetime.now()
        logger.info("Starting COMET bot initialization sequence...")
        
        success = True
        
        for i, phase in enumerate(self.phases):
            logger.info(f"Phase {i+1}/{len(self.phases)}: {phase.description}")
            
            phase.start_time = datetime.now()
            
            try:
                result = await phase.handler()
                phase.completed = True
                phase.end_time = datetime.now()
                phase.duration = (phase.end_time - phase.start_time).total_seconds()
                
                if result is False and phase.required:
                    logger.error(f"Required phase '{phase.name}' failed")
                    phase.error = "Phase returned False"
                    self.failed_phases.append(phase)
                    success = False
                    break
                elif result is False:
                    logger.warning(f"Optional phase '{phase.name}' failed")
                    self.warnings.append(f"Optional phase '{phase.name}' failed")
                
                logger.info(f"✅ {phase.name} completed in {phase.duration:.2f}s")
                
            except Exception as e:
                phase.error = str(e)
                phase.end_time = datetime.now()
                phase.duration = (phase.end_time - phase.start_time).total_seconds()
                
                logger.error(f"❌ Phase '{phase.name}' failed: {e}")
                
                if phase.required:
                    self.failed_phases.append(phase)
                    success = False
                    break
                else:
                    self.warnings.append(f"Optional phase '{phase.name}' failed: {e}")
        
        self.startup_end_time = datetime.now()
        self.total_duration = (self.startup_end_time - self.startup_start_time).total_seconds()
        
        if success:
            logger.info(f"🎉 COMET bot initialization completed successfully in {self.total_duration:.2f}s")
        else:
            logger.error(f"💥 COMET bot initialization failed after {self.total_duration:.2f}s")
        
        return success
    
    def get_startup_report(self) -> Dict[str, Any]:
        """起動レポートの生成"""
        completed_phases = [p for p in self.phases if p.completed]
        
        return {
            "success": len(self.failed_phases) == 0,
            "total_duration": self.total_duration,
            "total_phases": len(self.phases),
            "completed_phases": len(completed_phases),
            "failed_phases": len(self.failed_phases),
            "warnings": len(self.warnings),
            "phase_details": [
                {
                    "name": p.name,
                    "description": p.description,
                    "completed": p.completed,
                    "required": p.required,
                    "duration": p.duration,
                    "error": p.error
                }
                for p in self.phases
            ],
            "failed_phase_details": [
                {
                    "name": p.name,
                    "error": p.error,
                    "required": p.required
                }
                for p in self.failed_phases
            ],
            "warnings": self.warnings,
            "start_time": self.startup_start_time,
            "end_time": self.startup_end_time
        }
```

### 2. システム要件チェック

```python
class SystemRequirementsChecker:
    def __init__(self):
        self.requirements = {
            "python_version": (3, 8),
            "memory_mb": 512,
            "disk_space_mb": 1024,
            "required_packages": [
                "discord.py", "aiohttp", "asyncio", "logging"
            ]
        }
    
    async def check_python_version(self) -> bool:
        """Python バージョンの確認"""
        current_version = sys.version_info[:2]
        required_version = self.requirements["python_version"]
        
        if current_version >= required_version:
            logger.info(f"✅ Python version: {'.'.join(map(str, current_version))}")
            return True
        else:
            logger.error(f"❌ Python version {'.'.join(map(str, required_version))} or higher required, got {'.'.join(map(str, current_version))}")
            return False
    
    async def check_system_resources(self) -> bool:
        """システムリソースの確認"""
        try:
            memory = psutil.virtual_memory()
            available_mb = memory.available / 1024 / 1024
            required_mb = self.requirements["memory_mb"]
            
            if available_mb < required_mb:
                logger.error(f"❌ Insufficient memory: {available_mb:.0f}MB available, {required_mb}MB required")
                return False
            
            logger.info(f"✅ Memory: {available_mb:.0f}MB available")
            
            disk = psutil.disk_usage('.')
            available_disk_mb = disk.free / 1024 / 1024
            required_disk_mb = self.requirements["disk_space_mb"]
            
            if available_disk_mb < required_disk_mb:
                logger.error(f"❌ Insufficient disk space: {available_disk_mb:.0f}MB available, {required_disk_mb}MB required")
                return False
            
            logger.info(f"✅ Disk space: {available_disk_mb:.0f}MB available")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to check system resources: {e}")
            return False
    
    async def check_required_packages(self) -> bool:
        """必須パッケージの確認"""
        missing_packages = []
        
        for package in self.requirements["required_packages"]:
            try:
                __import__(package.replace("-", "_"))
                logger.debug(f"✅ Package found: {package}")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"❌ Missing package: {package}")
        
        if missing_packages:
            logger.error(f"❌ Missing required packages: {', '.join(missing_packages)}")
            return False
        
        logger.info("✅ All required packages are available")
        return True
```

### 3. 環境設定検証

```python
class EnvironmentValidator:
    def __init__(self):
        self.required_env_vars = [
            "BOT_TOKEN",
            "ADMIN_MAIN_GUILD_ID",
            "ADMIN_DEV_GUILD_ID"
        ]
        self.optional_env_vars = [
            "OPENAI_API_KEY",
            "UPTIME_KUMA_URL",
            "WEBHOOK_URL"
        ]
    
    async def validate_environment_variables(self) -> bool:
        """環境変数の検証"""
        missing_required = []
        missing_optional = []
        
        for var in self.required_env_vars:
            value = os.getenv(var)
            if not value:
                missing_required.append(var)
            else:
                if not self._validate_env_var_value(var, value):
                    missing_required.append(f"{var} (invalid format)")
                else:
                    logger.debug(f"✅ Environment variable: {var}")
        
        for var in self.optional_env_vars:
            value = os.getenv(var)
            if not value:
                missing_optional.append(var)
            else:
                logger.debug(f"✅ Optional environment variable: {var}")
        
        if missing_required:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_required)}")
            return False
        
        if missing_optional:
            logger.warning(f"⚠️ Missing optional environment variables: {', '.join(missing_optional)}")
        
        logger.info("✅ Environment variables validation passed")
        return True
    
    def _validate_env_var_value(self, var_name: str, value: str) -> bool:
        """環境変数値の検証"""
        if var_name == "BOT_TOKEN":
            return len(value) > 50 and "." in value
        elif var_name.endswith("_GUILD_ID") or var_name.endswith("_CHANNEL_ID"):
            try:
                int(value)
                return len(value) >= 17
            except ValueError:
                return False
        elif var_name.endswith("_URL"):
            return value.startswith(("http://", "https://"))
        
        return True
```

---

## 関連ドキュメント

- [アプリケーション起動フロー](../01-architecture/02-application-startup-flow.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [データベース管理](01-database-management.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
