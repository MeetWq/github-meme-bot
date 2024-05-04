from typing import Literal

import httpx
from nonebot.adapters.github import (
    Bot,
    CommitCommentCreated,
    GitHubBot,
    IssueCommentCreated,
    PullRequestReviewCommentCreated,
)
from nonebot.params import Depends
from pydantic import BaseModel

from .config import plugin_config

BOT_MARKER = "[bot]"
"""机器人的名字结尾都会带有这个"""


class RepoInfo(BaseModel):
    """仓库信息"""

    owner: str
    repo: str


def get_repo_info(
    event: IssueCommentCreated | PullRequestReviewCommentCreated | CommitCommentCreated,
) -> RepoInfo:
    """获取仓库信息"""
    repo = event.payload.repository
    return RepoInfo(owner=repo.owner.login, repo=repo.name)


async def get_installation_id(
    bot: GitHubBot,
    repo_info: RepoInfo = Depends(get_repo_info),
) -> int:
    """获取 GitHub App 的 Installation ID"""
    installation = (
        await bot.rest.apps.async_get_repo_installation(**repo_info.model_dump())
    ).parsed_data
    return installation.id


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
    data = resp.json()
    return data["data"]["url"]
