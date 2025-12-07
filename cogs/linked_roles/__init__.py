"""
MyHFS Linked Roles Cog

Discord Linked Roles APIを使用して、MyHFSカード情報を
Discordプロフィールに表示する機能を提供します。
"""

from cogs.linked_roles.linked_roles import LinkedRolesCog


async def setup(bot) -> None:
    """Cogセットアップ"""
    await bot.add_cog(LinkedRolesCog(bot))
