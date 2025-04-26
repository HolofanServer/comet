import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import random
import json
import os
from typing import Dict, List, Optional, Union
import asyncio

class TARIFF(commands.Cog):
    """
    関税を課して外国産パッケージからアメリカのコードを守る素晴らしいCog！
    輸入を再び偉大にする！ #MIPA (Make Importing Python Again)
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tariffs: Dict[str, int] = {}
        self.import_stats: Dict[str, Dict[str, Union[int, float]]] = {}
        self.tariff_file = 'data/tariffs.json'
        self.countries = ["中国", "メキシコ", "カナダ", "日本", "ドイツ", "韓国", "イギリス", "フランス", "イタリア", "インド"]
        self.package_origins: Dict[str, str] = {}
        self.load_tariffs()
        self.auto_tariff_change.start()
        
        # オリジナルのimport関数を保存
        self.__original_import = __builtins__['__import__']
        # 関税付きimport関数で置き換え
        __builtins__['__import__'] = self.tariffed_import
        
    def cog_unload(self):
        # Cogがアンロードされたときに元のimport関数を復元
        __builtins__['__import__'] = self.__original_import
        self.auto_tariff_change.cancel()
        self.save_tariffs()

    def tariffed_import(self, name, *args, **kwargs):
        """関税を課した輸入を行う偉大な関数！"""
        start_time = time.time()
        
        # 本来のインポートを実行
        module = self.__original_import(name, *args, **kwargs)
        
        original_time = (time.time() - start_time) * 1000000  # マイクロ秒に変換
        
        # パッケージに関税があるか確認
        if name in self.tariffs:
            tariff_rate = self.tariffs[name]
            
            # 関税に基づいて遅延を追加
            delay = original_time * (tariff_rate / 100)
            time.sleep(delay / 1000000)  # マイクロ秒をsleepの秒に変換
            
            # 統計を更新
            if name not in self.import_stats:
                # パッケージの「出身国」をランダムに割り当て
                self.package_origins[name] = random.choice(self.countries)
                self.import_stats[name] = {
                    "count": 0,
                    "total_time": 0,
                    "total_tariff_time": 0
                }
            
            self.import_stats[name]["count"] += 1
            self.import_stats[name]["total_time"] += original_time
            self.import_stats[name]["total_tariff_time"] += delay
            
            # 関税メッセージをコンソールに出力（デバッグ用）
            print(f"🔥 {self.package_origins[name]}産の{name}に{tariff_rate}%の関税を課しました！元の輸入時間：{original_time:.0f}μs、現在：{original_time + delay:.0f}μs。アメリカ製パッケージが再び勝利！ #MIPA")
        
        return module

    def load_tariffs(self):
        """保存された関税設定を読み込む"""
        os.makedirs('data', exist_ok=True)
        if os.path.exists(self.tariff_file):
            try:
                with open(self.tariff_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tariffs = data.get('tariffs', {})
                    self.package_origins = data.get('origins', {})
                    self.import_stats = data.get('stats', {})
            except Exception as e:
                print(f"関税データの読み込みに失敗しました: {e}")

    def save_tariffs(self):
        """関税設定を保存する"""
        os.makedirs('data', exist_ok=True)
        try:
            with open(self.tariff_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'tariffs': self.tariffs,
                    'origins': self.package_origins,
                    'stats': self.import_stats
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"関税データの保存に失敗しました: {e}")

    @tasks.loop(hours=24)
    async def auto_tariff_change(self):
        """毎日ランダムに関税率を変更する"""
        if not self.tariffs:
            return
        
        # ランダムなパッケージを選択
        package = random.choice(list(self.tariffs.keys()))
        old_rate = self.tariffs[package]
        
        # ランダムな調整（上下50%まで）
        adjustment = random.randint(-50, 50)
        new_rate = max(1, old_rate + adjustment)
        self.tariffs[package] = new_rate
        
        # 調整理由をランダムに選択
        reasons = [
            f"{self.package_origins[package]}との貿易戦争が激化したため",
            f"{self.package_origins[package]}が不公正な取引を行ったため",
            f"アメリカの偉大なパッケージ産業を守るため",
            f"{package}の輸入が急増したため",
            f"アメリカのプログラマーの雇用を守るため",
            f"国家安全保障上の理由から"
        ]
        reason = random.choice(reasons)
        
        # お知らせを送信するチャンネルがあれば送信
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="bot-log")
            if channel:
                if adjustment > 0:
                    message = f"📢 **速報**：{self.package_origins[package]}産の{package}に対する関税を**{old_rate}%から{new_rate}%に引き上げ**ました！理由：{reason} 🔥"
                else:
                    message = f"📢 **通知**：{self.package_origins[package]}産の{package}に対する関税を**{old_rate}%から{new_rate}%に引き下げ**ました。理由：貿易関係の改善により 🤝"
                
                await channel.send(message)
        
        self.save_tariffs()

    @auto_tariff_change.before_loop
    async def before_auto_tariff_change(self):
        await self.bot.wait_until_ready()

    # コマンドグループを設定
    tariff_group = app_commands.Group(
        name="tariff",
        description="偉大な関税システム！輸入を再び素晴らしくする！ #MIPA",
    )

    @tariff_group.command(name="set", description="パッケージに関税を設定します")
    @app_commands.describe(
        package="関税を課すパッケージの名前",
        rate="関税率（1〜500％）"
    )
    async def set_tariff(self, interaction: discord.Interaction, package: str, rate: int):
        if rate < 1 or rate > 500:
            await interaction.response.send_message("関税率は1%から500%の間で設定してください！", ephemeral=True)
            return
        
        old_rate = self.tariffs.get(package, 0)
        self.tariffs[package] = rate
        
        if package not in self.package_origins:
            self.package_origins[package] = random.choice(self.countries)
        
        self.save_tariffs()
        
        # トランプ風の誇大表現をランダムに選択
        trump_phrases = [
            "これは素晴らしい取引です！",
            "これが最高の関税です！信じてください！",
            "我々は再び勝利します！",
            "アメリカのコードを守るために！",
            "これほど素晴らしい関税は誰も見たことがない！",
            "我々は賢いプログラマーが大好きです！"
        ]
        
        if old_rate == 0:
            message = f"🔥 {self.package_origins[package]}産の「{package}」に**{rate}%の関税**を課しました！ {random.choice(trump_phrases)} #MIPA"
        else:
            message = f"🔥 {self.package_origins[package]}産の「{package}」に対する関税を**{old_rate}%から{rate}%に変更**しました！ {random.choice(trump_phrases)} #MIPA"
        
        await interaction.response.send_message(message)

    @tariff_group.command(name="list", description="現在設定されている関税を表示します")
    async def list_tariffs(self, interaction: discord.Interaction):
        if not self.tariffs:
            await interaction.response.send_message("現在、関税は設定されていません。`/tariff set`で設定しましょう！", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔥 偉大なる関税一覧 🔥",
            description="アメリカのコードを守るために課された現在の関税率",
            color=discord.Color.red()
        )
        
        for package, rate in sorted(self.tariffs.items(), key=lambda x: x[1], reverse=True):
            origin = self.package_origins.get(package, "不明")
            embed.add_field(
                name=f"{package} ({origin}産)",
                value=f"**{rate}%** の関税 {'🔥' * min(5, rate // 100 + 1)}",
                inline=False
            )
        
        embed.set_footer(text="Make Importing Python Again! #MIPA")
        await interaction.response.send_message(embed=embed)

    @tariff_group.command(name="remove", description="パッケージの関税を解除します")
    @app_commands.describe(package="関税を解除するパッケージの名前")
    async def remove_tariff(self, interaction: discord.Interaction, package: str):
        if package not in self.tariffs:
            await interaction.response.send_message(f"「{package}」には関税が設定されていません！", ephemeral=True)
            return
        
        rate = self.tariffs[package]
        origin = self.package_origins.get(package, "不明")
        del self.tariffs[package]
        self.save_tariffs()
        
        # 悲しいメッセージをランダムに選択
        sad_phrases = [
            "これは悲しい日です...",
            "アメリカのコードが危険にさらされています...",
            "ただでさえ大きな貿易赤字がさらに拡大します...",
            "我々は再交渉する必要があります！",
            "これは最悪の取引です。おそらく史上最悪です。"
        ]
        
        message = f"😢 {origin}産の「{package}」に課していた**{rate}%の関税**を解除しました。{random.choice(sad_phrases)} #MIPA"
        await interaction.response.send_message(message)

    @tariff_group.command(name="clear", description="すべての関税を解除します")
    async def clear_tariffs(self, interaction: discord.Interaction):
        if not self.tariffs:
            await interaction.response.send_message("現在、関税は設定されていません。", ephemeral=True)
            return
        
        count = len(self.tariffs)
        self.tariffs.clear()
        self.save_tariffs()
        
        message = f"😱 **緊急事態**：{count}個のパッケージに対する関税をすべて解除しました！これはアメリカのコード産業にとって壊滅的な影響を与えるでしょう！#MIPA"
        await interaction.response.send_message(message)

    @tariff_group.command(name="trade_war", description="貿易戦争を開始し、特定の国のすべてのパッケージに高関税を課します")
    @app_commands.describe(country="貿易戦争を開始する国")
    @app_commands.choices(country=[
        app_commands.Choice(name="中国", value="中国"),
        app_commands.Choice(name="メキシコ", value="メキシコ"),
        app_commands.Choice(name="カナダ", value="カナダ"),
        app_commands.Choice(name="日本", value="日本"),
        app_commands.Choice(name="ドイツ", value="ドイツ"),
        app_commands.Choice(name="韓国", value="韓国"),
        app_commands.Choice(name="イギリス", value="イギリス"),
        app_commands.Choice(name="フランス", value="フランス"),
        app_commands.Choice(name="イタリア", value="イタリア"),
        app_commands.Choice(name="インド", value="インド"),
    ])
    async def trade_war(self, interaction: discord.Interaction, country: str):
        # まず応答を送信
        await interaction.response.defer(thinking=True)
        
        # 関税率を設定
        base_rate = random.randint(200, 300)
        affected_packages = []
        
        # パッケージに原産国を割り当て（まだ割り当てられていない場合）
        for package in list(self.tariffs.keys()):
            if package not in self.package_origins:
                self.package_origins[package] = random.choice(self.countries)
        
        # その国のパッケージすべてに高関税を課す
        for package, origin in list(self.package_origins.items()):
            if origin == country:
                # 少しランダム性を持たせる
                rate = base_rate + random.randint(-20, 20)
                self.tariffs[package] = rate
                affected_packages.append((package, rate))
        
        # 新しいパッケージを追加（ランダムな有名パッケージ）
        popular_packages = [
            "requests", "pandas", "numpy", "tensorflow", "flask", 
            "django", "matplotlib", "scrapy", "sqlalchemy", "pillow"
        ]
        
        for _ in range(3):
            package = random.choice(popular_packages)
            popular_packages.remove(package)
            if package not in self.package_origins:
                self.package_origins[package] = country
                rate = base_rate + random.randint(-20, 20)
                self.tariffs[package] = rate
                affected_packages.append((package, rate))
        
        self.save_tariffs()
        
        # 貿易戦争開始メッセージ
        embed = discord.Embed(
            title=f"🔥🔥🔥 {country}との貿易戦争が開始されました！ 🔥🔥🔥",
            description=f"不公正な取引慣行に対抗するため、{country}からの輸入パッケージに高関税を課しました！",
            color=discord.Color.dark_red()
        )
        
        if affected_packages:
            packages_text = "\n".join([f"**{package}**: {rate}% の関税 {'🔥' * min(5, rate // 100)}" for package, rate in affected_packages])
            embed.add_field(name="影響を受けるパッケージ", value=packages_text, inline=False)
        else:
            embed.add_field(name="影響を受けるパッケージ", value=f"現在{country}産のパッケージはありません。今後追加されるパッケージには高関税が課されます。", inline=False)
        
        quotes = [
            f"{country}は長年にわたって我々を利用してきました。もうこれ以上は許しません！",
            f"{country}との貿易赤字は巨大です。我々は勝利します！",
            f"この動きにより、アメリカのコード産業は再び偉大になります！",
            f"{country}は我々のプログラマーの仕事を奪っています。これを止めなければなりません！",
            f"これまで誰もこのような強力な対応をしなかったのは私には理解できません。しかし、私はしました！"
        ]
        
        embed.set_footer(text=random.choice(quotes) + " #MIPA")
        
        await interaction.followup.send(embed=embed)

    @tariff_group.command(name="stats", description="インポート統計を表示します")
    async def show_stats(self, interaction: discord.Interaction):
        if not self.import_stats:
            await interaction.response.send_message("まだインポート統計データがありません。いくつかのパッケージをインポートしてから再試行してください。", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 インポート統計 📊",
            description="関税がどれだけの収益をもたらしているか",
            color=discord.Color.gold()
        )
        
        total_tariff_time = 0
        
        for package, stats in sorted(self.import_stats.items(), key=lambda x: x[1].get("total_tariff_time", 0), reverse=True):
            count = stats.get("count", 0)
            org_time = stats.get("total_time", 0)
            tariff_time = stats.get("total_tariff_time", 0)
            total_tariff_time += tariff_time
            
            origin = self.package_origins.get(package, "不明")
            rate = self.tariffs.get(package, 0)
            
            embed.add_field(
                name=f"{package} ({origin}産)",
                value=f"関税率: **{rate}%**\n"
                      f"インポート回数: **{count}回**\n"
                      f"遅延時間: **{tariff_time/1000:.2f}ms**\n"
                      f"徴収効率: **{tariff_time/org_time*100:.1f}%**",
                inline=True
            )
        
        embed.add_field(
            name="🏦 総徴収時間 🏦",
            value=f"**{total_tariff_time/1000:.2f}ms**の遅延が追加されました！\nこれはアメリカのコード産業を守るための偉大な投資です！",
            inline=False
        )
        
        embed.set_footer(text="Make Importing Python Again! #MIPA")
        await interaction.response.send_message(embed=embed)

    @tariff_group.command(name="random", description="ランダムなパッケージに関税を課します")
    async def random_tariff(self, interaction: discord.Interaction):
        # 人気のあるPythonパッケージリスト
        popular_packages = [
            "requests", "pandas", "numpy", "tensorflow", "flask", 
            "django", "matplotlib", "scrapy", "sqlalchemy", "pillow",
            "beautifulsoup4", "pytorch", "opencv", "scikit-learn", "pygame",
            "fastapi", "pydantic", "aiohttp", "asyncio", "pytest"
        ]
        
        # すでに関税がかかっているパッケージを除外
        available_packages = [pkg for pkg in popular_packages if pkg not in self.tariffs]
        
        if not available_packages:
            await interaction.response.send_message("すべての主要パッケージにすでに関税がかかっています！これは偉大な経済政策です！", ephemeral=True)
            return
        
        # ランダムに3つのパッケージを選択
        selected_packages = random.sample(available_packages, min(3, len(available_packages)))
        added_tariffs = []
        
        for package in selected_packages:
            rate = random.randint(50, 300)
            origin = random.choice(self.countries)
            
            self.tariffs[package] = rate
            self.package_origins[package] = origin
            added_tariffs.append((package, origin, rate))
        
        self.save_tariffs()
        
        # 結果を表示
        embed = discord.Embed(
            title="🎲 ランダム関税イニシアチブ 🎲",
            description="新たなパッケージに関税を課して輸入を偉大にします！",
            color=discord.Color.blue()
        )
        
        for package, origin, rate in added_tariffs:
            embed.add_field(
                name=f"{package} ({origin}産)",
                value=f"**{rate}%**の新関税を課しました！{'🔥' * min(5, rate // 100)}",
                inline=False
            )
        
        quotes = [
            "ランダムな関税が最高の関税です！信じてください！",
            "これが私の天才的な経済戦略です！",
            "誰も予測できない関税が一番効果的です！",
            "我々は再び勝利します！",
            "これがアメリカン・コード・ファースト政策です！"
        ]
        
        embed.set_footer(text=random.choice(quotes) + " #MIPA")
        await interaction.response.send_message(embed=embed)

    @tariff_group.command(name="simulate_impact", description="関税の経済的影響をシミュレーションします")
    async def simulate_impact(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        if not self.tariffs:
            await interaction.followup.send("関税が設定されていないため、シミュレーションを実行できません！")
            return
        
        # 架空の経済指標を計算
        total_rate = sum(self.tariffs.values())
        avg_rate = total_rate / len(self.tariffs) if self.tariffs else 0
        
        # ランダムな経済影響を生成
        code_quality = min(100, max(0, random.normalvariate(50, 15) + avg_rate / 10))
        american_jobs = min(100, max(0, random.normalvariate(50, 15) + avg_rate / 5))
        innovation = min(100, max(0, random.normalvariate(50, 15) - avg_rate / 20))
        code_cost = min(100, max(0, random.normalvariate(50, 15) + avg_rate / 3))
        satisfaction = min(100, max(0, random.normalvariate(50, 15) - avg_rate / 15))
        
        # 結果を表示
        embed = discord.Embed(
            title="📈 関税影響シミュレーション 📈",
            description="現在の関税政策による素晴らしい経済的影響！",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🏭 国内コード生産指数",
            value=self.generate_bar(american_jobs) + f" **{american_jobs:.1f}%** {'📈' if american_jobs > 50 else '📉'}",
            inline=False
        )
        
        embed.add_field(
            name="✨ コード品質指数",
            value=self.generate_bar(code_quality) + f" **{code_quality:.1f}%** {'📈' if code_quality > 50 else '📉'}",
            inline=False
        )
        
        embed.add_field(
            name="💡 イノベーション指数",
            value=self.generate_bar(innovation) + f" **{innovation:.1f}%** {'📈' if innovation > 50 else '📉'}",
            inline=False
        )
        
        embed.add_field(
            name="💰 コードコスト指数",
            value=self.generate_bar(code_cost) + f" **{code_cost:.1f}%** {'📈' if code_cost < 50 else '📉'} (低いほど良い)",
            inline=False
        )
        
        embed.add_field(
            name="😊 プログラマー満足度",
            value=self.generate_bar(satisfaction) + f" **{satisfaction:.1f}%** {'📈' if satisfaction > 50 else '📉'}",
            inline=False
        )
        
        # 総合的な評価メッセージ
        avg_score = (american_jobs + code_quality + innovation + (100 - code_cost) + satisfaction) / 5
        
        if avg_score >= 70:
            conclusion = "素晴らしい結果です！この関税政策はコード経済を大きく改善しています！"
        elif avg_score >= 50:
            conclusion = "良い結果です。関税政策が効果を発揮しています！"
        else:
            conclusion = "結果は期待より低いですが、もっと関税を課せば改善するでしょう！"
        
        embed.add_field(
            name="🏆 総合評価",
            value=conclusion,
            inline=False
        )
        
        embed.set_footer(text=f"平均関税率: {avg_rate:.1f}% | 総関税数: {len(self.tariffs)} | #MIPA")
        await interaction.followup.send(embed=embed)

    def generate_bar(self, value: float) -> str:
        """パーセンテージを示すビジュアルバーを生成"""
        filled = int(value / 10)
        empty = 10 - filled
        return '█' * filled + '░' * empty
        
async def setup(bot: commands.Bot):
    await bot.add_cog(TARIFF(bot))
