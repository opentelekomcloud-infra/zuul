# Copyright 2022, 2024 Acme Gating, LLC
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
import os

from zuul.zk.components import (
    ComponentRegistry,
)
from tests.base import (
    ZuulTestCase,
    gerrit_config,
    simple_layout,
    iterate_timeout,
    model_version,
    FIXTURE_DIR,
)
from zuul import model
from zuul.zk.locks import management_queue_lock


class TestModelUpgrade(ZuulTestCase):
    tenant_config_file = "config/single-tenant/main-model-upgrade.yaml"
    scheduler_count = 1

    def getJobData(self, tenant, pipeline):
        item_path = f'/zuul/tenant/{tenant}/pipeline/{pipeline}/item'
        count = 0
        for item in self.zk_client.client.get_children(item_path):
            bs_path = f'{item_path}/{item}/buildset'
            for buildset in self.zk_client.client.get_children(bs_path):
                data = json.loads(self.getZKObject(
                    f'{bs_path}/{buildset}/job/check-job'))
                count += 1
                yield data
        if not count:
            raise Exception("No job data found")

    @model_version(0)
    @simple_layout('layouts/simple.yaml')
    def test_model_upgrade_0_1(self):
        component_registry = ComponentRegistry(self.zk_client)
        self.assertEqual(component_registry.model_api, 0)

        # Upgrade our component
        self.model_test_component_info.model_api = 1

        for _ in iterate_timeout(30, "model api to update"):
            if component_registry.model_api == 1:
                break

    @model_version(33)
    def test_model_upgrade_33_34(self):

        attrs = model.SystemAttributes.fromDict({
            "use_relative_priority": True,
            "max_hold_expiration": 7200,
            "default_hold_expiration": 3600,
            "default_ansible_version": "X",
            "web_root": "/web/root",
            "websocket_url": "/web/socket",
            "web_status_url": "ignored",
        })

        attr_dict = attrs.toDict()
        self.assertIn("web_status_url", attr_dict)
        self.assertEqual(attr_dict["web_status_url"], "")

        # Upgrade our component
        self.model_test_component_info.model_api = 34

        component_registry = ComponentRegistry(self.zk_client)
        for _ in iterate_timeout(30, "model api to update"):
            if component_registry.model_api == 34:
                break

        attr_dict = attrs.toDict()
        self.assertNotIn("web_status_url", attr_dict)


class TestModelUpgradeGerritCircularDependencies(ZuulTestCase):
    config_file = "zuul-gerrit-github.conf"
    tenant_config_file = "config/circular-dependencies/main.yaml"

    @model_version(31)
    @gerrit_config(submit_whole_topic=True)
    def test_model_31_32(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project1', "master", "A",
                                           topic='test-topic')
        B = self.fake_gerrit.addFakeChange('org/project2', "master", "B",
                                           topic='test-topic')

        A.addApproval("Code-Review", 2)
        B.addApproval("Code-Review", 2)
        B.addApproval("Approved", 1)

        self.fake_gerrit.addEvent(A.addApproval("Approved", 1))
        self.waitUntilSettled()

        first = self.scheds.first
        second = self.createScheduler()
        second.start()
        self.assertEqual(len(self.scheds), 2)
        for _ in iterate_timeout(10, "until priming is complete"):
            state_one = first.sched.local_layout_state.get("tenant-one")
            if state_one:
                break

        for _ in iterate_timeout(
                10, "all schedulers to have the same layout state"):
            if (second.sched.local_layout_state.get(
                    "tenant-one") == state_one):
                break

        self.model_test_component_info.model_api = 32
        with first.sched.layout_update_lock, first.sched.run_handler_lock:
            self.fake_gerrit.addEvent(A.addApproval("Approved", 1))
            self.waitUntilSettled(matcher=[second])

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()
        self.assertEqual(A.data["status"], "MERGED")
        self.assertEqual(B.data["status"], "MERGED")


class TestSemaphoreReleaseUpgrade(ZuulTestCase):
    tenant_config_file = 'config/global-semaphores/main.yaml'

    @model_version(32)
    def test_model_32(self):
        # This tests that a job finishing in one tenant will correctly
        # start a job in another tenant waiting on the semaphore.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        B = self.fake_gerrit.addFakeChange('org/project2', 'master', 'B')
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        self.assertHistory([])
        self.assertBuilds([
            dict(name='test-global-semaphore', changes='1,1'),
        ])

        # Block tenant management event queues so we know that the
        # semaphore release events are dispatched via the pipeline
        # trigger event queue.
        with (management_queue_lock(self.zk_client, "tenant-one"),
              management_queue_lock(self.zk_client, "tenant-two")):

            self.executor_server.hold_jobs_in_build = False
            self.executor_server.release()
            self.waitUntilSettled()

            self.assertHistory([
                dict(name='test-global-semaphore',
                     result='SUCCESS', changes='1,1'),
                dict(name='test-global-semaphore',
                     result='SUCCESS', changes='2,1'),
            ], ordered=False)


class TestOidcSecretSupport(ZuulTestCase):
    tenant_config_file = 'config/secrets/main.yaml'

    @model_version(34)
    def test_model_34(self):
        self._run_test()

    @model_version(35)
    def test_model_35(self):
        self._run_test()

    def _run_test(self):
        with open(os.path.join(FIXTURE_DIR,
                               'config/secrets/git/',
                               'org_project2/zuul-secret.yaml')) as f:
            config = f.read()
        file_dict = {'zuul.yaml': config}

        A = self.fake_gerrit.addFakeChange('org/project2', 'master', 'A',
                                           files=file_dict)
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertEqual(A.reported, 1, "A should report success")
        self.assertHistory([
            dict(name='project2-secret', result='SUCCESS', changes='1,1'),
        ])
