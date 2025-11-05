# Copyright 2024-2025 Acme Gating, LLC
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

import contextlib
from unittest import mock

from zuul.driver.kubernetes.kubernetesendpoint import (
    KubernetesProviderEndpoint,
)

from tests.fake_kubernetes import (
    FakeCoreClient,
    FakeRbacClient,
)
from tests.base import (
    ZuulTestCase,
    simple_layout,
)
from tests.unit.test_cloud_driver import BaseCloudDriverTest


class BaseKubernetesDriverTest(ZuulTestCase):
    cloud_test_connection_type = 'kubectl'
    cloud_test_provider_name = 'kube-main'
    cloud_test_min_instances = 1

    def setUp(self):
        self.initTestConfig()
        self.fake_core_client = FakeCoreClient()
        self.fake_rbac_client = FakeRbacClient()

        def _getClient(this):
            return (self.fake_core_client, self.fake_rbac_client)

        self.patch(KubernetesProviderEndpoint, '_getClient',
                   _getClient)

        super().setUp()

    @contextlib.contextmanager
    def _block_futures(self):
        with (mock.patch(
                'zuul.driver.kubernetes.kubernetesendpoint.'
                'KubernetesProviderEndpoint._completeApi', return_value=None)):
            yield


class TestKubernetesDriver(BaseKubernetesDriverTest, BaseCloudDriverTest):
    def _assertProviderNodeAttributes(self, pnode):
        # Don't call the superclass here since it assumes IP connectivity.
        self.assertEqual(pnode.connection_type,
                         self.cloud_test_connection_type)
        if checks := self.test_config.driver.kubernetes.get('node_checks'):
            checks(self, pnode)

    @simple_layout('layouts/kubernetes/nodepool.yaml', enable_nodepool=True)
    def test_kubernetes_node_lifecycle(self):
        self._test_node_lifecycle('debian-normal')

    @simple_layout('layouts/kubernetes/more.yaml', enable_nodepool=True)
    def test_kubernetes_node_lifecycle_more(self):
        # Test with more options than the normal test
        secret = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'type': 'kubernetes.io/dockerconfigjson',
            'metadata': {
                'name': 'testsecret',
            },
            'data': 'something',
        }
        self.fake_core_client.create_namespaced_secret('default', secret)
        self._test_node_lifecycle('debian-normal')

    @simple_layout('layouts/kubernetes/resource-limits.yaml',
                   enable_nodepool=True)
    def test_kubernetes_resource_limits(self):
        self._test_quota('debian-normal')
