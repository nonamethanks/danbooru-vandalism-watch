from __future__ import annotations

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING

from danboorutools.exceptions import DanbooruHTTPError, HTTPError
from danboorutools.logical.sessions.danbooru import danbooru_api, kwargs_to_include
from danboorutools.models.danbooru import DanbooruUser  # noqa: TC002
from danboorutools.util.misc import BaseModel
from discord import Color, Embed
from discord.ext import commands, tasks

from danbooru_vandalism_watch.bot import NNTBot
from danbooru_vandalism_watch.view import PersistentView

if TYPE_CHECKING:
    from danboorutools.models.danbooru import DanbooruPostVersion


BOT_IDS = [
    "502584",  # danboorubot
    "865894",  # nntbot
]


def user_embed(user: DanbooruUser) -> str:
    return f"[user #{user.id}, {user.name}]({user.url})"


class ArtistData(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime

    @property
    def url(self) -> str:
        return f"https://danbooru.donmai.us/artists/{self.id}"


class ArtistVersionData(BaseModel):
    id: int
    updater: DanbooruUser
    created_at: datetime.datetime
    updated_at: datetime.datetime
    urls: list[str]

    artist: ArtistData

    @property
    def url(self) -> str:
        return f"https://danbooru.donmai.us/artist_versions?search[artist_id]={self.artist.id}"


class VandalismChecker(commands.Cog):
    def __init__(self, bot: NNTBot):
        self.index = 0
        self.bot = bot
        self.main_loop.start()

        self.last_checked_post_version = danbooru_api.post_versions(limit=1)[0].id
        self.last_checked_artist_version = self._get_artist_versions(limit=1)[0].id

    @staticmethod
    def _get_artist_versions(**kwargs) -> list[ArtistVersionData]:
        data = danbooru_api.danbooru_request(
            "GET",
            "artist_versions.json",
            params=kwargs_to_include(**kwargs, only="id,updater,artist,urls,updated_at,created_at"),
        )
        return [ArtistVersionData(**a) for a in data]

    @tasks.loop(seconds=10 if NNTBot.test_mode else 60, count=None)
    async def main_loop(self) -> None:
        try:
            self.bot.logger.info("Scanning for tag vandalism...")
            await self.check_for_tag_vandalism()
            self.bot.logger.info("Scanning for artist vandalism...")
            await self.check_for_artist_vandalism()
            self.bot.logger.info("Done!")
        except (HTTPError, DanbooruHTTPError):
            self.bot.logger.exception("Encountered an exception with danbooru. Trying again later...")
        except Exception:
            self.bot.logger.exception("Encountered an exception. Sending to owner...")
            await self.bot.alert_owner()

    @main_loop.before_loop
    async def wait_for_boot(self) -> None:
        self.bot.logger.info("Starting up...")
        await self.bot.wait_until_ready()

    async def check_for_tag_vandalism(self) -> None:
        new_post_versions = danbooru_api.post_versions(
            id=f">{self.last_checked_post_version}",
            updater_id_not=",".join(BOT_IDS),
            is_new=False,
            limit=1000,
        )

        if not new_post_versions:
            self.bot.logger.info("No new post edits found.")
            return

        detected_by_user: dict[str, dict[DanbooruUser, list[DanbooruPostVersion]]] = defaultdict(lambda: defaultdict(list))
        for post_version in new_post_versions:
            self.bot.logger.info(f"Checking post version {post_version.url}")
            if (tag_vandalism_type := self.is_tag_vandalism(post_version)) is not None:
                self.bot.logger.info(
                    f"<r>Post version {post_version.url} was detected as vandalism of type '{tag_vandalism_type}'. Sending...</r>",
                )
                detected_by_user[tag_vandalism_type][post_version.updater].append(post_version)

        for vandalism_type, edits_by_user in detected_by_user.items():
            for edits in edits_by_user.values():
                await self.send_tag_vandalism(vandalism_type=vandalism_type, post_versions=list(edits))

        self.last_checked_post_version = max(new_post_versions, key=lambda x: x.id).id

    async def check_for_artist_vandalism(self) -> None:
        new_artist_versions = self._get_artist_versions(
            id=f">{self.last_checked_artist_version}",
            updater_id_not=",".join(BOT_IDS),
            limit=1000,
        )

        if not new_artist_versions:
            self.bot.logger.info("No new artist edits found.")
            return

        new_artist_versions.sort(key=lambda a: a.id)

        for artist_version in new_artist_versions:
            self.bot.logger.info(f"Checking artist version for artist {artist_version.artist.url}")
            if self.is_artist_vandalism(artist_version):
                self.bot.logger.info(f"<r>Artist version for artist {artist_version.artist.url} was detected as vandalism. Sending...</r>")
                await self.send_artist_vandalism_url_nuke(artist_version)
            self.last_checked_artist_version = artist_version.id

    def is_tag_vandalism(self, post_version: DanbooruPostVersion) -> str | None:
        if self.bot.test_mode:
            return "Mass Tag Removal"

        if post_version.post.is_deleted:
            self.bot.logger.trace("The post was deleted. Ignoring.")
            # no point in reporting these
            return None

        if post_version.updater.level > 30:
            # assume builders are not vandals (big assumption lmao)
            self.bot.logger.trace("Was done by a builder or above. Skipping.")

        tag_stats = (
            f"The post had {len(removed_tags := post_version.removed_tags)} tags removed, "
            f"{len(post_version.tags_after_edit)} tags in the end"
        )

        if (
            (len(removed_tags) >= 5 and len(post_version.tags_after_edit) <= 5)
            or (len(removed_tags) >= 10 and len(post_version.tags_after_edit) <= 10)
            or len(removed_tags) >= 20
        ):
            # most tags removed
            self.bot.logger.trace(f"Found mass tag removal. {tag_stats}")
            return "Mass Tag Removal"

        if len(post_version.added_tags) >= 200:
            # tag spam
            self.bot.logger.trace("Found mass tag addition.")
            return "Mass Tag Addition"

        self.bot.logger.trace(f"No vandalism here. {tag_stats}")
        return None

    async def send_tag_vandalism(self, vandalism_type: str, post_versions: list[DanbooruPostVersion]) -> None:
        user = post_versions[0].updater
        self.bot.logger.info(f"<r>Sending vandalism for user #{user.url}</r>")

        total_edit_url = f"https://danbooru.donmai.us/post_versions?search[updater_id]={user.id}"
        timeframe_edits_url = "https://danbooru.donmai.us/post_versions?search[id]=" + ",".join(map(str, [p.id for p in post_versions]))
        timeframe_edit_link = f"[{len(post_versions)} posts]({timeframe_edits_url if len(post_versions) < 100 else total_edit_url})"

        embed = Embed(
            title="Tag Vandalism",
            color=Color.red(),
        )
        embed.add_field(name="Type", value=vandalism_type, inline=True)
        embed.add_field(name="\u200b", value="\u200b")
        embed.add_field(name="Posts", value=timeframe_edit_link, inline=True)
        embed.add_field(name="All Edits", value=f"[Link]({total_edit_url})", inline=True)
        embed.add_field(name="\u200b", value="\u200b")
        embed.add_field(name="Username", value=f"[{user.name}]({user.url})", inline=True)
        embed.add_field(name="ID", value=f"{user.id}", inline=True)
        embed.add_field(name="Role", value=f"{user.level_string}", inline=True)

        timestamp = int(max(post_versions, key=lambda x: x.updated_at).updated_at.timestamp())
        embed.add_field(name="When", value=f"<t:{timestamp}:R>", inline=False)

        await self.bot.channel.send(embed=embed, view=PersistentView())

    def is_artist_vandalism(self, artist_version: ArtistVersionData) -> bool:
        elapsed_since_creation = artist_version.updated_at - artist_version.artist.created_at
        if elapsed_since_creation < datetime.timedelta(hours=1):
            # just someone creating an artist wiki and then adding the urls after
            self.bot.logger.trace("This seems to be a new version. Skipping.")
            return False

        if artist_version.updater.level > 30:
            # assume builders are not vandals (big assumption lmao)
            self.bot.logger.trace("Was done by a builder or above. Skipping.")
            return False

        previous_versions = self._get_artist_versions(artist_id=artist_version.artist.id, id=f"<{artist_version.id}")
        if not previous_versions:
            self.bot.logger.trace("This was a new version. Skipping.")
            return False

        return bool(not artist_version.urls and previous_versions[0].urls)

    async def send_artist_vandalism_url_nuke(self, artist_version: ArtistVersionData) -> None:
        user = artist_version.updater
        self.bot.logger.info(f"<r>Sending vandalism for artist {artist_version.urls}</r>")

        embed = Embed(
            title="Artist Vandalism",
            color=Color.red(),
        )
        embed.add_field(name="Type", value="Mass Url Removal", inline=True)
        embed.add_field(name="Artist", value=f"[{artist_version.artist.name}]({artist_version.url})", inline=True)
        embed.add_field(name="\u200b", value="\u200b")
        embed.add_field(name="Username", value=f"[{user.name}]({user.url})", inline=True)
        embed.add_field(name="ID", value=f"#{user.id}", inline=True)
        embed.add_field(name="Role", value=f"{user.level_string}", inline=True)

        timestamp = int(artist_version.updated_at.timestamp())
        embed.add_field(name="When", value=f"<t:{timestamp}:R>", inline=False)

        await self.bot.channel.send(embed=embed, view=PersistentView())


async def setup(bot: NNTBot) -> None:
    await bot.add_cog(VandalismChecker(bot))
