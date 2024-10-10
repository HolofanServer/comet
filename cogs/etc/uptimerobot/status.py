import discord
from discord.ext import commands, tasks

import httpx
import json
import os
import threading
import subprocess
from flask import Flask
import requests
import time

from utils.logging import setup_logging
from utils.commands_help import is_owner, is_guild

logger = setup_logging()

api_key = os.getenv("UPTIMEROBOT_API_KEY")
channel_id = os.getenv("UPTIMEROBOT_CHANNEL_ID")

app = Flask(__name__)

@app.route('/status')
def status():
    return "Bot is running", 200

def run_flask():
    app.run(host='0.0.0.0', port=6767)

def run_ngrok():
    subprocess.Popen(["ngrok", "http", "6767"])

def get_ngrok_url():
    for _ in range(10):
        try:
            response = requests.get("http://localhost:4040/api/tunnels")
            data = response.json()
            return data['tunnels'][0]['public_url']
        except Exception as e:
            time.sleep(2)
    return None

class UptimeRobotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = api_key
        self.monitor_id = None
        self.channel_id = channel_id
        self.monitor_file = "data/uptimerobot/monitor_id.json"
        self.load_monitor_id()

        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

        # ngrokをバックグラウンドで起動
        ngrok_thread = threading.Thread(target=run_ngrok)
        ngrok_thread.daemon = True
        ngrok_thread.start()

        time.sleep(5)
        self.ngrok_url = get_ngrok_url()

        if not self.ngrok_url:
            logger.error("ngrokのURL取得に失敗しました。")
        else:
            logger.info(f"ngrok URL: {self.ngrok_url}")

        self.create_or_get_monitor.start()

    def load_monitor_id(self):
        if not os.path.exists(self.monitor_file):
            os.makedirs(os.path.dirname(self.monitor_file), exist_ok=True)
            return
        with open(self.monitor_file, "r") as f:
            data = json.load(f)
            self.monitor_id = data.get("monitor_id", None)

    def save_monitor_id(self):
        if not os.path.exists(self.monitor_file):
            os.makedirs(os.path.dirname(self.monitor_file), exist_ok=True)
        with open(self.monitor_file, "w") as f:
            json.dump({"monitor_id": self.monitor_id}, f)

    def cog_unload(self):
        self.create_or_get_monitor.cancel()

    async def create_monitor(self):
        url = "https://api.uptimerobot.com/v2/newMonitor"
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "ngrok-skip-browser-warning": "any_value"
        }
        data = {
            "api_key": self.api_key,
            "friendly_name": f"{self.bot.user.name} Status",
            "url": f"{self.ngrok_url}/status",
            "type": 1,
            "interval": 60
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            if response.status_code == 200:
                result = response.json()
                self.monitor_id = result["monitor"]["id"]
                self.save_monitor_id()
                logger.info(f"Monitor created with ID: {self.monitor_id}")
            else:
                logger.error(f"Failed to create monitor: {response.status_code}")

    async def get_monitor(self):
        url = "https://api.uptimerobot.com/v2/getMonitors"
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "ngrok-skip-browser-warning": "any_value"
        }
        data = {"api_key": self.api_key}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            if response.status_code == 200:
                result = response.json()
                if len(result["monitors"]) > 0:
                    self.monitor_id = result["monitors"][0]["id"]
                    self.save_monitor_id()
                    return result["monitors"][0]
            else:
                logger.error(f"Failed to get monitor: {response.status_code}")
                return None

    @tasks.loop(count=1)
    async def create_or_get_monitor(self):
        if not self.monitor_id:
            await self.create_monitor()

    @commands.command(name="check_monitor")
    @is_owner()
    @is_guild()
    async def check_monitor(self, ctx):
        monitor = await self.get_monitor()
        if monitor:
            status = monitor["status"]
            friendly_name = monitor["friendly_name"]
            monitor_url = monitor["url"]
            embed = discord.Embed(title="BOTステータス", description="BOTのステータスを確認します。")
            if status == 2:
                embed.add_field(name="ステータス", value="UP")
                embed.add_field(name="モニター名", value=friendly_name)
                embed.add_field(name="URL", value=monitor_url)
                await ctx.send(embed=embed)
            elif status == 9:
                embed.add_field(name="ステータス", value="DOWN")
                embed.add_field(name="モニター名", value=friendly_name)
                embed.add_field(name="URL", value=monitor_url)
                await ctx.send(embed=embed)
            else:
                embed.add_field(name="ステータス", value="UNKNOWN")
                embed.add_field(name="モニター名", value=friendly_name)
                embed.add_field(name="URL", value=monitor_url)
                await ctx.send(embed=embed)
        else:
            await ctx.send("モニターが見つかりません。")

async def setup(bot):
    await bot.add_cog(UptimeRobotStatus(bot))