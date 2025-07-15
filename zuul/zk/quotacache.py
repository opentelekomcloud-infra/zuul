# Copyright 2025 Acme Gating, LLC
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

import json
import logging
import os
import time
import urllib.parse

from kazoo.exceptions import (
    BadVersionError,
    NodeExistsError,
)

from zuul import model
from zuul.zk.cache import ZuulTreeCache
from zuul.zk.zkobject import ZKObject, ZKContext


class ZKQuotaInfo(ZKObject):
    def __init__(self):
        super().__init__()

    def getPath(self):
        if self.resource is None:
            return f'zuul/endpoint/{self.endpoint}/quota/limit'
        return (f'zuul/endpoint/{self.endpoint}/quota/'
                f'resource/{self.resource}')

    def serialize(self, context):
        data = {
            'quota': self.quota,
        }
        return json.dumps(data, sort_keys=True).encode("utf8")


class QuotaCache(ZuulTreeCache):
    """Stores endpoint quota information in ZK

    This stores two types of information: the overall quota limits of
    the endpoint, and resource usage for instance types, etc.

    The overall quota usage is expected to change very infrequently,
    and the resource usage even less (never).  To that end, any writes
    that fail due to concurrent modifications are simply ignored under
    the assumption that another launcher is refreshing the data at the
    same time.
    """

    log = logging.getLogger('zuul.QuotaCache')

    def __init__(self, client, endpoint_name):
        self.endpoint = urllib.parse.quote_plus(endpoint_name)
        root = f'/zuul/endpoint/{self.endpoint}/quota'
        resource_path = os.path.join(root, 'resource')
        super().__init__(client, root, async_worker=False)
        self.zk_client.client.ensure_path(resource_path)
        self.last_set_limits = None

    def objectFromRaw(self, key, data, zstat):
        if len(key) == 2:
            resource = key[1]
        else:
            resource = None
        obj = ZKQuotaInfo._fromRaw(data, zstat, None)
        obj._set(endpoint=self.endpoint,
                 resource=resource)
        return obj

    def updateFromRaw(self, obj, key, data, zstat):
        obj._updateFromRaw(data, zstat, None)

    def parsePath(self, path):
        parts = path.split('/')
        parts = parts[5:]
        key = None
        if len(parts) == 1 and parts[0] == 'limit':
            key = ('limit',)
        if len(parts) == 2 and parts[0] == 'resource':
            key = ('resource', parts[1])
        # We should fetch if we have a matching key
        return (key, bool(key))

    def getLimits(self):
        obj = self._cached_objects.get(('limit',))
        return model.QuotaInformation(**obj.quota)

    def getResource(self, resource):
        obj = self._cached_objects.get(('resource', resource))
        return model.QuotaInformation(**obj.quota)

    def createZKContext(self):
        return ZKContext(self.zk_client, None, None, self.log)

    def setLimits(self, quota_info):
        path = os.path.join(self.root, 'limit')
        key = ('limit',)
        obj = self._cached_objects.get(key)
        context = self.createZKContext()
        try:
            if obj:
                obj.updateAttributes(context, quota=quota_info.quota)
            else:
                obj = ZKQuotaInfo.new(context,
                                      quota=quota_info.quota,
                                      endpoint=self.endpoint,
                                      resource=None)
            self.last_set_limits = time.time()
        except (BadVersionError, NodeExistsError) as exc:
            self.log.debug("Skipping update of %s: %s", path, exc)

    def setResource(self, resource, quota_info):
        path = os.path.join(self.root, 'resource')
        key = ('resource', resource)
        obj = self._cached_objects.get(key)
        context = self.createZKContext()
        try:
            if obj:
                obj.updateAttributes(quota=quota_info.quota)
            else:
                obj = ZKQuotaInfo.new(context,
                                      quota=quota_info.quota,
                                      endpoint=self.endpoint,
                                      resource=resource)
        except (BadVersionError, NodeExistsError) as exc:
            self.log.debug("Skipping update of %s: %s", path, exc)
