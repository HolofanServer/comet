import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        # Discord Bot
        self.bot_token: str = os.getenv("BOT_TOKEN", "")
        self.bot_owner_id: int = int(os.getenv("BOT_OWNER_ID", "0"))
        self.bot_help_command_id: str = os.getenv("BOT_HELP_COMMAND_ID", "")
        self.bot_service_name: str = os.getenv("BOT_SERVICE_NAME", "")

        # 管理者
        self.admin_main_guild_id: int = int(os.getenv("ADMIN_MAIN_GUILD_ID", "0"))
        self.admin_dev_guild_id: int = int(os.getenv("ADMIN_DEV_GUILD_ID", "0"))
        self.admin_error_log_channel_id: int = int(os.getenv("ADMIN_ERROR_LOG_CHANNEL_ID", "0"))
        self.admin_startup_channel_id: int = int(os.getenv("ADMIN_STARTUP_CHANNEL_ID", "0"))
        self.admin_bug_report_channel_id: int = int(os.getenv("ADMIN_BUG_REPORT_CHANNEL_ID", "0"))
        self.admin_help_channel_id: int = int(os.getenv("ADMIN_HELP_CHANNEL_ID", "0"))
        self.admin_attachment_channel_id: int = int(os.getenv("ADMIN_ATTACHMENT_CHANNEL_ID", "0"))
        self.admin_attachment_thread_id: int = int(os.getenv("ADMIN_ATTACHMENT_THREAD_ID", "0"))
        self.admin_spam_notice_channel_id: int = int(os.getenv("ADMIN_SPAM_NOTICE_CHANNEL_ID", "0"))
        self.admin_commands_log_channel_id: int = int(os.getenv("ADMIN_COMMANDS_LOG_CHANNEL_ID", "0"))
        self.admin_tubuyaki_channel_id: int = int(os.getenv("ADMIN_TUBUYAKI_CHANNEL_ID", "0"))
        self.admin_mod_channel_id: int = int(os.getenv("ADMIN_MOD_CHANNEL_ID", "0"))

        # GitHub
        self.github_pat: str = os.getenv("GITHUB_PAT", "")
        self.github_repo: str = os.getenv("GITHUB_REPO", "")
        self.github_author: str = os.getenv("GITHUB_AUTHOR", "")

        # その他のAPI
        self.etc_api_openai_api_key: str = os.getenv("ETC_API_OPENAI_API_KEY", "")
        self.etc_api_realtime_api_key: str = os.getenv("ETC_API_REALTIME_API_KEY", "")

        # UptimeKuma
        self.uptimekuma_push_url: str = os.getenv("UPTIMEKUMA_PUSH_URL", "")
        self.uptimekuma_status_url: str = os.getenv("UPTIMEKUMA_STATUS_URL", "")

        # FastAPI
        self.fastapi_url: str = os.getenv("FASTAPI_URL", "")

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
