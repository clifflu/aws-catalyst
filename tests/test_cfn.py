import botocore.exceptions
import boto3
import pytest
import random

from awscatalyst import cfn

MAGIC_KEY = "".join(["%x" % random.randint(0, 255) for _ in range(16)])
MAGIC_VALUE = "".join(["%x" % random.randint(0, 255) for _ in range(16)])


class Exactly(Exception):
    """
    Exception to be raised from a monkeypatched function to signify success,
    usually mocking functions that depends on external services and return None.
    """
    pass


def raise_later(err, *args, **kwargs):
    def inner(*_args, **_kwargs):
        raise err(*args, **kwargs) if type(err) is type else err
    return inner


def assertion_hook(**kwargs):
    """
    A hook for monkeypatch that raises `Exactly` when called and i_kwargs is subset
    of kwargs. Raises AssertionError if key from i_kwargs (called from tested function)
    is missing in kwargs, or values doesn't match.

    :param dict kwargs:
    :return:
    """
    def inner(**i_kwargs):
        for k, v in i_kwargs.items():
            assert v == kwargs[k]

        raise Exactly()

    return inner


@pytest.fixture
def stack_key():
    return cfn.CfnStack(MAGIC_KEY)


def test_cfn_stack_capability(stack_key):
    assert [] == stack_key.aws_capabilities()
    assert id(stack_key) == id(stack_key.with_capability(MAGIC_VALUE)), "with_capability should return stack itself"
    assert [MAGIC_VALUE] == stack_key.aws_capabilities()
    assert id(stack_key) == id(stack_key.without_capability(""))
    assert [MAGIC_VALUE] == stack_key.aws_capabilities()
    stack_key.without_capability(MAGIC_VALUE)
    assert [] == stack_key.aws_capabilities()


def test_cfn_stack_create(monkeypatch, stack_key):
    monkeypatch.setattr(getattr(stack_key, '_cfn'), 'create_stack', assertion_hook(
        StackName=getattr(stack_key, '_stack_name'),
        TemplateBody=MAGIC_VALUE,
        Parameters=stack_key.aws_parameters(),
        Capabilities=stack_key.aws_capabilities(),
        Tags=stack_key.aws_tags(),
    ))

    with pytest.raises(Exactly):
        stack_key.create(template=MAGIC_VALUE)


def test_cfn_stack_create_calls_update_param(monkeypatch, stack_key):
    false_stack = MAGIC_VALUE

    stack_key.with_parameter(MAGIC_KEY, MAGIC_VALUE)

    monkeypatch.setattr(getattr(stack_key, '_cfn'), 'create_stack', lambda **_: false_stack)
    stack_key.create(template=MAGIC_VALUE)
    assert getattr(stack_key, '_stack') == false_stack
    assert stack_key.aws_parameters() == [{"ParameterKey": MAGIC_KEY, "UsePreviousValue": True}]

    monkeypatch.setattr(getattr(stack_key, '_cfn'), 'create_stack', raise_later(Exactly))
    with pytest.raises(Exactly):
        stack_key.create(template=MAGIC_VALUE)

    bce = botocore.exceptions.ClientError({'Error': {'Code': ""}}, "noname")
    monkeypatch.setattr(getattr(stack_key, '_cfn'), 'create_stack', raise_later(bce))
    with pytest.raises(botocore.exceptions.ClientError):
        stack_key.create(template=MAGIC_VALUE)

    # Simulates boto exception on stack name duplication
    bce = botocore.exceptions.ClientError({'Error': {'Code': "AlreadyExistsException"}}, "noname")
    monkeypatch.setattr(getattr(stack_key, '_cfn'), 'create_stack', raise_later(bce))
    with pytest.raises(cfn.StackExists):
        stack_key.create(template=MAGIC_VALUE)


def test_cfn_stack_delete(monkeypatch, stack_key):
    monkeypatch.setattr(getattr(stack_key, '_stack'), "delete", raise_later(Exactly()))
    with pytest.raises(Exactly):
        stack_key.delete()


def test_cfn_stack_parameters(stack_key):
    pk, pv, upv = "ParameterKey", "ParameterValue", "UsePreviousValue"

    assert [] == stack_key.aws_parameters()

    assert id(stack_key) == id(stack_key.with_parameter(MAGIC_KEY))
    assert [{pk: MAGIC_KEY, upv: True}] == stack_key.aws_parameters()

    stack_key.with_parameter(MAGIC_VALUE)
    tmp = stack_key.aws_parameters()
    assert 2 == len(tmp)
    assert {pk: MAGIC_KEY, upv: True} in tmp
    assert {pk: MAGIC_VALUE, upv: True} in tmp

    assert id(stack_key) == id(stack_key.without_parameter(MAGIC_VALUE))
    assert [{pk: MAGIC_KEY, upv: True}] == stack_key.aws_parameters()

    stack_key.without_parameter(MAGIC_VALUE)
    assert [{pk: MAGIC_KEY, upv: True}] == stack_key.aws_parameters()

    stack_key.with_parameter(MAGIC_KEY, MAGIC_VALUE)
    assert [{pk: MAGIC_KEY, pv: MAGIC_VALUE}] == stack_key.aws_parameters()

    stack_key.carry_over_parameters()
    assert [{pk: MAGIC_KEY, upv: True}] == stack_key.aws_parameters()

    stack_key.with_parameter(MAGIC_KEY, 33)
    assert [{pk: MAGIC_KEY, pv: "33"}] == stack_key.aws_parameters(), "with_parameters should convert values to str"


def test_cfn_stack_tags(stack_key):
    k, v = "Key", "Value"

    assert [] == stack_key.aws_tags()

    assert id(stack_key) == id(stack_key.with_tag(MAGIC_KEY, MAGIC_VALUE))
    assert [{k: MAGIC_KEY, v: MAGIC_VALUE}] == stack_key.aws_tags()

    stack_key.with_tag(MAGIC_VALUE, MAGIC_KEY)
    tmp = stack_key.aws_tags()
    assert 2 == len(tmp)
    assert {k: MAGIC_KEY, v: MAGIC_VALUE} in tmp
    assert {k: MAGIC_VALUE, v: MAGIC_KEY} in tmp

    assert id(stack_key) == id(stack_key.without_tag(MAGIC_VALUE))
    assert [{k: MAGIC_KEY, v: MAGIC_VALUE}] == stack_key.aws_tags()

    stack_key.without_tag(MAGIC_VALUE)
    assert [{k: MAGIC_KEY, v: MAGIC_VALUE}] == stack_key.aws_tags()

    stack_key.with_tag(MAGIC_KEY, MAGIC_KEY)
    assert [{k: MAGIC_KEY, v: MAGIC_KEY}] == stack_key.aws_tags()

    assert id(stack_key) == id(stack_key.without_tag(MAGIC_KEY))
    assert [] == stack_key.aws_tags()

    stack_key.with_tag(33, 33)
    assert [{k: "33", v: "33"}] == stack_key.aws_tags(), "with_tags should convert values to str"
