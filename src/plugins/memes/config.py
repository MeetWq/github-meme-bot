from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    smms_secret_token: str


plugin_config = get_plugin_config(Config)
