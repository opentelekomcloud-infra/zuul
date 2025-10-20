# Copyright 2024 Acme Gating, LLC
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

# This file contains provider-related schema chunks that can be reused
# by multiple drivers.  When adding new configuration options, if they
# can be used by more than one driver, add them here instead of in the
# driver.

import voluptuous as vs
from zuul.lib.voluputil import Required, Optional, Nullable, Constant

# Labels

# The label attributes which can appear either in the main body of the
# section stanza, or in a section/provider label, or in a standalone
# label.
common_label = vs.Schema({
    Optional(
        'boot-timeout', default=300,
        doc="""The time (in seconds) to wait for a node to boot.""",
    ): int,
    Optional(
        'max-ready-age', default=0,
        doc="""\
        The time (in seconds) an unassigned node should stay in ready state.
        """
    ): int,
    Optional(
        'max-age', default=0,
        doc="""\
        The time (in seconds) since creation that a node may be
        available for use.  Ready nodes older than this time will be
        deleted.
        """
    ): int,
    Optional(
        'min-retention-time', default=0,
        doc="""\
        The time (in seconds) since an instance was launched, during
        which a node will not be deleted. For node resources with
        minimum billing times, this can be used to ensure that the
        instance is retained for at least the minimum billing interval.

        This setting takes precedence over `max-[ready-]age`.
        """
    ): int,
    Optional(
        'snapshot-timeout', default=3600,
        doc="""The time (in seconds) to wait for a snapshot to complete."""
    ): int,
    Optional(
        'snapshot-expiration', default=3600 * 24 * 7,
        doc="""The time (in seconds) until a snapshot expires."""
    ): int,
    Optional(
        'slots', default=1,
        doc="""\
        How many jobs are permitted run on the same node simultaneously."""
    ): int,
    Optional(
        'reuse', default=False,
        doc="""\
        Should the node be reused (True) or deleted (False) after use."""
    ): bool,
    Optional(
        'executor-zone',
        doc="""\
        Specify that a Zuul executor in the specified zone is
        used to run jobs with nodes from this label.
        """,
    ): Nullable(str),
    Optional('tags', default=dict): {str: str},
    Optional(
        'final',
        doc="""\
        Whether the configuration of the label may be updated
        by values in label-defaults or overidden with a new definition
        by sections or providers lower in the hierarchy than the point
        at which the final attribute is applied.""",
        default=False): vs.Any(
            Constant(True,
                     doc="The label may not be updated or overidden."),
            Constant(False,
                     doc="The label may be updated or overidden."),
            Constant('allow-override',
                     doc="""\
                     The label may not be updated by label-defaults
                     but may be explicitly overidden by redefining
                     it in a new 'label' entry.""")),
})

# The label attributes that can appear in a section/provider label or
# a standalone label (but not in the section body).
base_label = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
    Optional('image'): Nullable(str),
    Optional('flavor'): Nullable(str),
    Optional('min-ready', default=0): int,
})

# Label attributes that are common to any kind of ssh-based driver.
ssh_label = vs.Schema({
    Optional('key-name'): Nullable(str),
    Optional('host-key-checking', default=True): bool,
})

# Images

# The image attributes which can appear either in the main body of the
# section stanza, or in a section/provider image, or in a standalone
# image.
common_image = vs.Schema({
    Optional('username'): Nullable(str),
    Optional('connection-type'): Nullable(str),
    Optional('connection-port'): Nullable(int),
    Optional('python-path'): Nullable(str),
    Optional('shell-type'): Nullable(str),
    Optional('import-timeout', default=300): int,
    Optional(
        'final',
        doc="""\
        Whether the configuration of the label may be updated
        by values in label-defaults or overidden with a new definition
        by sections or providers lower in the hierarchy than the point
        at which the final attribute is applied.""",
        default=False): vs.Any(
            Constant(True,
                     doc="The label may not be updated or overidden."),
            Constant(False,
                     doc="The label may be updated or overidden."),
            Constant('allow-override',
                     doc="""\
                     The label may not be updated by label-defaults
                     but may be explicitly overidden by redefining
                     it in a new 'label' entry.""")),
})

# Same as above, but only for cloud drivers.
cloud_image = vs.Schema({
    Optional('userdata'): Nullable(str),
})

# Same as above, but only for zuul images.
common_image_zuul = vs.Schema({
    Optional('upload-methods', default=['copy', 'import', 'upload']):
    vs.Any(['copy', 'import', 'upload']),
    Optional('tags', default=dict): {str: str},
})

# The image attributes that, in addition to those above, can appear in
# a section/provider image or a standalone image (but not in the
# section body).
base_image = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
    Required('branch'): str,
    Required('type'): vs.Any('cloud', 'zuul'),
})

# Flavors

# The flavor attributes that can appear in a section/provider flavor or
# a standalone flavor (but not in the section body).
base_flavor = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
})

common_flavor = vs.Schema({
    Optional(
        'final',
        doc="""\
        Whether the configuration of the flavor may be updated
        by values in flavor-defaults or overidden with a new definition
        by sections or providers lower in the hierarchy than the point
        at which the final attribute is applied.""",
        default=False): vs.Any(
            Constant(True,
                     doc="The flavor may not be updated or overidden."),
            Constant(False,
                     doc="The flavor may be updated or overidden."),
            Constant('allow-override',
                     doc="""\
                     The flavor may not be updated by flavor-defaults
                     but may be explicitly overidden by redefining
                     it in a new 'flavor' entry.""")),
})

# Flavor attributes that are common to any kind of cloud driver.
cloud_flavor = vs.Schema({
    Optional('public-ipv4', default=False): bool,
    Optional('public-ipv6', default=False): bool,
})
