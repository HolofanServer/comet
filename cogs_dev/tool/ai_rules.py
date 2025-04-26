from discord.ext import commands
from openai import OpenAI
from dotenv import load_dotenv

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

load_dotenv()

class AiRulesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = settings.etc_api_openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client_ai = OpenAI(api_key=api_key)

    @commands.hybrid_group(name='ai_rule', with_app_command=True)
    async def ai_rules(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。")

    @ai_rules.command(name='make')
    async def make_ai_rule(self, ctx: commands.Context, *, describe: str):
        """サーバーの雰囲気やルールを入力すると、AIがわかりやすいルールを生成します。
        
        Parameters
        ----------
        describe : str
            サーバーの雰囲気や既存のルールについての説明
        """
        # 処理中のメッセージを送信
        await ctx.defer()
        logger.debug("AI rule making process started.")
        
        try:
            # OpenAIのプロンプト
            prompt = f"""
あなたはDiscordサーバーのルール作成の専門家です。以下の説明に基づいて、サーバールールを作成してください：

サーバーの説明：
{describe}

以下の点に注意してルールを作成してください：
1. 初心者にもわかりやすい、シンプルな言葉で説明
2. 法的に問題のない内容（著作権法、個人情報保護法等に配慮）
3. ポジティブで友好的な表現を使用
4. Discord特有の機能（チャンネル、ロール等）への言及
5. 具体例を含める

フォーマット：
- Discordのマークダウン記法を使用（**太字**、__下線__、> 引用など）
- 箇条書きで整理
- 重要なルールは太字で強調
- 各セクションを明確に分ける

出力形式：
# サーバールール

## 基本ルール
[基本的なルール]

## コミュニケーション
[コミュニケーションに関するルール]

## 禁止事項
[禁止事項のリスト]

## その他
[その他の重要な情報]
"""

            # OpenAI APIを使用してルールを生成
            response = self.client_ai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたはDiscordサーバーのルール作成の専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # 生成されたルールを送信
            response_text = response.choices[0].message.content.strip() if response.choices[0].message.content is not None else ""
            
            logger.debug("AI rule making process completed.")
            
            # ルールが長い場合は分割して送信
            if len(response_text) > 2000:
                parts = [response_text[i:i+1990] for i in range(0, len(response_text), 1990)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await ctx.send(f"生成されたルール (パート {i+1}/{len(parts)}):\n{part}")
                    else:
                        await ctx.send(f"(パート {i+1}/{len(parts)}):\n{part}")
            else:
                await ctx.send(response_text)

        except Exception as e:
            await ctx.send(f"ルールの生成中にエラーが発生しました: {str(e)}")


async def setup(bot):
    await bot.add_cog(AiRulesCog(bot))
