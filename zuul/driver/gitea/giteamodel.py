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

from zuul.model import Change
from zuul.model import EventFilter
from zuul.model import RefFilter
from zuul.model import TriggerEvent

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
            states=None, ignore_deletes=True, debug=None):
        super().__init__(connection_name, trigger, debug)

        types = types if types is not None else []
        refs = refs if refs is not None else []
        comments = comments if comments is not None else []
        states = states if states is not None else []

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

        return True


class GiteaRefFilter(RefFilter):
    """Ref filter for Gitea refs"""
    pass
