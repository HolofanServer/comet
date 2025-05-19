import discord
from discord.ext import commands
import json
import os
import aiohttp
import traceback
from typing import Dict, Optional
from datetime import datetime
import pytz
from discord.ext import tasks

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging()
settings = get_settings()


class StaffManager(commands.Cog):
    """スタッフページのデータを管理するCog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config_path = 'config/members.json'  # 一時的なローカルキャッシュとして使用
        
        # 設定ファイルからの値が期待と異なるため、直接URLを指定
        self.api_endpoint = "https://test.local.hfs.jp/api"
        self.api_token = settings.staff_api_key  # APIの認証キー
        self.last_update = None
        self.members_cache = {"staff": [], "specialThanks": []}
        
        # デバッグ情報
        # logger.info(f"スタッフマネージャー初期化: APIエンドポイント = {self.api_endpoint}")
        # logger.info(f"設定から読み込まれたAPIエンドポイント = {settings.homepage_api_url} (この値は不正確なため使用しません)")
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Cogが読み込まれたときの処理"""
        logger.info('スタッフ管理Cogが読み込まれました')
        # 起動時に一度データをロード
        await self.load_members_data()
        
        # 自動更新タスクがまだ実行されていない場合は開始
        if not self.auto_update_staff.is_running():
            self.auto_update_staff.start()
            # logger.info('スタッフ情報の自動更新タスクを開始しました')
    
    def cog_unload(self):
        """Cogがアンロードされるときの処理"""
        if self.auto_update_staff.is_running():
            self.auto_update_staff.cancel()
            # logger.info('スタッフ情報の自動更新タスクを停止しました')
    
    @tasks.loop(hours=3)
    async def auto_update_staff(self):
        """3時間ごとにスタッフ情報を自動更新する"""
        try:
            # logger.info('スタッフ情報の自動更新を開始します')
            await self.update_staff_data()
            # logger.info('スタッフ情報の自動更新が完了しました')
        except Exception:
            # logger.error(f'スタッフ情報の自動更新中にエラーが発生しました: {e}')
            logger.error(traceback.format_exc())
    
    @auto_update_staff.before_loop
    async def before_auto_update(self):
        """BOTが準備完了するまで待機"""
        await self.bot.wait_until_ready()
        
    async def load_members_data(self):
        """ウェブサイトまたはローカルからメンバーデータをロード"""
        try:
            # まずAPIからデータを取得を試みる
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'{self.api_endpoint}/members', headers=self._get_auth_headers()) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.members_cache = data
                            self.last_update = datetime.now(pytz.timezone('Asia/Tokyo'))
                            # logger.info('APIからメンバーデータを読み込みました')
                            return data
            except Exception as e:
                logger.error(f'APIからのデータ取得に失敗しました: {e}')

            # APIからの取得に失敗した場合はローカルファイルから読み込む
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.members_cache = data
                    # logger.info('ローカルからメンバーデータを読み込みました')
                    return data
            
            logger.warning('メンバーデータが見つかりませんでした。空のデータを使用します。')
            return {"staff": [], "specialThanks": []}
            
        except Exception as e:
            logger.error(f'メンバーデータの読み込み中にエラーが発生しました: {e}')
            return {"staff": [], "specialThanks": []}
    
    def _get_auth_headers(self):
        """API認証ヘッダーを生成"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
    async def update_staff_data(self) -> bool:
        """サーバーのロール情報を取得し、スタッフデータを更新する"""
        try:
            guild = self.bot.guilds[0]  # BOTが参加している最初のサーバー、必要に応じてIDで指定
            
            # 役職の優先順位
            role_priority = {
                "Administrator": 1,
                "Moderator": 2,
                "Staff": 3
            }
            
            # メンバーデータを格納するリスト
            staff_members = []
            special_thanks = []
            
            # サーバー内の全メンバーをチェック
            for member in guild.members:
                if member.bot:  # BOTはスキップ
                    continue
                    
                member_roles = [role.name for role in member.roles]
                
                # 運営ロールを持つメンバーを処理
                staff_role = None
                for role_name, priority in role_priority.items():
                    if role_name in member_roles:
                        staff_role = role_name
                        break  # 最上位のロールを優先
                
                if staff_role:
                    # 既存のメッセージがあれば保持、なければ空文字
                    message = await self.get_member_message(str(member.id)) or ""
                    
                    # ソーシャルリンク情報を取得
                    socials = await self.get_member_socials(str(member.id))
                    
                    # 参加日時の处理
                    if member.joined_at:
                        joined_date = member.joined_at
                    else:
                        # 参加日時が取得できない場合は現在日時を使用
                        joined_date = datetime.now(pytz.timezone('Asia/Tokyo'))
                        logger.warning(f'Member {member.display_name} has no joined_at date, using current time')
                    
                    # 日付フォーマットをISO形式と日本語表記の両方で保存
                    joined_at_iso = joined_date.strftime("%Y-%m-%d")
                    joined_at_jp = joined_date.strftime("%Y年%m月%d日")
                    
                    # ロールの色情報を取得
                    role_color = None
                    for role in member.roles:
                        if role.name == staff_role:
                            # 16進カラーコードに変換
                            role_color = f'#{role.color.value:06x}'
                            break
                    
                    # メンバー情報を作成
                    member_data = {
                        "id": str(member.id),
                        "name": member.display_name,
                        "role": staff_role,
                        "avatar": str(member.display_avatar.url),
                        "message": message,
                        "joinedAt": joined_at_iso,
                        "joinedAtJp": joined_at_jp,
                        "roleColor": role_color,
                        "socials": socials
                    }
                    staff_members.append(member_data)
                
                # スペシャルサンクスロールを持つメンバーを处理
                for role in member.roles:
                    if role.name.startswith("常連"):
                        # 既存のメッセージがあれば保持、なければ空文字
                        message = await self.get_member_message(str(member.id)) or ""
                        
                        # ソーシャルリンク情報を取得
                        socials = await self.get_member_socials(str(member.id))
                        
                        # 参加日時の处理
                        if member.joined_at:
                            joined_date = member.joined_at
                        else:
                            # 参加日時が取得できない場合は現在日時を使用
                            joined_date = datetime.now(pytz.timezone('Asia/Tokyo'))
                            logger.warning(f'Member {member.display_name} has no joined_at date, using current time')
                        
                        # 日付フォーマットをISO形式と日本語表記の両方で保存
                        joined_at_iso = joined_date.strftime("%Y-%m-%d")
                        joined_at_jp = joined_date.strftime("%Y年%m月%d日")
                        
                        # ロールの色情報を取得 - 16進カラーコードに変換
                        role_color = f'#{role.color.value:06x}'
                        
                        # メンバー情報を作成
                        member_data = {
                            "id": str(member.id),
                            "name": member.display_name,
                            "role": role.name,  # プレフィックスを削除
                            "avatar": str(member.display_avatar.url),
                            "message": message,
                            "joinedAt": joined_at_iso,
                            "joinedAtJp": joined_at_jp,
                            "roleColor": role_color,
                            "socials": socials
                        }
                        special_thanks.append(member_data)
                        break  # 複数の[常連]ロールがある場合は最初の1つだけを使用
            
            # テスターメンバーを追加
            tester_members = []
            tester_ids = [
                1355706337480278207,
                1203337222514941954,
                1346651342306938932,
                1331949252867264516,
                1176273035230187523,
                1071729729620688976
            ]
            for member_id in tester_ids:
                member = guild.get_member(member_id)
                if member:
                    # メンバーが見つかった場合のみ追加
                    # ディスプレイネームを使用
                    
                    # 実際のサーバー参加日時を取得
                    if member.joined_at:
                        joined_date = member.joined_at.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Tokyo'))
                    else:
                        # サーバー参加日時が取得できない場合は現在時間を使用
                        joined_date = datetime.now(pytz.timezone('Asia/Tokyo'))
                        logger.warning(f'Member {member.display_name} has no joined_at date, using current time')
                    
                    joined_at_iso = joined_date.strftime("%Y-%m-%d")
                    joined_at_jp = joined_date.strftime("%Y年%m月%d日")
                    
                    # 白色のカラーコード
                    role_color = "#ffffff"
                    
                    tester_data = {
                        "id": str(member.id),
                        "name": member.display_name,
                        "role": "テスター",  # ハードコードで「テスター」設定
                        "avatar": str(member.display_avatar.url),
                        "message": "",  # 空のメッセージ
                        "joinedAt": joined_at_iso,
                        "joinedAtJp": joined_at_jp,
                        "roleColor": role_color,
                        "socials": {}
                    }
                    tester_members.append(tester_data)
            
            # logger.info(f'スタッフメンバー数: {len(staff_members)}, 常連メンバー数: {len(special_thanks)}, テスター数: {len(tester_members)}')
            
            # APIに送信するデータを準備
            data = {
                "staff": staff_members,
                "specialThanks": special_thanks,
                "testers": tester_members  # テスターメンバーを追加
            }
            
            # 一時的にローカルにも保存
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # キャッシュを更新
            self.members_cache = data
            self.last_update = datetime.now(pytz.timezone('Asia/Tokyo'))
            
            # APIエンドポイントにデータを送信
            success = await self.send_data_to_api(data)
            return success
                
        except Exception as e:
            logger.error(f'スタッフデータの更新中にエラーが発生しました: {e}')
            logger.error(traceback.format_exc())
            return False
    
    async def send_data_to_api(self, data):
        """データをウェブサイトのAPIに送信"""
        try:
            # APIエンドポイントのURLを構築
            # 終端の / を取り除き、正しいパスを組み立てる
            base_url = self.api_endpoint.rstrip('/')
            api_url = f"{base_url}/members/update"
            
            # # デバッグ情報の詳細出力
            # logger.info(f'現在のself.api_endpoint値: {self.api_endpoint}')
            # logger.info(f'設定されたAPI URL: {settings.homepage_api_url}')
            # logger.info(f'構築されたAPIエンドポイント: {api_url}')
            # logger.info(f'APIエンドポイントにデータを送信: {api_url}')
            
            # # 送信内容の詳細ログ
            # logger.info('送信データ詳細:')
            # logger.info(f'- スタッフ数: {len(data["staff"])}')
            # logger.info(f'- スペシャルサンクス数: {len(data["specialThanks"])}')
            # logger.info(f'- テスター数: {len(data.get("testers", []))}')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url, 
                    headers=self._get_auth_headers(),
                    json=data
                ) as response:
                    if response.status in [200, 201, 204]:
                        # logger.info(f'APIにデータを送信しました: ステータス {response.status}')
                        return True
                    else:
                        logger.error(f'APIへのデータ送信に失敗しました: ステータス {response.status}')
                        logger.error(await response.text())
                        return False
        except Exception as e:
            logger.error(f'APIへのデータ送信中にエラーが発生しました: {e}')
            return False
    
    async def get_member_message(self, member_id: str) -> Optional[str]:
        """メンバーの一言メッセージを取得する"""
        try:
            # キャッシュから検索
            for member_list in [self.members_cache.get("staff", []), self.members_cache.get("specialThanks", []), self.members_cache.get("testers", [])]:
                for member in member_list:
                    if member.get("id") == member_id:
                        return member.get("message", "")
            
            return None
        except Exception as e:
            logger.error(f'メンバーメッセージの取得中にエラーが発生しました: {e}')
            return None
    
    async def get_member_socials(self, member_id: str) -> Dict[str, str]:
        """メンバーのソーシャルリンク情報を取得する"""
        try:
            # キャッシュから検索
            for member_list in [self.members_cache.get("staff", []), self.members_cache.get("specialThanks", []), self.members_cache.get("testers", [])]:
                for member in member_list:
                    if member.get("id") == member_id:
                        return member.get("socials", {})
            
            return {}
        except Exception as e:
            logger.error(f'メンバーソーシャル情報の取得中にエラーが発生しました: {e}')
            return {}
    
    @commands.command(name="update_staff")
    @commands.has_permissions(administrator=True)
    async def update_staff_command(self, ctx):
        """スタッフ情報を更新するコマンド（管理者のみ使用可能）"""
        await ctx.send("スタッフ情報の更新を開始します...")
        
        async with ctx.typing():
            success = await self.update_staff_data()
        
        if success:
            await ctx.send(f"✅ スタッフ情報の更新が完了しました！({len(self.members_cache['staff'])}名のスタッフと{len(self.members_cache['specialThanks'])}名のスペシャルサンクスと{len(self.members_cache['testers'])}名のテスターを更新)")
        else:
            await ctx.send("❌ スタッフ情報の更新中にエラーが発生しました。詳細はログを確認してください。")
    
    @commands.hybrid_command(name="ひとこと")
    async def set_message_command(self, ctx, *, message: str = None):
        """自分の一言メッセージを設定するコマンド"""
        try:
            if not message:
                await ctx.send("📝 使用方法: `hfs-hp/ひとこと [あなたの一言メッセージ]`")
                return
                
            # メッセージが長すぎないか確認
            if len(message) > 100:
                await ctx.send("❌ メッセージは100文字以内にしてください。")
                return
                
            member_id = str(ctx.author.id)
            
            # 一度現在のデータをロード
            await self.load_members_data()
            updated = False
            
            # スタッフとスペシャルサンクスの両方をチェック
            new_data = self.members_cache.copy()
            
            for category in ["staff", "specialThanks", "testers"]:
                for i, member in enumerate(new_data.get(category, [])):
                    if member.get("id") == member_id:
                        new_data[category][i]["message"] = message
                        updated = True
            
            if not updated:
                await ctx.send("❌ あなたはスタッフまたはスペシャルサンクスのリストに登録されていないため、メッセージを設定できません。")
                return
                
            # データを保存
            success = await self.send_data_to_api(new_data)
            
            if success:
                # キャッシュを更新
                self.members_cache = new_data
                await ctx.send(f"✅ あなたの一言メッセージを設定しました: 「{message}」")
            else:
                await ctx.send("❌ メッセージの設定中にエラーが発生しました。あとでもう一度お試しください。")
            
        except Exception as e:
            logger.error(f'メッセージ設定中にエラーが発生しました: {e}')
            await ctx.send("❌ メッセージの設定中にエラーが発生しました。")

    @commands.hybrid_command(name="ひとことリセット")
    async def clear_message_command(self, ctx):
        """自分の一言メッセージをリセットするコマンド"""
        try:
            member_id = str(ctx.author.id)
            
            # 一度現在のデータをロード
            await self.load_members_data()
            updated = False
            
            # スタッフとスペシャルサンクスの両方をチェック
            new_data = self.members_cache.copy()
            
            for category in ["staff", "specialThanks", "testers"]:
                for i, member in enumerate(new_data.get(category, [])):
                    if member.get("id") == member_id:
                        new_data[category][i]["message"] = ""
                        updated = True
            
            if not updated:
                await ctx.send("❌ あなたはスタッフまたはスペシャルサンクスのリストに登録されていないため、メッセージをリセットできません。")
                return
                
            # データを保存
            success = await self.send_data_to_api(new_data)
            
            if success:
                # キャッシュを更新
                self.members_cache = new_data
                await ctx.send("✅ あなたの一言メッセージをリセットしました。")
            else:
                await ctx.send("❌ メッセージのリセット中にエラーが発生しました。あとでもう一度お試しください。")
            
        except Exception as e:
            logger.error(f'メッセージリセット中にエラーが発生しました: {e}')
            await ctx.send("❌ メッセージのリセット中にエラーが発生しました。")

    @commands.command(name="staff_status")
    @commands.has_permissions(administrator=True)
    async def staff_status_command(self, ctx):
        """スタッフ情報の現在の状態を表示するコマンド（管理者のみ使用可能）"""
        embed = discord.Embed(
            title="スタッフ情報ステータス",
            color=discord.Color.blue()
        )
        
        staff_count = len(self.members_cache.get("staff", []))
        special_thanks_count = len(self.members_cache.get("specialThanks", []))
        
        embed.add_field(name="スタッフ数", value=f"{staff_count}名", inline=True)
        embed.add_field(name="スペシャルサンクス数", value=f"{special_thanks_count}名", inline=True)
        
        if self.last_update:
            last_update_str = self.last_update.strftime("%Y年%m月%d日 %H:%M:%S")
            embed.add_field(name="最終更新日時", value=last_update_str, inline=False)
        else:
            embed.add_field(name="最終更新日時", value="未更新", inline=False)
            
        embed.add_field(name="API接続状態", value=f"🔗 {self.api_endpoint}", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffManager(bot))
