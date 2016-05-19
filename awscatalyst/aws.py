import boto3

class Aws(object):
    """
    """

    @staticmethod
    def get_region():
        return boto3.Session().region_name
