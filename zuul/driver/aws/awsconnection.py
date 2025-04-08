# Copyright 2024 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging

import boto3
from botocore.exceptions import BotoCoreError

from zuul.connection import BaseConnection


class AwsConnection(BaseConnection):
    driver_name = 'aws'
    log = logging.getLogger("zuul.AwsConnection")

    def __init__(self, driver, connection_name, connection_config):
        super().__init__(driver, connection_name, connection_config)

        # Users can provide credentials directly in zuul.conf, or via
        # standard AWS_ environment variables or locations.
        self.access_key_id = self.connection_config.get('access_key_id')
        self.secret_access_key = self.connection_config.get(
            'secret_access_key')
        # Rate limit: requests/second
        self.rate = self.connection_config.get('rate', 2)

        try:
            session = boto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
            sts = session.client("sts")
            sts.get_caller_identity()
        except BotoCoreError as exc:
            raise Exception("AWS credentials not found") from exc
