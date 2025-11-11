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
import time
from unittest import mock

from zuul.driver.kubernetes.kubernetesendpoint import (
    KubernetesProviderEndpoint,
)

from tests.fake_kubernetes import (
    FakeCoreClient,
    FakeRbacClient,
    FakeDynamicClient,
)
from tests.base import (
    iterate_timeout,
    simple_layout,
    ZuulTestCase,
)
from tests.unit.test_cloud_driver import BaseCloudDriverTest


class BaseKubernetesDriverTest(ZuulTestCase):
    cloud_test_connection_type = 'kubectl'
    cloud_test_provider_name = 'kube-main'
    cloud_test_min_instances = 1
    is_openshift = False

    def setUp(self):
        self.initTestConfig()
        self.fake_core_client = FakeCoreClient()
        self.fake_rbac_client = FakeRbacClient()
        self.fake_dynamic_client = FakeDynamicClient(self.fake_core_client,
                                                     self.is_openshift)

        def _getClient(this):
            return (self.fake_core_client, self.fake_rbac_client,
                    self.fake_dynamic_client)

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

    @simple_layout('layouts/kubernetes/nodepool.yaml', enable_nodepool=True)
    def test_kubernetes_resource_cleanup(self):
        self.waitUntilSettled()
        self.launcher.cleanup_worker.INTERVAL = 1

        system_id = self.launcher.system.system_id
        tags = {
            'zuul_system_id': system_id,
            'zuul_node_uuid': '0000000042',
        }
        ns_body = {
            'apiVersion': 'v1',
            'kind': 'Namespace',
            'metadata': {
                'name': 'test',
                'labels': tags,
            }
        }
        self.fake_core_client.create_namespace(ns_body)
        self.assertEqual(2, len(self.fake_core_client.list_namespace().items))

        self.log.debug("Start cleanup worker")
        self.launcher.cleanup_worker.start()

        for _ in iterate_timeout(30, 'instance deletion'):
            if len(self.fake_core_client.list_namespace().items) == 1:
                break
            time.sleep(1)


class TestKubernetesDriverOpenShift(
        BaseKubernetesDriverTest, BaseCloudDriverTest):
    is_openshift = True

    def _assertProviderNodeAttributes(self, pnode):
        # Don't call the superclass here since it assumes IP connectivity.
        self.assertEqual(pnode.connection_type,
                         self.cloud_test_connection_type)
        if checks := self.test_config.driver.kubernetes.get('node_checks'):
            checks(self, pnode)

    @simple_layout('layouts/kubernetes/openshift.yaml', enable_nodepool=True)
    def test_kubernetes_node_lifecycle_openshift(self):
        self._test_node_lifecycle('debian-normal')

    @simple_layout('layouts/kubernetes/openshift.yaml', enable_nodepool=True)
    def test_kubernetes_resource_cleanup_openshift(self):
        self.waitUntilSettled()
        self.launcher.cleanup_worker.INTERVAL = 1

        system_id = self.launcher.system.system_id
        tags = {
            'zuul_system_id': system_id,
            'zuul_node_uuid': '0000000042',
        }
        proj_body = {
            'apiVersion': 'project.openshift.io/v1',
            'kind': 'ProjectRequest',
            'metadata': {
                'name': 'test',
                'labels': tags,
            }
        }
        projects = self.fake_dynamic_client.resources.get(
            api_version='project.openshift.io/v1', kind='ProjectRequest')
        projects.create(body=proj_body)

        def list_projects():
            projects = self.fake_dynamic_client.resources.get(
                api_version='v1', kind='Project')
            return projects.get().items

        self.assertEqual(2, len(list_projects()))

        self.log.debug("Start cleanup worker")
        self.launcher.cleanup_worker.start()

        for _ in iterate_timeout(30, 'instance deletion'):
            if len(list_projects()) == 1:
                break
            time.sleep(1)
