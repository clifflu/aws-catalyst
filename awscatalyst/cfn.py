"""
Helper functions and wrapper classes to AWS CloudFormation.
"""
from __future__ import print_function

import boto3
import botocore.exceptions
import copy
import json
import os.path
import sys
import time

from aws import Aws
from s3 import S3
from exceptions import StackExists


class CfnStack(Aws):
    """
    Avatar to AWS CloudFormation
    """
    QUERY_DELAY_SEC = 2

    def __init__(self, stack_name, region_name=None):
        """
        :param str stack_name: Name to the CFN Stack
        :param cfn_r: CFN Resource or None
        """
        self._cfn = boto3.resource('cloudformation', region_name=region_name)
        self._stack_name = stack_name
        self._stack = self._cfn.Stack(stack_name)

        self._capabilities = set()
        self._parameters = {}  # key: {cond: value}, hydrated to {"Key": key, cond: value}
        self._tags = {}

    def delete(self, cleanup_s3=False):
        """
        Delete the stack no matter it exists or not.
        """

        try:
            if cleanup_s3:
                self._stack.load()

                s3 = S3()
                for res in self._stack.resource_summaries.iterator():
                    if res.resource_type != "AWS::S3::Bucket":
                        continue

                    s3.cleanup_bucket(res.physical_resource_id)
        except botocore.exceptions.ClientError:
            pass

        self._stack.delete()

    def aws_capabilities(self):
        """
        Gets `capabilities`, valid values = {"CAPABILITY_IAM"}.
        @see http://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateStack.html

        :return: list of capabilities
        """
        return list(self._capabilities)

    def with_capability(self, capability):
        """
        Enable capability

        :param str capability: capability
        :return: self
        :rtype: CfnStack
        """
        self._capabilities.add(str(capability))
        return self

    def without_capability(self, capability):
        """
        Disable capability, proceed silently if capability doesn't exist.
        Note: stack update may fail if required capability revoked in later updates.

        :param str capability: capability
        :return: self
        :rtype: CfnStack
        """
        try:
            self._capabilities.remove(str(capability))
        except KeyError:
            pass

        return self

    def aws_parameters(self):
        """
        Gets parameters in AWS Cloudformation format::

            [
                {
                    "ParameterKey": "somekey",
                    "ParameterValue": "somevalue"
                },
                {
                    "ParameterKey": "anotherkey",
                    "UsePreviousValue": True
                },
                ...
            ]

        :return: Parameters
        :rtype: list(dict)
        """
        def merge_dict(dict1, dict2):
            return dict(dict1.items() + dict2.items())

        return [
            merge_dict({"ParameterKey": k}, v) for k, v in self._parameters.items()
        ]

    def with_parameter(self, key, value=None):
        """
        Append parameter `key` to the list. Value would be `value` if it's not None, or `UsePreviousValue` otherwise.
        CfnStack guarantees Parameter Key uniqueness by storing them as dict{key: {cond: value}} internally.
        Therefore, updating a known parameter overrides it.

        :param key: Parameter key
        :param None|str value: Parameter value if not None, or trigger UsePreviousValue otherwise
        :return: self
        :rtype: CfnStack
        """
        key = str(key)

        if value is None:
            self._parameters[key] = {"UsePreviousValue": True}
        else:
            self._parameters[key] = {"ParameterValue": str(value)}

        return self

    def without_parameter(self, key):
        """
        Disable parameter, returns silently if key doesn't exist.

        :param str key: Parameter key
        :return: self
        :rtype: CfnStack
        """
        try:
            del self._parameters[str(key)]
        except KeyError:
            pass

        return self

    def carry_over_parameters(self):
        """
        Updates parameter list, so that all of them UsePreviousValue.
        Called after updating stack successfully.
        """
        for k in self._parameters:
            self.with_parameter(k, None)

    def aws_tags(self):
        """
        Gets tags in AWS Cloudformation format::

            [
                {"Key": key, "Value": value},
                ...
            ]

        :return: tags
        :rtype: list(dict)
        """
        return [{"Key": k, "Value": v} for k, v in self._tags.items()]

    def with_tag(self, key, value):
        """
        Append tag

        :param str key: Tag key
        :param str value: Tag value
        :return: self
        :rtype: CfnStack
        """
        self._tags[str(key)] = str(value)
        return self

    def without_tag(self, key):
        """
        Remove tag

        :param str key: Tag key
        :return: self
        :rtype: CfnStack
        """
        try:
            del self._tags[str(key)]
        except KeyError:
            pass

        return self

    def create(self, template, **kwargs):
        """
        @see cloudformation.create_stack()

        :param template:
        :param kwargs:
        :return: cloudformation stack
        """
        try:
            self._stack = self._cfn.create_stack(
                StackName=self._stack_name,
                TemplateBody=str(template),
                Parameters=self.aws_parameters(),
                Capabilities=self.aws_capabilities(),
                Tags=self.aws_tags(),
                **kwargs
            )
            self.carry_over_parameters()

        except botocore.exceptions.ClientError as e:
            if e.response.get('Error', {}).get('Code', '') == "AlreadyExistsException":
                raise StackExists()
            else:
                raise e

        return self

    def update(self, template=None, **kwargs):
        """
        @see cloudformation.update_stack()
        Calls CfnStack.carry_over_parameters if update() succeeds.

        :param template:
        :param kwargs:
        :return: cloudformation stack
        """
        params = {
            "Parameters": self.aws_parameters(),
            "Capabilities": self.aws_capabilities(),
            "Tags": self.aws_tags(),
        }

        if template is None:
            params.update({"UsePreviousTemplate": True})
        else:
            params.update({"TemplateBody": str(template)})

        params.update(kwargs)

        self._stack.update(**params)
        self.carry_over_parameters()

        return self

    def wait(self):
        """
        Waits and blocks until stack is in resolved state (*_COMPLETE).
        """
        if not self._stack:
            raise Exception("No stack available")

        stack = self._stack
        state_ready = (
                    'CREATE_COMPLETE',
                    'UPDATE_COMPLETE',
                    'UPDATE_ROLLBACK_COMPLETE')

        state_in_progress = (
                    'UPDATE_IN_PROGRESS',
                    'CREATE_IN_PROGRESS',
                    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS')

        state_fail = (
            "UPDATE_ROLLBACK_IN_PROGRESS",
        )

        while True:
            # The infinite loop, return on success, throw exception on error, pass to wait
            time.sleep(self.QUERY_DELAY_SEC)
            stack.load()
            if stack.stack_status in state_ready:
                # Completed
                break
            elif stack.stack_status in state_in_progress:
                pass
            elif stack.stack_status in state_fail:
                print("Stack operation failed (%s), try again later" % stack.stack_status)
                sys.exit(1)
            else:
                raise Exception("Unknown state: %s" % stack.stack_status)

        return self

    @property
    def outputs(self):
        return {i['OutputKey']: i['OutputValue'] for i in self._stack.outputs}

    @staticmethod
    def list(region_name=None):
        """
        Generator to list all cloudformation stacks

        :return: generator of Stacks
        :rtype: list(Stack)
        """
        cfn = boto3.resource('cloudformation', region_name=region_name)
        for stack in cfn.stacks.all():
            yield stack

    @classmethod
    def wait_for_stack(cls, stack_name):
        """
        Waits and blocks until stack is in resolved state (*_COMPLETE).
        """
        stack = CfnStack(stack_name)
        stack.wait()


class CfnTemplate(object):
    """
    Handles Cloud Formation Templates
    """
    KEYS_IGNORE = ('AWSTemplateFormatVersion',)
    KEYS_OVERWRITE = ('Description',)
    KEYS_KEY_MERGE = ('Parameters', 'Mappings', 'Conditions', 'Resources', 'Outputs')

    def load_template(self, f, deep_copy_dict=False):
        """
        Load template from f

        :param f: json string, plain file (json), and native data structure
        :param deep_copy_dict:
        :return: template as dict / list
        """
        if isinstance(f, str):
            try:
                return json.loads(f)
            except ValueError:
                pass

            # @TODO: Secure f ?
            f = os.path.join(self._template_path, f)
            if not f.endswith(".json"):
                f += ".json"

            with open(f) as fp:
                return json.load(fp)
        elif isinstance(f, file):
            return json.load(f)
        elif deep_copy_dict:
            return copy.deepcopy(f)

        return f

    def compose_template(self, base, *extends):
        """
        Loads `base` and `extend` respectively and combine them based on specifications
        on AWS CloudFormation templates. Deep copy on `base` if it's a dict.

        Doesn't rewind when base / extend is file.

        :param str|file|dict base: Base object or filename
        :param list[str|file|dict] extends: Extend object or filename

        :return: Combined object
        :rtype: dict
        """

        output = self.load_template(base, deep_copy_dict=True)

        for extend in extends:
            self.extend_template(output, extend)

        return output

    def extend_template(self, base, extend):
        """
        Extend properties from extend to base and return.
        Note: base is changed in the process.
        """
        base, extend = self.load_template(base), self.load_template(extend)

        if not base:
            base.update(extend)
            return base

        for key, value in extend.items():
            if key in self.KEYS_IGNORE:
                pass
            elif key in self.KEYS_OVERWRITE:
                base[key] = value
            elif key in self.KEYS_KEY_MERGE:
                for _k, _v in value.items():
                    base.setdefault(key, {})[_k] = _v
            else:
                print("Unknown key `%s` found.")

        return base

    def __init__(self, template_path, mapping=None):
        """
        :param template_path: Where to lookup templates
        :param mapping: Mapping table to render table
        """
        self._template_path = template_path
        self._template_dict = {}
        self._mapping = mapping or {}

    def with_documents(self, *templates):
        """
        Append templates to itself.
        @see CfnTemplate.load_template for supported formats.

        :param templates: templates
        :return: self
        :rtype: CfnTemplate
        """
        for template in templates:
            self.extend_template(self._template_dict, self.load_template(template))

        return self

    def with_mapping_key(self, key, value):
        """
        Append key=>value to mapping table, update if key already exists.

        :param key:
        :param value:
        :return: self
        :rtype: CfnTemplate
        """
        self._mapping[key] = value
        return self

    def without_mapping_key(self, key):
        """
        Remove key from mapping table, return silently if key doesn't exist.

        :param key:
        :return: self
        :rtype: CfnTemplate
        """
        try:
            del self._mapping[key]
        except KeyError:
            pass
        return self

    def with_updated_mapping(self, mapping):
        """
        Update multiple k-v mappings at once

        :param mapping:
        :return: self
        :rtype: CfnTemplate
        """
        self._mapping.update(mapping)
        return self

    def patch_resources(self, **kwargs):
        res_name, res_type, property, new_value = (kwargs.get(n, False) for n in ('Name', 'Type', 'Property', 'NewValue'))

        try:
            assert bool(res_name) ^ bool(res_type)
        except AssertionError:
            raise TypeError("keyword argment `Name` and `Type` are mutually exclusive.")

        try:
            assert property and new_value
        except AssertionError:
            raise TypeError("keyword argument `Property` and `NewValue` required.")

        if res_name:
            if res_name not in self._template_dict['Resources']:
                raise KeyError('resource `%s` not found' % res_name)

            self._template_dict['Resources'][res_name]['Properties'][property] = new_value
            return self

        for res_value in self._template_dict.get('Resources', {}).values():
            if res_value['Type'] == res_type:
                res_value['Properties'][property] = new_value

        return self

    def as_json(self, indent=2):
        """
        Return merged template in json without mapping

        :param indent:
        :return: template as json
        :rtype: str
        """
        from util import render

        return render(
            template=json.dumps(self._template_dict, indent=indent),
            mapping=self._mapping
        )

    def __str__(self):
        return self.as_json()
