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

# In newer pbr versions the private attribute _from_git was removed/renamed.
# We only need to trigger the javascript build before version calculation; if
# the original helper is not present we degrade gracefully instead of failing.
try:  # backward compatibility with pbr<6
    _old_from_git = pbr.packaging._from_git  # type: ignore[attr-defined]
except AttributeError:  # pbr>=6 (internal API removed)
    _old_from_git = None  # noqa: N816 (preserve existing variable name pattern)


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


def _from_git(distribution):  # noqa: D401 - internal hook wrapper
    """Wrapper which ensures the JS bundle exists before versioning.

    If the legacy pbr.packaging._from_git is available we delegate to it;
    otherwise (newer pbr) we simply return and let pbr continue with its
    normal version resolution path (which no longer uses this symbol).
    """
    _build_javascript()
    if _old_from_git is not None:
        return _old_from_git(distribution)
    # Newer pbr: nothing further required. Returning None keeps behavior
    # consistent with a no-op hook.
    return None


def setup_hook(config):  # noqa: D401 - pbr entry point
    # Only monkeypatch if the legacy attribute exists; on newer pbr this would
    # raise AttributeError and break editable installs.
    if _old_from_git is not None:
        pbr.packaging._from_git = _from_git  # type: ignore[attr-defined]
    else:
        # Still run JS build eagerly so sdist/wheel have assets.
        _build_javascript()
