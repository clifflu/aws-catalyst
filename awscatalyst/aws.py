import boto3
import json
import urllib2

class Aws(object):
    """
    """
    TIMEOUT_MAGIC_URL = 1

    @classmethod
    def get_region_magic_url(cls):
        url = "http://169.254.169.254/latest/dynamic/instance-identity/document"
        try:
            return json.loads(urllib2.urlopen(url, timeout=cls.TIMEOUT_MAGIC_URL).read()).get('region')
        except (urllib2.HTTPError, urllib2.URLError, ValueError):
            pass

        return None

    @classmethod
    def get_region(cls):
        return boto3.Session().region_name or \
            cls.get_region_magic_url()

    @classmethod
    def get_region_shortname(cls, region_name=None):
        alternatives = {
            'use1': {'us-east-1', },
            'usw1': {'us-west-1', },
            'usw2': {'us-west-2', },
            'sae1': {'sa-east-1', },
            'apn1': {'ap-northeast-1', },
            'apn2': {'ap-northeast-2', },
            'aps1': {'ap-southeast-1', },
            'ap22': {'ap-southeast-2', },
            'euw1': {'eu-west-1', },
            'euc1': {'eu-central-1', },
        }

        region_name = region_name.lower() if region_name else cls.get_region()

        for shortname, candidates in alternatives.items():
            if region_name in candidates:
                return shortname

        return region_name
