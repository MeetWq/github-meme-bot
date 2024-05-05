from typing import Literal

import httpx
from nonebot.adapters.github import (
    CommitCommentCreated,
    GitHubBot,
    IssueCommentCreated,
    PullRequestReviewCommentCreated,
)

from .config import plugin_config

CommentEvent = (
    IssueCommentCreated | PullRequestReviewCommentCreated | CommitCommentCreated
)


async def get_installation_id(
    bot: GitHubBot,
    event: CommentEvent,
) -> int:
    """获取 GitHub App 的 Installation ID"""
    repo = event.payload.repository
    installation = (
        await bot.rest.apps.async_get_repo_installation(
            owner=repo.owner.login, repo=repo.name
        )
    ).parsed_data
    return installation.id


async def creation_reaction(
    bot: GitHubBot,
    event: CommentEvent,
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

    repo = event.payload.repository
    await func(
        owner=repo.owner.login,
        repo=repo.name,
        comment_id=event.payload.comment.id,
        data={"content": content},
    )


async def get_user(bot: GitHubBot, username: str):
    return (await bot.rest.users.async_get_by_username(username=username)).parsed_data


async def upload_image(image: bytes) -> str:
    api = "https://sm.ms/api/v2/upload"
    headers = {"Authorization": plugin_config.smms_secret_token}
    files = {"smfile": image}
    async with httpx.AsyncClient() as client:
        resp = await client.post(api, headers=headers, files=files)
    data = resp.json()
    return data["data"]["url"]
