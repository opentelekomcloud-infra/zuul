# Copyright 2022-2024 Acme Gating, LLC
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
import math

import zuul.provider.schema as provider_schema
from zuul.lib.voluputil import (
    AsList,
    Nullable,
    Optional,
    Required,
    assemble,
    discriminate,
)

import voluptuous as vs

from zuul.driver.openstack.openstackendpoint import (
    OpenstackCreateStateMachine,
    OpenstackDeleteStateMachine,
)
from zuul.model import QuotaInformation
from zuul.provider import (
    BaseProvider,
    BaseProviderFlavor,
    BaseProviderImage,
    BaseProviderLabel,
    BaseProviderSchema,
)


class OpenstackProviderImage(BaseProviderImage):
    # This is used here and in flavors and labels
    inheritable_openstack_image_schema = assemble(
        vs.Schema({
            Optional('volume-size'): Nullable(int),
        }),
        provider_schema.cloud_image,
    )
    openstack_cloud_schema = vs.Schema({
        Required('image-id'): str,
        Optional('config-drive', default=True): bool,
        Required('type'): 'cloud',
    })
    cloud_schema = vs.All(
        assemble(
            BaseProviderImage.cloud_schema,
            openstack_cloud_schema,
            inheritable_openstack_image_schema,
        ),
    )
    inheritable_openstack_zuul_schema = vs.Schema({
        # None is an acceptable explicit value for imds-support
        Optional('config-drive', default=True): bool,
    })
    openstack_zuul_schema = vs.Schema({
        Required('type'): 'zuul',
    })
    zuul_schema = assemble(
        BaseProviderImage.zuul_schema,
        openstack_zuul_schema,
        inheritable_openstack_image_schema,
        inheritable_openstack_zuul_schema,
    )
    inheritable_cloud_schema = assemble(
        BaseProviderImage.inheritable_cloud_schema,
        inheritable_openstack_image_schema,
    )
    inheritable_zuul_schema = assemble(
        BaseProviderImage.inheritable_zuul_schema,
        inheritable_openstack_image_schema,
        inheritable_openstack_zuul_schema,
    )
    schema = vs.Union(
        cloud_schema, zuul_schema,
        discriminant=discriminate(
            lambda val, alt: val['type'] == alt['type']),
    )
    inheritable_schema = assemble(
        inheritable_cloud_schema,
        inheritable_zuul_schema,
    )

    def __init__(self, image_config, provider_config, image_format):
        self.image_id = None
        super().__init__(image_config, provider_config)
        self.format = image_format
        # Implement provider defaults
        if self.connection_type is None:
            self.connection_type = 'ssh'
        if self.connection_port is None:
            self.connection_port = 22


class OpenstackProviderFlavor(BaseProviderFlavor):
    openstack_flavor_schema = vs.Schema({
        Required('flavor-name'): str,
    })

    inheritable_schema = assemble(
        BaseProviderFlavor.inheritable_schema,
        OpenstackProviderImage.inheritable_openstack_image_schema,
        provider_schema.cloud_flavor,
    )
    schema = assemble(
        BaseProviderFlavor.schema,
        provider_schema.cloud_flavor,
        OpenstackProviderImage.inheritable_openstack_image_schema,
        openstack_flavor_schema,
    )


class OpenstackProviderLabel(BaseProviderLabel):
    inheritable_openstack_label_schema = vs.Schema({
        Optional('az'): Nullable(str),
        Optional('auto-floating-ip', default=True): bool,
        Optional('boot-from-volume', default=False): bool,
        Optional(
            'networks', default=[],
            doc="""The OpenStack networks to associate with the node."""
        ): AsList(str),
        Optional('security-groups', default=[]): AsList(str),
    })
    inheritable_schema = assemble(
        BaseProviderLabel.inheritable_schema,
        OpenstackProviderImage.inheritable_openstack_image_schema,
        provider_schema.ssh_label,
        inheritable_openstack_label_schema,
    )
    schema = assemble(
        BaseProviderLabel.schema,
        OpenstackProviderImage.inheritable_openstack_image_schema,
        provider_schema.ssh_label,
        inheritable_openstack_label_schema,
    )


class OpenstackProviderSchema(BaseProviderSchema):
    def getLabelSchema(self):
        return OpenstackProviderLabel.schema

    def getImageSchema(self):
        return OpenstackProviderImage.schema

    def getFlavorSchema(self):
        return OpenstackProviderFlavor.schema

    def getInheritableLabelSchema(self):
        return OpenstackProviderLabel.inheritable_schema

    def getInheritableImageSchema(self):
        return OpenstackProviderImage.inheritable_schema

    def getInheritableFlavorSchema(self):
        return OpenstackProviderFlavor.inheritable_schema

    def getProviderSchema(self):
        schema = super().getProviderSchema()

        resource_limits = {
            'instances': int,
            'cores': int,
            'ram': int,
            'volumes': int,
            'volume-gb': int,
        }

        openstack_provider_schema = vs.Schema({
            Optional('region'): Nullable(str),
            Optional('resource-limits', default=dict()): resource_limits,
            Optional('floating-ip-cleanup', default=False): bool,
            Optional('port-cleanup-interval', default=600): int,
        })

        return assemble(
            schema,
            openstack_provider_schema,
        )


class OpenstackProvider(BaseProvider, subclass_id='openstack'):
    log = logging.getLogger("zuul.OpenstackProvider")
    schema = OpenstackProviderSchema().getProviderSchema()

    @property
    def endpoint(self):
        ep = getattr(self, '_endpoint', None)
        if ep:
            return ep
        self._set(_endpoint=self.getEndpoint())
        return self._endpoint

    def parseImage(self, image_config, provider_config, connection):
        # We are not fully constructed yet at this point, so we need
        # to peek to get the region and endpoint.
        region = provider_config.get('region')
        endpoint = connection.driver._getEndpoint(
            self.zk_client, connection, region, self.system_id)
        return OpenstackProviderImage(
            image_config, provider_config,
            image_format=endpoint.getImageFormat())

    def parseFlavor(self, flavor_config, provider_config, connection):
        return OpenstackProviderFlavor(flavor_config, provider_config)

    def parseLabel(self, label_config, provider_config, connection):
        return OpenstackProviderLabel(label_config, provider_config)

    def getEndpoint(self):
        return self.driver.getEndpoint(self)

    def getCreateStateMachine(self, node, image_external_id, log):
        # TODO: decide on a method of producing a hostname
        # that is max 15 chars.
        hostname = f"np{node.uuid[:13]}"
        label = self.labels[node.label]
        flavor = self.flavors[label.flavor]
        image = self.images[label.image]
        return OpenstackCreateStateMachine(
            self.endpoint,
            node,
            hostname,
            label,
            flavor,
            image,
            image_external_id,
            node.tags,
            log)

    def getDeleteStateMachine(self, node, log):
        return OpenstackDeleteStateMachine(self.endpoint, node, log)

    def listInstances(self):
        return self.endpoint.listInstances()

    def getQuotaLimits(self):
        limits = self.endpoint.quota_cache.getLimits()
        if limits is None:
            limits = {}
        else:
            limits = limits.quota
        cloud = QuotaInformation(default=math.inf, **limits)
        zuul = QuotaInformation(default=math.inf, **self.resource_limits)
        cloud.min(zuul)
        return cloud

    def getQuotaForLabel(self, label):
        flavor = self.flavors[label.flavor]
        return self.endpoint.getQuotaForLabel(label, flavor)

    def refreshQuotaForLabel(self, label, update):
        flavor = self.flavors[label.flavor]
        return self.endpoint.refreshQuotaForLabel(label, flavor, update)

    def getImageUploadJob(self, provider_image, image_name,
                          image_format, metadata, md5, sha256):
        return self.endpoint.getImageUploadJob(
            provider_image, image_name,
            image_format, metadata, md5, sha256)

    def deleteImage(self, external_id):
        self.endpoint.deleteImage(external_id)
