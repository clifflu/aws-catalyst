import json
import random

from awscatalyst import cfn

MAGIC_KEY = "".join(["%x" % random.randint(0, 255) for _ in range(16)])
MAGIC_VALUE = "".join(["%x" % random.randint(0, 255) for _ in range(16)])


def td(tpl):
    """
    Gets _template_dict from tpl, just to comply with the PEP-8
    :param tpl: CfnTemplate
    :return: CfnTemplate._template_dict
    """
    return getattr(tpl, "_template_dict")


def test_tpl_load():
    src = {"Resources": {MAGIC_KEY: MAGIC_VALUE}}

    tpl = cfn.CfnTemplate('/').with_documents(src)
    assert src == td(tpl)

    tpl = cfn.CfnTemplate('/').with_documents(json.dumps(src))
    assert src == td(tpl)


def test_tpl_append():
    tpl = cfn.CfnTemplate({})

    tpl.with_documents({"Resources": {MAGIC_KEY: MAGIC_KEY}})
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_KEY

    tpl.with_documents({"Resources": {MAGIC_VALUE: MAGIC_VALUE}})
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_KEY
    assert td(tpl)["Resources"][MAGIC_VALUE] == MAGIC_VALUE

    tpl = cfn.CfnTemplate({})

    tpl.with_documents({"Resources": {MAGIC_KEY: MAGIC_KEY}})
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_KEY

    tpl.with_documents({"Resources": {MAGIC_KEY: MAGIC_VALUE}})
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_VALUE, "Should override"

    tpl = cfn.CfnTemplate({})

    tpl.with_documents(
        {"Resources": {MAGIC_KEY: MAGIC_KEY}},
        {"Resources": {MAGIC_KEY: MAGIC_VALUE}}
    )
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_VALUE, "Should override"

    tpl = cfn.CfnTemplate({})

    tpl.with_documents(
        {"Resources": {MAGIC_KEY: MAGIC_KEY}},
        {"Resources": {MAGIC_VALUE: MAGIC_VALUE}}
    )
    assert td(tpl)["Resources"][MAGIC_KEY] == MAGIC_KEY, "Should override"
    assert td(tpl)["Resources"][MAGIC_VALUE] == MAGIC_VALUE, "Should override"
