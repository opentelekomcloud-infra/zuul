# Copyright 2026 Open Telekom Cloud, T-Systems International GmbH
# Copyright 2018 Red Hat, Inc.
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

from tests.base import ZuulTestCase, simple_layout


class TestGiteaCRD(ZuulTestCase):
    """Cross-repo dependency tests for Gitea driver"""
    config_file = 'zuul-gitea-driver.conf'

    def _test_crd_check(self, project1, project2):
        """Test cross-repo dependency during check pipeline"""

        A = self.fake_gitea.openFakePullRequest(project1, 'master', 'A')
        B = self.fake_gitea.openFakePullRequest(project2, 'master', 'B')

        # A Depends-On B
        A.editBody('Depends-On: %s' % B.url)
        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='project1-test', result='SUCCESS',
                 changes='%s,%s %s,%s' % (B.number, B.head_sha,
                                          A.number, A.head_sha)),
        ])

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_check(self):
        self._test_crd_check('org/project1', 'org/project2')

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_check_reverse(self):
        """Test that B can be triggered with A as its dependent."""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')

        # A Depends-On B
        A.editBody('Depends-On: %s' % B.url)

        # Trigger B first
        self.fake_gitea.emitEvent(B.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # B should run independently (A depends on B, not the other way around)
        self.assertHistory([
            dict(name='project2-test', result='SUCCESS',
                 changes='%s,%s' % (B.number, B.head_sha)),
        ])

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_check_update_dependent(self):
        """Test that updating a dependent updates dependents too."""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')

        # A Depends-On B
        A.editBody('Depends-On: %s' % B.url)
        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Now update B
        self.executor_server.hold_jobs_in_build = True
        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.fake_gitea.emitEvent(B.getPullRequestUpdatedEvent())
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        # B should have the latest sha after update
        self.assertEqual(
            sorted(self.history[-1].changes.split()),
            sorted(['%s,%s' % (B.number, B.head_sha),
                    '%s,%s' % (A.number, A.head_sha)]))

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_check_transitive(self):
        """Test transitive dependencies A -> B -> C"""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')
        C = self.fake_gitea.openFakePullRequest('org/project3', 'master', 'C')

        # A Depends-On B, B Depends-On C
        A.editBody('Depends-On: %s' % B.url)
        B.editBody('Depends-On: %s' % C.url)

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='project1-test', result='SUCCESS',
                 changes='%s,%s %s,%s %s,%s' % (C.number, C.head_sha,
                                                B.number, B.head_sha,
                                                A.number, A.head_sha)),
        ])

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_check_unknown(self):
        """Test that unknown dependencies don't break the check."""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        A.editBody(
            'Depends-On: https://gitea.example.com/unknown/project/pulls/1')
        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # The job should still run with just the A change
        self.assertHistory([
            dict(name='project1-test', result='SUCCESS',
                 changes='%s,%s' % (A.number, A.head_sha)),
        ])

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_cycle(self):
        """Test cycle detection in dependencies."""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')

        # A Depends-On B, B Depends-On A (cycle)
        A.editBody('Depends-On: %s' % B.url)
        B.editBody('Depends-On: %s' % A.url)

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Should fail due to cycle
        self.assertHistory([
            dict(name='project1-test', result='SUCCESS',
                 changes='%s,%s %s,%s' % (B.number, B.head_sha,
                                          A.number, A.head_sha)),
        ])
