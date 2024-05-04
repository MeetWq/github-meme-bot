import shlex
import traceback
from dataclasses import dataclass

from meme_generator.exception import ArgParserExit, MemeGeneratorException
from meme_generator.manager import get_memes
from meme_generator.meme import Meme
from nonebot import on_message
from nonebot.adapters.github import (
    CommitCommentCreated,
    GitHubBot,
    IssueCommentCreated,
    Message,
    PullRequestReviewCommentCreated,
)
from nonebot.drivers import Request
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.typing import T_Handler, T_State

from .rule import MSG_KEY, TEXTS_KEY, command_rule, regex_rule
from .utils import (
    BOT_MARKER,
    creation_reaction,
    get_installation_id,
    get_user,
    upload_image,
)


def handler(meme: Meme) -> T_Handler:
    async def handle(
        bot: GitHubBot,
        event: IssueCommentCreated
        | PullRequestReviewCommentCreated
        | CommitCommentCreated,
        matcher: Matcher,
        state: T_State,
        installation_id: int = Depends(get_installation_id),
    ):
        @dataclass
        class UserInfo:
            name: str
            avatar_url: str

        msg: Message = state[MSG_KEY]
        texts: list[str] = []
        images: list[bytes] = []
        image_urls: list[str] = []
        user_infos: list[UserInfo] = []
        args: dict = {}

        sender = event.payload.sender
        event_user_info = UserInfo(
            sender.name if isinstance(sender.name, str) else "",
            sender.avatar_url,
        )

        for text in shlex.split(msg.extract_plain_text()):
            if text.startswith("@") and (name := text[1:]):
                try:
                    user = await get_user(bot, name)
                    image_urls.append(user.avatar_url)
                    user_infos.append(UserInfo(user.name or "", user.avatar_url))
                except Exception:
                    logger.warning(traceback.format_exc())
                    texts.append(text)

            elif text == "自己":
                image_urls.append(event_user_info.avatar_url)
                user_infos.append(event_user_info)

            elif text:
                texts.append(text)

        if meme.params_type.min_images == 2 and len(image_urls) == 1:
            image_urls.insert(0, event_user_info.avatar_url)
            user_infos.insert(0, event_user_info)

        texts = state.get(TEXTS_KEY, []) + texts

        if meme.params_type.args_type:
            try:
                parse_result = meme.parse_args(texts)
            except ArgParserExit:
                logger.warning(traceback.format_exc())
                await matcher.finish()
            texts = parse_result["texts"]
            parse_result.pop("texts")
            args = parse_result

        if not (
            meme.params_type.min_images
            <= len(image_urls)
            <= meme.params_type.max_images
        ) or not (
            meme.params_type.min_texts <= len(texts) <= meme.params_type.max_texts
        ):
            logger.warning("图片数量或文字数量不符")
            await matcher.finish()
        matcher.stop_propagation()

        for image_url in image_urls:
            resp = await bot.adapter.request(Request("GET", image_url))
            assert resp.status_code == 200
            assert isinstance(resp.content, bytes)
            images.append(resp.content)

        args["user_infos"] = [{"name": user_info.name} for user_info in user_infos]

        try:
            result = await meme(images=images, texts=texts, args=args)
        except MemeGeneratorException:
            logger.warning(traceback.format_exc())
            await creation_reaction(bot, event, "confused")
            await matcher.finish()

        url = await upload_image(result.getvalue())

        async with bot.as_installation(installation_id):
            await matcher.finish(f"![{meme.keywords[0]}]({url})")

    return handle


async def not_bot(
    event: IssueCommentCreated | PullRequestReviewCommentCreated | CommitCommentCreated,
) -> bool:
    return not event.payload.sender.login.endswith(BOT_MARKER)


def create_matchers():
    for meme in get_memes():
        matchers: list[type[Matcher]] = []
        if meme.keywords:
            matchers.append(
                on_message(
                    command_rule(meme.keywords),
                    permission=not_bot,
                    block=False,
                    priority=1,
                )
            )
        if meme.patterns:
            matchers.append(
                on_message(
                    regex_rule(meme.patterns),
                    permission=not_bot,
                    block=False,
                    priority=2,
                )
            )

        for matcher in matchers:
            matcher.append_handler(handler(meme))


create_matchers()
