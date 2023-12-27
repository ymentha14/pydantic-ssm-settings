import logging
from typing import Any, Tuple, Type

from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)

from .source import AwsSsmSettingsSource

logger = logging.getLogger(__name__)


class BaseSettingsV2(BaseSettings):
    def __init__(self, *args, ssm_prefix: str = "/", **kwargs: Any) -> None:
        self.__dict__["__ssm_prefix"] = ssm_prefix
        super().__init__(self, *args, **kwargs)


class AwsSsmSourceConfig(BaseSettingsV2):
    def settings_customise_sources(
        self,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        ssm_settings = AwsSsmSettingsSource(
            settings_cls=settings_cls,
            ssm_prefix=self.__dict__["__ssm_prefix"],
        )

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            ssm_settings,
            file_secret_settings,
        )
