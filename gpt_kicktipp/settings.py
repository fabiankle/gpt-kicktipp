from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from gpt_kicktipp.utils import get_user_from_keepassxc, get_password_from_keepassxc, \
    get_openai_api_key_from_keepassxc


class GlobalSettings(BaseSettings):
    kicktipp_group_name: str = Field(type=str, description="Kicktipp Spielgruppenname")
    kicktipp_user: str = Field(default_factory=get_user_from_keepassxc)
    kicktipp_password: str = Field(default_factory=get_password_from_keepassxc)
    openai_api_key: str | None = Field(default_factory=get_openai_api_key_from_keepassxc)
    openai_base_url: str | None = Field(default=None, description="OpenAI base url (if e.g. using a proxy)")

    class Config:
        env_file = ".env"

    @field_validator("openai_api_key")
    def openai_api_key(cls, key):
        """ little workaround for local config using keepass """
        if not key  or key == "nothing":
            return get_openai_api_key_from_keepassxc()