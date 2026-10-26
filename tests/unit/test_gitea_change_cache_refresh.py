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

"""Regression tests for the Gitea change-cache refresh behaviour.

A comment event ("recheck") carries no patchset, so GiteaSource.getChangeKey
builds a key whose revision is None. Every such event hits the same
revision-less cache entry, which keeps whatever head was current the first time
the PR was seen. After a force-push that entry is stale, and because
GiteaReporter.setCommitStatus posts to change.patchset the gitea/check status
lands on the pre-rebase commit -- so the PR never turns green.

These tests pin the rule: a cached change is only trusted when the key pins a
revision.
"""

import types
import unittest

from zuul.driver.gitea.giteaconnection import GiteaConnection


OLD_SHA = "8d5eebea6122e090ef86be23ffd176b29552bf3b"
NEW_SHA = "488a87c0ae6f7ba24a0a85f9eaefa9bb4a84db53"


class FakeKey:
    def __init__(self, revision, stable_id="1849", project_name="docs/doc-exports"):
        self.revision = revision
        self.stable_id = stable_id
        self.project_name = project_name


class FakeCache:
    def __init__(self, change):
        self._change = change
        self.get_calls = 0

    def get(self, key):
        self.get_calls += 1
        return self._change

    def updateChangeWithRetry(self, key, change, update):
        update(change)
        return change


def make_connection(cached_change, head_sha):
    """A GiteaConnection stub carrying only what _getChange touches."""
    conn = GiteaConnection.__new__(GiteaConnection)
    conn.log = types.SimpleNamespace(
        error=lambda *a, **k: None,
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    conn._change_cache = FakeCache(cached_change)
    conn.source = types.SimpleNamespace(getProject=lambda name: object())
    conn.api_calls = []

    def getPullRequest(project_name, number):
        conn.api_calls.append((project_name, number))
        return {
            "number": number,
            "head": {"sha": head_sha, "ref": "topic"},
            "base": {"sha": "base", "ref": "main"},
            "state": "open",
            "title": "t",
            "user": {"login": "u"},
        }

    conn.getPullRequest = getPullRequest
    # _updateChange does far more than this test cares about; the contract under
    # test is only "was the API consulted and the head applied".
    def _updateChange(change, event, pr_data):
        change.patchset = pr_data["head"]["sha"]
        change.commit_id = change.patchset
        change.newrev = change.patchset

    conn._updateChange = _updateChange
    return conn


class TestGiteaChangeCacheRefresh(unittest.TestCase):

    def test_revisionless_key_refetches_after_force_push(self):
        """A recheck (no patchset in the event) must not trust the cache."""
        cached = types.SimpleNamespace(patchset=OLD_SHA, number=1849)
        conn = make_connection(cached, NEW_SHA)

        change = conn._getChange(FakeKey(revision=None))

        self.assertEqual(
            1, len(conn.api_calls),
            "revision-less key must consult the API, not return the cache")
        self.assertEqual(
            NEW_SHA, change.patchset,
            "the change must carry the current head after a force-push; "
            "reporting to the stale sha is what leaves gitea/check pending")

    def test_string_none_revision_also_refetches(self):
        """getChangeKey can stringify a missing patchset as 'None'."""
        cached = types.SimpleNamespace(patchset=OLD_SHA, number=1849)
        conn = make_connection(cached, NEW_SHA)

        change = conn._getChange(FakeKey(revision="None"))

        self.assertEqual(1, len(conn.api_calls))
        self.assertEqual(NEW_SHA, change.patchset)

    def test_pinned_key_still_uses_the_cache(self):
        """Push/sync events pin a sha; those keep the cheap cache path."""
        cached = types.SimpleNamespace(patchset=OLD_SHA, number=1849)
        conn = make_connection(cached, NEW_SHA)

        change = conn._getChange(FakeKey(revision=OLD_SHA))

        self.assertEqual(
            [], conn.api_calls,
            "a key that pins a revision must not cost an extra API call")
        self.assertIs(cached, change)
        self.assertEqual(OLD_SHA, change.patchset)

    def test_explicit_refresh_still_refetches_with_pinned_key(self):
        """refresh=True must win over the cache regardless of the key."""
        cached = types.SimpleNamespace(patchset=OLD_SHA, number=1849)
        conn = make_connection(cached, NEW_SHA)

        change = conn._getChange(FakeKey(revision=OLD_SHA), refresh=True)

        self.assertEqual(1, len(conn.api_calls))
        self.assertEqual(NEW_SHA, change.patchset)


if __name__ == "__main__":
    unittest.main()
