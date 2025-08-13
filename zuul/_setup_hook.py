# Copyright 2018 Red Hat, Inc
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
"""Hook for pbr to build javascript as part of tarball."""

import os
import subprocess

import pbr.packaging
from pbr import git


def _build_javascript():
    if subprocess.call(['which', 'yarn']) != 0:
        return
    if not os.path.exists('web/node_modules/.bin/webpack'):
        r = subprocess.Popen(['yarn', 'install', '-d'], cwd="web/").wait()
        if r:
            raise RuntimeError("Yarn install failed")
    if not os.path.exists('zuul/web/static/index.html'):
        os.makedirs('zuul/web/static', exist_ok=True)
        if not os.path.islink('../zuul/web/static'):
            os.symlink('../zuul/web/static', 'web/build',
                       target_is_directory=True)
        r = subprocess.Popen(['yarn', 'build'], cwd="web/").wait()
        if r:
            raise RuntimeError("Yarn build failed")


def _from_git(distribution):
    _build_javascript()
    option_dict = distribution.get_option_dict('pbr')
    changelog = git._iter_log_oneline()
    if changelog:
        changelog = git._iter_changelog(changelog)
    git.write_git_changelog(option_dict=option_dict, changelog=changelog)
    git.generate_authors(option_dict=option_dict)


def setup_hook(config):
    pbr.packaging._from_git = _from_git
