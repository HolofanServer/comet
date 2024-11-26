import discord
from discord.ext import commands
from discord import ui, app_commands

import os
from typing import Tuple, List, Optional, Dict
import subprocess

from utils.logging import setup_logging
from utils.commands_help import is_guild_app, log_commands
from utils.startup import get_github_branch

logger = setup_logging("D")

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
                        embeds = self.cog._parse_word_result(outputs)
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
            branch = get_github_branch()
            if branch != "main":
                result = subprocess.run(
                ['/home/freewifi110/iphone3g/iphone3g/bin/jisho', 'search', command, query],
                    capture_output=True,
                    text=True,
                    check=True
                )
            else:
                result = subprocess.run(
                    ['jisho', 'search', command, query],
                    capture_output=True,
                    text=True,
                    check=True
                )
            outputs = [line for line in result.stdout.split('\n') if line.strip()]
            return outputs, True
        except subprocess.CalledProcessError:
            return [], False
        except Exception as e:
            print(f"Error in _run_jisho_cli: {str(e)}")
            return [], False

    def _parse_word_result(self, outputs: List[str]) -> List[discord.Embed]:
        """単語検索結果をEmbedのリストに整形"""
        if not outputs:
            return []

        embeds = []
        current_word = None
        current_readings = []
        current_info = []
        current_definitions = []
        
        for line in outputs:
            if line.startswith('─'):
                if current_word:
                    embed = discord.Embed(
                        title=f"📚 「{current_word}」",
                        color=0x3b82f6
                    )
                    
                    if current_readings:
                        readings_text = ' | '.join(f"**{r}**" for r in current_readings)
                        embed.description = readings_text

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
                
                current_word = None
                current_readings = []
                current_info = []
                current_definitions = []
            elif not line.startswith('['):
                if current_word is None:
                    parts = line.split(' ', 1)
                    current_word = parts[0]
                    if len(parts) > 1:
                        readings = parts[1].strip('()')
                        current_readings = [r.strip() for r in readings.split(',')]
                elif line.strip().startswith('['):
                    info = line.strip('[]').split(', ')
                    current_info.extend(i for i in info if i.startswith(('JLPT', 'Common', 'Wanikani')))
                elif line.strip().startswith(str(len(current_definitions) + 1) + '.'):
                    definition = line.split('.', 1)[1].strip()
                    if ' [' in definition:
                        base_def, info = definition.split(' [', 1)
                        info = info.rstrip(']')
                        if "See also:" in info:
                            info, see_also = info.split("See also:", 1)
                            see_also = see_also.strip()
                            definition = f"{base_def} [{info}]\n↳ 参照: {see_also}"
                        else:
                            definition = f"{base_def} [{info}]"
                    current_definitions.append(definition)

        if current_word:
            embed = discord.Embed(
                title=f"📚 「{current_word}」",
                color=0x3b82f6
            )
            
            if current_readings:
                readings_text = ' | '.join(f"**{r}**" for r in current_readings)
                embed.description = readings_text

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

        for i, embed in enumerate(embeds, 1):
            embed.set_footer(text=f"Page {i} of {len(embeds)}")

        return embeds

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

    @app_commands.command(name="jisho", description="日本語の単語を検索します。漢字・ひらがな・カタカナ・英語で検索できます。")
    @is_guild_app()
    @log_commands()
    @app_commands.describe(query="日本語の単語を入力してください。")
    async def jisho(self, interaction: discord.Interaction, query: str):
        try:
            await interaction.response.defer(ephemeral=True)

            word_outputs, word_success = self._run_jisho_cli('word', query)
            if word_success and word_outputs:
                embeds = self._parse_word_result(word_outputs)
                if embeds:
                    if len(embeds) > 1:
                        view = JishoPages(embeds, query, self)
                        view.original_interaction = interaction
                        first_embed = embeds[0]
                        first_embed.title = f"📚 「{query}」"
                        first_embed.set_footer(text=f"Page 1/{len(embeds)}")
                        await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
                    else:
                        view = SearchTypeView(self, query)
                        view.original_interaction = interaction
                        embeds[0].title = f"📚 「{query}」"
                        view.embeds["word"] = embeds[0]
                        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
                    return

            kanji_outputs, kanji_success = self._run_jisho_cli('kanji', query)
            if kanji_success and kanji_outputs:
                embed = self._parse_kanji_result(kanji_outputs)
                if embed:
                    view = SearchTypeView(self, query)
                    view.original_interaction = interaction
                    embed.title = f"🈁 「{query}」"
                    view.embeds["kanji"] = embed
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                    return

            sentence_outputs, sentence_success = self._run_jisho_cli('sentence', query)
            if sentence_success and sentence_outputs:
                embeds = self._parse_sentence_result(sentence_outputs)
                if embeds:
                    view = JishoPages(embeds, query, self)
                    view.original_interaction = interaction
                    first_embed = embeds[0]
                    first_embed.title = f"📝 「{query}」"
                    first_embed.set_footer(text=f"Page 1/{len(embeds)}")
                    await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
                    return

            await interaction.followup.send(f"⚠️ 申し訳ありません。「{query}」の検索結果が見つかりませんでした。", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"⚠️ エラーが発生しました: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(JishoCog(bot))
