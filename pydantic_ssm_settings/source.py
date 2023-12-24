import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from pydantic._internal._typing_extra import origin_is_union
from pydantic.fields import Field, FieldInfo
from pydantic.v1.utils import deep_update
from pydantic_settings import BaseSettings
from pydantic_settings.sources import (
    PydanticBaseEnvSettingsSource,
    _annotation_is_complex,
)
from typing_extensions import get_args, get_origin

if TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient


logger = logging.getLogger(__name__)


class AwsSsmSettingsSource(PydanticBaseEnvSettingsSource):
    __slots__ = ("ssm_prefix", "env_nested_delimiter")

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        ssm_prefix: Optional[str],
        env_nested_delimiter: Optional[str] = None,
    ):
        super().__init__(settings_cls)
        self.ssm_prefix: Optional[str] = ssm_prefix
        self.env_nested_delimiter: Optional[str] = env_nested_delimiter
        self.ssm_values = self.load_from_ssm(
            ssm_prefix, case_sensitive=self.case_sensitive
        )

    @property
    def client(self) -> "SSMClient":
        return boto3.client("ssm", config=self.client_config)

    @property
    def client_config(self) -> Config:
        timeout = float(os.environ.get("SSM_TIMEOUT", 0.5))
        return Config(connect_timeout=timeout, read_timeout=timeout)

    def load_from_ssm(self, secrets_path: Path, case_sensitive: bool):
        if not secrets_path.is_absolute():
            raise ValueError("SSM prefix must be absolute path")

        logger.debug(f"Building SSM settings with prefix of {secrets_path=}")

        output = {}
        try:
            paginator = self.client.get_paginator("get_parameters_by_path")
            response_iterator = paginator.paginate(
                Path=str(secrets_path), WithDecryption=True
            )

            for page in response_iterator:
                for parameter in page["Parameters"]:
                    key = Path(parameter["Name"]).relative_to(secrets_path).as_posix()
                    output[key if case_sensitive else key.lower()] = parameter["Value"]

        except ClientError:
            logger.exception("Failed to get parameters from %s", secrets_path)

        return output

    # The following was lifted from https://github.com/pydantic/pydantic-settings/blob/4f24fad3609fe046b4755c67d11e361825afc9eb/pydantic_settings/sources.py#L391C2-L467C1
    def _field_is_complex(self, field: FieldInfo) -> tuple[bool, bool]:
        """
        Find out if a field is complex, and if so whether JSON errors should be ignored
        """
        if self.field_is_complex(field):
            allow_parse_failure = False
        elif origin_is_union(get_origin(field.annotation)) and self._union_is_complex(
            field.annotation, field.metadata
        ):
            allow_parse_failure = True
        else:
            return False, False

        return True, allow_parse_failure

    def _explode_ssm_values(
        self, field: Field, env_vars: Mapping[str, Optional[str]]
    ) -> Dict[str, Any]:
        """
        Process env_vars and extract the values of keys containing
        env_nested_delimiter into nested dictionaries.

        This is applied to a single field, hence filtering by env_var prefix.
        """
        prefixes = [
            f"{env_name}{self.env_nested_delimiter}"
            for env_name in field.field_info.extra["env_names"]
        ]
        result: Dict[str, Any] = {}
        for env_name, env_val in env_vars.items():
            if not any(env_name.startswith(prefix) for prefix in prefixes):
                continue
            _, *keys, last_key = env_name.split(self.env_nested_delimiter)
            env_var = result
            for key in keys:
                env_var = env_var.setdefault(key, {})
            env_var[last_key] = env_val

        return result

    def __repr__(self) -> str:
        return f"AwsSsmSettingsSource(ssm_prefix={self.ssm_prefix!r})"

    def _union_is_complex(self, annotation, metadata: list[Any]) -> bool:
        return any(
            _annotation_is_complex(arg, metadata) for arg in get_args(annotation)
        )

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        is_complex, allow_parse_failure = self._field_is_complex(field)
        if is_complex or value_is_complex:
            if value is None:
                # field is complex but no value found so far, try explode_env_vars
                env_val_built = self.explode_ssm_values(
                    field, field_name, self.ssm_values
                )
                if env_val_built:
                    return env_val_built
            else:
                # field is complex and there's a value, decode that
                # as JSON, then add explode_env_vars
                try:
                    value = self.decode_complex_value(field_name, field, value)
                except ValueError as e:
                    if not allow_parse_failure:
                        raise e

                if isinstance(value, dict):
                    return deep_update(
                        value,
                        self.explode_ssm_values(field, field_name, self.ssm_values),
                    )
                else:
                    return value
        elif value is not None:
            # simplest case, field is not complex, we only need to add
            # the value if it was found
            return value

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        for field_key, env_name, value_is_complex in self._extract_field_info(
            field, field_name
        ):
            env_val = self.ssm_values.get(env_name)
            if env_val is not None:
                break

        return env_val, field_key, value_is_complex
