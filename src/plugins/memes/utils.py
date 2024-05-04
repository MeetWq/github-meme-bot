from typing import Literal

import httpx
from nonebot.adapters.github import (
    Bot,
    CommitCommentCreated,
    IssueCommentCreated,
    PullRequestReviewCommentCreated,
)

from .config import plugin_config


async def creation_reaction(
    bot: Bot,
    event: IssueCommentCreated | PullRequestReviewCommentCreated | CommitCommentCreated,
    content: Literal[
        "+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes"
    ],
):
    if isinstance(event, CommitCommentCreated):
        func = bot.rest.reactions.async_create_for_commit_comment

    elif isinstance(event, IssueCommentCreated):
        func = bot.rest.reactions.async_create_for_issue_comment

    elif isinstance(event, PullRequestReviewCommentCreated):
        func = bot.rest.reactions.async_create_for_pull_request_review_comment

    else:
        raise RuntimeError(
            f"Cannot creation reaction for event type {event.__class__.__name__}"
        )

    await func(
        owner=event.payload.repository.owner.login,
        repo=event.payload.repository.name,
        comment_id=event.payload.comment.id,
        data={"content": content},
    )


async def get_user(bot: Bot, username: str):
    return (await bot.rest.users.async_get_by_username(username=username)).parsed_data


async def upload_image(image: bytes) -> str:
    api = "https://sm.ms/api/v2/upload"
    headers = {"Authorization": plugin_config.smms_secret_token}
    files = {"smfile": image}
    async with httpx.AsyncClient() as client:
        resp = await client.post(api, headers=headers, files=files)
    data = await resp.json()
    return data["data"]["url"]
