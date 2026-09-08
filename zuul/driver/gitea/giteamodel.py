# Copyright 2026 OTC
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

import re2

from zuul.model import Change
from zuul.model import EventFilter
from zuul.model import FalseWithReason
from zuul.model import RefFilter
from zuul.model import TriggerEvent
from zuul.driver.util import to_list

EMPTY_GIT_REF = '0' * 40  # git sha of all zeros, used during creates/deletes


class PullRequest(Change):
    """Gitea Pull Request model"""

    def __init__(self, project):
        super(PullRequest, self).__init__(project)
        self.updated_at = None
        self.pr = None
        self.title = None
        self.body_text = None
        self.labels = []
        self.reviews = []  # List of review dicts with user info and state
        self.mergeable = True
        self.merge_commit_sha = None
        # Branch protection attributes
        self.branch_protected = False
        self.required_approvals = 0
        self.enable_status_check = False
        self.required_contexts = []
        self.approved = False
        # Latest commit status per context on the PR head, formatted like the
        # GitHub driver: "<creator login>:<context>:<state>", so pipeline
        # require/reject "status" filters work the same way for both drivers.
        self.status = []

    def __repr__(self):
        r = ['<Change 0x%x' % id(self)]
        if self.project:
            r.append('project: %s' % self.project)
        if self.number:
            r.append('number: %s' % self.number)
        if self.patchset:
            r.append('patchset: %s' % self.patchset)
        if self.updated_at:
            r.append('updated: %s' % self.updated_at)
        if self.is_merged:
            r.append('state: merged')
        if self.open:
            r.append('state: open')
        if self.labels:
            r.append('labels: %s' % ', '.join(self.labels))
        return ' '.join(r) + '>'

    def serialize(self):
        d = super().serialize()
        d.update({
            "pr": self.pr,
            "updated_at": self.updated_at,
            "title": self.title,
            "body_text": self.body_text,
            "labels": self.labels,
            "reviews": self.reviews,
            "mergeable": self.mergeable,
            "merge_commit_sha": self.merge_commit_sha,
            "branch_protected": self.branch_protected,
            "required_approvals": self.required_approvals,
            "enable_status_check": self.enable_status_check,
            "required_contexts": self.required_contexts,
            "approved": self.approved,
            "status": self.status,
        })
        return d

    def deserialize(self, data):
        super().deserialize(data)
        self.pr = data.get("pr")
        self.updated_at = data.get("updated_at")
        self.title = data.get("title")
        self.body_text = data.get("body_text")
        self.labels = data.get("labels", [])
        self.reviews = data.get("reviews", [])
        self.mergeable = data.get("mergeable", True)
        self.merge_commit_sha = data.get("merge_commit_sha")
        self.branch_protected = data.get("branch_protected", False)
        self.required_approvals = data.get("required_approvals", 0)
        self.enable_status_check = data.get("enable_status_check", False)
        self.required_contexts = data.get("required_contexts", [])
        self.approved = data.get("approved", False)
        self.status = data.get("status", [])

    def isUpdateOf(self, other):
        if (self.project == other.project and
            hasattr(other, 'number') and self.number == other.number and
            hasattr(other, 'patchset') and self.patchset != other.patchset and
            hasattr(other, 'updated_at') and
            self.updated_at > other.updated_at):
            return True
        return False


class GiteaTriggerEvent(TriggerEvent):
    """Gitea webhook event model"""

    def __init__(self):
        super(GiteaTriggerEvent, self).__init__()
        self.trigger_name = 'gitea'
        self.title = None
        self.action = None
        self.label = None
        self.unlabel = None
        self.state = None  # For review events: approved, comment, request_changes
        self.change_number = None
        self.commits = []
        self.tag = None
        self.message_edited = None  # Track if PR description was edited
        # "<creator login>:<context>:<state>" for action=status events.
        # Gitea has no commit-status webhook; GiteaConnection.setCommitStatus
        # synthesizes these when Zuul itself posts a status.
        self.status = None

    def toDict(self):
        d = super().toDict()
        d["trigger_name"] = self.trigger_name
        d["title"] = self.title
        d["action"] = self.action
        d["label"] = self.label
        d["unlabel"] = self.unlabel
        d["state"] = self.state
        d["message_edited"] = self.message_edited
        d["change_number"] = self.change_number
        d["commits"] = self.commits
        d["tag"] = self.tag
        d["status"] = self.status
        return d

    def updateFromDict(self, d):
        super().updateFromDict(d)
        self.trigger_name = d["trigger_name"]
        self.title = d["title"]
        self.action = d["action"]
        self.label = d.get("label")
        self.unlabel = d.get("unlabel")
        self.state = d.get("state")
        self.message_edited = d.get("message_edited")
        self.change_number = d["change_number"]
        self.commits = d.get("commits", [])
        self.tag = d.get("tag")
        self.status = d.get("status")

    def _repr(self):
        r = [super(GiteaTriggerEvent, self)._repr()]
        if self.action:
            r.append("action:%s" % self.action)
        r.append("project:%s" % self.project_name)
        if self.change_number:
            r.append("pr:%s" % self.change_number)
        if self.label:
            r.append("label:%s" % self.label)
        if self.unlabel:
            r.append("unlabel:%s" % self.unlabel)
        if self.state:
            r.append("state:%s" % self.state)
        if self.status:
            r.append("status:%s" % self.status)
        return ' '.join(r)

    def isPatchsetCreated(self):
        if self.type == 'pull_request':
            return self.action in ['opened', 'synchronized', 'reopened']
        return False

    def isChangeAbandoned(self):
        if self.type == 'pull_request':
            return self.action == 'closed'
        return False

    def isMessageChanged(self):
        """Check if PR message/description was edited"""
        return bool(self.message_edited)


class GiteaEventFilter(EventFilter):
    """Event filter for Gitea events"""

    def __init__(
            self, connection_name, trigger, types=None, actions=None,
            branches=[], comments=None, refs=None, labels=None, unlabels=None,
            states=None, statuses=None, ignore_deletes=True, debug=None):
        super().__init__(connection_name, trigger, debug)

        types = types if types is not None else []
        refs = refs if refs is not None else []
        comments = comments if comments is not None else []
        states = states if states is not None else []
        statuses = statuses if statuses is not None else []

        self._statuses = [x.pattern for x in statuses]
        self.statuses = statuses

        self._refs = [x.pattern for x in refs]
        self.refs = refs

        self._types = [x.pattern for x in types]
        self.types = types

        self._comments = [x.pattern for x in comments]
        self.comments = comments

        self._branches = [x.pattern for x in branches]
        self.branches = branches

        self._states = [x.pattern for x in states]
        self.states = states

        self.actions = actions or []
        self.labels = labels or []
        self.unlabels = unlabels or []
        self.ignore_deletes = ignore_deletes

    def __repr__(self):
        ret = '<GiteaEventFilter'
        ret += ' connection: %s' % self.connection_name

        if self._types:
            ret += ' types: %s' % ', '.join(str(t) for t in self._types)
        if self.actions:
            ret += ' actions: %s' % ', '.join(str(a) for a in self.actions)
        if self._comments:
            ret += ' comments: %s' % ', '.join(str(c) for c in self._comments)
        if self._branches:
            ret += ' branches: %s' % ', '.join(str(b) for b in self._branches)
        if self._refs:
            ret += ' refs: %s' % ', '.join(str(r) for r in self._refs)
        if self.labels:
            ret += ' labels: %s' % ', '.join(str(l) for l in self.labels)
        if self.unlabels:
            ret += ' unlabels: %s' % ', '.join(str(u) for u in self.unlabels)
        if self._states:
            ret += ' states: %s' % ', '.join(str(s) for s in self._states)
        if self._statuses:
            ret += ' statuses: %s' % ', '.join(str(s) for s in self._statuses)
        ret += '>'

        return ret

    def matches(self, event, change):
        """Check if event matches filter criteria"""
        # First check parent class matches
        if not super().matches(event, change):
            return False

        # event types are ORed
        matches_type = False
        for etype in self.types:
            if etype.match(event.type):
                matches_type = True
        if self.types and not matches_type:
            return False

        # branches are ORed
        if self.branches:
            matches_branch = False
            for branch in self.branches:
                if hasattr(event, 'branch') and event.branch:
                    if branch.match(event.branch):
                        matches_branch = True
            if not matches_branch:
                return False

        # refs are ORed
        if self.refs:
            matches_ref = False
            if hasattr(event, 'ref') and event.ref is not None:
                for ref in self.refs:
                    if ref.match(event.ref):
                        matches_ref = True
            if not matches_ref:
                return False

        # Check ignore_deletes
        if self.ignore_deletes and hasattr(event, 'newrev'):
            if event.newrev == EMPTY_GIT_REF:
                return False

        # actions are ORed
        if self.actions:
            matches_action = False
            for action in self.actions:
                if hasattr(event, 'action') and event.action:
                    if action.match(event.action):
                        matches_action = True
            if not matches_action:
                return False

        # comments are ORed - only match if comment filter is specified
        if self.comments:
            matches_comment = False
            if hasattr(event, 'comment') and event.comment is not None:
                for comment_re in self.comments:
                    if comment_re.search(event.comment):
                        matches_comment = True
            if not matches_comment:
                return False

        # labels are ORed - check if any event label matches any filter label pattern
        if self.labels:
            matches_label = False
            if hasattr(event, 'label') and event.label:
                event_labels = event.label if isinstance(event.label, list) else [event.label]
                for event_label in event_labels:
                    for label_re in self.labels:
                        if label_re.match(event_label):
                            matches_label = True
                            break
                    if matches_label:
                        break
            if not matches_label:
                return False

        # unlabels are ORed - check if any event unlabel matches any filter unlabel pattern
        if self.unlabels:
            matches_unlabel = False
            if hasattr(event, 'unlabel') and event.unlabel:
                event_unlabels = event.unlabel if isinstance(event.unlabel, list) else [event.unlabel]
                for event_unlabel in event_unlabels:
                    for unlabel_re in self.unlabels:
                        if unlabel_re.match(event_unlabel):
                            matches_unlabel = True
                            break
                    if matches_unlabel:
                        break
            if not matches_unlabel:
                return False

        # Check state filter (for review events)
        if self._states and hasattr(event, 'state') and event.state:
            matches_state = False
            for state_regex in self.states:
                if state_regex.match(event.state):
                    matches_state = True
                    break
            if not matches_state:
                return False

        # statuses are ORed (only meaningful for action=status events)
        if self.statuses:
            matches_status = False
            event_status = getattr(event, 'status', None)
            if event_status:
                for status_re in self.statuses:
                    if status_re.match(event_status):
                        matches_status = True
                        break
            if not matches_status:
                return False

        return True


class GiteaRefFilter(RefFilter):
    """Pipeline require/reject filter for Gitea pull requests.

    Mirrors the GitHub driver's GithubRefFilter for the attributes the Gitea
    driver tracks: status, label, open, merged, current-patchset, approved.
    """

    def __init__(self, connection_name, statuses=None, reject_statuses=None,
                 labels=None, reject_labels=None,
                 open=None, merged=None, current_patchset=None,
                 approved=None, reject_open=None, reject_merged=None,
                 reject_current_patchset=None, reject_approved=None):
        RefFilter.__init__(self, connection_name)
        self.required_statuses = list(statuses or [])
        self.reject_statuses = list(reject_statuses or [])
        self.required_labels = list(labels or [])
        self.reject_labels = list(reject_labels or [])
        self.open = (not reject_open) if reject_open is not None else open
        self.merged = ((not reject_merged) if reject_merged is not None
                       else merged)
        self.current_patchset = ((not reject_current_patchset)
                                 if reject_current_patchset is not None
                                 else current_patchset)
        self.approved = ((not reject_approved) if reject_approved is not None
                         else approved)

    @classmethod
    def requiresFromConfig(cls, connection_name, config):
        return cls(
            connection_name=connection_name,
            statuses=to_list(config.get('status')),
            labels=to_list(config.get('label')),
            open=config.get('open'),
            merged=config.get('merged'),
            current_patchset=config.get('current-patchset'),
            approved=config.get('approved'),
        )

    @classmethod
    def rejectFromConfig(cls, connection_name, config):
        return cls(
            connection_name=connection_name,
            reject_statuses=to_list(config.get('status')),
            reject_labels=to_list(config.get('label')),
            reject_open=config.get('open'),
            reject_merged=config.get('merged'),
            reject_current_patchset=config.get('current-patchset'),
            reject_approved=config.get('approved'),
        )

    def __repr__(self):
        ret = '<GiteaRefFilter connection_name: %s' % self.connection_name
        if self.required_statuses:
            ret += ' status: %s' % self.required_statuses
        if self.reject_statuses:
            ret += ' reject-status: %s' % self.reject_statuses
        if self.required_labels:
            ret += ' labels: %s' % self.required_labels
        if self.reject_labels:
            ret += ' reject-labels: %s' % self.reject_labels
        for name in ('open', 'merged', 'current_patchset', 'approved'):
            val = getattr(self, name)
            if val is not None:
                ret += ' %s: %s' % (name.replace('_', '-'), val)
        return ret + '>'

    def matchesStatuses(self, change):
        if not (self.required_statuses or self.reject_statuses):
            return True
        if not hasattr(change, 'number'):
            return FalseWithReason("Can not match statuses without PR")
        change_status = getattr(change, 'status', None) or []
        if self.required_statuses:
            # ORed: any change status matching any required pattern
            matched = False
            for required in self.required_statuses:
                for status in change_status:
                    if re2.fullmatch(required, status):
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                return FalseWithReason(
                    "Required statuses %s do not match %s" % (
                        self.required_statuses, change_status))
        for rejected in self.reject_statuses:
            for status in change_status:
                if re2.fullmatch(rejected, status):
                    return FalseWithReason(
                        "Reject statuses %s match %s" % (
                            self.reject_statuses, change_status))
        return True

    def matchesLabels(self, change):
        if not (self.required_labels or self.reject_labels):
            return True
        if not hasattr(change, 'number'):
            return FalseWithReason("Can not match labels without PR")
        change_labels = getattr(change, 'labels', None) or []
        for label in self.required_labels:
            if label not in change_labels:
                return FalseWithReason(
                    "Required labels %s do not match %s" % (
                        self.required_labels, change_labels))
        for label in self.reject_labels:
            if label in change_labels:
                return FalseWithReason(
                    "Reject labels %s match %s" % (
                        self.reject_labels, change_labels))
        return True

    def matches(self, change):
        if self.open is not None:
            if not hasattr(change, 'open'):
                return FalseWithReason("Change is not a PR")
            if self.open != bool(change.open):
                return FalseWithReason(
                    "Change does not match open requirement %s" % self.open)

        if self.merged is not None:
            if not hasattr(change, 'is_merged'):
                return FalseWithReason("Change is not a PR")
            if self.merged != bool(change.is_merged):
                return FalseWithReason(
                    "Change does not match merged requirement %s" %
                    self.merged)

        if self.current_patchset is not None:
            if not hasattr(change, 'is_current_patchset'):
                return FalseWithReason("Change is not a PR")
            if self.current_patchset != bool(change.is_current_patchset):
                return FalseWithReason(
                    "Change does not match current-patchset requirement "
                    "%s" % self.current_patchset)

        if self.approved is not None:
            if not hasattr(change, 'number'):
                return FalseWithReason("Change is not a PR")
            if self.approved != bool(getattr(change, 'approved', False)):
                return FalseWithReason(
                    "Change does not match approved requirement %s" %
                    self.approved)

        result = self.matchesStatuses(change)
        if not result:
            return result

        result = self.matchesLabels(change)
        if not result:
            return result

        return True
