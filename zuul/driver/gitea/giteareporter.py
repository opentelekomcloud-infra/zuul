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
from zuul.reporter import BaseReporter
from zuul.exceptions import MergeFailure
from zuul.lib.logutil import get_annotated_logger
from zuul.model import MERGER_MERGE, MERGER_MERGE_RESOLVE, MERGER_SQUASH_MERGE, MERGER_MAP


def getSchema():
    """Schema for Gitea reporter configuration"""
    gitea_reporter = {
        'status': v.Any('pending', 'success', 'failure', 'error'),
        'status-url': str,
        'comment': bool,
        'merge': bool,
    }
    return gitea_reporter


class GiteaReporter(BaseReporter):
    name = 'gitea'
    log = logging.getLogger("zuul.GiteaReporter")

    # Merge modes supported by Gitea (matching GitHub driver)
    merge_modes = {
        MERGER_MERGE: 'merge',
        MERGER_MERGE_RESOLVE: 'merge',
        MERGER_SQUASH_MERGE: 'squash',
    }

    def __init__(self, driver, connection, pipeline, config=None, parse_context=None):
        super(GiteaReporter, self).__init__(driver, connection, config, parse_context)
        self.pipeline = pipeline
        self._commit_status = self.config.get('status', None) if self.config else None
        self._create_comment = self.config.get('comment', False) if self.config else False
        self._merge = self.config.get('merge', False) if self.config else False

    def report(self, item, phase1=True, phase2=True):
        """Report build results to Gitea"""
        self.log.info("Reporting to Gitea for item: %s", item)
        
        ret = []
        for change in item.changes:
            err = self._reportChange(item, change, phase1, phase2)
            if err:
                ret.append(err)
        return ret

    def _reportChange(self, item, change, phase1=True, phase2=True):
        """Report on a single change"""
        # Only report to Gitea if the source is GiteaSource
        if not hasattr(change.project, 'source'):
            return
        
        from zuul.driver.gitea.giteasource import GiteaSource
        if not isinstance(change.project.source, GiteaSource):
            return

        # Filter by canonical hostname
        if change.project.source.connection.canonical_hostname != \
                self.connection.canonical_hostname:
            return

        # Set commit status (for both PRs and pushes)
        if phase1 and self._commit_status is not None:
            if (hasattr(change, 'patchset') and change.patchset is not None):
                self.setCommitStatus(item, change)
            elif (hasattr(change, 'newrev') and change.newrev is not None):
                self.setCommitStatus(item, change)

        # Comments can only be added to pull requests
        if phase2 and self._create_comment and hasattr(change, 'number'):
            self.addComment(item, change)

        # Merge can only be performed on pull requests
        if phase2 and self._merge and hasattr(change, 'number'):
            errors_received = False
            err = self.mergePull(item, change)
            if err:
                errors_received = True
            return err if errors_received else None

    def setCommitStatus(self, item, change):
        """Set commit status on Gitea"""
        project = change.project.name
        if hasattr(change, 'patchset'):
            sha = change.patchset
        elif hasattr(change, 'newrev'):
            sha = change.newrev
        else:
            self.log.warning("Change has no patchset or newrev, cannot set status")
            return

        # Compute context dynamically from item (tenant/pipeline format)
        context = "{}/{}".format(item.manager.tenant.name, item.manager.pipeline.name)
        
        state = self._commit_status
        url = item.formatItemUrl() if hasattr(item, 'formatItemUrl') else None
        description = '%s status: %s (%s)' % (
            item.manager.pipeline.name, self._commit_status, sha)

        self.log.info(
            'Setting commit status for %s, sha: %s, state: %s, context: %s, url: %s, description: %s',
            change, sha, state, context, url, description)

        try:
            # Match upstream parameter order: project, sha, state, url, description, context
            self.connection.setCommitStatus(
                project, sha, state, url, description, context)
        except Exception as e:
            self.log.error("Failed to set commit status: %s", e)
            return str(e)

    def addComment(self, item, change):
        """Add comment to PR"""
        if not hasattr(change, 'number'):
            return

        message = self._formatComment(item, change)
        try:
            self.connection.commentPull(
                change.project.name, change.number, message)
        except Exception as e:
            self.log.error("Failed to add comment: %s", e)
            return str(e)

    def _formatComment(self, item, change):
        """Format comment message with job results"""
        result = item.current_build_set.result
        
        # Build header with result
        if result == 'SUCCESS':
            message = "Build succeeded"
        elif result == 'FAILURE':
            message = "Build failed"
        else:
            message = f"Build {result.lower()}"
        
        # Add buildset URL
        if hasattr(item, 'formatItemUrl'):
            url = item.formatItemUrl()
            message += f". {url}\n\n"
        else:
            message += "\n\n"
        
        # Add individual job results
        if hasattr(item, 'getJobs'):
            for job in item.getJobs():
                build = item.current_build_set.getBuild(job)
                if build:
                    job_result = build.result if build.result else "RUNNING"
                    
                    # Format duration if available
                    du

    def mergePull(self, item, change):
        """Merge a pull request using Gitea API
        
        Supports different merge modes based on project configuration:
        - merge: Standard merge commit
        - squash: Squash and merge
        """
        log = get_annotated_logger(self.log, item.event)
        merge_mode = item.current_build_set.getMergeMode(change)

        if merge_mode not in self.merge_modes:
            mode = [x[0] for x in MERGER_MAP.items() if x[1] == merge_mode][0]
            log.warning('Merge mode %s not supported by Gitea', mode)
            raise MergeFailure('Merge mode %s not supported by Gitea' % mode)

        merge_mode = self.merge_modes[merge_mode]
        project = change.project.name
        pr_number = change.number
        sha = change.patchset

        log.debug(
            f"Merging PR {change} via Gitea API with mode {merge_mode}"
        )

        try:
            self.connection.mergePull(
                project, pr_number,
                merge_title=change.title,
                merge_message=self._formatMergeMessage(change),
                sha=sha,
                method=merge_mode,
                zuul_event_id=item.event)
            change.is_merged = True
            return None
        except MergeFailure as e:
            log.exception(
                'Merge attempt of change %s failed: %s' %
                (change, str(e)))
            return str(e)

    def _formatMergeMessage(self, change):
        """Format merge commit message with review information"""
        merge_message = ''
        
        # Add review information if available
        if hasattr(change, 'pr') and change.pr:
            reviews = change.pr.get('reviews', [])
            if reviews:
                review_users = []
                for r in reviews:
                    # Get full name or fallback to login
                    name = r.get('user', {}).get('full_name') or r.get('user', {}).get('login', 'Unknown')
                    email = r.get('user', {}).get('email', 'unknown@example.com')
                    
                    if r.get('state') == 'APPROVED':
                        review_users.append('Reviewed-by: {} <{}>'.format(name, email))
                
                if review_users:
                    merge_message = '\n'.join(review_users)
        
        return merge_message

    def getSubmitAllowNeeds(self):
        """Return list of allowed needs for merge submission"""
        return []ration = ""
                    if build.start_time and build.end_time:
                        seconds = int(build.end_time - build.start_time)
                        minutes, secs = divmod(seconds, 60)
                        duration = f" in {minutes}m {secs:02d}s"
                    
                    message += f"**{job.name}**: {job_result}{duration}\n"
        
        return message
