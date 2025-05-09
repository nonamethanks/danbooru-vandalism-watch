import discord
from discord.ext import commands, tasks
import os
import random

import platform

from danboorutools import logger  # type: ignore[import-untyped]

from danbooru_vandalism_watch.view import PersistentView

intents = discord.Intents.all()


class NNTBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("$"),
            intents=intents,
            help_command=None,
        )

        self.logger = logger
        self.channel_id = int(os.environ["NTTBOT_DISCORD_CHANNEL_ID"])

    async def load_cogs(self) -> None:
        await self.load_extension("danbooru_vandalism_watch.vandalism_checker")

    @tasks.loop(seconds=30)
    async def status_task(self) -> None:
        statuses = [
            "Browsing guro...",
            "Watching... Plotting...",
            "Killing nonamethanks...",
            "Beating my metal meat...",
            "Practicing chikan...",
            "Having a builder meltdown™...",
            "I have no nose and I must sniff...",
            "Approving random BURs...",
            "Opening a Fate thread...",
            "Opening a Bridget thread...",
            "Uploading simpsons porn...",
            "alias luigi -> luigi_mario",
            "Arguing in bad faith...",
            "Stalking Fumimi...",
            "Returning to Hyperborea...",
        ]
        await self.change_presence(activity=discord.CustomActivity(name=random.choice(statuses)))

    @status_task.before_loop
    async def before_status_task(self) -> None:
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        self.logger.info(f"Logged in as {self.user.name}")  # type: ignore[union-attr]
        self.logger.info(f"Target channel: {self.channel_id}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Running on: {platform.system()} {platform.release()} ({os.name})")
        self.logger.info("-------------------")
        await self.load_cogs()

        self.add_view(PersistentView())

        self.status_task.start()

    @property
    def channel(self) -> discord.TextChannel:
        channel = self.get_channel(self.channel_id)
        assert isinstance(channel, discord.TextChannel)
        return channel

    async def on_ready(self) -> None:
        logger.info("Bot is ready and online.")
