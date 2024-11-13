from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """ 全ての設定クラス """
    # Discord Bot の設定
    bot_token: str
    bot_owner_id: int
    bot_help_command_id: str
    bot_service_name: str

    # 管理者用の設定
    admin_main_guild_id: int
    admin_dev_guild_id: int
    admin_error_log_channel_id: int
    admin_startup_channel_id: int
    admin_bug_report_channel_id: int
    admin_help_channel_id: int
    admin_attachment_channel_id: int
    admin_attachment_thread_id: int
    admin_spam_notice_channel_id: int
    admin_commands_log_channel_id: int

    # GitHub に関する設定
    github_pat: str
    github_repo: str
    github_author: str

    # その他の API の設定
    etc_api_openai_api_key: str
    etc_api_realtime_api_key: str

    # UptimeKuma の設定
    uptimekuma_push_url: str
    uptimekuma_status_url: str

    # FastAPI に関する設定
    fastapi_url: str

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """ キャッシュする部分 """
    return Settings()


settings = get_settings()
