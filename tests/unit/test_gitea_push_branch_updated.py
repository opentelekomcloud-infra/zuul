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

"""Regression tests: a Gitea push must flag the branch as updated.

The scheduler only reconfigures a tenant after a push when
``event.branch_updated`` is set (or ``branch_created``/``branch_deleted``).
The Gitea push handler never called
``clearConnectionCacheOnBranchEvent``, so the flag stayed False and a merged
``zuul.yaml`` change was ignored until the next full reconfigure
(docs/doc-exports PR 2041 -> PR 2042 ran the old job filters).
"""

import types
import unittest

from zuul.driver.gitea.giteaconnection import GiteaEventConnector

OLD = "1" * 40
NEW = "2" * 40
ZERO = "0" * 40


def make_connector():
    calls = []

    def clear(event):
        calls.append(event)
        if event.oldrev == ZERO:
            event.branch_created = True
        elif event.newrev == ZERO:
            event.branch_deleted = True
        else:
            event.branch_updated = True

    connector = GiteaEventConnector.__new__(GiteaEventConnector)
    connector.connection = types.SimpleNamespace(
        canonical_hostname="gitea.example.com",
        clearConnectionCacheOnBranchEvent=clear,
    )
    return connector, calls


def payload(before, after, ref="refs/heads/main"):
    return {
        "ref": ref,
        "before": before,
        "after": after,
        "repository": {"full_name": "docs/doc-exports"},
    }


class TestGiteaPushBranchFlags(unittest.TestCase):

    def test_push_marks_branch_updated(self):
        connector, calls = make_connector()
        event = connector._handlePushEvent(payload(OLD, NEW))
        self.assertEqual(len(calls), 1)
        self.assertTrue(event.branch_updated)
        self.assertEqual(event.branch, "main")

    def test_new_branch_marks_created(self):
        connector, _ = make_connector()
        event = connector._handlePushEvent(
            payload(ZERO, NEW, "refs/heads/feat"))
        self.assertTrue(event.branch_created)
        self.assertFalse(event.branch_updated)

    def test_deleted_branch_marks_deleted(self):
        connector, _ = make_connector()
        event = connector._handlePushEvent(
            payload(OLD, ZERO, "refs/heads/feat"))
        self.assertTrue(event.branch_deleted)

    def test_tag_push_does_not_touch_branch_cache(self):
        connector, calls = make_connector()
        event = connector._handlePushEvent(payload(OLD, NEW, "refs/tags/v1"))
        self.assertEqual(calls, [])
        self.assertFalse(event.branch_updated)
