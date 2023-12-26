import logging

import pytest
from pydantic import BaseModel

from pydantic_ssm_settings.settings import AwsSsmSourceConfig

logger = logging.getLogger("pydantic_ssm_settings")
logger.setLevel(logging.DEBUG)


class SimpleSettings(AwsSsmSourceConfig):
    foo: str


class IntSettings(AwsSsmSourceConfig):
    foo: str
    bar: int

class ChildSetting(BaseModel):
    bar : str
class ParentSetting(AwsSsmSourceConfig):
    foo :ChildSetting 


def test_ssm_prefix_must_be_absolute():
    with pytest.raises(ValueError):
        SimpleSettings(ssm_prefix="asdf")


def test_lookup_from_ssm(ssm):
    ssm.put_parameter(Name="/asdf/foo", Value="xyz123")
    settings = SimpleSettings(ssm_prefix="/asdf")
    assert settings.foo == "xyz123"


def test_prefer_provided(ssm):
    settings = SimpleSettings(ssm_prefix="/asdf", foo="manually set")
    assert settings.foo == "manually set"


def test_casting(ssm):
    ssm.put_parameter(Name="/asdf/foo", Value="xyz123")
    ssm.put_parameter(Name="/asdf/bar", Value="99")
    settings = IntSettings(ssm_prefix="/asdf")
    assert settings.bar == 99

def test_parameter_override(ssm):
    ssm.put_parameter(Name="/asdf/foo", Value= '{"bar": "xyz123"}')
    ssm.put_parameter(Name="/asdf/foo/bar", Value= "overwritten")
    settings = ParentSetting(ssm_prefix="/asdf")
    assert settings.foo.bar == "overwritten"