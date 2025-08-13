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
from setuptools import setup
from setuptools.command.sdist import sdist as _sdist
from setuptools.command.build_py import build_py as _build_py


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


class sdist(_sdist):
    def run(self):
        _build_javascript()
        super().run()


class build_py(_build_py):
    def run(self):
        _build_javascript()
        super().run()


setup(
    setup_requires=['pbr'],
    pbr=True,
    cmdclass={
        'sdist': sdist,
        'build_py': build_py,
    }
)
