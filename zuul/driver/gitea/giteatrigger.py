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

import voluptuous as v
from zuul.trigger import BaseTrigger
from zuul.driver.util import to_list, make_regex


def getSchema():
    """Get voluptuous schema for Gitea trigger configuration"""
    gitea_trigger = {
        v.Required('event'): v.Any('gt_pull_request', 'gt_pull_request_review', 'gt_push', 'gt_tag'),
        'action': v.Any(str, [str]),
        'branch': v.Any(str, [str]),
        'ref': v.Any(str, [str]),
        'comment': v.Any(str, [str]),
        'label': v.Any(str, [str]),
        'unlabel': v.Any(str, [str]),
        'state': v.Any(str, [str]),  # For review events (approved, comment, request_changes)
    }
    return gitea_trigger


class GiteaTrigger(BaseTrigger):
    name = 'gitea'

    def __init__(self, driver, connection, config=None):
        super(GiteaTrigger, self).__init__(driver, connection, config)

    def getEventFilters(self, connection_name, trigger_config, parse_context):
        from zuul.driver.gitea.giteamodel import GiteaEventFilter
        efilters = []
        pcontext = parse_context

        for trigger in to_list(trigger_config):
            with pcontext.confAttr(trigger, 'event') as attr:
                types = [make_regex(x, pcontext)
                        for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'action') as attr:
                actions = [make_regex(x, pcontext)
                          for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'branch') as attr:
                branches = [make_regex(x, pcontext)
                           for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'ref') as attr:
                refs = [make_regex(x, pcontext)
                       for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'comment') as attr:
                comments = [make_regex(x, pcontext)
                           for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'label') as attr:
                labels = [make_regex(x, pcontext)
                         for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'unlabel') as attr:
                unlabels = [make_regex(x, pcontext)
                           for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'state') as attr:
                states = [make_regex(x, pcontext)
                         for x in to_list(attr)]

            f = GiteaEventFilter(
                connection_name=connection_name,
                trigger=self,
                types=types,
                actions=actions,
                branches=branches,
                refs=refs,
                comments=comments,
                labels=labels,
                unlabels=unlabels,
                states=states,
            )
            efilters.append(f)

        return efilters
