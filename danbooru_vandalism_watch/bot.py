import os
import platform
import random
from functools import cached_property

import discord
from danboorutools import logger  # type: ignore[import-untyped]
from discord.ext import commands, tasks

from danbooru_vandalism_watch.view import PersistentView

intents = discord.Intents.all()


class NNTBot(commands.Bot):
    test_mode = os.environ.get("NNTBOT_DISCORD_TEST_MODE", "FALSE").lower() in ["true", "1"]

    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("$"),
            intents=intents,
            help_command=None,
        )

        self.logger = logger
        self.channel_id = int(os.environ["NTTBOT_DISCORD_CHANNEL_ID"])
        self.test_channel_id = int(os.environ["NTTBOT_DISCORD_TEST_CHANNEL_ID"])

    @cached_property
    def owner(self) -> discord.User:
        assert self.application, "Bot hasn't started yet!"

        if owner_id := os.environ.get("NNTBOT_OWNER_ID", None):
            if owner := self._get_owner_from_team(int(owner_id)):
                return owner

            owner = self.get_user(int(owner_id))
            assert owner is not None, f"Couldn't find owner user with id {owner_id}"
            return owner

        return self.application.owner

    def _get_owner_from_team(self, user_id: int) -> discord.User | None:
        assert self.application, "Bot hasn't started yet!"

        if not (team := self.application.team):
            return None
        try:
            member = next(u for u in team.members if u.id == int(user_id))
        except StopIteration:
            return None

        owner_data = member._to_minimal_user_json()  # i really hate discord
        owner = discord.User(state=self._connection, data=owner_data)  # type: ignore[arg-type]
        return owner

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
        await self.load_cogs()

        self.add_view(PersistentView())

        self.status_task.start()

        self.logger.info(f"Logged in as {self.user.name}")  # type: ignore[union-attr]
        self.logger.info(f"Target channel: {self.channel_id}")
        self.logger.info(f"Owner: {self.owner}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Running on: {platform.system()} {platform.release()} ({os.name})")
        if self.test_mode:
            self.logger.info("<r>Running in test mode. Everything will be marked as vandalism.</r>")
        else:
            self.logger.info("<g>Running in prod mode.</g>")
        self.logger.info("-------------------")

        await self.alert_owner("Bot started successfully.")

    @property
    def channel(self) -> discord.TextChannel:
        channel_id = self.test_channel_id if self.test_mode else self.channel_id
        channel = self.get_channel(channel_id)
        assert isinstance(channel, discord.TextChannel), f"Couldn't find {channel_id}"
        return channel

    async def on_ready(self) -> None:
        logger.info("Bot is ready and online.")

    async def alert_owner(self, msg: str | None = None) -> None:
        logger.info(f"Sending warning message to {self.owner.display_name}.")
        msg = msg or "Yo, the bot crapped out. Check the logs."
        await self.owner.send(msg)
