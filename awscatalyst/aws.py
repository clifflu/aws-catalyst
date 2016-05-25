import boto3

class Aws(object):
    """
    """

    @staticmethod
    def get_region():
        return boto3.Session().region_name

    @classmethod
    def get_region_shortname(cls, s=None):
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

        s = s.lower() if s else cls.get_region()

        for sn, candidates in alternatives.items():
            if s in candidates:
                return sn

        return s
