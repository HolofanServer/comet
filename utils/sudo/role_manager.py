import discord

class RoleManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def load_roles(self):
        data = self.config_manager.load()
        return data.get("roles", {})

    def save_roles(self, roles):
        self.config_manager.save({"roles": roles})

    def get_role_by_name(self, guild, role_name):
        return discord.utils.get(guild.roles, name=role_name)

    def get_role_by_id(self, guild, role_id):
        return discord.utils.get(guild.roles, id=role_id)
