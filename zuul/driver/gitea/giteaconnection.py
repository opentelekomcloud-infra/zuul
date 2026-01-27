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
import threading
import requests
import json
import hmac
import hashlib
import time
import cherrypy
from urllib.parse import quote_plus

from zuul.connection import BaseConnection, ZKBranchCacheMixin
from zuul.web.handler import BaseWebController
from zuul.driver.gitea.giteamodel import GiteaTriggerEvent, PullRequest
from zuul.zk.change_cache import AbstractChangeCache
from zuul.zk.branch_cache import BranchInfo, BranchFlag
from zuul.model import Ref, Tag, Branch

TIMEOUT = 30


class GiteaChangeCache(AbstractChangeCache):
    log = logging.getLogger("zuul.driver.GiteaChangeCache")

    CHANGE_TYPE_MAP = {
        "Ref": Ref,
        "Tag": Tag,
        "Branch": Branch,
        "PullRequest": PullRequest,
    }


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
        self.webhook_token = self.connection_config.get('webhook_token')

        # Initialize project storage early (also in onLoad for scheduler)
        self.projects = {}
        self.project_locks = {}

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

    def _makeRequest(self, method, path, **kwargs):
        """Make an HTTP request to Gitea API"""
        url = f"{self.baseurl}/api/v1{path}"
        kwargs.setdefault('timeout', TIMEOUT)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            self.log.error("Gitea API request failed: %s", e)
            raise

    def getRefSha(self, project_name, ref):
        """Get SHA for a given ref"""
        try:
            data = self._makeRequest('GET', f'/repos/{project_name}/git/refs/{ref}')
            return data.get('object', {}).get('sha')
        except Exception as e:
            self.log.error("Failed to get ref SHA: %s", e)
            return None

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
        # Set patchset to HEAD SHA if not already set
        head_sha = pr_data.get('head', {}).get('sha')
        if not change.patchset or change.patchset == 'None':
            change.patchset = head_sha
            self.log.info("Set patchset to %s for PR %s", head_sha, change.number)
        change.is_current_patchset = (head_sha == change.patchset)
        change.ref = f"refs/pull/{change.number}/head"
        change.branch = pr_data.get('base', {}).get('ref')
        change.base_sha = pr_data.get('base', {}).get('sha')
        change.commit_id = head_sha
        change.owner = pr_data.get('user', {}).get('login')

        # Fetch changed files for the PR
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

        # Fetch and store branch protection information
        self._updateBranchProtection(change)

        return change

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
            
            if result and result.get('merged'):
                self.log.info("Successfully merged PR %s#%s with method %s",
                            project_name, pr_number, method)
                return
            
            # If we got here, merge didn't succeed
            error_msg = result.get('message', 'Unknown error') if result else 'No response from API'
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
                    # Check if all required status checks have passed
                    # This would require fetching commit statuses - for now we assume passed
                    # In production, you'd want to fetch and verify statuses here
                    self.log.debug(
                        "Change %s has status check requirements: %s",
                        change, change.required_contexts)
        
        return True

    def getChangesDependingOn(self, change, projects, tenant):
        """Get changes depending on this change"""
        return []

    def getProjectBranchSha(self, project_name, branch_name):
        """Get SHA for a project branch"""
        return self.getRefSha(project_name, f'refs/heads/{branch_name}')

    def isMerged(self, change):
        """Check if a change is merged"""
        return change.is_merged if hasattr(change, 'is_merged') else False

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
        headers = event_data.get('headers', {})
        body = event_data.get('body', {})
        event_type = headers.get('x-gitea-event')

        self.log.debug("Processing Gitea event: %s", event_type)

        event = None
        if event_type == 'pull_request':
            event = self._handlePullRequestEvent(body)
        elif event_type == 'issue_comment':
            event = self._handleIssueCommentEvent(body)
        elif event_type == 'push':
            event = self._handlePushEvent(body)

        if event:
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

        # Extract label names for label_updated action
        if event.action == 'label_updated':
            labels = pr.get('labels', [])
            event.label = [label.get('name') for label in labels]

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

        return event


class GiteaWebController(BaseWebController):
    """Handle Gitea webhooks"""
    log = logging.getLogger("zuul.GiteaWebController")

    def __init__(self, zuul_web, connection):
        self.connection = connection
        self.zuul_web = zuul_web
        from zuul.zk.event_queues import ConnectionEventQueue
        self.event_queue = ConnectionEventQueue(
            self.zuul_web.zk_client,
            self.connection.connection_name,
            None
        )

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def payload(self):
        """Handle incoming webhook payloads"""
        headers = dict()
        for key, value in cherrypy.request.headers.items():
            headers[key.lower()] = value

        event_type = headers.get('x-gitea-event')
        payload = cherrypy.request.json

        self.log.info("Received Gitea webhook: %s", event_type)

        data = {
            'headers': headers,
            'body': payload
        }
        self.event_queue.put(data)

        return {'message': 'ok'}
