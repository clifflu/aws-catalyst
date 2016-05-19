from __future__ import print_function

import os.path
import shutil

from datetime import datetime
from subprocess import call
from util import render

from util import tempdir
from s3 import S3


class LambdaBuilder(object):
    """
    Create and upload ZIP archive to S3 for AWS lambda function from CFN.
    """

    def __init__(self, *zip_args, **zip_kwargs):
        self._zip_args = zip_args
        self._zip_kwargs = zip_kwargs
        self._created = {}  # "filename": "file body"
        self._copied = {}  # "filename": "source filename"

    def create_file(self, file_body, path, render_mapping=None):
        print("  * created `%s` from LambdaBuilder" % path)
        self._created[path] = file_body if render_mapping is None else render(file_body, render_mapping)
        return self

    def append(self, file_name, path=None, render_mapping=None):
        assert os.path.exists(file_name)
        assert os.path.isfile(file_name) or not render_mapping
        path = path or os.path.basename(file_name)

        if render_mapping:
            with open(file_name) as fp:
                self.create_file(fp.read(), path, render_mapping)
        else:
            print("  * copied `%s` from LambdaBuilder" % path)
            self._copied[path] = file_name

        return self

    def upload_to_s3(self, bucket_name, prefix=None, key_name=None):
        """
        Upload composed archive (.zip) to S3

        :param str prefix: without leading and trailing slashes
        """
        s3 = S3()
        prefix = prefix or "lambda-src"
        key_name = key_name or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ.zip")
        uploaded_path = "%s/lambda-src/%s" % (prefix, key_name)

        with tempdir() as td:
            archive_name = self._compile(td.path, key_name)
            s3.upload(archive_name, bucket_name, uploaded_path)

        return uploaded_path

    def _compile(self, temp_path, archive_name):
        """
        Compiles to an zip archive and return its fullpath.
        Uses temp_path as working directory.

        :param temp_path:
        :param archive_name:
        :return: Fullpath to archive
        """
        old_umask = os.umask(0o022)

        build_path = os.path.join(temp_path, "build")
        os.mkdir(build_path, 0o755)

        archive_name = os.path.join(temp_path, archive_name)
        try:
            for filename, body in self._created.items():
                filename = os.path.join(build_path, filename)

                with open(filename, "wb") as fp:
                    fp.write(body)

            for filename, source in self._copied.items():
                filename = os.path.join(build_path, filename)

                if os.path.isdir(source):
                    shutil.copytree(source, filename)
                else:
                    shutil.copy(source, filename)

            call(["chmod", "-R", "go+rX", temp_path])
            call(["zip", "-qr", archive_name, ".", "-x", ".*", "*/.*", "__pycache__", "*/__pycache__"], cwd=build_path)

        finally:
            os.umask(old_umask)

        return archive_name
