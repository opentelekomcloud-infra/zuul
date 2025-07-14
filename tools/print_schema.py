# Copyright 2025 Acme Gating, LLC
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

# Print out a representation of a provider configuration schema.

from zuul.driver.openstack import openstackprovider
from zuul.driver.aws import awsprovider
from zuul.lib.voluputil import Nullable

import voluptuous as vs
import yaml


class IndentedListDumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)


class SchemaWalker:
    def __init__(self, schema):
        self.schema = schema

    def toYaml(self):
        if isinstance(self.schema, str):
            return self.schema
        if type(self.schema) == type(str):  # noqa
            return "str"
        if type(self.schema) == type(int):  # noqa
            return "int"
        if type(self.schema) == type(bool):  # noqa
            return "bool"
        if type(self.schema) == type(float):  # noqa
            return "float"
        if isinstance(self.schema, Nullable):
            w = SchemaWalker(self.schema.schema)
            return w.toYaml()
        if isinstance(self.schema, vs.Schema):
            w = SchemaWalker(self.schema.schema)
            return w.toYaml()
        if isinstance(self.schema, vs.All):
            alts = []
            for v in self.schema.validators:
                w = SchemaWalker(v)
                v = w.toYaml()
                alts.append(v)
            ret = {}
            for x in alts:
                if isinstance(x, dict):
                    ret.update(x)
            return ret
        if isinstance(self.schema, vs.Union):
            ret = []
            for v in self.schema.validators:
                w = SchemaWalker(v)
                v = w.toYaml()
                ret.append(v)
            return ret
        if isinstance(self.schema, dict):
            ret = {}
            for k, v in self.schema.items():
                name = str(k)
                if '_' in name:
                    continue
                w = SchemaWalker(v)
                v = w.toYaml()
                ret[name] = v
            return ret
        if isinstance(self.schema, list):
            ret = []
            for v in self.schema:
                w = SchemaWalker(v)
                v = w.toYaml()
                if isinstance(v, list):
                    ret.extend(v)
                else:
                    ret.append(v)
            return ret


if __name__ == '__main__':
    driver = 'openstack'
    if driver == 'aws':
        ps = awsprovider.AwsProviderSchema()
    else:
        ps = openstackprovider.OpenstackProviderSchema()
    s = ps.getProviderSchema()
    w = SchemaWalker(s)
    out = w.toYaml()
    print(yaml.dump(out, Dumper=IndentedListDumper, default_flow_style=False))
