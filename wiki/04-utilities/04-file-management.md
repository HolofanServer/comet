# ファイル管理

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

C.O.M.E.T.ボットのファイル管理システムについて説明します。画像処理、ファイルアップロード、ダウンロード、ストレージ管理などの機能について詳しく解説します。

## ファイル処理システム

### 基本ファイル操作

```python
import aiofiles
import aiohttp
import os
from pathlib import Path
from typing import Optional, BinaryIO
import hashlib

class FileManager:
    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.max_file_size = 50 * 1024 * 1024  # 50MB
    
    async def save_file(self, file_data: bytes, filename: str, subfolder: str = "") -> str:
        """ファイル保存"""
        if len(file_data) > self.max_file_size:
            raise FileTooLargeError(f"ファイルサイズが制限を超えています: {len(file_data)} bytes")
        
        # サブフォルダ作成
        save_dir = self.storage_path / subfolder
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイルパス生成
        file_path = save_dir / filename
        
        # ファイル保存
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        return str(file_path)
    
    async def load_file(self, file_path: str) -> bytes:
        """ファイル読み込み"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()
    
    def get_file_hash(self, file_data: bytes) -> str:
        """ファイルハッシュ生成"""
        return hashlib.sha256(file_data).hexdigest()
```

### Discord添付ファイル処理

```python
import discord
from io import BytesIO

class DiscordFileHandler:
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov'}
    
    async def download_attachment(self, attachment: discord.Attachment) -> bytes:
        """Discord添付ファイルダウンロード"""
        if attachment.size > self.file_manager.max_file_size:
            raise FileTooLargeError(f"ファイルサイズが制限を超えています: {attachment.size} bytes")
        
        # ファイル拡張子チェック
        file_ext = Path(attachment.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise UnsupportedFileTypeError(f"サポートされていないファイル形式: {file_ext}")
        
        # ファイルダウンロード
        file_data = await attachment.read()
        return file_data
    
    async def save_attachment(self, attachment: discord.Attachment, subfolder: str = "attachments") -> str:
        """Discord添付ファイル保存"""
        file_data = await self.download_attachment(attachment)
        
        # ファイル名生成（重複回避）
        file_hash = self.file_manager.get_file_hash(file_data)
        file_ext = Path(attachment.filename).suffix
        filename = f"{file_hash}{file_ext}"
        
        return await self.file_manager.save_file(file_data, filename, subfolder)
    
    async def create_discord_file(self, file_path: str, filename: str = None) -> discord.File:
        """Discordファイルオブジェクト作成"""
        file_data = await self.file_manager.load_file(file_path)
        
        if filename is None:
            filename = Path(file_path).name
        
        return discord.File(BytesIO(file_data), filename=filename)
```

## 画像処理

### 画像変換・リサイズ

```python
from PIL import Image, ImageOps
import io

class ImageProcessor:
    def __init__(self):
        self.max_width = 1920
        self.max_height = 1080
        self.quality = 85
    
    async def process_image(self, image_data: bytes, format: str = "JPEG") -> bytes:
        """画像処理"""
        try:
            # 画像読み込み
            image = Image.open(io.BytesIO(image_data))
            
            # RGBA -> RGB変換（JPEG用）
            if format.upper() == "JPEG" and image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                image = background
            
            # リサイズ
            image = self.resize_image(image)
            
            # 出力
            output = io.BytesIO()
            image.save(output, format=format, quality=self.quality, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise ImageProcessingError(f"画像処理エラー: {e}")
    
    def resize_image(self, image: Image.Image) -> Image.Image:
        """画像リサイズ"""
        width, height = image.size
        
        # 最大サイズチェック
        if width <= self.max_width and height <= self.max_height:
            return image
        
        # アスペクト比を保持してリサイズ
        ratio = min(self.max_width / width, self.max_height / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    async def create_thumbnail(self, image_data: bytes, size: tuple = (256, 256)) -> bytes:
        """サムネイル作成"""
        try:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail(size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=self.quality)
            return output.getvalue()
            
        except Exception as e:
            raise ImageProcessingError(f"サムネイル作成エラー: {e}")
```

### 画像メタデータ抽出

```python
from PIL import Image
from PIL.ExifTags import TAGS
import json

class ImageMetadataExtractor:
    def __init__(self):
        pass
    
    def extract_metadata(self, image_data: bytes) -> dict:
        """画像メタデータ抽出"""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            metadata = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'has_transparency': image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            }
            
            # EXIF情報抽出
            exif_data = image.getexif()
            if exif_data:
                exif_dict = {}
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_dict[tag] = str(value)
                metadata['exif'] = exif_dict
            
            return metadata
            
        except Exception as e:
            return {'error': f"メタデータ抽出エラー: {e}"}
```

## ファイルキャッシュシステム

### LRUキャッシュ

```python
from collections import OrderedDict
import time
from typing import Any, Optional

class FileCache:
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.cache = OrderedDict()
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        if key not in self.cache:
            return None
        
        # TTLチェック
        if time.time() - self.timestamps[key] > self.ttl:
            self.remove(key)
            return None
        
        # LRU更新
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: str, value: Any) -> None:
        """キャッシュ保存"""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                # 最も古いアイテムを削除
                oldest_key = next(iter(self.cache))
                self.remove(oldest_key)
            
            self.cache[key] = value
        
        self.timestamps[key] = time.time()
    
    def remove(self, key: str) -> None:
        """キャッシュ削除"""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]
    
    def clear(self) -> None:
        """キャッシュクリア"""
        self.cache.clear()
        self.timestamps.clear()
```

## ファイルセキュリティ

### ファイル検証

```python
import magic
import hashlib
from typing import List

class FileValidator:
    def __init__(self):
        self.allowed_mime_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'video/mp4', 'video/quicktime'
        }
        self.max_file_size = 50 * 1024 * 1024  # 50MB
    
    def validate_file(self, file_data: bytes, filename: str) -> bool:
        """ファイル検証"""
        # サイズチェック
        if len(file_data) > self.max_file_size:
            raise FileTooLargeError("ファイルサイズが制限を超えています")
        
        # MIMEタイプチェック
        mime_type = magic.from_buffer(file_data, mime=True)
        if mime_type not in self.allowed_mime_types:
            raise UnsupportedFileTypeError(f"サポートされていないファイル形式: {mime_type}")
        
        # ファイル名チェック
        if not self.is_safe_filename(filename):
            raise UnsafeFilenameError("安全でないファイル名です")
        
        return True
    
    def is_safe_filename(self, filename: str) -> bool:
        """安全なファイル名チェック"""
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        return not any(char in filename for char in dangerous_chars)
    
    def calculate_checksum(self, file_data: bytes) -> str:
        """チェックサム計算"""
        return hashlib.sha256(file_data).hexdigest()
```

## ストレージ管理

### ディスク使用量監視

```python
import shutil
import os
from pathlib import Path

class StorageManager:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.max_storage_size = 10 * 1024 * 1024 * 1024  # 10GB
    
    def get_storage_usage(self) -> dict:
        """ストレージ使用量取得"""
        total_size = 0
        file_count = 0
        
        for file_path in self.storage_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        free_space = shutil.disk_usage(self.storage_path).free
        
        return {
            'total_size': total_size,
            'file_count': file_count,
            'free_space': free_space,
            'usage_percentage': (total_size / self.max_storage_size) * 100
        }
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """古いファイルクリーンアップ"""
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        deleted_count = 0
        for file_path in self.storage_path.rglob('*'):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1
        
        return deleted_count
```

## エラーハンドリング

### カスタム例外

```python
class FileManagementError(Exception):
    """ファイル管理関連のエラー"""
    pass

class FileTooLargeError(FileManagementError):
    """ファイルサイズ制限エラー"""
    pass

class UnsupportedFileTypeError(FileManagementError):
    """サポートされていないファイル形式エラー"""
    pass

class UnsafeFilenameError(FileManagementError):
    """安全でないファイル名エラー"""
    pass

class ImageProcessingError(FileManagementError):
    """画像処理エラー"""
    pass

class StorageFullError(FileManagementError):
    """ストレージ容量不足エラー"""
    pass
```

## 関連ドキュメント

- [API統合](02-api-integration.md)
- [AI統合](03-ai-integration.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [ツールCogs](../03-cogs/05-tool-cogs.md)
