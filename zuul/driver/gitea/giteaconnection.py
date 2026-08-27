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

import collections
import logging
import re
import threading
import requests
import json
import hmac
import hashlib
import time
import urllib.parse
import uuid

import cherrypy
import cachetools

from opentelemetry import trace

from urllib.parse import quote_plus


def _sign_request(body, secret):
    """Create HMAC signature for webhook verification.

    Args:
        body: The raw request body bytes
        secret: The webhook secret string

    Returns:
        The hex digest of the HMAC-SHA256 signature
    """
    signature = hmac.new(
        secret.encode('utf-8'),
        body if isinstance(body, bytes) else body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def _verify_signature(body, secret, signature):
    """Verify HMAC signature for webhook payload.

    Args:
        body: The raw request body bytes
        secret: The webhook secret string
        signature: The signature from x-gitea-signature header

    Returns:
        True if signature is valid, False otherwise
    """
    expected = _sign_request(body, secret)
    return hmac.compare_digest(expected, signature)

from zuul.connection import BaseConnection, ZKBranchCacheMixin
from zuul.web.handler import BaseWebController
from zuul.lib.logutil import get_annotated_logger
from zuul.lib import tracing
from zuul.driver.gitea.giteamodel import GiteaTriggerEvent, PullRequest
from zuul.zk.change_cache import AbstractChangeCache
from zuul.zk.branch_cache import BranchInfo, BranchFlag
from zuul.model import Ref, Tag, Branch

TIMEOUT = 30

# EventTuple for structured webhook event data
EventTuple = collections.namedtuple(
    "EventTuple", ["timestamp", "body", "event_type", "delivery"]
)


class GiteaChangeCache(AbstractChangeCache):
    log = logging.getLogger("zuul.driver.GiteaChangeCache")

    CHANGE_TYPE_MAP = {
        "Ref": Ref,
        "Tag": Tag,
        "Branch": Branch,
        "PullRequest": PullRequest,
    }


class GiteaShaCache:
    """Cache for mapping SHA to PR numbers.

    This cache helps quickly look up which PRs are associated with a
    given commit SHA, improving performance when processing webhooks
    that reference commits by SHA.
    """

    def __init__(self):
        self.projects = {}

    def update(self, project_name, pr):
        """Update the cache with PR information.

        Args:
            project_name: The project name (owner/repo)
            pr: Pull request data dict containing 'head.sha' and 'number'
        """
        project_cache = self.projects.setdefault(
            project_name,
            # Cache up to 4k shas for each project
            # Note we cache the actual sha for a PR and the
            # merge_commit_sha so we make this fairly large.
            cachetools.LRUCache(4096)
        )
        sha = pr.get('head', {}).get('sha')
        number = pr.get('number')
        if sha and number is not None:
            cached_prs = project_cache.setdefault(sha, set())
            cached_prs.add(number)
        merge_commit_sha = pr.get('merge_commit_sha')
        if merge_commit_sha and number is not None:
            cached_prs = project_cache.setdefault(merge_commit_sha, set())
            cached_prs.add(number)

    def get(self, project_name, sha):
        """Get PR numbers associated with a SHA.

        Args:
            project_name: The project name (owner/repo)
            sha: The commit SHA to look up

        Returns:
            Set of PR numbers associated with the SHA, or empty set
        """
        project_cache = self.projects.get(project_name, {})
        cached_prs = project_cache.get(sha, set())
        return cached_prs


class GiteaConnection(ZKBranchCacheMixin, BaseConnection):
    driver_name = 'gitea'
    log = logging.getLogger("zuul.GiteaConnection")

    def __init__(self, driver, connection_name, connection_config):
        super(GiteaConnection, self).__init__(driver, connection_name,
                                               connection_config)
        self.server = self.connection_config.get('server', 'gitea.example.com')
        self.canonical_hostname = self.connection_config.get(
            'canonical_hostname', self.server)
        self.baseurl = self.connection_config.get(
            'baseurl', 'https://%s' % self.server)
        self.api_token = self.connection_config.get('api_token')
        self.webhook_secret = self.connection_config.get('webhook_secret')

        # Initialize project storage early (also in onLoad for scheduler)
        self.projects = {}
        self.project_locks = {}

        # Initialize SHA cache for PR lookups
        self._sha_pr_cache = GiteaShaCache()

        # Initialize source for change cache
        self.source = driver.getSource(self)

        # SSH configuration for git cloning
        self.git_ssh_key = self.connection_config.get('sshkey')
        self.git_host = self.connection_config.get('git_host', self.server)
        self.git_port = int(self.connection_config.get('git_port', 22))
        self.git_user = self.connection_config.get('git_user', 'git')

        # Debug logging
        self.log.info(f'Gitea connection {self.connection_name} SSH config: '
                     f'git_ssh_key={self.git_ssh_key}, git_host={self.git_host}, '
                     f'git_port={self.git_port}, git_user={self.git_user}')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {self.api_token}',
            'Content-Type': 'application/json',
        })

    def onLoad(self, zk_client, component_registry):
        self.log.info('Starting Gitea connection: %s', self.connection_name)

        # Initialize project storage
        self.projects = {}
        self.project_locks = {}

        # Set the project branch cache to read only if no scheduler is
        # provided to prevent fetching the branches from the connection.
        self.read_only = not self.sched

        self.log.debug('Creating Zookeeper change cache')
        self._change_cache = GiteaChangeCache(zk_client, self)

        self.log.debug('Creating Zookeeper branch cache')
        from zuul.zk.branch_cache import BranchCache
        self._branch_cache = BranchCache(zk_client, self, component_registry)

        self.log.info('Creating Zookeeper event queue')
        if self.sched:
            component_info = self.sched.component_info
        else:
            component_info = None
        from zuul.zk.event_queues import ConnectionEventQueue
        self.event_queue = ConnectionEventQueue(
            zk_client, self.connection_name, component_info)

        # If the connection was not loaded by a scheduler, but by e.g.
        # zuul-web, we want to stop here.
        if not self.sched:
            return

        self.log.info('Starting event connector')
        self._start_event_connector()

    def onStop(self):
        self.log.info("Stopping Gitea connection %s", self.connection_name)
        self._stop_event_connector()

    def getWebController(self, zuul_web):
        return GiteaWebController(zuul_web, self)

    def _makeRequest(self, method, path, retries=3, **kwargs):
        """Make an HTTP request to Gitea API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/repos/owner/repo/pulls')
            retries: Number of retry attempts for transient failures
            **kwargs: Additional arguments passed to requests

        Returns:
            Parsed JSON response or None if no content

        Raises:
            requests.exceptions.RequestException: If all retries fail
        """
        url = f"{self.baseurl}/api/v1{path}"
        kwargs.setdefault('timeout', TIMEOUT)

        last_exception = None
        for attempt in range(retries):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else None
            except requests.exceptions.HTTPError as e:
                # Don't retry client errors (4xx) except rate limiting
                if e.response is not None:
                    if e.response.status_code == 429:
                        # Rate limited - wait and retry
                        retry_after = int(e.response.headers.get('Retry-After', 60))
                        self.log.warning(
                            "Rate limited by Gitea API, waiting %d seconds",
                            retry_after)
                        time.sleep(retry_after)
                        last_exception = e
                        continue
                    elif 400 <= e.response.status_code < 500:
                        # Client error - don't retry
                        self.log.error("Gitea API client error: %s", e)
                        raise
                # Server error - retry
                last_exception = e
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.log.warning(
                        "Gitea API request failed (attempt %d/%d), "
                        "retrying in %d seconds: %s",
                        attempt + 1, retries, wait_time, e)
                    time.sleep(wait_time)
            except requests.exceptions.ConnectionError as e:
                # Connection error - retry
                last_exception = e
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    self.log.warning(
                        "Gitea API connection error (attempt %d/%d), "
                        "retrying in %d seconds: %s",
                        attempt + 1, retries, wait_time, e)
                    time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                self.log.error("Gitea API request failed: %s", e)
                raise

        # All retries exhausted
        self.log.error("Gitea API request failed after %d attempts: %s",
                      retries, last_exception)
        raise last_exception

    def getRefSha(self, project_name, ref):
        """Get SHA for a given ref"""
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/git/refs/{ref}')
            return data.get('object', {}).get('sha')
        except Exception as e:
            self.log.error("Failed to get ref SHA: %s", e)
            return None

    def getPRsBySha(self, project_name, sha):
        """Get PR numbers associated with a SHA from cache.

        Uses the GiteaShaCache to quickly look up which PRs contain
        a specific commit SHA, avoiding full PR searches.

        Args:
            project_name: The project name (owner/repo)
            sha: The commit SHA to look up

        Returns:
            Set of PR numbers, or empty set if not found
        """
        return self._sha_pr_cache.get(project_name, sha)

    def getPullRequest(self, project_name, pr_number):
        """Get pull request details"""
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/pulls/{pr_number}')
            return data
        except Exception as e:
            self.log.error("Failed to get pull request: %s", e)
            return None

    def getChange(self, change_key, refresh=False, event=None):
        """Get a Change object from a change key"""
        if change_key.connection_name != self.connection_name:
            return None
        if change_key.change_type == 'PullRequest':
            return self._getChange(change_key, refresh=refresh, event=event)
        elif change_key.change_type == 'Tag':
            return self._getTag(change_key, refresh=refresh, event=event)
        elif change_key.change_type == 'Branch':
            return self._getBranch(change_key, refresh=refresh, event=event)
        elif change_key.change_type == 'Ref':
            return self._getRef(change_key, refresh=refresh, event=event)
        return None

    def _getChange(self, change_key, refresh=False, event=None):
        """Fetch pull request from Gitea API and create Change object"""
        number = int(change_key.stable_id)
        change = self._change_cache.get(change_key)
        if change and not refresh:
            return change

        project = self.source.getProject(change_key.project_name)
        if not change:
            change = PullRequest(project)
            change.project = project
            change.number = number
            # Don't set patchset to string 'None' - leave as None and let _updateChange set it
            if change_key.revision and change_key.revision != 'None':
                change.patchset = change_key.revision
            else:
                change.patchset = None

        # Fetch PR data from API
        pr_data = self.getPullRequest(change_key.project_name, number)
        if not pr_data:
            self.log.error("Unable to fetch PR %s for project %s",
                          number, change_key.project_name)
            return None

        # Update change with PR data
        def _update_change(c):
            self._updateChange(c, event, pr_data)

        try:
            change = self._change_cache.updateChangeWithRetry(
                change_key, change, _update_change)
        except Exception as e:
            self.log.exception("Failed to update change in cache: %s", e)
            change = self._change_cache.get(change_key)

        return change

    def _getTag(self, change_key, refresh=False, event=None):
        """Get Tag change"""
        tag = change_key.stable_id
        change = self._change_cache.get(change_key)
        if change:
            if refresh:
                try:
                    self._change_cache.updateChangeWithRetry(
                        change_key, change, lambda c: None)
                except Exception:
                    pass
            return change
        project = self.source.getProject(change_key.project_name)
        change = Tag(project)
        change.tag = tag
        change.ref = f'refs/tags/{tag}'
        change.oldrev = change_key.oldrev
        change.newrev = change_key.newrev
        change.url = self.getGitwebUrl(change_key.project_name, sha=change.newrev)
        if event and hasattr(event, 'commits'):
            change.files = []
        try:
            self._change_cache.set(change_key, change)
        except Exception:
            change = self._change_cache.get(change_key)
        return change

    def _getBranch(self, change_key, refresh=False, event=None):
        """Get Branch change"""
        branch = change_key.stable_id
        change = self._change_cache.get(change_key)
        if change:
            if refresh:
                try:
                    self._change_cache.updateChangeWithRetry(
                        change_key, change, lambda c: None)
                except Exception:
                    pass
            return change
        project = self.source.getProject(change_key.project_name)
        change = Branch(project)
        change.branch = branch
        change.ref = f'refs/heads/{branch}'
        change.oldrev = change_key.oldrev
        change.newrev = change_key.newrev
        change.url = self.getGitwebUrl(change_key.project_name, sha=change.newrev)
        if event and hasattr(event, 'commits'):
            change.files = []
        try:
            self._change_cache.set(change_key, change)
        except Exception:
            change = self._change_cache.get(change_key)
        return change

    def _getRef(self, change_key, refresh=False, event=None):
        """Get generic Ref change"""
        change = self._change_cache.get(change_key)
        if change:
            if refresh:
                try:
                    self._change_cache.updateChangeWithRetry(
                        change_key, change, lambda c: None)
                except Exception:
                    pass
            return change
        project = self.source.getProject(change_key.project_name)
        change = Ref(project)
        change.ref = change_key.stable_id
        change.oldrev = change_key.oldrev
        change.newrev = change_key.newrev
        change.url = self.getGitwebUrl(change_key.project_name, sha=change.newrev)
        if event and hasattr(event, 'commits'):
            change.files = []
        try:
            self._change_cache.set(change_key, change)
        except Exception:
            change = self._change_cache.get(change_key)
        return change

    def _updateChange(self, change, event, pr_data):
        """Update a Change object with PR data from Gitea API"""
        self.log.info("Updating %s", change)
        change.pr = pr_data

        # Update SHA cache for quick PR lookups by SHA
        self._sha_pr_cache.update(change.project.name, pr_data)

        # Always track the PR's authoritative current head SHA from the API.
        # Previously this only set patchset when it was unset, so a cached
        # change kept the first-seen commit forever: after new pushes Zuul
        # never re-evaluated the real head and kept testing stale in-repo
        # config (e.g. old nodesets -> NODE_FAILURE). Update unconditionally
        # and invalidate per-commit data when the head moves.
        head_sha = pr_data.get('head', {}).get('sha')
        if head_sha and change.patchset != head_sha:
            if change.patchset and change.patchset != 'None':
                self.log.info(
                    "PR %s head moved %s -> %s; refreshing change",
                    change.number, change.patchset, head_sha)
                # Head advanced: drop cached per-commit data so it is refetched
                change.files = None
            else:
                self.log.info(
                    "Set patchset to %s for PR %s", head_sha, change.number)
            change.patchset = head_sha
        change.is_current_patchset = True
        change.ref = f"refs/pull/{change.number}/head"
        change.branch = pr_data.get('base', {}).get('ref')
        change.base_sha = pr_data.get('base', {}).get('sha')
        change.commit_id = head_sha
        change.newrev = head_sha
        change.owner = pr_data.get('user', {}).get('login')

        # Fetch changed files for the PR (also re-fetched if invalidated above)
        if not change.files:
            change.files = self.getPullFiles(change.project.name, change.number)

        change.title = pr_data.get('title')
        change.open = pr_data.get('state') == 'open'

        # Never change is_merged back to unmerged (matches GitHub driver)
        if not change.is_merged:
            change.is_merged = pr_data.get('merged', False)

        # Set labels
        labels = [l.get('name') for l in pr_data.get('labels', [])]
        change.labels = labels

        # Compose message from title and body
        message = pr_data.get('body') or ''
        if change.title:
            if message:
                message = f"{change.title}\n\n{message}"
            else:
                message = change.title
        change.message = message
        change.body_text = pr_data.get('body', '')

        # Set updated_at timestamp
        if not change.updated_at:
            import dateutil.parser
            import time
            updated_at_str = pr_data.get('updated_at')
            if updated_at_str:
                change.updated_at = int(time.mktime(
                    dateutil.parser.parse(updated_at_str).timetuple()))

        # Set URL
        change.url = pr_data.get('html_url')
        change.uris = [
            f'https://{self.server}/{change.project.name}/pulls/{change.number}',
        ]

        # Set mergeable state
        change.mergeable = pr_data.get('mergeable', True)
        change.merge_commit_sha = pr_data.get('merge_commit_sha')

        # Fetch and store reviews for this PR
        self._updateReviews(change)

        # Fetch and store branch protection information
        self._updateBranchProtection(change)

        return change

    def _updateReviews(self, change):
        """Fetch and store PR reviews.

        Fetches review data from Gitea API and stores it on the change
        object for use in merge commit messages and approval checking.
        """
        if not hasattr(change, 'number') or not change.number:
            return

        try:
            reviews = self.getPullReviews(change.project.name, change.number)
            change.reviews = reviews
            # Store reviews in pr dict as well for compatibility
            if hasattr(change, 'pr') and change.pr:
                change.pr['reviews'] = reviews
        except Exception as e:
            self.log.warning("Failed to fetch reviews for PR %s: %s",
                           change.number, e)
            change.reviews = []

    def getPullReviews(self, project_name, pr_number):
        """Get reviews for a pull request from Gitea API.

        Args:
            project_name: The project name (e.g., 'owner/repo')
            pr_number: The pull request number

        Returns:
            List of review dictionaries with user info and state
        """
        try:
            data = self._makeRequest(
                'GET',
                f'/repos/{project_name}/pulls/{pr_number}/reviews'
            )
            return data if data else []
        except Exception as e:
            self.log.warning("Failed to get reviews for PR %s#%s: %s",
                           project_name, pr_number, e)
            return []

    def _updateBranchProtection(self, change):
        """Update branch protection information for a change

        Fetches branch protection settings from Gitea API and updates
        the change object with protection requirements.
        """
        if not hasattr(change, 'branch') or not change.branch:
            return

        try:
            protection = self.getBranchProtection(change.project.name, change.branch)

            if protection:
                change.branch_protected = protection.get('protected', False)
                change.required_approvals = protection.get('required_approvals', 0)
                change.enable_status_check = protection.get('enable_status_check', False)
                change.required_contexts = protection.get('status_check_contexts', [])

                # Check if PR has enough approvals
                if change.required_approvals > 0 and hasattr(change, 'pr'):
                    reviews = change.pr.get('reviews', [])
                    approved_count = sum(1 for r in reviews if r.get('state') == 'APPROVED')
                    change.approved = approved_count >= change.required_approvals
                    self.log.debug(
                        "PR %s has %d approvals (required: %d), approved: %s",
                        change.number, approved_count, change.required_approvals, change.approved)
                else:
                    # No approvals required or no reviews available
                    change.approved = True
            else:
                # Branch not protected, no special requirements
                change.branch_protected = False
                change.required_approvals = 0
                change.enable_status_check = False
                change.required_contexts = []
                change.approved = True

        except Exception as e:
            self.log.warning("Failed to fetch branch protection for %s/%s: %s",
                           change.project.name, change.branch, e)
            # On error, assume no protection
            change.branch_protected = False
            change.required_approvals = 0
            change.enable_status_check = False
            change.required_contexts = []
            change.approved = True

    def getPullFiles(self, project_name, pr_number):
        """Get list of changed files in a pull request"""
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/pulls/{pr_number}/files')
            if data:
                return [f.get('filename') for f in data if f.get('filename')]
            return []
        except Exception as e:
            self.log.warning("Failed to get PR files, using empty list: %s", e)
            return []

    def setCommitStatus(self, project_name, sha, state, url=None, description=None, context=None):
        """Set commit status on Gitea

        Args:
            project_name: The project name (e.g., 'owner/repo')
            sha: The commit SHA
            state: Status state ('pending', 'success', 'error', 'failure')
            url: Optional URL for the status
            description: Optional description text
            context: Status context (e.g., 'preprod/check')
        """
        try:
            data = {
                'state': state,
            }
            if context:
                data['context'] = context
            if url:
                data['target_url'] = url
            if description:
                data['description'] = description

            self._makeRequest('POST', f'/repos/{project_name}/statuses/{sha}', json=data)
            self.log.info("Set commit status for %s/%s: %s (context: %s)",
                         project_name, sha[:8], state, context)
        except Exception as e:
            self.log.error("Failed to set commit status for %s/%s: %s",
                          project_name, sha[:8], e)

    def commentPull(self, project_name, pr_number, message):
        """Add comment to a pull request

        Args:
            project_name: The project name (e.g., 'owner/repo')
            pr_number: The pull request number
            message: The comment message text
        """
        try:
            data = {'body': message}
            self._makeRequest('POST', f'/repos/{project_name}/issues/{pr_number}/comments', json=data)
            self.log.info("Added comment to PR %s#%s", project_name, pr_number)
        except Exception as e:
            self.log.error("Failed to add comment to PR %s#%s: %s",
                          project_name, pr_number, e)
            raise

    def mergePull(self, project_name, pr_number, merge_title=None, merge_message=None,
                  sha=None, method='merge', zuul_event_id=None):
        """Merge a pull request via Gitea API

        Args:
            project_name: The project name (e.g., 'owner/repo')
            pr_number: The pull request number
            merge_title: Optional merge commit title (defaults to PR title)
            merge_message: Optional merge commit message
            sha: The head SHA to verify before merging
            method: Merge method ('merge' or 'squash')
            zuul_event_id: Optional event ID for logging

        Raises:
            MergeFailure: If the merge fails
        """
        from zuul.exceptions import MergeFailure

        try:
            # Prepare merge request payload
            data = {
                'Do': method,  # Gitea uses 'Do' field with values 'merge', 'squash', etc.
            }

            # Add optional fields
            if merge_title:
                data['MergeTitleField'] = merge_title
            if merge_message:
                data['MergeMessageField'] = merge_message
            if sha:
                data['MergeWhenChecksSucceed'] = False
                data['head_commit_id'] = sha

            # Perform the merge
            result = self._makeRequest(
                'POST',
                f'/repos/{project_name}/pulls/{pr_number}/merge',
                json=data)

            # Gitea answers a successful merge with 200 and an empty body,
            # which _makeRequest returns as None. Anything non-2xx would have
            # raised before reaching here.
            if result is None or result.get('merged'):
                self.log.info("Successfully merged PR %s#%s with method %s",
                            project_name, pr_number, method)
                return

            # If we got here, merge didn't succeed
            error_msg = result.get('message', 'Unknown error')
            raise MergeFailure(f"Failed to merge PR {project_name}#{pr_number}: {error_msg}")

        except MergeFailure:
            raise
        except Exception as e:
            self.log.error("Failed to merge PR %s#%s: %s",
                          project_name, pr_number, e)
            raise MergeFailure(f"Failed to merge PR {project_name}#{pr_number}: {str(e)}")

    def getBranchProtection(self, project_name, branch_name, zuul_event_id=None):
        """Get branch protection settings from Gitea API

        Returns protection settings including:
        - protected: Whether the branch is protected
        - required_approvals: Number of required approvals
        - enable_status_check: Whether status checks are required
        - required_status_checks: List of required status check contexts

        Args:
            project_name: The project name (e.g., 'owner/repo')
            branch_name: The branch name
            zuul_event_id: Optional event ID for logging

        Returns:
            dict: Branch protection settings, or None if not protected
        """
        try:
            data = self._makeRequest(
                'GET',
                f'/repos/{project_name}/branch_protections/{branch_name}')

            if not data:
                return None

            protection = {
                'protected': True,
                'required_approvals': data.get('required_approvals', 0),
                'enable_status_check': data.get('enable_status_check', False),
                'status_check_contexts': data.get('status_check_contexts', []),
                'user_can_push': data.get('user_can_push', False),
                'user_can_merge': data.get('user_can_merge', True),
            }

            self.log.debug("Branch protection for %s/%s: %s",
                         project_name, branch_name, protection)
            return protection

        except Exception as e:
            # If branch protection endpoint fails, check basic protected status
            self.log.debug("Failed to get branch protection details for %s/%s: %s",
                         project_name, branch_name, e)

            # Fall back to basic branch info
            try:
                branch_data = self._makeRequest('GET', f'/repos/{project_name}/branches/{branch_name}')
                if branch_data and branch_data.get('protected'):
                    return {
                        'protected': True,
                        'required_approvals': 0,
                        'enable_status_check': False,
                        'status_check_contexts': [],
                        'user_can_push': False,
                        'user_can_merge': True,
                    }
            except Exception:
                pass

            return None

    def _getProjectBranchesRequiredFlags(self, exclude_unprotected, exclude_locked):
        """Get the flags required for branch queries

        This is used by ZKBranchCacheMixin to determine what data to fetch.
        """
        flags = BranchFlag.PRESENT
        if exclude_unprotected:
            flags |= BranchFlag.PROTECTED
        return flags

    def _filterProjectBranches(self, branch_infos, exclude_unprotected, exclude_locked):
        """Filter branches based on flags

        This is used by ZKBranchCacheMixin to filter cached branches.
        """
        if exclude_unprotected:
            branch_infos = [b for b in branch_infos if b.protected is True]
        return branch_infos

    def _fetchProjectBranches(self, project, required_flags):
        """Fetch branch information from Gitea API

        This is called by ZKBranchCacheMixin when cache needs refresh.
        Returns (valid_flags, list of BranchInfo objects).
        """
        valid_flags = BranchFlag.CLEAR
        branch_infos = {}

        # Always fetch all branches with their protection status
        if BranchFlag.PRESENT in required_flags or BranchFlag.PROTECTED in required_flags:
            valid_flags |= BranchFlag.PRESENT
            try:
                data = self._makeRequest('GET', f'/repos/{project.name}/branches')
                for branch_data in data:
                    branch_name = branch_data['name']
                    bi = branch_infos.setdefault(branch_name, BranchInfo(branch_name))
                    bi.present = True

                    # Check if branch is protected
                    if BranchFlag.PROTECTED in required_flags:
                        bi.protected = branch_data.get('protected', False)
                        valid_flags |= BranchFlag.PROTECTED
            except Exception as e:
                self.log.error("Failed to fetch branches for %s: %s", project.name, e)
                return valid_flags, []

        return valid_flags, list(branch_infos.values())

    def isBranchProtected(self, project_name, branch_name, zuul_event_id=None):
        """Check if a branch is protected

        Required by ZKBranchCacheMixin.
        """
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/branches/{branch_name}')
            return data.get('protected', False)
        except Exception as e:
            self.log.warning("Failed to check if branch %s is protected in %s: %s",
                           branch_name, project_name, e)
            return None

    def getProjectBranchSha(self, project_name, branch_name, zuul_event_id=None):
        """Get the SHA of a branch

        Required for branch caching.
        """
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/branches/{branch_name}')
            return data['commit']['id']
        except Exception as e:
            self.log.error("Failed to get SHA for branch %s in %s: %s",
                          branch_name, project_name, e)
            return None

    def _fetchProjectDefaultBranch(self, project):
        """Fetch the default branch for a project

        Required by ZKBranchCacheMixin for branch caching.
        """
        try:
            data = self._makeRequest('GET', f'/repos/{project.name}')
            return data.get('default_branch', 'main')
        except Exception as e:
            self.log.error("Failed to get default branch for %s: %s", project.name, e)
            return None

    def getProject(self, name):
        """Get a project by name

        Returns the Project object if it exists, None otherwise.
        """
        return self.projects.get(name)

    def addProject(self, project):
        """Add a project to the connection's project storage

        This is used to track projects that are being managed.
        """
        import threading
        self.projects[project.name] = project
        if project.name not in self.project_locks:
            self.project_locks[project.name] = threading.Lock()

    def getGitUrl(self, project):
        """Get git URL for cloning

        Args:
            project: Either a Project object or a string project name
        """
        # Handle both Project objects and string names
        if hasattr(project, 'name'):
            project_name = project.name
        else:
            project_name = project

        # If SSH key is configured, use ssh:// URL with explicit port
        if self.git_ssh_key:
            # Use ssh:// format with explicit port since SSH config isn't consulted by git
            url = f'ssh://{self.git_user}@{self.git_host}:{self.git_port}/{project_name}.git'
            self.log.debug(f'Returning SSH URL for {project_name}: {url}')
            return url

        # Fall back to HTTPS URL
        url = f"{self.baseurl}/{project_name}.git"
        self.log.debug(f'Returning HTTPS URL for {project_name}: {url}')
        return url

    def getWebController(self, zuul_web):
        """Get web controller for webhook handling"""
        return GiteaWebController(zuul_web, self)

    def getGitwebUrl(self, project_name, sha=None):
        """Get web URL for a project or specific commit"""
        if sha:
            return f"{self.baseurl}/{project_name}/commit/{sha}"
        return f"{self.baseurl}/{project_name}"

    def canMerge(self, change, allow_needs, event=None):
        """Check if a change can be merged

        Takes into account:
        - Basic mergeable status from Gitea
        - Branch protection requirements
        - Required approvals
        - Required status checks (if enabled)
        """
        if not hasattr(change, 'mergeable'):
            return True

        # Basic mergeable check
        if not change.mergeable:
            self.log.debug("Change %s is not mergeable according to Gitea", change)
            return False

        # If branch is protected, check requirements
        if hasattr(change, 'branch_protected') and change.branch_protected:
            # Check approval requirements
            if hasattr(change, 'required_approvals') and change.required_approvals > 0:
                if not hasattr(change, 'approved') or not change.approved:
                    self.log.debug(
                        "Change %s does not have required approvals (%d required)",
                        change, change.required_approvals)
                    return False

            # Check status check requirements if enabled
            if hasattr(change, 'enable_status_check') and change.enable_status_check:
                if hasattr(change, 'required_contexts') and change.required_contexts:
                    # Fetch and verify commit statuses
                    if not self._checkRequiredStatuses(change):
                        self.log.debug(
                            "Change %s failed required status checks: %s",
                            change, change.required_contexts)
                        return False

        return True

    def _checkRequiredStatuses(self, change):
        """Check if all required status checks have passed.

        Args:
            change: The change object with required_contexts set

        Returns:
            True if all required status checks passed, False otherwise
        """
        if not hasattr(change, 'patchset') or not change.patchset:
            return True

        try:
            statuses = self.getCommitStatuses(change.project.name, change.patchset)
            if not statuses:
                return False

            # Build a dict of context -> latest status
            context_status = {}
            for status in statuses:
                ctx = status.get('context', '')
                # Only keep the most recent status per context
                if ctx not in context_status:
                    context_status[ctx] = status.get('status', '')

            # Check each required context
            for required_ctx in change.required_contexts:
                if required_ctx not in context_status:
                    self.log.debug("Required context %s not found", required_ctx)
                    return False
                if context_status[required_ctx] != 'success':
                    self.log.debug(
                        "Required context %s has status %s, not success",
                        required_ctx, context_status[required_ctx])
                    return False

            return True
        except Exception as e:
            self.log.warning("Failed to check required statuses: %s", e)
            return False

    def getCommitStatuses(self, project_name, sha):
        """Get commit statuses from Gitea API.

        Args:
            project_name: The project name (e.g., 'owner/repo')
            sha: The commit SHA

        Returns:
            List of status dictionaries
        """
        try:
            data = self._makeRequest(
                'GET',
                f'/repos/{project_name}/statuses/{sha}')
            return data if data else []
        except Exception as e:
            self.log.warning("Failed to get commit statuses for %s/%s: %s",
                           project_name, sha[:8], e)
            return []

    def getChangesDependingOn(self, change, projects, tenant):
        """Get changes that depend on this change via Depends-On.

        Searches for open pull requests that reference this change
        in their body using the 'Depends-On:' syntax.

        Args:
            change: The change to find dependents for
            projects: List of projects to search in
            tenant: The tenant context

        Returns:
            List of Change objects that depend on this change
        """
        changes = []
        if not hasattr(change, 'number'):
            return changes

        # Construct the URL that would be used in Depends-On references
        change_url = f"https://{self.canonical_hostname}/{change.project.name}/pulls/{change.number}"

        self.log.debug("Searching for changes depending on %s", change_url)

        # Search for PRs mentioning this change URL
        for project in projects:
            try:
                prs = self._searchPullRequests(
                    project.name,
                    query=change_url,
                    state='open'
                )
                for pr in prs:
                    # Verify the Depends-On reference is in the body
                    body = pr.get('body', '') or ''
                    if f"Depends-On: {change_url}" in body:
                        # Get the change object for this PR
                        from zuul.zk.change_cache import ChangeKey
                        pr_number = pr.get('number')
                        pr_sha = pr.get('head', {}).get('sha')
                        change_key = ChangeKey(
                            self.connection_name,
                            project.name,
                            'PullRequest',
                            str(pr_number),
                            str(pr_sha)
                        )
                        dep_change = self._getChange(change_key)
                        if dep_change:
                            changes.append(dep_change)
            except Exception as e:
                self.log.warning(
                    "Error searching for dependencies in %s: %s",
                    project.name, e)

        return changes

    def _searchPullRequests(self, project_name, query=None, state='open'):
        """Search for pull requests in a project.

        Args:
            project_name: The project name
            query: Optional search query string
            state: PR state to filter ('open', 'closed', 'all')

        Returns:
            List of pull request dictionaries
        """
        try:
            params = {'state': state}
            # Gitea doesn't have a direct search API for PR bodies,
            # so we fetch all open PRs and filter
            data = self._makeRequest(
                'GET',
                f'/repos/{project_name}/pulls',
                params=params
            )
            if not data:
                return []

            if query:
                # Filter PRs that contain the query in their body
                filtered = []
                for pr in data:
                    body = pr.get('body', '') or ''
                    if query in body:
                        filtered.append(pr)
                return filtered
            return data
        except Exception as e:
            self.log.warning("Failed to search PRs in %s: %s", project_name, e)
            return []

    def getPull(self, project_name, pr_number, event=None):
        """Get pull request data from Gitea API.

        This is a convenience wrapper around getPullRequest that matches
        the interface expected by getChangeByURL.

        Args:
            project_name: The project name
            pr_number: The pull request number
            event: Optional event context

        Returns:
            Pull request dictionary or None
        """
        return self.getPullRequest(project_name, pr_number)

    def getProjectBranchSha(self, project_name, branch_name):
        """Get SHA for a project branch"""
        return self.getRefSha(project_name, f'refs/heads/{branch_name}')

    def isMerged(self, change, head=None):
        """Check if a change is merged"""
        # head is unused: the merge API call updates is_merged directly, so no
        # extra query is needed (matches the GitHub driver).
        return getattr(change, 'is_merged', False)

    def _start_event_connector(self):
        """Start the event connector thread"""
        self.gitea_event_connector = GiteaEventConnector(self)
        self.gitea_event_connector.start()

    def _stop_event_connector(self):
        """Stop the event connector thread"""
        if hasattr(self, 'gitea_event_connector'):
            self.gitea_event_connector.stop()
            self.gitea_event_connector.join()


class GiteaEventConnector(threading.Thread):
    """Move events from Gitea event queue into the scheduler"""
    log = logging.getLogger("zuul.GiteaEventConnector")
    tracer = trace.get_tracer("zuul")

    def __init__(self, connection):
        super(GiteaEventConnector, self).__init__()
        self.daemon = True
        self.connection = connection
        self.event_queue = connection.event_queue
        self._stopped = False
        self._process_event = threading.Event()

    def stop(self):
        self._stopped = True
        self._process_event.set()
        self.event_queue.election.cancel()

    def _onNewEvent(self):
        self._process_event.set()
        return not self._stopped

    def run(self):
        self.connection.sched.primed_event.wait()
        if self._stopped:
            return
        self.event_queue.registerEventWatch(self._onNewEvent)
        while not self._stopped:
            try:
                self.event_queue.election.run(self._run)
            except Exception:
                self.log.exception("Exception handling Gitea event:")

    def _run(self):
        while not self._stopped:
            for event_data in self.event_queue:
                # Restore span context from event for distributed tracing
                event_span = tracing.restoreSpanContext(
                    event_data.get("span_context"))
                attributes = {"rel": "GiteaEvent"}
                link = trace.Link(event_span.get_span_context(),
                                  attributes=attributes)
                with self.tracer.start_as_current_span(
                        "GiteaEventProcessing", links=[link]):
                    try:
                        self._handleEvent(event_data)
                    finally:
                        self.event_queue.ack(event_data)
                if self._stopped:
                    return
            self._process_event.wait(10)
            self._process_event.clear()

    def _handleEvent(self, event_data):
        """Process a queued event and create trigger event"""
        zuul_event_id = str(uuid.uuid4())
        log = get_annotated_logger(self.log, zuul_event_id)

        headers = event_data.get('headers', {})
        body = event_data.get('body', {})
        event_type = headers.get('x-gitea-event')

        log.debug("Processing Gitea event: %s", event_type)

        event = None
        if event_type == 'pull_request':
            event = self._handlePullRequestEvent(body)
        elif event_type == 'pull_request_review':
            event = self._handlePullRequestReviewEvent(body)
        elif event_type == 'pull_request_review_dismissed':
            event = self._handlePullRequestReviewDismissedEvent(body)
        elif event_type == 'issue_comment':
            event = self._handleIssueCommentEvent(body)
        elif event_type == 'push':
            event = self._handlePushEvent(body)

        if event:
            event.zuul_event_id = zuul_event_id
            event.connection_name = self.connection.connection_name
            # Ensure timestamp is always set (fallback for old cached events)
            if not hasattr(event, 'timestamp') or event.timestamp is None:
                event.timestamp = time.time()
            self.connection.logEvent(event)
            self.connection.sched.addTriggerEvent(
                self.connection.driver_name, event
            )

    def _handlePullRequestEvent(self, payload):
        """Handle pull request webhook"""
        event = GiteaTriggerEvent()
        event.type = 'gt_pull_request'
        event.action = payload.get('action')
        event.project_hostname = self.connection.canonical_hostname
        event.timestamp = time.time()

        pr = payload.get('pull_request', {})
        event.project_name = payload.get('repository', {}).get('full_name')
        event.change_number = pr.get('number')
        event.branch = pr.get('base', {}).get('ref')
        event.ref = f"refs/pull/{pr.get('number')}/head"
        event.patchset = pr.get('head', {}).get('sha')
        event.title = pr.get('title')

        # The webhook payload's embedded pull_request object can carry a stale
        # head SHA (Gitea does not always refresh it on synchronize), which
        # would pin the change-key to an old commit and make Zuul re-test stale
        # code. Resolve the authoritative current head from the API so the
        # change-key always reflects the real PR head.
        if event.project_name and event.change_number is not None:
            try:
                pr_api = self.connection.getPullRequest(
                    event.project_name, event.change_number)
                api_sha = (pr_api or {}).get('head', {}).get('sha')
                if api_sha and api_sha != event.patchset:
                    self.log.info(
                        "PR %s webhook head %s differs from API head %s; "
                        "using API head", event.change_number,
                        event.patchset, api_sha)
                    event.patchset = api_sha
            except Exception:
                self.log.exception(
                    "Failed to resolve authoritative head for PR %s; "
                    "using webhook head %s",
                    event.change_number, event.patchset)

        # Handle label changes
        if event.action == 'label_updated':
            labels = pr.get('labels', [])
            event.label = [label.get('name') for label in labels]

        # Handle PR edits (title/body changes)
        if event.action == 'edited':
            changes = payload.get('changes', {})
            # Track if body/description was edited
            if 'body' in changes:
                event.message_edited = True

        return event

    def _handlePushEvent(self, payload):
        """Handle push webhook"""
        event = GiteaTriggerEvent()
        event.type = 'gt_push'
        event.project_hostname = self.connection.canonical_hostname
        event.project_name = payload.get('repository', {}).get('full_name')
        event.ref = payload.get('ref')
        event.branch = payload.get('ref', '').replace('refs/heads/', '')
        event.newrev = payload.get('after')
        event.oldrev = payload.get('before')
        event.timestamp = time.time()

        return event

    def _handlePullRequestReviewEvent(self, payload):
        """Handle pull request review webhook"""
        event = GiteaTriggerEvent()
        event.type = 'gt_pull_request_review'
        event.action = payload.get('action', 'submitted')
        event.project_hostname = self.connection.canonical_hostname
        event.timestamp = time.time()

        pr = payload.get('pull_request', {})
        review = payload.get('review', {})

        event.project_name = payload.get('repository', {}).get('full_name')
        event.change_number = pr.get('number')
        event.branch = pr.get('base', {}).get('ref')
        event.ref = f"refs/pull/{pr.get('number')}/head"
        event.patchset = pr.get('head', {}).get('sha')

        # Map Gitea review states to Zuul states
        review_state = review.get('state', '').lower()
        if review_state == 'approved':
            event.state = 'approved'
        elif review_state == 'request_changes':
            event.state = 'request_changes'
        elif review_state == 'comment':
            event.state = 'comment'
            event.comment = review.get('body', '')
        else:
            event.state = review_state

        return event

    def _handlePullRequestReviewDismissedEvent(self, payload):
        """Handle pull request review dismissal webhook"""
        event = GiteaTriggerEvent()
        event.type = 'gt_pull_request_review'
        event.action = 'dismissed'
        event.project_hostname = self.connection.canonical_hostname
        event.timestamp = time.time()

        pr = payload.get('pull_request', {})
        review = payload.get('review', {})

        event.project_name = payload.get('repository', {}).get('full_name')
        event.change_number = pr.get('number')
        event.branch = pr.get('base', {}).get('ref')
        event.ref = f"refs/pull/{pr.get('number')}/head"
        event.patchset = pr.get('head', {}).get('sha')
        event.state = 'dismissed'

        return event

    def _handleIssueCommentEvent(self, payload):
        """Handle issue comment webhook (includes PR comments)"""
        issue = payload.get('issue', {})
        if not issue.get('pull_request'):
            return None

        comment = payload.get('comment', {})
        pr = payload.get('pull_request', {})

        event = GiteaTriggerEvent()
        event.type = 'gt_pull_request'
        event.action = 'comment'
        event.project_hostname = self.connection.canonical_hostname
        event.project_name = payload.get('repository', {}).get('full_name')
        event.change_number = issue.get('number')
        event.comment = comment.get('body', '')
        event.timestamp = time.time()

        # Add PR-specific fields needed for event matching
        event.branch = pr.get('base', {}).get('ref')
        event.ref = f"refs/pull/{issue.get('number')}/head"
        event.patchset = pr.get('head', {}).get('sha')
        event.title = pr.get('title', '')

        return event


class GiteaWebController(BaseWebController):
    """Handle Gitea webhooks"""
    log = logging.getLogger("zuul.GiteaWebController")
    tracer = trace.get_tracer("zuul")

    def __init__(self, zuul_web, connection):
        self.connection = connection
        self.zuul_web = zuul_web
        from zuul.zk.event_queues import ConnectionEventQueue
        self.event_queue = ConnectionEventQueue(
            self.zuul_web.zk_client,
            self.connection.connection_name,
            None
        )
        self.webhook_secret = self.connection.connection_config.get(
            'webhook_secret')

    def _validate_signature(self, body, headers):
        """Validate webhook signature using HMAC-SHA256.

        Args:
            body: Raw request body bytes
            headers: Request headers dict (lowercase keys)

        Returns:
            True if signature is valid

        Raises:
            cherrypy.HTTPError: If signature is missing or invalid
        """
        if not self.webhook_secret:
            # No secret configured, skip validation (but log warning)
            self.log.warning(
                "No webhook_secret configured - skipping signature "
                "validation. This is a security risk!")
            return True

        try:
            request_signature = headers['x-gitea-signature']
        except KeyError:
            raise cherrypy.HTTPError(401, 'X-Gitea-Signature header missing.')

        # Gitea sends just the hex digest, not "sha256=..." format
        payload_signature = _sign_request(body, self.webhook_secret)
        # Extract just the hex part if it has a prefix
        if '=' in payload_signature:
            payload_signature = payload_signature.split('=', 1)[1]

        self.log.debug("Payload Signature: %s", payload_signature)
        self.log.debug("Request Signature: %s", request_signature)

        if not hmac.compare_digest(payload_signature, request_signature):
            raise cherrypy.HTTPError(
                401,
                'Request signature does not match calculated payload '
                'signature. Check that webhook_secret is correct.')

        return True

    @cherrypy.expose
    @cherrypy.tools.json_out(content_type='application/json; charset=utf-8')
    @tracer.start_as_current_span("GiteaEvent")
    def payload(self):
        """Handle incoming webhook payloads.

        Reads raw body to validate HMAC signature before processing.
        """
        # Normalize headers to lowercase for consistent access
        headers = dict()
        for key, value in cherrypy.request.headers.items():
            headers[key.lower()] = value

        # Read raw body for signature validation
        body = cherrypy.request.body.read()

        # Validate webhook signature
        self._validate_signature(body, headers)

        # Parse JSON body after validation
        json_body = json.loads(body.decode('utf-8'))

        event_type = headers.get('x-gitea-event')
        self.log.info("Received Gitea webhook: %s", event_type)

        # Include tracing span context for distributed tracing
        data = {
            'headers': headers,
            'body': json_body,
            'span_context': tracing.getSpanContext(trace.get_current_span()),
        }
        self.event_queue.put(data)

        return {'message': 'ok'}
