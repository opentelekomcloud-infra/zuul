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

"""Tests for gating on Gitea commit statuses.

Background (docs/doc-exports#1945, 2026-09-07): branch protection requires
the ``gitea/check`` status on the head, gate ``supercedes: check``, and Gitea
sends no webhook when a status is created. A PR approved and labelled before
its check finished entered gate, passed, and Gitea refused the merge; nothing
re-triggered gate and nothing was reported. These tests pin the three parts
of the fix:

* a real ``GiteaRefFilter`` so a pipeline can ``require`` a status;
* a synthesized ``gt_pull_request``/``status`` trigger event when Zuul posts a
  status, so a pipeline can trigger on ``zuul:gitea/check:success``;
* a PR comment when the merge is refused.
"""

import types
import unittest
from unittest import mock

from zuul.driver.gitea.giteaconnection import GiteaConnection, GiteaShaCache
from zuul.driver.gitea.giteamodel import (
    GiteaEventFilter, GiteaRefFilter, GiteaTriggerEvent, PullRequest)
from zuul.driver.gitea.giteareporter import GiteaReporter
from zuul.driver.util import make_regex
from zuul.exceptions import MergeFailure


SHA = "9a09f0324fa7a1a4197bb4385eaef81b4ae4d219"


class FakeProject:
    name = "docs/doc-exports"
    connection_name = "gitea-vm"


class FakeParseContext:
    """make_regex only needs an object with accumulate_errors."""
    def accumulate_errors(self):
        import contextlib
        return contextlib.nullcontext()


def make_pr(**attrs):
    pr = PullRequest(FakeProject())
    pr.number = 1945
    pr.patchset = SHA
    pr.open = True
    pr.is_current_patchset = True
    for k, v in attrs.items():
        setattr(pr, k, v)
    return pr


def make_connection():
    conn = GiteaConnection.__new__(GiteaConnection)
    conn.log = mock.Mock()
    conn.connection_name = "gitea-vm"
    conn.canonical_hostname = "gitea.example.com"
    conn.sched = mock.Mock()
    conn._sha_pr_cache = GiteaShaCache()
    conn._api_user_login = "zuul"
    conn._makeRequest = mock.Mock(return_value=None)
    return conn


class TestGiteaRefFilter(unittest.TestCase):

    def test_require_status_matches_latest_check_success(self):
        f = GiteaRefFilter.requiresFromConfig(
            "gitea-vm", {"status": "zuul:gitea/check:success"})
        self.assertTrue(f.matches(make_pr(
            status=["zuul:gitea/gate:pending", "zuul:gitea/check:success"])))

    def test_require_status_rejects_missing_or_pending(self):
        f = GiteaRefFilter.requiresFromConfig(
            "gitea-vm", {"status": "zuul:gitea/check:success"})
        # only the old tenant's context on the head (the #1945 shape)
        self.assertFalse(f.matches(make_pr(status=["zuul:gl/check:success"])))
        self.assertFalse(f.matches(make_pr(
            status=["zuul:gitea/check:pending"])))
        self.assertFalse(f.matches(make_pr(status=[])))

    def test_require_open_label_approved(self):
        f = GiteaRefFilter.requiresFromConfig(
            "gitea-vm", {"open": True, "label": "gate", "approved": True})
        self.assertTrue(f.matches(make_pr(labels=["gate"], approved=True)))
        self.assertFalse(f.matches(make_pr(labels=[], approved=True)))
        self.assertFalse(f.matches(make_pr(labels=["gate"], approved=False)))
        self.assertFalse(f.matches(make_pr(labels=["gate"], approved=True,
                                           open=False)))

    def test_reject_status(self):
        f = GiteaRefFilter.rejectFromConfig(
            "gitea-vm", {"status": "zuul:gitea/check:failure"})
        self.assertTrue(f.matches(make_pr(status=["zuul:gitea/check:success"])))
        self.assertFalse(f.matches(make_pr(status=["zuul:gitea/check:failure"])))

    def test_source_returns_filters(self):
        from zuul.driver.gitea.giteasource import GiteaSource
        src = GiteaSource.__new__(GiteaSource)
        src.connection = types.SimpleNamespace(connection_name="gitea-vm")
        filters = src.getRequireFilters({"status": "x:y:z"}, None)
        self.assertEqual(1, len(filters))
        self.assertEqual(["x:y:z"], filters[0].required_statuses)
        filters = src.getRejectFilters({"label": "wip"}, None)
        self.assertEqual(["wip"], filters[0].reject_labels)


class TestGiteaStatusTrigger(unittest.TestCase):

    def _filter(self, status_pattern):
        pc = FakeParseContext()
        return GiteaEventFilter(
            connection_name="gitea-vm", trigger=None,
            types=[make_regex("gt_pull_request", pc)],
            actions=[make_regex("status", pc)],
            statuses=[make_regex(status_pattern, pc)])

    def _event(self, status):
        e = GiteaTriggerEvent()
        e.connection_name = "gitea-vm"
        e.type = "gt_pull_request"
        e.action = "status"
        e.status = status
        return e

    def test_status_trigger_matches_check_success_only(self):
        f = self._filter("zuul:gitea/check:success")
        self.assertTrue(f.matches(self._event("zuul:gitea/check:success"),
                                  None))
        self.assertFalse(f.matches(self._event("zuul:gitea/gate:success"),
                                   None))
        self.assertFalse(f.matches(self._event("zuul:gitea/check:failure"),
                                   None))
        self.assertFalse(f.matches(self._event(None), None))

    def test_event_status_survives_serialization(self):
        e = self._event("zuul:gitea/check:success")
        e.project_name = "docs/doc-exports"
        e.change_number = 1945
        d = e.toDict()
        e2 = GiteaTriggerEvent()
        e2.updateFromDict(d)
        self.assertEqual("zuul:gitea/check:success", e2.status)
        self.assertEqual("status", e2.action)


class TestSetCommitStatusEmitsEvent(unittest.TestCase):

    def test_success_status_emits_event_for_known_change(self):
        conn = make_connection()
        change = make_pr(branch="main")
        conn.setCommitStatus("docs/doc-exports", SHA, "success",
                             url="http://z/", description="d",
                             context="gitea/check", change=change)
        conn.sched.addTriggerEvent.assert_called_once()
        driver_name, event = conn.sched.addTriggerEvent.call_args[0]
        self.assertEqual("gitea", driver_name)
        self.assertEqual("gt_pull_request", event.type)
        self.assertEqual("status", event.action)
        self.assertEqual("zuul:gitea/check:success", event.status)
        self.assertEqual(1945, event.change_number)
        self.assertEqual(SHA, event.patchset)
        self.assertEqual("main", event.branch)
        self.assertEqual("refs/pull/1945/head", event.ref)
        self.assertEqual("gitea-vm", event.connection_name)

    def test_login_comes_from_the_created_status(self):
        # The token may not be allowed to GET /user (403 in prod); the POST
        # response carries the creator, and that login must be used so the
        # event matches the "login:context:state" strings on change.status.
        conn = make_connection()
        conn._api_user_login = None
        conn._makeRequest = mock.Mock(side_effect=[
            {"id": 1, "context": "gitea/check", "status": "success",
             "creator": {"login": "zuul"}},
            RuntimeError("GET /user must not be needed"),
        ])
        conn.setCommitStatus("docs/doc-exports", SHA, "success",
                             context="gitea/check", change=make_pr())
        _, event = conn.sched.addTriggerEvent.call_args[0]
        self.assertEqual("zuul:gitea/check:success", event.status)
        self.assertEqual("zuul", conn._api_user_login)

    def test_pending_status_emits_nothing(self):
        conn = make_connection()
        conn.setCommitStatus("docs/doc-exports", SHA, "pending",
                             context="gitea/check", change=make_pr())
        conn.sched.addTriggerEvent.assert_not_called()

    def test_unknown_sha_without_change_emits_nothing(self):
        conn = make_connection()
        conn.setCommitStatus("docs/doc-exports", SHA, "success",
                             context="gitea/check")
        conn.sched.addTriggerEvent.assert_not_called()

    def test_sha_cache_resolves_pr_when_change_missing(self):
        conn = make_connection()
        conn._sha_pr_cache.update("docs/doc-exports",
                                  {"number": 1945, "head": {"sha": SHA}})
        conn.getPullRequest = mock.Mock(
            return_value={"base": {"ref": "main"}})
        conn.setCommitStatus("docs/doc-exports", SHA, "failure",
                             context="gitea/check")
        _, event = conn.sched.addTriggerEvent.call_args[0]
        self.assertEqual("zuul:gitea/check:failure", event.status)
        self.assertEqual(1945, event.change_number)
        self.assertEqual("main", event.branch)


class TestCommitStatusList(unittest.TestCase):

    def test_latest_per_context_in_github_format(self):
        conn = make_connection()
        conn._makeRequest = mock.Mock(return_value={
            "state": "success", "sha": SHA, "statuses": [
                {"context": "gitea/check", "status": "success",
                 "creator": {"login": "zuul"}},
                {"context": "gitea/gate", "status": "pending",
                 "creator": {"login": "zuul"}},
                {"context": "Docs Precheck / x", "status": "success",
                 "creator": {"login": "gitea-actions"}},
            ]})
        self.assertEqual(
            ["zuul:gitea/check:success", "zuul:gitea/gate:pending",
             "gitea-actions:Docs Precheck / x:success"],
            conn._getCommitStatusList("docs/doc-exports", SHA))
        conn._makeRequest.assert_called_once_with(
            "GET", "/repos/docs/doc-exports/commits/%s/status" % SHA)

    def test_api_error_yields_empty_list(self):
        conn = make_connection()
        conn._makeRequest = mock.Mock(side_effect=RuntimeError("boom"))
        self.assertEqual([], conn._getCommitStatusList("p/r", SHA))


class TestMergeFailureComment(unittest.TestCase):

    def _reporter(self):
        r = GiteaReporter.__new__(GiteaReporter)
        r.log = mock.Mock()
        r.connection = mock.Mock()
        r.merge_modes = GiteaReporter.merge_modes
        return r

    def test_refused_merge_is_commented_on_the_pr(self):
        r = self._reporter()
        r.connection.mergePull.side_effect = MergeFailure(
            "Failed to merge PR docs/doc-exports#1945: 405 Client Error: "
            "Method Not Allowed: Please try again later")
        r._formatMergeMessage = mock.Mock(return_value="msg")
        change = make_pr(title="t")
        item = mock.Mock()
        item.current_build_set.getMergeMode.return_value = \
            list(GiteaReporter.merge_modes)[0]
        err = r.mergePull(item, change)
        self.assertIn("405", err)
        r.connection.commentPull.assert_called_once()
        project, number, body = r.connection.commentPull.call_args[0]
        self.assertEqual(("docs/doc-exports", 1945), (project, number))
        self.assertIn("Merge failed after a successful gate run", body)
        self.assertIn("405 Client Error", body)
        self.assertIn("recheck", body)

    def test_successful_merge_does_not_comment(self):
        r = self._reporter()
        r._formatMergeMessage = mock.Mock(return_value="msg")
        item = mock.Mock()
        item.current_build_set.getMergeMode.return_value = \
            list(GiteaReporter.merge_modes)[0]
        self.assertIsNone(r.mergePull(item, make_pr(title="t")))
        r.connection.commentPull.assert_not_called()


if __name__ == "__main__":
    unittest.main()
