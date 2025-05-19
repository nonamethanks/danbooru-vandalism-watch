import os

from danboorutools import logger

from danbooru_vandalism_watch.bot import NNTBot

log_path = logger.log_to_file(folder="logs")

BOT_TOKEN = os.environ["NTTBOT_DISCORD_TOKEN_DEV"]


def main() -> None:
    bot = NNTBot()
    bot.run(BOT_TOKEN)
