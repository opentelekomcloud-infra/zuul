#!/usr/bin/env python

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

import json
import logging
import os
import time
import hmac
import hashlib

import git
import requests

import zuul.driver.gitea.giteaconnection as giteaconnection


class GiteaChangeReference(git.Reference):
    _common_path_default = "refs/pull"
    _points_to_commits_only = True


class FakeGiteaConnection(giteaconnection.GiteaConnection):
    """A Fake Gitea connection for use in tests.

    This subclasses
    :py:class:`~zuul.driver.gitea.GiteaConnection` to add the
    ability for tests to add changes to the fake Gitea it represents.
    """

    log = logging.getLogger("zuul.test.FakeGiteaConnection")

    def __init__(self, driver, connection_name, connection_config,
                 changes_db=None, upstream_root=None):
        super(FakeGiteaConnection, self).__init__(
            driver, connection_name, connection_config)
        self.connection_name = connection_name
        self.pr_number = 0
        self.pull_requests = changes_db
        self.statuses = {}
        self.upstream_root = upstream_root
        self.merge_failure = None
        self.merge_not_allowed_count = 0
        self.zuul_web_port = None

    def setZuulWebPort(self, port):
        self.zuul_web_port = port

    def onLoad(self, zk_client, component_registry):
        """Override onLoad to skip ZK operations in tests."""
        self.log.info('Starting FakeGitea connection: %s',
                      self.connection_name)

        # Initialize project storage
        self.projects = {}
        self.project_locks = {}

        # Set read-only mode
        self.read_only = not self.sched

        # Create mock change cache
        from zuul.zk.change_cache import AbstractChangeCache
        from zuul.driver.gitea.giteamodel import PullRequest
        from zuul.model import Ref, Tag, Branch

        class FakeGiteaChangeCache(AbstractChangeCache):
            log = logging.getLogger("zuul.test.FakeGiteaChangeCache")

            CHANGE_TYPE_MAP = {
                "Ref": Ref,
                "Tag": Tag,
                "Branch": Branch,
                "PullRequest": PullRequest,
            }

        self._change_cache = FakeGiteaChangeCache(zk_client, self)

        # Create ZK branch cache
        self.log.debug('Creating Zookeeper branch cache')
        from zuul.zk.branch_cache import BranchCache
        self._branch_cache = BranchCache(zk_client, self, component_registry)

        # Create event queue
        self.log.info('Creating Zookeeper event queue')
        if self.sched:
            component_info = self.sched.component_info
        else:
            component_info = None
        from zuul.zk.event_queues import ConnectionEventQueue
        self.event_queue = ConnectionEventQueue(
            zk_client, self.connection_name, component_info)

        # Skip starting event connector for tests
        if self.sched:
            self._start_event_connector()

    def getGitUrl(self, project):
        return 'file://' + os.path.join(self.upstream_root, project.name)

    def getGitwebUrl(self, project, sha=None):
        url = 'https://%s/%s' % (self.server, project)
        if sha:
            url += '/commit/%s' % sha
        return url

    def openFakePullRequest(self, project, branch, subject, files=None,
                            initial_comment=None):
        self.pr_number += 1
        pull_request = FakePullRequest(
            self, self.pr_number, project, branch,
            subject, self.upstream_root,
            files=files, initial_comment=initial_comment)
        if self.pull_requests is None:
            self.pull_requests = {}
        self.pull_requests.setdefault(
            project, {})[str(self.pr_number)] = pull_request
        return pull_request

    def emitEvent(self, event, use_zuulweb=False, project=None,
                  wrong_token=False):
        name, subtype, data = event
        payload = json.dumps(data).encode('utf8')
        secret = self.connection_config.get('webhook_token', 'fake_token')
        signature = hmac.new(
            secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
        headers = {'x-gitea-signature': signature,
                   'x-gitea-event': name}
        if subtype:
            headers['x-gitea-event-type'] = subtype
        if use_zuulweb:
            return requests.post(
                'http://127.0.0.1:%s/api/connection/%s/payload'
                % (self.zuul_web_port, self.connection_name),
                data=payload, headers=headers)
        else:
            data = {'headers': headers, 'payload': data}
            self.event_queue.put(data)
            return data

    def getGitPushEvent(self, project, branch='master'):
        name = 'push'
        repo_path = os.path.join(self.upstream_root, project)
        repo = git.Repo(repo_path)
        headsha = repo.head.commit.hexsha
        data = {
            'ref': f'refs/heads/{branch}',
            'before': '1' * 40,
            'after': headsha,
            'commits': [],
            'repository': {'full_name': project},
        }
        return (name, 'push', data)

    def getGitBranchEvent(self, project, branch, event_type, rev):
        """Get branch create/delete event

        Args:
            project: Project name
            branch: Branch name
            event_type: 'create' or 'delete'
            rev: Commit SHA
        """
        name = event_type
        data = {
            'ref': branch,
            'ref_type': 'branch',
            'sha': rev,
            'repository': {'full_name': project},
        }
        return (name, event_type, data)

    def getPullRequest(self, project_name, pr_number):
        """Override to return fake PR data"""
        pr = self.pull_requests.get(project_name, {}).get(str(pr_number))
        if not pr:
            return None
        return pr.getPRData()

    def getPullFiles(self, project_name, pr_number):
        """Override to return fake PR files"""
        pr = self.pull_requests.get(project_name, {}).get(str(pr_number))
        if not pr:
            return []
        return list(pr.files.keys())

    def setCommitStatus(self, project_name, sha, state, url=None,
                        description=None, context=None):
        """Override to store status in fake storage"""
        status = self.statuses.setdefault(sha, {})
        status[state] = {
            'context': context, 'url': url, 'description': description}
        self.log.info(
            "Set fake commit status for %s/%s: %s (context: %s)",
            project_name, sha[:8], state, context)

    def commentPull(self, project_name, pr_number, message):
        """Override to add comment to fake PR"""
        pr = self.pull_requests.get(project_name, {}).get(str(pr_number))
        if pr:
            pr.addComment(message)
        self.log.info(
            "Added fake comment to PR %s#%s", project_name, pr_number)

    def mergePull(self, project_name, pr_number, merge_title=None,
                  merge_message=None, sha=None, method='merge',
                  zuul_event_id=None):
        """Override to merge fake PR"""
        from zuul.exceptions import MergeFailure

        if self.merge_failure:
            raise MergeFailure(self.merge_failure)

        pr = self.pull_requests.get(project_name, {}).get(str(pr_number))
        if not pr:
            raise MergeFailure(f"PR {pr_number} not found")

        pr.is_merged = True
        pr.state = 'closed'
        pr.merge_mode = method
        pr.merge_title = merge_title or pr.subject
        pr.merge_message = merge_message
        self.log.info(
            "Merged fake PR %s#%s with method %s",
            project_name, pr_number, method)

    def getBranchProtection(
            self, project_name, branch_name, zuul_event_id=None):
        """Override to return fake branch protection"""
        return {
            'protected': True,
            'required_approvals': 1,
            'enable_status_check': False,
            'status_check_contexts': [],
            'user_can_push': False,
            'user_can_merge': True,
        }

    def addProjectByName(self, project_name):
        """Add a project by its name for test registration"""
        pass  # Projects are automatically available via upstream_root

    def _makeRequest(self, method, path, **kwargs):
        """Override to prevent actual HTTP requests"""
        self.log.debug("Fake Gitea request: %s %s", method, path)
        return {}


class FakePullRequest:
    log = logging.getLogger("zuul.test.FakeGiteaPullRequest")

    def __init__(self, gitea, number, project, branch, subject,
                 upstream_root, files=None, number_of_commits=1,
                 initial_comment=None):
        self.gitea = gitea
        self.source = gitea
        self.number = number
        self.project = project
        self.branch = branch
        self.subject = subject
        self.upstream_root = upstream_root
        self.number_of_commits = 0
        self.state = 'open'
        self.body = initial_comment
        self.comments = []
        self.files = {}
        self.labels = []
        self.sha = None
        self.head_sha = None
        self.is_merged = False
        self.merge_mode = None
        self.merge_title = None
        self.merge_message = None
        self.reviews = []
        self.url = "https://%s/%s/pulls/%s" % (
            self.gitea.server, self.project, self.number)
        self.pr_ref = self._createPRRef()
        self._addCommitToRepo(files=files)
        self._updateTimeStamp()

    def getPRData(self):
        """Return PR data in Gitea API format"""
        return {
            'number': self.number,
            'body': self.body,
            'title': self.subject,
            'state': self.state,
            'updated_at': self.last_updated,
            'comments': len(self.comments),
            'mergeable': True,
            'merged': self.is_merged,
            'base': {
                'ref': self.branch,
                'sha': self._getBaseSha(),
                'repo': {'full_name': self.project},
            },
            'head': {
                'sha': self.head_sha,
                'repo': {'full_name': self.project},
            },
            'html_url': (
                f'https://{self.gitea.server}/{self.project}/'
                f'pulls/{self.number}'),
            'user': {
                'login': 'fake_zuul_user',
            },
            'labels': [{'name': label} for label in self.labels],
            'reviews': self.reviews,
        }

    def _getBaseSha(self):
        """Get the base branch SHA"""
        repo = self._getRepo()
        try:
            return repo.heads[self.branch].commit.hexsha
        except Exception:
            return repo.commit('refs/tags/init').hexsha

    def _getPullRequestEvent(self, action, changes=None):
        name = 'pull_request'
        data = {
            'action': action,
            'pull_request': {
                'comments': len(self.comments),
                'number': self.number,
                'base': {
                    'ref': self.branch,
                    'repo': {
                        'full_name': self.project
                    }
                },
                'head': {
                    'sha': self.head_sha,
                    'repo': {
                        'full_name': self.project
                    }
                },
                'mergeable': True,
                'state': self.state,
                'title': self.subject,
                'body': self.body,
                'sha': self.sha,
                'updated_at': self.last_updated,
            },
            'repository': {
                'full_name': self.project,
            },
            'sender': {
                'login': 'fake_zuul_user'
            },
            'labels': [
                {'name': x} for x in self.labels
            ],
        }
        if action == 'edited':
            if changes:
                data['changes'] = changes
        return (name, 'pull_request', data)

    def _getIssueCommentEvent(self, action, body):
        name = 'issue_comment'
        data = {
            'action': action,
            'issue': {
                'number': self.number,
                'title': self.subject,
                'updated_at': self.last_updated,
            },
            'repository': {
                'full_name': self.project,
            },
            'comment': {
                'body': body,
            },
            'sender': {
                'login': 'fake_zuul_user'
            },
            'is_pull': True,
        }
        return (name, 'pull_request_comment', data)

    def _getRepo(self):
        repo_path = os.path.join(self.upstream_root, self.project)
        return git.Repo(repo_path)

    def _createPRRef(self):
        repo = self._getRepo()
        return GiteaChangeReference.create(
            repo, self.getPRReference(), 'refs/tags/init')

    def _addCommitToRepo(self, files=None, delete_files=None, reset=False):
        repo = self._getRepo()
        ref = repo.references[self.getPRReference()]
        if reset:
            self.number_of_commits = 0
            ref.set_object('refs/tags/init')
        self.number_of_commits += 1
        repo.head.reference = ref
        repo.git.clean('-x', '-f', '-d')

        if files:
            self.files = files
        elif not delete_files:
            fn = '%s-%s' % (self.branch.replace('/', '_'), self.number)
            self.files = {fn: "test %s %s\n" % (self.branch, self.number)}
        msg = self.subject + '-' + str(self.number_of_commits)
        for fn, content in self.files.items():
            fn = os.path.join(repo.working_dir, fn)
            with open(fn, 'w') as f:
                f.write(content)
            repo.index.add([fn])

        if delete_files:
            for fn in delete_files:
                if fn in self.files:
                    del self.files[fn]
                fn = os.path.join(repo.working_dir, fn)
                repo.index.remove([fn])

        self.head_sha = repo.index.commit(msg).hexsha
        self.sha = self.head_sha

        repo.create_head(self.getPRReference(), self.head_sha, force=True)
        self.pr_ref.set_commit(self.head_sha)
        repo.head.reference = 'master'
        repo.git.clean('-x', '-f', '-d')
        repo.heads['master'].checkout()

    def _updateTimeStamp(self):
        self.last_updated = str(int(time.time()))

    def closePullRequest(self):
        self.state = 'closed'
        self._updateTimeStamp()

    def mergePullRequest(self):
        self.state = 'closed'
        self.is_merged = True
        self._updateTimeStamp()

    def reopenPullRequest(self):
        self.state = 'open'
        self.is_merged = False
        self._updateTimeStamp()

    def addReview(self, state='APPROVED', official=True):
        self.reviews.append({
            'state': state,
            'official': official,
            'user': {'full_name': 'tester', 'email': 'fake_mail'},
        })

    def addCommit(self, files=None, delete_files=None):
        """Adds a commit on top of the actual PR head."""
        self._addCommitToRepo(files=files, delete_files=delete_files)
        self._updateTimeStamp()

    def getPRHeadSha(self):
        repo = self._getRepo()
        return repo.references[self.getPRReference()].commit.hexsha

    def getPRReference(self):
        return '%s/head' % self.number

    def getPullRequestOpenedEvent(self):
        return self._getPullRequestEvent('opened')

    def getPullRequestReopenedEvent(self):
        return self._getPullRequestEvent('reopened')

    def getPullRequestClosedEvent(self):
        return self._getPullRequestEvent('closed')

    def getPullRequestUpdatedEvent(self):
        self._addCommitToRepo()
        return self._getPullRequestEvent('synchronized')

    def getPullRequestEditedEvent(self, changes=None):
        return self._getPullRequestEvent('edited', changes=changes)

    def addComment(self, message):
        self.comments.append(message)
        self._updateTimeStamp()

    def editBody(self, body):
        """Edit the PR body/description"""
        self.body = body
        self._updateTimeStamp()

    def getPullRequestCommentCreatedEvent(self, comment):
        return self._getIssueCommentEvent('created', comment)

    def getPullRequestCommentDeletedEvent(self, comment):
        return self._getIssueCommentEvent('deleted', comment)

    def getPullRequestLabelUpdatedEvent(self):
        return self._getPullRequestEvent('label_updated')

    def getPullRequestReviewApprovedEvent(self, review):
        (_, _, data) = self._getPullRequestEvent('reviewed')
        data['review'] = {'content': review}
        return (
            'pull_request_approved',
            'pull_request_review_approved',
            data
        )

    def getPullRequestReviewRejectedEvent(self, review):
        (_, _, data) = self._getPullRequestEvent('reviewed')
        data['review'] = {'content': review}
        return (
            'pull_request_rejected',
            'pull_request_review_rejected',
            data
        )

    def getPullRequestReviewCommentEvent(self, review):
        (_, _, data) = self._getPullRequestEvent('reviewed')
        data['review'] = {'content': review}
        return (
            'issue_comment',
            'pull_request_comment',
            data
        )
