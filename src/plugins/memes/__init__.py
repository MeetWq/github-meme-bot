import re
import traceback
from dataclasses import dataclass
from typing import Any

from arclet.alconna import config as alc_config
from meme_generator.exception import MemeGeneratorException
from meme_generator.manager import get_memes
from meme_generator.meme import Meme
from nonebot import require
from nonebot.adapters.github import GitHubBot
from nonebot.drivers import Request
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.utils import run_sync

require("nonebot_plugin_alconna")

from nonebot_plugin_alconna import AlcMatches, Alconna, Args, MultiVar, Text, on_alconna

from .utils import (
    CommentEvent,
    creation_reaction,
    get_installation_id,
    get_user,
    upload_image,
)

alc_config.command_max_count += 1000

meme_params_key = "meme_params"
arg_meme_params = Args[meme_params_key, MultiVar(Text, "*")]


def create_matcher(meme: Meme):
    options = [
        opt.option()
        for opt in (
            meme.params_type.args_type.parser_options
            if meme.params_type.args_type
            else []
        )
    ]
    meme_matcher = on_alconna(
        Alconna(meme.keywords[0], *options, arg_meme_params),
        aliases=set(meme.keywords[1:]),
        block=True,
        use_cmd_start=True,
    )
    for shortcut in meme.shortcuts:
        meme_matcher.shortcut(
            shortcut.key,
            arguments=shortcut.args,
            prefix=True,
            humanized=shortcut.humanized,
        )

    @meme_matcher.handle()
    async def _(
        bot: GitHubBot,
        event: CommentEvent,
        matcher: Matcher,
        alc_matches: AlcMatches,
        installation_id: int = Depends(get_installation_id),
    ):
        sender = event.payload.sender
        if sender.type == "Bot":
            logger.info("评论来自机器人，已跳过")
            return

        @dataclass
        class UserInfo:
            name: str
            avatar_url: str

        texts: list[str] = []
        images: list[bytes] = []
        image_urls: list[str] = []
        user_infos: list[UserInfo] = []

        args: dict[str, Any] = {}
        options = alc_matches.options
        for option, option_result in options.items():
            if option_result.value is None:
                args.update(option_result.args)
            else:
                args[option] = option_result.value

        meme_params: list[Text] = list(alc_matches.query(meme_params_key, ()))

        event_user_info = UserInfo(sender.login, sender.avatar_url)

        async with bot.as_installation(installation_id):
            for param in meme_params:
                text = param.text
                if text.startswith("@") and (name := text[1:]):
                    try:
                        user = await get_user(bot, name)
                        image_urls.append(user.avatar_url)
                        user_infos.append(UserInfo(user.login, user.avatar_url))
                    except Exception:
                        logger.warning(traceback.format_exc())
                        texts.append(text)

                elif text == "自己":
                    image_urls.append(event_user_info.avatar_url)
                    user_infos.append(event_user_info)

                elif matched := re.match(r"!\[(.*?)\]\((.*?)\)", text):
                    name, url = matched.groups()
                    match_url = True
                    repo = event.payload.repository
                    repo_name = f"{repo.owner.login}/{repo.name}"
                    if url.startswith("http"):
                        pass
                    elif url.startswith(f"/{repo_name}"):
                        url = f"https://github.com{url}"
                    elif url.startswith("/"):
                        url = f"https://github.com/{repo_name}{url}"
                    else:
                        match_url = False
                    if match_url:
                        image_urls.append(url)
                        user_infos.append(UserInfo(name, url))
                    else:
                        texts.append(text)

                elif text:
                    texts.append(text)

            if meme.params_type.min_images == 2 and len(image_urls) == 1:
                image_urls.insert(0, event_user_info.avatar_url)
                user_infos.insert(0, event_user_info)

            args["user_infos"] = [{"name": user_info.name} for user_info in user_infos]

            if not (
                meme.params_type.min_images
                <= len(image_urls)
                <= meme.params_type.max_images
            ) or not (
                meme.params_type.min_texts <= len(texts) <= meme.params_type.max_texts
            ):
                logger.warning("图片数量或文字数量不符")
                await creation_reaction(bot, event, "confused")
                await matcher.finish()

            for image_url in image_urls:
                resp = await bot.adapter.request(Request("GET", image_url))
                assert resp.status_code == 200
                assert isinstance(resp.content, bytes)
                images.append(resp.content)

            try:
                result = await run_sync(meme)(images=images, texts=texts, args=args)
            except MemeGeneratorException:
                logger.warning(traceback.format_exc())
                await creation_reaction(bot, event, "confused")
                await matcher.finish()

            url = await upload_image(result.getvalue())
            await matcher.finish(f"![{meme.keywords[0]}]({url})")


def create_matchers():
    for meme in get_memes():
        create_matcher(meme)


create_matchers()
