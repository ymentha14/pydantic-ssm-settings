import logging
from pathlib import Path
from typing import Tuple, Type

from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)

from .source import AwsSsmSettingsSource

logger = logging.getLogger(__name__)


class AwsSsmSourceConfig(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        ssm_settings = AwsSsmSettingsSource(
            settings_cls=settings_cls,
            ssm_prefix=Path(file_secret_settings.secrets_dir),
            env_nested_delimiter=env_settings.env_nested_delimiter,
        )

        return (
            init_settings,
            env_settings,
            # Usurping the `secrets_dir` arg. We can't expect any other args to
            # be passed to # the Settings module because Pydantic will complain
            # about unexpected arguments. `secrets_dir` comes from `_secrets_dir`,
            # one of the few special kwargs that Pydantic will allow:
            # https://github.com/samuelcolvin/pydantic/blob/45db4ad3aa558879824a91dd3b011d0449eb2977/pydantic/env_settings.py#L33
            ssm_settings,
        )
