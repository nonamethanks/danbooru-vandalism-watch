from __future__ import annotations

import datetime
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from danboorutools.logical.sessions.danbooru import danbooru_api
from danboorutools.models.danbooru import DanbooruPostVersion, DanbooruUser
from discord import Color, Embed
from discord.ext import commands, tasks
import os

from danbooru_vandalism_watch.view import PersistentView

if TYPE_CHECKING:
    from danbooru_vandalism_watch.bot import NNTBot

BOT_IDS = [
    "502584",  # danboorubot
    "865894",  # nntbot
]


def user_embed(user: DanbooruUser) -> str:
    return f"[user #{user.id}, {user.name}]({user.url})"


TEST_MODE = os.environ.get("TEST_MODE", "FALSE").lower() in ["true", "1"]


class VandalismChecker(commands.Cog):
    def __init__(self, bot: NNTBot):
        self.index = 0
        self.bot = bot
        self.main_loop.start()

        self.test_mode = TEST_MODE
        if self.test_mode:
            self.bot.logger.info("<r>Running in test mode. Everything will be marked as vandalism.</r>")

        self.last_checked_post_version = danbooru_api.post_versions(limit=1)[0].id

    @tasks.loop(seconds=5 if TEST_MODE else 60, count=None)
    async def main_loop(self):
        self.bot.logger.info("Scanning for tag vandalism...")
        await self.check_for_tag_vandalism()
        self.bot.logger.info("Done!")

    @main_loop.before_loop
    async def wait_for_boot(self):
        self.bot.logger.info("Starting up...")
        await self.bot.wait_until_ready()

    async def check_for_tag_vandalism(self) -> None:
        new_post_versions = danbooru_api.post_versions(
            id=f">{self.last_checked_post_version}",
            updater_id_not=",".join(BOT_IDS),
            limit=1000,
        )

        if not new_post_versions:
            self.bot.logger.info("No new post edits found.")
            return

        detected_by_user = defaultdict(list)
        for post_version in new_post_versions:
            if self.is_tag_vandalism(post_version):
                detected_by_user[post_version.updater].append(post_version)

        for edits in detected_by_user.values():
            await self.send_tag_vandalism_mass_tag_removal(*edits)

        self.last_checked_post_version = max(new_post_versions, key=lambda x: x.id).id

    def is_tag_vandalism(self, post_version: DanbooruPostVersion) -> bool:
        self.bot.logger.info(f"Checking post version {post_version.url}")
        if self.test_mode:
            return True

        return len(post_version.removed_tags) >= len(post_version.post.tags)  # half the tags were removed

    async def send_tag_vandalism_mass_tag_removal(self, *post_versions: DanbooruPostVersion) -> None:
        user = post_versions[0].updater
        self.bot.logger.info(f"<r>Sending vandalism for user #{user.url}</r>")

        edits_url = "https://danbooru.donmai.us/post_versions?search[id]=" + ",".join(map(str, [p.id for p in post_versions]))
        embed = Embed(
            title="Tag Vandalism",
            color=Color.red(),
        )
        embed.add_field(name="Type", value="Mass Tag Removal", inline=False)
        embed.add_field(name="Posts", value=f"[{len(post_versions)} posts]({edits_url})", inline=False)
        embed.add_field(name="User", value=f"[{user.name}]({user.url})", inline=True)
        embed.add_field(name="Role", value=f"{user.level_string}", inline=True)
        embed.timestamp = datetime.datetime.now(datetime.UTC)
        embed.set_footer(text="\u200b")

        await self.bot.channel.send(embed=embed, view=PersistentView())

        time.sleep(1)


async def setup(bot: NNTBot) -> None:
    await bot.add_cog(VandalismChecker(bot))
