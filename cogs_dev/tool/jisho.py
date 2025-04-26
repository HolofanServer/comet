import discord
from discord.ext import commands
from discord import ui, app_commands

import os
import sys
from typing import Tuple, List, Optional, Dict
import subprocess
import re
from openai import OpenAI, OpenAIError
import json

from utils.logging import setup_logging
from config.setting import get_settings
from utils.commands_help import is_guild_app, log_commands, is_guild

logger = setup_logging("D")
settings = get_settings()

api_key = settings.etc_api_openai_api_key
client_ai = OpenAI(api_key=api_key)

class SearchTypeView(ui.View):
    def __init__(self, cog: 'JishoCog', query: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.query = query
        self.current_type = "word"
        self.embeds: Dict[str, discord.Embed] = {}
        self.pages: Dict[str, List[discord.Embed]] = {}
        self.current_page = 0
        self.original_interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return False
        return True

    async def update_message(self, interaction: discord.Interaction, search_type: str = None, page: int = None):
        if search_type is not None:
            if search_type not in self.embeds:
                outputs, success = self.cog._run_jisho_cli(search_type, self.query)
                if success and outputs:
                    if search_type == "word":
                        embeds = self.cog._parse_word_result(outputs, self.query)
                        if embeds:
                            self.pages[search_type] = embeds
                            self.embeds[search_type] = embeds[0]
                    elif search_type == "kanji":
                        embed = self.cog._parse_kanji_result(outputs)
                        if embed:
                            self.embeds[search_type] = embed
                    elif search_type == "sentence":
                        embeds = self.cog._parse_sentence_result(outputs)
                        if embeds:
                            self.pages[search_type] = embeds
                            self.embeds[search_type] = embeds[0]

            self.current_type = search_type
            self.current_page = 0

        if page is not None and self.current_type in self.pages:
            self.current_page = page
            self.embeds[self.current_type] = self.pages[self.current_type][page]

        embed = self.embeds.get(self.current_type)
        if embed:
            type_emoji = {"word": "📚", "kanji": "🈁", "sentence": "📝"}[self.current_type]
            embed.title = f"{type_emoji} 「{self.query}」"

            for button in self.children[:3]:
                if isinstance(button, ui.Button) and hasattr(button, 'custom_id'):
                    button.style = (
                        discord.ButtonStyle.success
                        if button.custom_id == self.current_type
                        else discord.ButtonStyle.blurple
                    )

            has_pages = self.current_type in self.pages and len(self.pages[self.current_type]) > 1
            if has_pages:
                for button in self.children[3:]:
                    if button.emoji.name == "◀️":
                        button.disabled = self.current_page == 0
                    elif button.emoji.name == "▶️":
                        button.disabled = self.current_page >= len(self.pages[self.current_type]) - 1
            else:
                for button in self.children[3:]:
                    button.disabled = True

            if self.current_type in self.pages:
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages[self.current_type])}")

            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                f"⚠️ 「{self.query}」の{self.current_type}検索結果が見つかりませんでした。",
                ephemeral=True
            )

    @ui.button(label="辞", emoji="📚", style=discord.ButtonStyle.success, custom_id="word", row=0)
    async def word_search(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_message(interaction, "word")

    @ui.button(label="漢", emoji="🈁", style=discord.ButtonStyle.blurple, custom_id="kanji", row=0)
    async def kanji_search(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_message(interaction, "kanji")

    @ui.button(label="例", emoji="📝", style=discord.ButtonStyle.blurple, custom_id="sentence", row=0)
    async def sentence_search(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_message(interaction, "sentence")

    @ui.button(emoji="◀️", style=discord.ButtonStyle.blurple, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            await self.update_message(interaction, page=self.current_page - 1)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.blurple, row=1)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_type in self.pages and self.current_page < len(self.pages[self.current_type]) - 1:
            await self.update_message(interaction, page=self.current_page + 1)

class JishoPages(ui.View):
    def __init__(self, embeds: List[discord.Embed], query: str, cog: 'JishoCog'):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.query = query
        self.cog = cog
        self.current_page = 0
        self.max_page = len(embeds)
        self.original_interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("このボタンは使用できません。", ephemeral=True)
            return False
        return True

    async def update_message(self, interaction: discord.Interaction):
        embed = self.embeds[self.current_page]
        embed.title = f"📚 「{self.query}」"
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_page}")

        for button in self.children[3:]:
            if button.emoji.name == "◀️":
                button.disabled = self.current_page == 0
            elif button.emoji.name == "▶️":
                button.disabled = self.current_page >= self.max_page - 1

        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="辞", emoji="📚", style=discord.ButtonStyle.success, custom_id="word", row=0)
    async def word_search(self, interaction: discord.Interaction, button: ui.Button):
        view = SearchTypeView(self.cog, self.query)
        view.original_interaction = self.original_interaction
        await view.update_message(interaction, "word")

    @ui.button(label="漢", emoji="🈁", style=discord.ButtonStyle.blurple, custom_id="kanji", row=0)
    async def kanji_search(self, interaction: discord.Interaction, button: ui.Button):
        view = SearchTypeView(self.cog, self.query)
        view.original_interaction = self.original_interaction
        await view.update_message(interaction, "kanji")

    @ui.button(label="例", emoji="📝", style=discord.ButtonStyle.blurple, custom_id="sentence", row=0)
    async def sentence_search(self, interaction: discord.Interaction, button: ui.Button):
        view = SearchTypeView(self.cog, self.query)
        view.original_interaction = self.original_interaction
        await view.update_message(interaction, "sentence")

    @ui.button(emoji="◀️", style=discord.ButtonStyle.blurple, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.blurple, row=1)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await self.update_message(interaction)

class JishoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _run_jisho_cli(self, command: str, query: str) -> Tuple[List[str], bool]:
        """CLIコマンドを実行して結果を取得"""
        try:
            jisho_dir = os.path.expanduser("~/.jisho/data")
            for subdir in ["word", "kanji", "sentence"]:
                dir_path = os.path.join(jisho_dir, subdir)
                os.makedirs(dir_path, exist_ok=True)
            
            venv_bin = os.path.dirname(sys.executable)
            jisho_path = os.path.join(venv_bin, 'jisho')
            logger.info(f"Using jisho path: {jisho_path}")
            
            cmd = [jisho_path, 'search', command, query]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Command output: {result.stdout if result.stdout else 'No output'}")
            if result.stderr:
                logger.error(f"Command stderr: {result.stderr}")
            outputs = [line for line in result.stdout.split('\n') if line.strip()]
            return outputs, True
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with error: {str(e)}")
            logger.error(f"Command stderr: {e.stderr}")
            return [], False
        except Exception as e:
            logger.error(f"Unexpected error in _run_jisho_cli: {str(e)}")
            return [], False

    def _parse_word_result(self, outputs: List[str], search_query: str = None) -> List[discord.Embed]:
        """単語検索結果をEmbedのリストに整形"""
        if not outputs:
            return []

        embeds = []
        current_word = None
        current_reading = None
        current_info = []
        current_definitions = []
        exact_match_embed = None
        raw_line = None
        
        for line in outputs:
            if line.startswith('─'):
                if current_word:
                    embed = discord.Embed(
                        title=f"📚 「{current_word}」",
                        color=0x3b82f6
                    )
                    
                    if raw_line:
                        embed.description = f"**{raw_line}**"

                    if current_info:
                        embed.add_field(
                            name="ℹ️ 情報",
                            value=', '.join(current_info),
                            inline=False
                        )

                    if current_definitions:
                        definitions_text = '\n'.join(f"・{d}" for d in current_definitions)
                        embed.add_field(
                            name="📝 意味",
                            value=definitions_text,
                            inline=False
                        )

                    if search_query and (
                        re.search(f"^{re.escape(search_query)}$", current_word, re.IGNORECASE) or
                        (current_reading and re.search(f"^{re.escape(search_query)}$", current_reading, re.IGNORECASE))
                    ):
                        exact_match_embed = embed
                    else:
                        embeds.append(embed)

                current_word = None
                current_reading = None
                current_info = []
                current_definitions = []
                raw_line = None
                continue

            if not line.strip():
                continue

            if not current_word:
                raw_line = line.strip()
                parts = line.strip().split(' ', 1)
                current_word = parts[0]
                if len(parts) > 1:
                    reading_match = re.match(r'\((.*?)\)', parts[1])
                    if reading_match:
                        current_reading = reading_match.group(1)
            elif line.strip().startswith('['):
                info = line.strip('[]').split(', ')
                current_info.extend(info)
            else:
                definition = re.sub(r'^\d+\.\s*', '', line.strip())
                if definition:
                    current_definitions.append(definition)

        if current_word:
            embed = discord.Embed(
                title=f"📚 「{current_word}」",
                color=0x3b82f6
            )
            
            if raw_line:
                embed.description = f"**{raw_line}**"

            if current_info:
                embed.add_field(
                    name="ℹ️ 情報",
                    value=', '.join(current_info),
                    inline=False
                )

            if current_definitions:
                definitions_text = '\n'.join(f"・{d}" for d in current_definitions)
                embed.add_field(
                    name="📝 意味",
                    value=definitions_text,
                    inline=False
                )
            embeds.append(embed)

        if exact_match_embed:
            embeds.insert(0, exact_match_embed)

        return embeds

    def _create_word_embed(self, word: str, readings: List[str], info: List[str], definitions: List[str]) -> discord.Embed:
        """単語のEmbedを作成"""
        embed = discord.Embed(
            title=f"📚 「{word}」",
            color=0x3b82f6
        )
        
        if readings:
            readings_text = ' | '.join(f"**{r}**" for r in readings)
            if all(char in 'ぁ-んー' or char in 'ァ-ンー' for char in word):
                try:
                    kanji = self._get_kanji_for_kana(word)
                    if kanji:
                        readings_text = f"**{kanji}** | {readings_text}"
                except Exception as e:
                    logger.error(f"Error getting kanji: {e}")
            embed.description = readings_text

        if info:
            embed.add_field(
                name="ℹ️ 情報",
                value=', '.join(info),
                inline=False
            )

        if definitions:
            definitions_text = '\n'.join(f"・{d}" for d in definitions)
            embed.add_field(
                name="📝 意味",
                value=definitions_text,
                inline=False
            )

        return embed

    def _parse_kanji_result(self, outputs: List[str]) -> Optional[discord.Embed]:
        """漢字検索結果をEmbedに整形"""
        if not outputs:
            return None

        first_line = outputs[0]
        kanji = first_line.split(' [', 1)[0].strip()
        
        info = {
            'grade': None,
            'jlpt': None,
            'strokes': None,
            'kunyomi': [],
            'onyomi': [],
            'radical': None,
            'radical_forms': [],
            'parts': None,
            'examples': {'kun': [], 'on': []}
        }
        
        current_section = None
        
        for line in outputs:
            try:
                line = line.strip()
                
                if 'Kun:' in line and 'On:' in line:
                    kun_part = line[line.find('Kun:')+4:line.find(']')]
                    if kun_part and kun_part != 'None':
                        info['kunyomi'] = [k.strip() for k in kun_part.split(',')]
                    on_start = line.find('On:') + 3
                    on_end = line.find(']', on_start)
                    if on_start > 3 and on_end > on_start:
                        on_part = line[on_start:on_end]
                        if on_part and on_part != 'None':
                            info['onyomi'] = [o.strip() for o in on_part.split(',')]
                
                elif line.startswith('['):
                    if 'Strokes:' in line:
                        strokes = line[line.find('Strokes:')+8:line.find(']')].strip()
                        if strokes != 'None':
                            info['strokes'] = strokes
                    elif 'JLPT:' in line:
                        jlpt = line[line.find('JLPT:')+5:line.find(']')].strip()
                        if jlpt != 'None':
                            info['jlpt'] = f"N{jlpt}"
                    elif 'Grade:' in line:
                        grade = line[line.find('Grade:')+6:line.find(']')].strip()
                        if grade != 'None':
                            info['grade'] = f"小学{grade}年生"
                
                elif line.startswith('[Base:'):
                    radical = line[line.find('-')+1:line.find(']')].strip()
                    if ' - ' in radical:
                        radical = radical.split(' - ')[0].strip()
                    info['radical'] = radical
                elif line.startswith('[Alternate Radical:'):
                    forms = line[line.find(':')+1:line.find(']')].strip()
                    if forms != 'None':
                        info['radical_forms'] = [f.strip() for f in forms.split(',')]
                elif line.startswith('[Parts:'):
                    parts = line[line.find(':')+1:line.find(']')].strip()
                    if parts != 'None':
                        info['parts'] = parts
                
                elif line == 'On Examples:':
                    current_section = 'on'
                elif line == 'Kun Examples:':
                    current_section = 'kun'
                elif line.startswith('•') and current_section:
                    parts = line[1:].strip().split(' [', 1)
                    if len(parts) == 2:
                        word = parts[0].strip()
                        rest = parts[1].split(']', 1)
                        if len(rest) > 0:
                            reading = rest[0].strip()
                            meaning = rest[1].strip() if len(rest) > 1 else None
                            info['examples'][current_section].append({
                                'word': word,
                                'reading': reading,
                                'meaning': meaning
                            })
            
            except Exception as e:
                print(f"Error parsing line: {line}")
                print(f"Error: {str(e)}")
                continue

        embed = discord.Embed(
            title=f"🈁 「{kanji}」",
            color=0x3b82f6
        )

        readings = []
        if info['kunyomi']:
            readings.append(f"**訓読み**：{', '.join(info['kunyomi'])}")
        if info['onyomi']:
            readings.append(f"**音読み**：{', '.join(info['onyomi'])}")
        if readings:
            embed.description = '\n'.join(readings)

        status = []
        if info['strokes']:
            status.append(f"画数：{info['strokes']}")
        if info['grade']:
            status.append(info['grade'])
        if info['jlpt']:
            status.append(info['jlpt'])
        if status:
            embed.add_field(
                name="ℹ️ 基本情報",
                value='\n'.join(status),
                inline=False
            )

        radical_info = []
        if info['radical']:
            radical_info.append(f"部首：{info['radical']}")
        if info['radical_forms']:
            radical_info.append(f"異体：{', '.join(info['radical_forms'])}")
        if info['parts']:
            radical_info.append(f"構成：{info['parts']}")
        if radical_info:
            embed.add_field(
                name="🔍 字形",
                value='\n'.join(radical_info),
                inline=False
            )

        if info['examples']['kun']:
            examples = []
            for ex in info['examples']['kun'][:3]:
                example = f"• {ex['word']} [{ex['reading']}]"
                if ex['meaning']:
                    example += f"\n  ↳ {ex['meaning']}"
                examples.append(example)
            embed.add_field(
                name="🔡 訓読み例",
                value='\n'.join(examples),
                inline=False
            )

        if info['examples']['on']:
            examples = []
            for ex in info['examples']['on'][:3]:
                example = f"• {ex['word']} [{ex['reading']}]"
                if ex['meaning']:
                    example += f"\n  ↳ {ex['meaning']}"
                examples.append(example)
            embed.add_field(
                name="🔠 音読み例",
                value='\n'.join(examples),
                inline=False
            )

        return embed

    def _parse_sentence_result(self, outputs: List[str]) -> List[discord.Embed]:
        """例文検索結果をEmbedのリストに整形"""
        embeds = []
        current_sentences = []
        

        current_set = {
            'japanese': None,
            'reading': None,
            'english': None
        }
        
        for line in outputs:
            if line.startswith('─'):
                if all(current_set.values()):
                    current_sentences.append(current_set)
                    current_set = {
                        'japanese': None,
                        'reading': None,
                        'english': None
                    }
            elif not line.startswith('['):
                if current_set['japanese'] is None:
                    current_set['japanese'] = line
                elif current_set['reading'] is None:
                    current_set['reading'] = line
                elif current_set['english'] is None:
                    current_set['english'] = line
                    current_sentences.append(current_set)
                    current_set = {
                        'japanese': None,
                        'reading': None,
                        'english': None
                    }

        if all(current_set.values()):
            current_sentences.append(current_set)

        for i in range(0, len(current_sentences), 4):
            embed = discord.Embed(
                title="📝 例文",
                color=0x3b82f6
            )

            for j, sentence in enumerate(current_sentences[i:i+4], 1):
                embed.add_field(
                    name=f"例文 {j}",
                    value=f"**{sentence['japanese']}**\n{sentence['reading']}\n{sentence['english']}",
                    inline=False
                )

            embeds.append(embed)

        for i, embed in enumerate(embeds, 1):
            embed.set_footer(text=f"Page {i} of {len(embeds)}")

        return embeds

    # @app_commands.command(name="jisho", description="日本語の単語を検索します。漢字・ひらがな・カタカナ・英語で検索できます。")
    # @is_guild_app()
    # @log_commands()
    # @app_commands.describe(query="日本語の単語を入力してください。")
    # async def jisho(self, interaction: discord.Interaction, query: str):
    #     try:
    #         await interaction.response.defer(ephemeral=True)

    #         word_outputs, word_success = self._run_jisho_cli('word', query)
    #         if word_success and word_outputs:
    #             embeds = self._parse_word_result(word_outputs, query)
    #             if embeds:
    #                 if len(embeds) > 1:
    #                     view = JishoPages(embeds, query, self)
    #                     view.original_interaction = interaction
    #                     first_embed = embeds[0]
    #                     first_embed.title = f"📚 「{query}」"
    #                     first_embed.set_footer(text=f"Page 1/{len(embeds)}")
    #                     await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
    #                 else:
    #                     view = SearchTypeView(self, query)
    #                     view.original_interaction = interaction
    #                     embeds[0].title = f"📚 「{query}」"
    #                     view.embeds["word"] = embeds[0]
    #                     await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
    #                 return

    #         kanji_outputs, kanji_success = self._run_jisho_cli('kanji', query)
    #         if kanji_success and kanji_outputs:
    #             embed = self._parse_kanji_result(kanji_outputs)
    #             if embed:
    #                 view = SearchTypeView(self, query)
    #                 view.original_interaction = interaction
    #                 embed.title = f"🈁 「{query}」"
    #                 view.embeds["kanji"] = embed
    #                 await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    #                 return

    #         sentence_outputs, sentence_success = self._run_jisho_cli('sentence', query)
    #         if sentence_success and sentence_outputs:
    #             embeds = self._parse_sentence_result(sentence_outputs)
    #             if embeds:
    #                 view = JishoPages(embeds, query, self)
    #                 view.original_interaction = interaction
    #                 first_embed = embeds[0]
    #                 first_embed.title = f"📝 「{query}」"
    #                 first_embed.set_footer(text=f"Page 1/{len(embeds)}")
    #                 await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
    #                 return

    #         await interaction.followup.send(f"⚠️ 申し訳ありません。「{query}」の検索結果が見つかりませんでした。", ephemeral=True)

    #     except Exception as e:
    #         await interaction.followup.send(f"⚠️ エラーが発生しました: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="jisho", description="日本語の単語を検索します。")
    @is_guild()
    @log_commands()
    async def jisho_ai(self, ctx: commands.Context, *, query: str):
        try:
            await ctx.defer(ephemeral=True)
            
            response = client_ai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """
                        あなたは日本語辞書として機能する専門家です。
                        入力された単語に対して以下の情報を提供してください。
                        特に漢字が含まれる場合は、その漢字に関する詳細な情報も提供してください。
                        英語の場合は逆に日本語での意味を同じように提供してください。

                        基本情報：
                        1. 読み方：漢字の場合は読み方（ひらがな）を提供
                        2. 品詞：名詞、動詞、形容詞など
                        3. 意味：日本語での意味や用法を箇条書きで説明
                        4. 英訳：英語での意味を箇条書きで提供
                        5. 例文：その単語を使用した例文を2つ提供（日本語と英訳）
                        6. JLPT レベル（わかる場合）

                        漢字情報（漢字を含む場合）：
                        1. 学年：小学校で習う学年（該当する場合）
                        2. 音読み：音読みのリスト
                        3. 訓読み：訓読みのリスト
                        4. 部首：漢字の部首
                        5. 画数：漢字の画数
                        6. 使用例：その漢字を使用する一般的な単語2-3例

                        以下の形式でJSON形式で返してください：
                        {
                            "word": "入力された単語",
                            "reading": "読み方（ひらがなのみ）",
                            "pos": "品詞",
                            "meanings_jp": ["意味1", "意味2", ...],
                            "meanings_en": ["meaning1", "meaning2", ...],
                            "examples": [
                                {"jp": "例文1", "en": "Example 1"},
                                {"jp": "例文2", "en": "Example 2"}
                            ],
                            "jlpt": "N1-N5 or null",
                            "kanji_info": {
                                "grade": "学年 or null",
                                "onyomi": ["音読み1", "音読み2", ...],
                                "kunyomi": ["訓読み1", "訓読み2", ...],
                                "radical": "部首",
                                "stroke_count": 画数,
                                "common_words": ["例1", "例2", "例3"]
                            }
                        }
                        """},
                    {"role": "user", "content": query}
                ]
            )
            
            result = response.choices[0].message.content
            logger.debug(f"OpenAI response: {result}")
            
            data = json.loads(result)
            
            embed = discord.Embed(
                title=f"📚 「{data['word']}」",
                description=f"**{data['word']} ({data['reading']})**",
                color=0x3b82f6
            )
            
            embed.add_field(
                name="📝 品詞",
                value=data['pos'],
                inline=False
            )
            
            if data['meanings_jp']:
                meanings_text = '\n'.join(f"・{m}" for m in data['meanings_jp'])
                embed.add_field(
                    name="🇯🇵 意味",
                    value=meanings_text,
                    inline=False
                )
            
            if data['meanings_en']:
                meanings_text = '\n'.join(f"・{m}" for m in data['meanings_en'])
                embed.add_field(
                    name="🇬🇧 English",
                    value=meanings_text,
                    inline=False
                )

            if 'kanji_info' in data and any(data['kanji_info'].values()):
                kanji_info = []
                if data['kanji_info'].get('grade'):
                    kanji_info.append(f"学年：{data['kanji_info']['grade']}")
                if data['kanji_info'].get('onyomi'):
                    kanji_info.append(f"音読み：{', '.join(data['kanji_info']['onyomi'])}")
                if data['kanji_info'].get('kunyomi'):
                    kanji_info.append(f"訓読み：{', '.join(data['kanji_info']['kunyomi'])}")
                if data['kanji_info'].get('radical'):
                    kanji_info.append(f"部首：{data['kanji_info']['radical']}")
                if data['kanji_info'].get('stroke_count'):
                    kanji_info.append(f"画数：{data['kanji_info']['stroke_count']}")
                if data['kanji_info'].get('common_words'):
                    kanji_info.append(f"使用例：{', '.join(data['kanji_info']['common_words'])}")
                
                if kanji_info:
                    embed.add_field(
                        name="漢字情報",
                        value='\n'.join(kanji_info),
                        inline=False
                    )
            
            if data['examples']:
                examples_text = []
                for i, example in enumerate(data['examples'], 1):
                    examples_text.append(f"{i}. {example['jp']}")
                    examples_text.append(f"   {example['en']}")
                embed.add_field(
                    name="💭 例文",
                    value='\n'.join(examples_text),
                    inline=False
                )
            
            if data.get('jlpt'):
                embed.add_field(
                    name="📊 JLPT",
                    value=data['jlpt'],
                    inline=True
                )

            await ctx.send(embed=embed, ephemeral=True)
            
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            await ctx.send("⚠️ AI処理中にエラーが発生しました。しばらく待ってから再度お試しください。", ephemeral=True)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            await ctx.send("⚠️ AI応答の解析に失敗しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error in jisho_ai: {str(e)}")
            await ctx.send(f"⚠️ エラーが発生しました: {str(e)}", ephemeral=True)
            
async def setup(bot):
    await bot.add_cog(JishoCog(bot))
