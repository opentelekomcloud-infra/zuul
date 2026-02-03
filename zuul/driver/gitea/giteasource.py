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

import logging
import re
import urllib.parse
import voluptuous as v
from zuul.source import BaseSource
from zuul.model import Project, ChangeKey, Branch, Ref, Tag


def getRequireSchema():
    """Schema for pull request requirements"""
    require = {
        'status': v.Any(str, [str]),
        'open': bool,
        'merged': bool,
        'approved': bool,
        'label': v.Any(str, [str]),
    }
    return require


def getRejectSchema():
    """Schema for pull request rejection criteria"""
    reject = {
        'status': v.Any(str, [str]),
        'open': bool,
        'merged': bool,
        'approved': bool,
        'label': v.Any(str, [str]),
    }
    return reject


class GiteaSource(BaseSource):
    name = 'gitea'
    log = logging.getLogger("zuul.GiteaSource")

    def __init__(self, driver, connection, config=None):
        hostname = connection.canonical_hostname
        super(GiteaSource, self).__init__(driver, connection,
                                           hostname, config)

    def getRefSha(self, project, ref):
        """Get the SHA for a given ref"""
        # TODO: Implement using Gitea API
        return self.connection.getRefSha(project.name, ref)

    def getChange(self, change_key, refresh=False, event=None):
        """Get a change object from an event"""
        self.log.debug("Getting change for key: %s, type: %s" %
                       (change_key, change_key.change_type))

        # For pull requests, delegate to connection
        if change_key.change_type == 'PullRequest':
            return self.connection.getChange(change_key, refresh=refresh, event=event)

        # For branch push events, create a Branch object
        if change_key.change_type == 'Branch':
            # Check cache first
            change = self.connection._change_cache.get(change_key)
            if change and not refresh:
                return change

            # If no event provided (e.g., loading from ZK), we can't create the change
            if not event:
                self.log.warning("Cannot create Branch change without event for key: %s", change_key)
                return None

            project = self.getProject(change_key.project_name)
            if not change:
                change = Branch(project)
                change.project = project
                change.branch = change_key.stable_id
            change.ref = event.ref
            change.oldrev = getattr(event, 'oldrev', None)
            change.newrev = getattr(event, 'newrev', None)
            change.url = self.connection.getGitwebUrl(change_key.project_name, sha=change.newrev)
            change.files = []
            change.source_event = event
            self.log.debug("Created Branch change: %s" % change)

            # Store in cache to set cache_stat
            try:
                self.connection._change_cache.set(change_key, change)
            except Exception as e:
                self.log.warning("Failed to cache change: %s", e)
                change = self.connection._change_cache.get(change_key)
            return change

        # For tag events, create a Tag object
        if change_key.change_type == 'Tag':
            # Check cache first
            change = self.connection._change_cache.get(change_key)
            if change and not refresh:
                return change

            project = self.getProject(change_key.project_name)
            if not change:
                change = Tag(project)
                change.project = project
                change.tag = change_key.stable_id
            change.ref = event.ref
            change.oldrev = getattr(event, 'oldrev', None)
            change.newrev = getattr(event, 'newrev', None)
            change.url = self.connection.getGitwebUrl(change_key.project_name, sha=change.newrev)
            self.log.debug("Created Tag change: %s" % change)

            # Store in cache to set cache_stat
            try:
                self.connection._change_cache.set(change_key, change)
            except Exception as e:
                self.log.warning("Failed to cache change: %s", e)
                change = self.connection._change_cache.get(change_key)
            return change

        # For generic refs, create a Ref object
        if change_key.change_type == 'Ref':
            # Check cache first
            change = self.connection._change_cache.get(change_key)
            if change and not refresh:
                return change

            project = self.getProject(change_key.project_name)
            if not change:
                change = Ref(project)
                change.project = project
            change.ref = event.ref
            change.oldrev = getattr(event, 'oldrev', None)
            change.newrev = getattr(event, 'newrev', None)
            change.url = self.connection.getGitwebUrl(change_key.project_name, sha=change.newrev)
            self.log.debug("Created Ref change: %s" % change)

            # Store in cache to set cache_stat
            try:
                self.connection._change_cache.set(change_key, change)
            except Exception as e:
                self.log.warning("Failed to cache change: %s", e)
                change = self.connection._change_cache.get(change_key)
            return change

        self.log.warning("Unknown change type: %s" % change_key.change_type)
        return None

    # Regex to parse Gitea pull request URLs
    # Matches: https://gitea.example.com/owner/repo/pulls/123
    change_re = re.compile(r"/(.*?)/(.*?)/pulls/(\d+)[\w]*")

    def getChangeByURL(self, url, event):
        """Get a change from a Gitea pull request URL.

        Parses URLs like:
        - https://gitea.example.com/owner/repo/pulls/123
        - https://gitea.example.com/org/project/pulls/456

        Args:
            url: The pull request URL to parse
            event: The event context

        Returns:
            Change object if found, None otherwise
        """
        self.log.debug("getChangeByURL: %s", url)
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError:
            return None

        # Check if this URL is for our connection
        if parsed.hostname != self.connection.canonical_hostname:
            return None

        m = self.change_re.match(parsed.path)
        if not m:
            return None

        org = m.group(1)
        proj = m.group(2)
        try:
            num = int(m.group(3))
        except ValueError:
            return None

        project_name = f'{org}/{proj}'
        self.log.debug("Parsed URL: project=%s, pr=%d", project_name, num)

        # Fetch the pull request data
        pull = self.connection.getPull(project_name, num, event=event)
        if not pull:
            self.log.debug("Pull request not found: %s#%d", project_name, num)
            return None

        # Create a change key and get the change
        pr_sha = pull.get('head', {}).get('sha')
        change_key = ChangeKey(
            self.connection.connection_name,
            project_name,
            'PullRequest',
            str(num),
            str(pr_sha)
        )
        change = self.connection._getChange(change_key, event=event)
        return change

    def getProject(self, name):
        """Get a project object"""
        p = self.connection.getProject(name)
        if not p:
            p = Project(name, self)
            self.connection.addProject(p)
        return p

    def getProjectBranchCacheLtime(self):
        """Get the branch cache logical time

        This is used by Zuul to track when branch information was last updated.
        """
        return self.connection._branch_cache.ltime

    def getProjectMergeModes(self, project, tenant, min_ltime=-1):
        """Get merge modes for a project

        Uses the default implementation from connection.
        """
        return self.connection.getProjectMergeModes(project, tenant, min_ltime)

    def getProjectDefaultBranch(self, project, tenant, min_ltime=-1):
        """Get the default branch for a project

        Try to get from cache, fall back to parent implementation.
        """
        try:
            default_branch = self.connection.getProjectDefaultBranch(
                project, tenant, min_ltime)
        except Exception:
            default_branch = None
        if default_branch is None:
            return super().getProjectDefaultBranch(project, tenant, min_ltime)
        return default_branch

    def getProjectBranchSha(self, project, branch_name):
        """Get the SHA for a specific branch

        Used by Zuul to check if branches have changed.
        """
        return self.connection.getProjectBranchSha(project.name, branch_name)

    def getProjectBranches(self, project, tenant, min_ltime=-1):
        """Get branches for a project

        Uses the ZKBranchCacheMixin implementation from the connection.
        """
        return self.connection.getProjectBranches(project, tenant, min_ltime)

    def getGitUrl(self, project):
        """Get the git URL for a project"""
        return self.connection.getGitUrl(project.name)

    def getRequireFilters(self, config, parse_context):
        """Get require filters from config"""
        # TODO: Implement filter parsing
        return []

    def getRejectFilters(self, config, parse_context):
        """Get reject filters from config"""
        # TODO: Implement filter parsing
        return []

    def canMerge(self, change, allow_needs, event=None, allow_refresh=False):
        """Determine if change can merge"""
        if not change.number:
            return True
        return self.connection.canMerge(change, allow_needs, event=event)

    def getChangeKey(self, event):
        """Get change key from event"""
        connection_name = self.connection.connection_name
        if event.change_number:
            # For pull requests, patchset is the head SHA
            patchset = getattr(event, 'patchset', getattr(event, 'patch_set', None))
            return ChangeKey(connection_name, event.project_name,
                             'PullRequest',
                             str(event.change_number),
                             str(patchset))
        revision = f'{event.oldrev}..{event.newrev}'
        if event.ref and event.ref.startswith('refs/tags/'):
            tag = event.ref[len('refs/tags/'):]
            return ChangeKey(connection_name, event.project_name,
                             'Tag', tag, revision)
        if event.ref and event.ref.startswith('refs/heads/'):
            branch = event.ref[len('refs/heads/'):]
            return ChangeKey(connection_name, event.project_name,
                             'Branch', branch, revision)
        if event.ref:
            return ChangeKey(connection_name, event.project_name,
                             'Ref', event.ref, revision)
        self.log.warning("Unable to format change key for %s" % (self,))

    def getChangesDependingOn(self, change, projects, tenant):
        """Get changes depending on this change"""
        return self.connection.getChangesDependingOn(
            change, projects, tenant)

    def getProjectBranchSha(self, project, branch_name):
        """Get SHA for a project branch"""
        return self.connection.getProjectBranchSha(project.name, branch_name)

    def getProjectBranchCacheLtime(self):
        """Get project branch cache ltime"""
        return self.connection._branch_cache.ltime if hasattr(self.connection, '_branch_cache') else -1

    def getProjectOpenChanges(self, project):
        """Get open changes (pull requests) for a project.

        Fetches all open pull requests from the Gitea API and returns
        them as Change objects.

        Args:
            project: The project to get open changes for

        Returns:
            List of Change objects for open pull requests
        """
        changes = []
        try:
            prs = self.connection._searchPullRequests(project.name, state='open')
            for pr in prs:
                pr_number = pr.get('number')
                pr_sha = pr.get('head', {}).get('sha')
                change_key = ChangeKey(
                    self.connection.connection_name,
                    project.name,
                    'PullRequest',
                    str(pr_number),
                    str(pr_sha)
                )
                change = self.connection._getChange(change_key)
                if change:
                    changes.append(change)
        except Exception as e:
            self.log.warning("Failed to get open changes for %s: %s",
                           project.name, e)
        return changes

    def isMerged(self, change):
        """Check if a change is merged"""
        return self.connection.isMerged(change)
