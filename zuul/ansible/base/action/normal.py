# Copyright 2025 Acme Gating, LLC
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

from zuul.ansible import paths, stream_setup

normal = paths._import_ansible_action_plugin("normal")


class ActionModule(normal.ActionModule):

    def run(self, tmp=None, task_vars=None):
        module_name = self._task.action
        if module_name in (
                'ansible.windows.win_shell',
                'ansible.windows.win_command',
        ):
            stream_setup.stream_setup_run(self, task_vars)
        return super(ActionModule, self).run(tmp, task_vars)

    def _execute_module(self, module_name=None, **kw):
        if module_name is None:
            module_name = self._task.action
        if module_name == 'ansible.windows.win_shell':
            module_name = 'win_shell'
        elif module_name == 'ansible.windows.win_command':
            module_name = 'win_command'
        return super(ActionModule, self)._execute_module(
            module_name=module_name, **kw)
