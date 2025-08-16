# Copyright 2017 Red Hat, Inc.
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

import logging
import threading
import json

import paho.mqtt.client as mqtt

from zuul.connection import BaseConnection
from zuul.exceptions import ConfigurationError
from zuul.lib.logutil import get_annotated_logger


class MQTTConnection(BaseConnection):
    driver_name = 'mqtt'
    log = logging.getLogger("zuul.MQTTConnection")

    def __init__(self, driver, connection_name, connection_config):
        super(MQTTConnection, self).__init__(driver, connection_name,
                                             connection_config)
        self.client = mqtt.Client(
            client_id=self.connection_config.get('client_id'))
        if self.connection_config.get('user'):
            self.client.username_pw_set(
                self.connection_config.get('user'),
                self.connection_config.get('password'))
        ca_certs = self.connection_config.get('ca_certs')
        certfile = self.connection_config.get('certfile')
        keyfile = self.connection_config.get('keyfile')
        ciphers = self.connection_config.get('ciphers')
        if (ciphers or certfile or keyfile) and not ca_certs:
            raise ConfigurationError(
                "MQTT TLS configuration requires the ca_certs option")
        if ca_certs:
            if bool(certfile) != bool(keyfile):
                raise ConfigurationError(
                    "MQTT configuration keyfile and certfile "
                    "options must both be set.")
            self.client.tls_set(
                ca_certs,
                certfile=certfile,
                keyfile=keyfile,
                ciphers=ciphers)
        self.connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.subscribed_topics = set()
        self.subscribe_lock = threading.Lock()
        self.response_lock = threading.Lock()
        self.item_events = {}
        self.item_results = {}

    def _on_connect(self, client, userdata, flags, rc):
        with self.subscribe_lock:
            self.connected = True
            for topic in self.subscribed_topics:
                self.log.debug("Subscribing to %s", topic)
                client.subscribe(topic)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False

    def _on_message(self, client, userdata, msg):
        self.log.debug("Received %s %s", msg.topic, msg.payload)
        data = json.loads(msg.payload)
        item_uuid = data.get('uuid', None)
        if item_uuid is None:
            return
        result = data.get('merge_response', None)
        if result is None:
            return
        result = bool(result)
        with self.response_lock:
            event = self.item_events.get(item_uuid)
            if event is None:
                return
            self.item_results[item_uuid] = result
            event.set()
            self.log.debug("Set result for %s to %s", item_uuid, result)

    def onLoad(self, zk_client, component_registry):
        self.log.debug("Starting MQTT Connection")

        # If the connection was not loaded by a scheduler, but by e.g.
        # zuul-web, we want to stop here.
        if not self.sched:
            return

        try:
            self.client.connect(
                self.connection_config.get('server', 'localhost'),
                port=int(self.connection_config.get('port', 1883)),
                keepalive=int(self.connection_config.get('keepalive', 60))
            )
            self.connected = True
        except Exception:
            self.log.exception("MQTT reporter (%s) couldn't connect" % self)
        self.client.loop_start()

    def onStop(self):
        if self.connected:
            self.log.debug("Stopping MQTT Connection")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    def publish(self, topic, message, qos, zuul_event_id):
        log = get_annotated_logger(self.log, zuul_event_id)
        if not self.connected:
            log.warning("MQTT reporter (%s) is disabled", self)
            return
        try:
            self.client.publish(topic, payload=json.dumps(message), qos=qos)
        except Exception:
            log.exception(
                "Could not publish message to topic '%s' via mqtt", topic)

    def subscribe(self, topic):
        if topic in self.subscribed_topics:
            return
        with self.subscribe_lock:
            if self.connected:
                self.log.debug("Subscribing to %s", topic)
                self.client.subscribe(topic)
            self.subscribed_topics.add(topic)
