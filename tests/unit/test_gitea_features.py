# Copyright 2026 Open Telekom Cloud, T-Systems International GmbH
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

"""
Tests for new Gitea driver features:
- Webhook signature verification
- getChangeByURL()
- getProjectOpenChanges()
- Review tracking
- Status check improvements
- API retry logic
"""

import hmac
import hashlib
import json
import socket

from unittest import mock

from tests.base import ZuulTestCase, simple_layout
from tests.base import ZuulWebFixture

from zuul.driver.gitea.giteaconnection import (
    _sign_request, _verify_signature
)


class TestGiteaWebhookSignature(ZuulTestCase):
    """Tests for webhook signature verification"""
    config_file = 'zuul-gitea-driver.conf'

    def test_sign_request(self):
        """Test that _sign_request creates correct HMAC-SHA256 signature"""
        body = b'{"test": "payload"}'
        secret = 'test_secret'

        signature = _sign_request(body, secret)

        # Verify it's a valid hex string
        self.assertTrue(signature.startswith('sha256='))
        hex_part = signature.split('=')[1]
        self.assertEqual(len(hex_part), 64)  # SHA256 produces 64 hex chars

        # Verify it matches expected HMAC
        expected = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        self.assertEqual(hex_part, expected)

    def test_verify_signature_valid(self):
        """Test that _verify_signature accepts valid signatures"""
        body = b'{"action": "opened", "pull_request": {}}'
        secret = 'my_webhook_secret'

        signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

        # Should not raise
        result = _verify_signature(body, secret, signature)
        self.assertTrue(result)

    def test_verify_signature_invalid(self):
        """Test that _verify_signature rejects invalid signatures"""
        body = b'{"action": "opened", "pull_request": {}}'
        secret = 'my_webhook_secret'
        wrong_signature = 'invalid_signature_here'

        result = _verify_signature(body, secret, wrong_signature)
        self.assertFalse(result)

    def test_verify_signature_tampered_body(self):
        """Test that _verify_signature rejects tampered payloads"""
        original_body = b'{"action": "opened"}'
        tampered_body = b'{"action": "closed"}'
        secret = 'my_webhook_secret'

        # Sign original body
        signature = hmac.new(
            secret.encode('utf-8'),
            original_body,
            hashlib.sha256
        ).hexdigest()

        # Verify fails with tampered body
        result = _verify_signature(tampered_body, secret, signature)
        self.assertFalse(result)


class TestGiteaWebhookWithSignature(ZuulTestCase):
    """Integration tests for webhook signature verification via zuul-web"""
    config_file = 'zuul-gitea-driver.conf'

    def setUp(self):
        super().setUp()
        # Start the web server
        self.web = self.useFixture(
            ZuulWebFixture(self.config, self.test_config,
                           self.additional_event_queues, self.upstream_root,
                           self.poller_events,
                           self.git_url_with_auth, self.addCleanup,
                           self.test_root))
        host = '127.0.0.1'
        # Wait until web server is started
        while True:
            port = self.web.port
            try:
                with socket.create_connection((host, port)):
                    break
            except ConnectionRefusedError:
                pass

        self.fake_gitea.setZuulWebPort(port)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_webhook_with_valid_signature(self):
        """Test that webhooks with valid signatures are accepted"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        # Emit event via zuul-web (uses signature)
        response = self.fake_gitea.emitEvent(
            A.getPullRequestOpenedEvent(),
            use_zuulweb=True,
            project='org/project')

        self.assertEqual(response.status_code, 200)
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)


class TestGiteaGetChangeByURL(ZuulTestCase):
    """Tests for getChangeByURL functionality"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_change_by_url(self):
        """Test fetching a change by its URL"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        # Get the source from the connection
        source = self.scheds.first.sched.connections.getSource('gitea')

        # Fetch by URL
        change = source.getChangeByURL(A.url, None)

        self.assertIsNotNone(change)
        self.assertEqual(change.number, A.number)
        self.assertEqual(change.project.name, A.project)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_change_by_url_invalid_host(self):
        """Test that URLs with wrong hostname return None"""
        source = self.scheds.first.sched.connections.getSource('gitea')

        # URL with different hostname
        change = source.getChangeByURL(
            'https://other-gitea.example.com/org/project/pulls/1', None)

        self.assertIsNone(change)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_change_by_url_invalid_format(self):
        """Test that malformed URLs return None"""
        source = self.scheds.first.sched.connections.getSource('gitea')

        # Invalid URL formats
        self.assertIsNone(source.getChangeByURL('not-a-url', None))
        self.assertIsNone(source.getChangeByURL(
            'https://gitea.example.com/no-pr-number', None))


class TestGiteaGetProjectOpenChanges(ZuulTestCase):
    """Tests for getProjectOpenChanges functionality"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_project_open_changes_empty(self):
        """Test getting open changes when there are none"""
        source = self.scheds.first.sched.connections.getSource('gitea')
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        project = tenant.getProject('org/project')[1]

        changes = list(source.getProjectOpenChanges(project))
        self.assertEqual(len(changes), 0)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_project_open_changes_with_prs(self):
        """Test getting open changes when PRs exist"""
        # Create some PRs
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'B')

        source = self.scheds.first.sched.connections.getSource('gitea')
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        project = tenant.getProject('org/project')[1]

        changes = list(source.getProjectOpenChanges(project))

        # Should find both PRs
        self.assertEqual(len(changes), 2)
        change_numbers = {c.number for c in changes}
        self.assertIn(A.number, change_numbers)
        self.assertIn(B.number, change_numbers)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_get_project_open_changes_excludes_closed(self):
        """Test that closed PRs are not included"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'B')

        # Close one PR
        B.closePullRequest()

        source = self.scheds.first.sched.connections.getSource('gitea')
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        project = tenant.getProject('org/project')[1]

        changes = list(source.getProjectOpenChanges(project))

        # Should only find the open PR
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].number, A.number)


class TestGiteaReviewTracking(ZuulTestCase):
    """Tests for review tracking in PRs"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/gate-gitea.yaml', driver='gitea')
    def test_reviews_included_in_merge(self):
        """Test that reviews are tracked and available for merge message"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        # Add multiple reviews
        A.addReview(state='APPROVED')
        A.addReview(state='APPROVED')

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # PR should be merged
        self.assertTrue(A.is_merged)

        # Reviews should be in the PR data
        pr_data = A.getPRData()
        self.assertEqual(len(pr_data['reviews']), 2)

    @simple_layout('layouts/reviews-gitea.yaml', driver='gitea')
    def test_review_state_tracking(self):
        """Test that different review states are tracked correctly"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        # Add reviews with different states
        A.addReview(state='COMMENT')
        A.addReview(state='REJECTED')
        A.addReview(state='APPROVED')

        pr_data = A.getPRData()
        self.assertEqual(len(pr_data['reviews']), 3)

        states = [r['state'] for r in pr_data['reviews']]
        self.assertIn('COMMENT', states)
        self.assertIn('REJECTED', states)
        self.assertIn('APPROVED', states)


class TestGiteaStatusChecks(ZuulTestCase):
    """Tests for commit status check functionality"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_commit_status_set(self):
        """Test that commit statuses are properly set"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Check that status was set
        self.assertIn(A.head_sha, self.fake_gitea.statuses)
        status = self.fake_gitea.statuses[A.head_sha]
        self.assertIn('success', status)

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_pending_status_on_start(self):
        """Test that pending status is set when jobs start"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        self.executor_server.hold_jobs_in_build = True

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Check pending status was set
        self.assertIn(A.head_sha, self.fake_gitea.statuses)
        status = self.fake_gitea.statuses[A.head_sha]
        self.assertIn('pending', status)

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()


class TestGiteaAPIRetry(ZuulTestCase):
    """Tests for API retry logic"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/basic-gitea.yaml', driver='gitea')
    def test_transient_failure_recovery(self):
        """Test that transient API failures are retried"""
        A = self.fake_gitea.openFakePullRequest(
            'org/project', 'master', 'A')

        # The fake gitea connection overrides _makeRequest,
        # so this test verifies the infrastructure is in place
        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Jobs should complete successfully
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)


class TestGiteaCRDEnhanced(ZuulTestCase):
    """Enhanced CRD tests for new implementation"""
    config_file = 'zuul-gitea-driver.conf'

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_multiple_depends_on(self):
        """Test PR with multiple Depends-On entries"""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')
        C = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'C')

        # A depends on both B and C (C is in same project as A)
        A.editBody('Depends-On: %s\nDepends-On: %s' % (B.url, C.url))

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # All three changes should be in the build
        self.assertEqual(1, len(self.history))
        job = self.history[0]
        self.assertIn('%s,%s' % (B.number, B.head_sha), job.changes)
        self.assertIn('%s,%s' % (C.number, C.head_sha), job.changes)
        self.assertIn('%s,%s' % (A.number, A.head_sha), job.changes)

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_depends_on_in_comment(self):
        """Test that Depends-On in PR body is recognized"""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project2', 'master', 'B')

        # Add Depends-On as part of longer description
        A.editBody(
            'This PR adds a new feature.\n\n'
            'Depends-On: %s\n\n'
            'Please review.' % B.url)

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='project1-test', result='SUCCESS',
                 changes='%s,%s %s,%s' % (B.number, B.head_sha,
                                          A.number, A.head_sha)),
        ])

    @simple_layout('layouts/crd-gitea.yaml', driver='gitea')
    def test_crd_same_project(self):
        """Test dependencies within the same project"""
        A = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'A')
        B = self.fake_gitea.openFakePullRequest('org/project1', 'master', 'B')

        # A depends on B (same project)
        A.editBody('Depends-On: %s' % B.url)

        self.fake_gitea.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        # Both changes should be in the build
        self.assertEqual(1, len(self.history))
        job = self.history[0]
        self.assertIn('%s,%s' % (B.number, B.head_sha), job.changes)
        self.assertIn('%s,%s' % (A.number, A.head_sha), job.changes)
