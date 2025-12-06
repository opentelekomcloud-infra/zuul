# Copyright 2021-2025 Acme Gating, LLC
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
    RequiredExclusive,
    assemble,
    discriminate,
)

import voluptuous as vs

from zuul.driver.azure.azureendpoint import (
    AzureCreateStateMachine,
    AzureDeleteStateMachine,
)
from zuul.model import QuotaInformation
from zuul.provider import (
    BaseProvider,
    BaseProviderFlavor,
    BaseProviderImage,
    BaseProviderLabel,
    BaseProviderSchema,
)


class AzureProviderImage(BaseProviderImage):
    azure_image_reference = {
        Required('sku'): str,
        Required('publisher'): str,
        Required('version'): str,
        Required('offer'): str,
    }
    azure_image_filter = {
        Optional('location'): Nullable(str),
        Optional('name'): Nullable(str),
        Optional('tags'): Nullable(dict),
    }
    azure_gallery_image = {
        Required('gallery-name'): str,
        Required('name'): str,
        Optional('version'): Nullable(str),
    }
    # This is used here and in flavors and labels
    inheritable_azure_image_schema = assemble(
        vs.Schema({
            Optional('volume-size'): Nullable(int),
            Optional('ephemeral-disk'): Nullable(bool),
            Optional('generate-password'): Nullable(bool),
        }),
        provider_schema.cloud_image,
    )
    azure_cloud_schema = vs.Schema({
        vs.Exclusive(Required('image-filter'), 'spec'): azure_image_filter,
        vs.Exclusive(Required('image-id'), 'spec'): str,
        vs.Exclusive(Required('image-reference'), 'spec'
                     ): azure_image_reference,
        vs.Exclusive(Required('community-gallery-image'), 'spec'
                     ): azure_gallery_image,
        vs.Exclusive(Required('shared-gallery-image'), 'spec'
                     ): azure_gallery_image,
    })
    cloud_schema = vs.All(
        assemble(
            BaseProviderImage.cloud_schema,
            azure_cloud_schema,
            inheritable_azure_image_schema,
        ),
        RequiredExclusive(
            'image_id', 'image_reference', 'image_filter',
            'community_gallery_image', 'shared_gallery_image',
            msg=('Provide one of "image-id", '
                 '"image-reference", "image-filter", '
                 '"community-gallery-image", or '
                 '"shared-gallery-image" keys'))
    )
    zuul_schema = assemble(
        BaseProviderImage.zuul_schema,
        inheritable_azure_image_schema,
    )
    inheritable_cloud_schema = assemble(
        BaseProviderImage.inheritable_cloud_schema,
        inheritable_azure_image_schema,
    )
    inheritable_zuul_schema = assemble(
        BaseProviderImage.inheritable_zuul_schema,
        inheritable_azure_image_schema,
    )
    schema = vs.Union(
        cloud_schema, zuul_schema,
        discriminant=discriminate(
            lambda val, alt: val['type'] == alt['type']))
    inheritable_schema = assemble(
        inheritable_cloud_schema,
        inheritable_zuul_schema,
    )

    def __init__(self, image_config, provider_config):
        self.image_id = None
        self.image_reference = None
        self.image_filter = None
        self.community_gallery_image = None
        self.shared_gallery_image = None
        super().__init__(image_config, provider_config)
        self.format = 'vhd'
        # Implement provider defaults
        if self.connection_type is None:
            self.connection_type = 'ssh'
        if self.connection_port is None:
            self.connection_port = 22


class AzureProviderFlavor(BaseProviderFlavor):
    azure_flavor_schema = vs.Schema({
        Required('vm-size'): str,
        # TODO: add "low" priority
        Optional('priority', default='regular'): vs.Any(
            'regular', 'spot'),
        Optional('ipv4', default=False): bool,
        Optional('ipv6', default=False): bool,
    })

    inheritable_schema = assemble(
        BaseProviderFlavor.inheritable_schema,
        # This is already included via the image, but listed again
        # here for clarity.
        AzureProviderImage.inheritable_azure_image_schema,
        provider_schema.cloud_flavor,
    )
    schema = assemble(
        BaseProviderFlavor.schema,
        provider_schema.cloud_flavor,
        AzureProviderImage.inheritable_azure_image_schema,
        azure_flavor_schema,
    )


class AzureProviderLabel(BaseProviderLabel):
    azure_network_reference = {
        Optional('resource-group'): Nullable(str),
        Required('network'): str,
        Optional('subnet', default='default'): str,
    }

    azure_identity_reference = {
        Optional('resource-group'): Nullable(str),
        vs.Required('name'): str,
    }

    azure_label_schema = vs.Schema({
        Optional('az'): Nullable(str),
        vs.Exclusive(Required('subnet-id'), 'subnet'
                     ): str,
        vs.Exclusive(Required('subnet-reference'), 'subnet'
                     ): azure_network_reference,
        Optional('user-assigned-identities', default=[]
                 ): AsList(azure_identity_reference),
        Optional('key-data'): Nullable(str),
    })

    inheritable_schema = assemble(
        BaseProviderLabel.inheritable_schema,
        # This is already included via the image, but listed again
        # here for clarity.
        AzureProviderImage.inheritable_azure_image_schema,
        provider_schema.host_key_checking,
        azure_label_schema,
    )

    schema = vs.All(
        assemble(
            BaseProviderLabel.schema,
            AzureProviderImage.inheritable_azure_image_schema,
            provider_schema.host_key_checking,
            azure_label_schema,
        ),
        RequiredExclusive(
            'subnet_id', 'subnet_reference',
            msg=('Provide one of "subnet-id" or '
                 '"subnet-reference" keys'))
    )

    image_flavor_inheritable_schema = assemble(
        AzureProviderImage.inheritable_azure_image_schema,
    )


class AzureProviderSchema(BaseProviderSchema):
    def getLabelSchema(self):
        return AzureProviderLabel.schema

    def getImageSchema(self):
        return AzureProviderImage.schema

    def getFlavorSchema(self):
        return AzureProviderFlavor.schema

    def getInheritableLabelSchema(self):
        return AzureProviderLabel.inheritable_schema

    def getInheritableImageSchema(self):
        return AzureProviderImage.inheritable_schema

    def getInheritableZuulImageSchema(self):
        return AzureProviderImage.inheritable_zuul_schema

    def getInheritableCloudImageSchema(self):
        return AzureProviderImage.inheritable_cloud_schema

    def getInheritableFlavorSchema(self):
        return AzureProviderFlavor.inheritable_schema

    def getProviderSchema(self):
        schema = super().getProviderSchema()

        resource_limits = {
            'instances': int,
            'cores': int,
            'ram': int,
            'lowPriorityCores': int,
        }

        azure_provider_schema = vs.Schema({
            Required('region'): str,
            Required('resource-group'): str,
            Optional('resource-limits', default=dict()): resource_limits,
        })

        return assemble(
            schema,
            azure_provider_schema,
        )


class AzureProvider(BaseProvider, subclass_id='azure'):
    log = logging.getLogger("zuul.AzureProvider")
    schema = AzureProviderSchema().getProviderSchema()

    @property
    def endpoint(self):
        ep = getattr(self, '_endpoint', None)
        if ep:
            return ep
        self._set(_endpoint=self.getEndpoint())
        return self._endpoint

    def parseImage(self, image_config, provider_config, connection):
        return AzureProviderImage(image_config, provider_config)

    def parseFlavor(self, flavor_config, provider_config, connection):
        return AzureProviderFlavor(flavor_config, provider_config)

    def parseLabel(self, label_config, provider_config, connection):
        return AzureProviderLabel(label_config, provider_config)

    def getEndpoint(self):
        return self.driver.getEndpoint(self)

    def getCreateStateMachine(self, node, image_external_id, log):
        # TODO: decide on a method of producing a hostname
        # that is max 15 chars.
        hostname = f"np{node.uuid[:13]}"
        label = self.labels[node.label]
        flavor = self.flavors[label.flavor]
        image = self.images[label.image]
        return AzureCreateStateMachine(
            self,
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
        return AzureDeleteStateMachine(self.endpoint, node, log)

    def getEndpointLimits(self):
        limits = self.endpoint.quota_cache.getLimits()
        if limits is None:
            limits = {}
        else:
            limits = limits.quota
        return QuotaInformation(default=math.inf, **limits)

    def getQuotaForLabel(self, label):
        flavor = self.flavors[label.flavor]
        return self.endpoint.getQuotaForLabel(label, flavor)

    def refreshQuotaForLabel(self, label, update):
        flavor = self.flavors[label.flavor]
        return self.endpoint.refreshQuotaForLabel(label, flavor, update)

    def getImageUploadJob(self, provider_image, image_name,
                          image_format, metadata, md5, sha256):
        return self.endpoint.getImageUploadJob(
            self.resource_group, provider_image, image_name,
            image_format, metadata, md5, sha256)

    def deleteImage(self, external_id):
        self.endpoint.deleteImage(external_id)
