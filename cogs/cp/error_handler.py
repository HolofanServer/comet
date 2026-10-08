"""
Checkpoint エラーハンドラー

リトライ・フォールバック・通知を管理
"""
import asyncio
import functools
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from utils.logging import setup_logging

logger = setup_logging(__name__)

T = TypeVar("T")


class CircuitBreaker:
    """サーキットブレーカー パターン"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._failures = 0
        self._last_failure_time: datetime | None = None
        self._state = "closed"  # closed, open, half-open
        self._half_open_successes = 0

    @property
    def is_open(self) -> bool:
        """回路が開いているか"""
        if self._state == "open":
            if self._last_failure_time:
                elapsed = (
                    datetime.now(timezone.utc) - self._last_failure_time
                ).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half-open"
                    self._half_open_successes = 0
                    return False
            return True
        return False

    def record_success(self):
        """成功を記録"""
        if self._state == "half-open":
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_requests:
                self._state = "closed"
                self._failures = 0
                logger.info("🔧 サーキットブレーカー: 回復完了")
        elif self._state == "closed":
            self._failures = 0

    def record_failure(self):
        """失敗を記録"""
        self._failures += 1
        self._last_failure_time = datetime.now(timezone.utc)

        if self._state == "half-open":
            self._state = "open"
            logger.warning("🔧 サーキットブレーカー: 再度オープン")
        elif self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"🔧 サーキットブレーカー: オープン（{self._failures}回失敗）"
            )


class RetryQueue:
    """失敗したログのリトライキュー"""

    def __init__(self, max_size: int = 1000):
        self.queue: deque[dict[str, Any]] = deque(maxlen=max_size)
        self._processing = False

    def add(self, log_type: str, data: dict[str, Any]):
        """リトライ対象を追加"""
        self.queue.append(
            {"type": log_type, "data": data, "attempts": 0, "added_at": datetime.now(timezone.utc)}
        )

    async def process(self, handlers: dict[str, Callable]) -> int:
        """キュー内のログを処理"""
        if self._processing or not self.queue:
            return 0

        self._processing = True
        processed = 0

        try:
            while self.queue:
                item = self.queue.popleft()
                handler = handlers.get(item["type"])

                if not handler:
                    continue

                try:
                    await handler(item["data"])
                    processed += 1
                except Exception as e:
                    item["attempts"] += 1
                    if item["attempts"] < 3:
                        self.queue.append(item)
                    else:
                        logger.error(f"リトライ失敗（3回目）: {item['type']} - {e}")

        finally:
            self._processing = False

        return processed


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """リトライデコレータ"""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff**attempt)
                        logger.warning(
                            f"リトライ {attempt + 1}/{max_attempts}: {func.__name__} "
                            f"（{wait_time:.1f}秒後）"
                        )
                        await asyncio.sleep(wait_time)

            logger.error(f"リトライ上限到達: {func.__name__}")
            raise last_exception

        return wrapper

    return decorator


class CheckpointErrorHandler:
    """Checkpointエラーハンドラー"""

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.retry_queue = RetryQueue()
        self._error_counts: dict[str, int] = {}
        self._last_error_notification: datetime | None = None

    async def handle_db_error(
        self,
        error: Exception,
        operation: str,
        context: dict[str, Any] | None = None,
    ):
        """DBエラーを処理"""
        self.circuit_breaker.record_failure()
        self._error_counts[operation] = self._error_counts.get(operation, 0) + 1

        logger.error(f"DB操作エラー [{operation}]: {error}")

        # リトライキューに追加
        if context:
            self.retry_queue.add(operation, context)

    def record_success(self, operation: str):
        """成功を記録"""
        self.circuit_breaker.record_success()
        self._error_counts[operation] = 0

    def should_skip_operation(self) -> bool:
        """操作をスキップすべきか"""
        return self.circuit_breaker.is_open

    def get_stats(self) -> dict[str, Any]:
        """エラー統計を取得"""
        return {
            "circuit_state": self.circuit_breaker._state,
            "failure_count": self.circuit_breaker._failures,
            "retry_queue_size": len(self.retry_queue.queue),
            "error_counts": self._error_counts.copy(),
        }


# シングルトンインスタンス
error_handler = CheckpointErrorHandler()
