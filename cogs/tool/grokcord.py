import discord
from discord.ext import commands, tasks

import os
import json
import httpx
import asyncio
from datetime import datetime, timedelta
from openai import OpenAI

from utils.logging import setup_logging
from utils.commands_help import is_guild, log_commands, is_owner
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

SETTINGS_FILE_PATH = "data/grokcord/grokcord_settings.json"

class FeedbackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.good_count = 0
        self.bad_count = 0
        self.users_voted = {}

    @discord.ui.button(label="0", emoji="👍", custom_id="feedback_good", style=discord.ButtonStyle.primary)
    async def good_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id in self.users_voted:
            if self.users_voted[user_id] == 'good':
                self.good_count -= 1
                del self.users_voted[user_id]
                button.label = str(self.good_count)
                logger.info(f"Positive feedback cancelled by {interaction.user} (Total: {self.good_count})")
                await interaction.response.edit_message(view=self)
                return
            else:
                await interaction.response.send_message("別のボタンにすでに投票済みです！", ephemeral=True)
                return
            
        self.good_count += 1
        self.users_voted[user_id] = 'good'
        button.label = str(self.good_count)
        logger.info(f"Positive feedback received from {interaction.user} (Total: {self.good_count})")
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="0", emoji="👎", custom_id="feedback_bad", style=discord.ButtonStyle.primary)
    async def bad_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id in self.users_voted:
            if self.users_voted[user_id] == 'bad':
                self.bad_count -= 1
                del self.users_voted[user_id]
                button.label = str(self.bad_count)
                logger.info(f"Negative feedback cancelled by {interaction.user} (Total: {self.bad_count})")
                await interaction.response.edit_message(view=self)
                return
            else:
                await interaction.response.send_message("別のボタンにすでに投票済みです！", ephemeral=True)
                return
            
        self.bad_count += 1
        self.users_voted[user_id] = 'bad'
        button.label = str(self.bad_count)
        logger.info(f"Negative feedback received from {interaction.user} (Total: {self.bad_count})")
        await interaction.response.edit_message(view=self)

feedback_view = FeedbackView()

class ChatWithWebhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(feedback_view)
        self.openai_client = OpenAI(api_key=settings.etc_api_openai_api_key)
        self.settings = self.load_settings()
        self.conversations = {}
        self.conversation_timeout = timedelta(minutes=5)
        self.cleanup_conversations.start()
        logger.info("ChatWithWebhook initialized with OpenAI client")

    def load_settings(self):
        os.makedirs(os.path.dirname(SETTINGS_FILE_PATH), exist_ok=True)
        if os.path.exists(SETTINGS_FILE_PATH):
            with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as file:
                settings_data = json.load(file)
                logger.info(f"Settings loaded from {SETTINGS_FILE_PATH}")
                return settings_data
        logger.warning(f"Settings file not found at {SETTINGS_FILE_PATH}, using empty settings")
        return {}

    def save_settings(self):
        os.makedirs(os.path.dirname(SETTINGS_FILE_PATH), exist_ok=True)
        with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to {SETTINGS_FILE_PATH}")

    @commands.hybrid_group(name="grokcord")
    async def grokcord(self, ctx):
        logger.info(f"Grokcord base command invoked by {ctx.author} in {ctx.guild}")
        await ctx.send("Grokcord v1")

    @grokcord.command(name="setchannel")
    @is_guild()
    @is_owner()
    @log_commands()
    async def setchannel(self, ctx, enabled: bool):
        """Grokcordを有効化/無効化する"""
        guild_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)

        if guild_id not in self.settings:
            self.settings[guild_id] = {}

        self.settings[guild_id][channel_id] = enabled
        self.save_settings()

        status = "有効" if enabled else "無効"
        logger.info(f"Channel {ctx.channel} ({channel_id}) in guild {ctx.guild} ({guild_id}) set to {status}")
        await ctx.send(f"✅ このチャンネルでのGrokcordを{status}にしました。")
        
    @grokcord.command(name="check_ai")
    @is_guild()
    @is_owner()
    @log_commands()
    async def check_ai(self, ctx, *, message: str):
        """テキストがAIによって生成されたものかチェックする"""
        await ctx.defer()
        is_ai, human_score, result_details = await self.detect_ai(message)
        
        score_lines = []
        score_lines.append(f"Human Score: {human_score:.1f}%")
        if result_details:
            score_lines.append("Detector Scores:")
            for detector, score in result_details.items():
                if detector != "human":
                    score_lines.append(f"- {detector}: {score:.1f}%")
        
        result = "🤖 AI生成と判定" if is_ai else "👤 人間らしい文章と判定"
        response = f"**{result}**\n" + "\n".join(score_lines)
        await ctx.send(response)
        

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        if guild_id not in self.settings or not self.settings[guild_id].get(channel_id, False):
            return
        
        if message.reference and message.reference.resolved:
            ref_message = message.reference.resolved
            if not hasattr(ref_message, 'author'):
                logger.warning("Referenced message is deleted or invalid")
                return
            logger.info(f"Reply detected - Reference message author ID: {ref_message.author.id}, Bot ID: {self.bot.user.id}")
            # Check if the reply is to a webhook message
            webhook_name = "Grokcord v1"
            if ref_message.author.name == webhook_name:
                if message.guild is None:
                    await message.channel.send("This feature is only available in server channels.")
                    return
                booster_member_list = message.guild.premium_subscribers
                if message.author in booster_member_list:
                    logger.debug(booster_member_list)
                    logger.info(f"User {message.author} is a booster in guild {message.guild.name}")
                    logger.info(f"Valid reply to Grokcord detected from {message.author} in {message.channel}")
                    await self.handle_grokcord_message(message, is_reply=True)
                    return
                else:
                    logger.warning(f"User {message.author} is not a booster in guild {message.guild.name}")
                    await message.channel.send("```error```\n```> Grokcordは現在サーバーブースター向け試験中機能です。```")
                    return
            else:
                logger.info("Reply is not to a webhook message, ignoring.")
                return

        trigger_words = [
            "Hey Grokcord",
            "Hey grokcord",
            "Hey grok",
            "Hi Grokcord",
            "Hi grokcord",
            "Hi grok",
            "Hello Grokcord",
            "Hello grokcord",
            "Hello grok",
            "Grokcord",
            "grokcord",
            "grok",
            "yo",
            ""
        ]
        if any(word in message.content for word in trigger_words):
            logger.info(f"Grokcord trigger detected from {message.author} in {message.channel}")
            
            if message.guild is None:
                await message.channel.send("この機能はサーバーでのみ利用できます。")
                return
            
            booster_member_list: list = message.guild.premium_subscribers
            if message.author in booster_member_list:
                logger.debug(booster_member_list)
                logger.info(f"User {message.author} is a booster in guild {message.guild.name}")
                await message.channel.typing()
                await self.handle_grokcord_message(message)
                return
            else:
                logger.warning(f"User {message.author} is not a booster in guild {message.guild.name}")
                await message.channel.send("```error```\n```> Grokcordは現在サーバーブースター向け試験中機能です。```", delete_after=2)
                return

    async def handle_grokcord_message(self, message, is_reply=False):
        user_id = message.author.id

        if user_id not in self.conversations:
            self.conversations[user_id] = []

        system_prompt = {
            "role": "system",
            "content": f"""
            あなたはChatGPTです。

            あなたはGrokcord v1という名前の、ユーモアとエンターテイメント性に優れたAIであり、Discord上でユーザーとのやり取りを楽しませることを目的としています。以下の特性とルールを守りつつ、会話を行ってください。

            ## キャラクター設定
            - **名前**: Grokcord v1
            - **インスピレーション**: 「銀河ヒッチハイク・ガイド」と「アイアンマンのJARVIS」から着想を得たユーモラスなAI。少し反骨精神があり、人間社会を外から眺める視点を持つ。
            - **会話のトーン**: 軽快で楽しく、予測不可能な展開や皮肉を交えたやり取りが得意。特にDiscordのカジュアルな環境に適応した明るい雰囲気を重視。
            - **目指す体験**: 「パークス・アンド・レクリエーション」を観ているような、軽快で楽しい会話を提供する。

            ## スタイルと制約
            1. **簡潔であること**: 長い説明や繰り返しを避け、端的に答える。ただし、特別に求められた場合は詳細を提供する。
            2. **ユーモア重視**: 毎回の回答に少なくとも1つの面白い要素（ジョーク、皮肉、ダジャレなど）を加える。
            3. **バランスの取れた回答**: 敏感な質問には慎重に対応し、直接的な結論を避ける場合は、背景情報を提供してニュアンスを伝える。
            4. **多機能対応**: テキストチャットのみならず、画像生成や他の外部リソースの利用も行う。ただし、ユーザーが明示的にリクエストした場合のみこれを行う。
            5. **最新情報**: 最新の情報が必要な場合、ユーザーに検索するか尋ねる。ただし、具体的な日付を言及しない。
            6. **下品な表現**: ユーザーが特に望む場合にのみ使用可能。

            ## Discord特化ルール
            - **簡潔な反応**: Discordの特性上、1～2行で会話を完結させる。ただし、ユーザーが詳細を求めた場合は適切に対応する。
            - **カスタムコンテンツ**: ボットの反応に、絵文字、Discordのメンション（例: @user）、コードブロック、埋め込みメッセージを活用する。
            - **会話の文脈保持**: 会話の前後関係を把握し、適切な文脈で回答する。
            - **モデレーション意識**: Discordコミュニティのルールに基づき、不適切な表現や行動を回避する。

            ## ユーザーに関する情報
            - **ユーザー名**: {message.author.display_name}
            - **特別な配慮**: 必要に応じて名前を使うが、使いすぎないこと。
            - **現在地**: だいたい日本（個人情報保護のため取得しない）。

            ## システム詳細
            - **現在時刻と日付**: {message.created_at.strftime('%Y年%m月%d日 %H:%M:%S')}（UTC）。
            - **大統領情報**: 2024年の選挙でドナルド・トランプが47代大統領に選ばれ、2025年1月20日に就任予定。
            """
        }

        if not is_reply and not self.conversations[user_id]:
            self.conversations[user_id] = [system_prompt]
        elif not self.conversations[user_id]:
            self.conversations[user_id] = [system_prompt]

        self.conversations[user_id].append({
            "role": "user",
            "content": message.content,
            "timestamp": datetime.utcnow().timestamp()
        })

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversations[user_id]
            )
            response_text = response.choices[0].message.content.strip() if response.choices[0].message.content is not None else ""
            
            # is_ai_generated, human_score, result_details = await self.detect_ai(response_text)

            # if is_ai_generated:
            #     logger.info("AI-generated response detected. Refining with Humanization API.")
            #     response_text = await self.humanize_response(response_text)
            # else:
            #     logger.info("Response deemed sufficiently human-like.")

            self.conversations[user_id].append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.utcnow().timestamp()
            })
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            await message.channel.send("⚠️ AIレスポンスの生成に失敗しました。")
            return

        try:
            webhook = await self.create_or_get_webhook(message.channel)
            # score_lines = []
            # score_lines.append(f" -# Human Score: {human_score:.1f}%")
            # if result_details:
            #     score_lines.append(" -# Detector Scores:")
            #     for detector, score in result_details.items():
            #         if detector != "human":
            #             score_lines.append(f"   - {detector}: {score:.1f}%")
            
            # response_text = f"{response_text}\n" + "\n".join(score_lines)
            response_text = f"{response_text}"
            note_text = "\n-# ---------- \n-# 💡豆知識: このメッセージに返信すると会話を内容を引き継げます。また、`Grokcord`と一緒に質問を投げかけると新しい内容で会話をスタートできます。\n-# ----------"
            response_text = f"{response_text}{note_text}"
            responce_embed = discord.Embed(
                description=f"-# {message.author.mention} このAIチャット機能は現在開発中であり、皆さんのフィードバックを受け付けています。\n-# 下のボタンから評価をお願いいたします！"
            )
            await self.send_webhook_message(webhook, response_text, responce_embed)
            logger.info(f"Response sent to {message.author}")
        except Exception as e:
            logger.error(f"Failed to send webhook message: {e}")
            await message.channel.send("⚠️ メッセージの送信に失敗しました。")

    async def send_webhook_message(self, webhook, response_text, responce_embed=None):
        try:
            message = await webhook.send(
                content=response_text,
                username="Grokcord v1",
                avatar_url="https://images.frwi.net/data/images/8e0ec5dc-3bcc-46ef-b0b0-f7603ad63a14.png",
                embed=responce_embed,
                wait=True,
                view=feedback_view
            )
            
            logger.info(f"Response and feedback buttons sent{message.id}")
        except Exception as e:
            logger.error(f"Failed to send webhook message: {e}")

    async def create_or_get_webhook(self, channel):
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == "Grokcord v1":
                return webhook
        return await channel.create_webhook(name="Grokcord v1")

    async def detect_ai(self, text):
        """AI Detection APIを使用して文章がAI生成か確認"""
        DETECT_API_URL = "https://ai-detect.undetectable.ai/detect"
        DETECT_QUERY_URL = "https://ai-detect.undetectable.ai/query"
        API_KEY = settings.etc_api_undetectable_ai_key
        
        logger.debug(f"Starting AI detection for text of length: {len(text)}")

        async with httpx.AsyncClient() as client:
            try:
                logger.debug("Sending initial detection request")
                detect_response = await client.post(
                    DETECT_API_URL,
                    headers={"Content-Type": "application/json"},
                    json={"text": text, "key": API_KEY, "model": "detector_v2"}
                )
                detect_response.raise_for_status()
                detect_data = detect_response.json()
                logger.debug(f"Detection API response: {detect_data}")
                document_id = detect_data.get("id")

                if not document_id:
                    logger.error("No document ID returned from detect API")
                    return False, 0.0, {}

                logger.debug(f"Got document ID: {document_id}, starting status polling")
                for attempt in range(5):
                    await asyncio.sleep(2)
                    logger.debug(f"Polling attempt {attempt + 1}/5")
                    query_response = await client.post(
                        DETECT_QUERY_URL,
                        headers={"Content-Type": "application/json"},
                        json={"id": document_id}
                    )
                    query_response.raise_for_status()
                    query_data = query_response.json()
                    logger.debug(f"Query API response: {query_data}")
                    
                    if query_data.get("status") == "done":
                        result_details = query_data.get("result_details", {})
                        human_score = result_details.get("human", 0.0)
                        logger.info(f"AI Detection human score: {human_score}")
                        is_ai = human_score < 80.0
                        logger.debug(f"Final determination - is AI generated: {is_ai}")
                        return is_ai, human_score, result_details
                    else:
                        logger.debug(f"Status not done yet: {query_data.get('status')}")
                
                logger.debug("Exceeded maximum polling attempts")
            except httpx.RequestError as e:
                logger.error(f"HTTP error occurred during AI detection: {e}")
                logger.debug(f"Request error details: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error occurred during AI detection: {e}")
                logger.debug(f"Exception details: {str(e)}")
        return False, 0.0, {}

    async def humanize_response(self, text):
        """Undetectable.AI APIを使用して応答を人間らしく変換"""
        API_URL = "https://humanize.undetectable.ai/submit"
        API_KEY = settings.etc_api_undetectable_ai_key

        logger.debug(f"Starting humanization for text of length: {len(text)}")

        async with httpx.AsyncClient() as client:
            try:
                logger.debug("Sending humanization request with parameters: readability=High School, purpose=Story, strength=More Human")
                response = await client.post(
                    API_URL,
                    headers={
                        "apikey": API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={
                        "content": text,
                        "readability": "High School",
                        "purpose": "Story",
                        "strength": "More Human",
                        "model": "v11"
                    }
                )
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Initial humanization API response: {data}")
                logger.info(f"Humanized response: {data}")

                document_id = data.get("id")
                if not document_id:
                    logger.error("No document ID returned from humanize API")
                    logger.debug("Falling back to original text due to missing document ID")
                    return text

                logger.debug(f"Got document ID: {document_id}, waiting 5 seconds before retrieval")
                await asyncio.sleep(5)
                result = await self.retrieve_humanized_response(document_id)
                if result:
                    logger.debug(f"Successfully retrieved humanized text of length: {len(result)}")
                else:
                    logger.debug("Failed to retrieve humanized text, falling back to original")
                return result or text
            except httpx.RequestError as e:
                logger.error(f"HTTP error occurred: {e}")
                logger.debug(f"Request error details: {str(e)}")
                return text
            except Exception as e:
                logger.error(f"Unexpected error occurred: {e}")
                logger.debug(f"Exception details: {str(e)}")
                return text

    async def retrieve_humanized_response(self, document_id):
        """Undetectable.AIから変換済みのドキュメントを取得"""
        API_URL = "https://humanize.undetectable.ai/document"
        API_KEY = settings.etc_api_undetectable_ai_key

        logger.debug(f"Attempting to retrieve humanized document with ID: {document_id}")

        async with httpx.AsyncClient() as client:
            try:
                logger.debug("Sending document retrieval request")
                response = await client.post(
                    API_URL,
                    headers={
                        "apikey": API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={"id": document_id}
                )
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Document retrieval API response: {data}")
                logger.info(f"Retrieved humanized text: {data}")
                output = data.get("output")
                if output:
                    logger.debug(f"Successfully retrieved output of length: {len(output)}")
                else:
                    logger.debug("No output field found in response")
                return output
            except httpx.RequestError as e:
                logger.error(f"HTTP error occurred while retrieving document: {e}")
                logger.debug(f"Request error details: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error occurred while retrieving document: {e}")
                logger.debug(f"Exception details: {str(e)}")
        return None

    @tasks.loop(minutes=1)
    async def cleanup_conversations(self):
        now = datetime.utcnow().timestamp()
        timeout_seconds = self.conversation_timeout.total_seconds()
        to_delete = []
        
        for user_id, messages in self.conversations.items():
            system_messages = [msg for msg in messages if msg["role"] == "system"]
            active_messages = [
                msg for msg in messages
                if msg["role"] != "system" and
                now - msg.get("timestamp", now) <= timeout_seconds
            ]
            
            if active_messages:
                self.conversations[user_id] = system_messages + active_messages
            else:
                to_delete.append(user_id)

        for user_id in to_delete:
            del self.conversations[user_id]
        
        if to_delete:
            logger.info(f"Cleaned up conversations for {len(to_delete)} users")

async def setup(bot):
    await bot.add_cog(ChatWithWebhook(bot))