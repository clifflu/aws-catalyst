import boto3
import urllib2

from awscatalyst import aws

MAGIC = "somewhere_out_there"


def test_aws_get_region_env(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', MAGIC)
    assert aws.Aws.get_region() == MAGIC


def test_aws_get_region_url(monkeypatch):
    class MonkeyBotoSession(object):
        region_name = None

    class MonkeyUrlResponse(object):
        def read(self):
            return '{"region": "%s"}' % MAGIC

    monkeypatch.setattr(boto3, 'Session', lambda: MonkeyBotoSession())
    monkeypatch.setattr(urllib2, 'urlopen', lambda *a, **k: MonkeyUrlResponse())
    assert aws.Aws.get_region() == MAGIC

def test_aws_get_region_url(monkeypatch):
    class MonkeyBotoSession(object):
        region_name = None

    class MonkeyUrlResponse(object):
        def read(self):
            raise ValueError()

    monkeypatch.setattr(boto3, 'Session', lambda: MonkeyBotoSession())
    monkeypatch.setattr(urllib2, 'urlopen', lambda *a, **k: MonkeyUrlResponse())
    assert aws.Aws.get_region() is None
