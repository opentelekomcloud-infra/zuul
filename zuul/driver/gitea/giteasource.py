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

    def getChangeByURL(self, url, event):
        """Get a change from a URL"""
        # TODO: Parse URL and get change
        return None

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
        """Get open changes for a project"""
        return []

    def isMerged(self, change):
        """Check if a change is merged"""
        return self.connection.isMerged(change)
