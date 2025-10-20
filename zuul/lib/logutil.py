# Copyright 2019 BMW Group
# Copyright 2021 Acme Gating, LLC
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


def get_annotated_logger(logger, event=None, request=None, **annotations):
    # Note(tobiash): When running with python 3.5 log adapters cannot be
    # stacked. We need to detect this case and modify the original one.
    if isinstance(logger, EventIdLogAdapter):
        extra = logger.extra
    else:
        extra = {}

    if event is not None:
        if hasattr(event, 'zuul_event_id'):
            extra['e'] = event.zuul_event_id
        else:
            extra['e'] = event
    if request is not None:
        extra['req'] = request
    extra.update(annotations)

    if isinstance(logger, EventIdLogAdapter):
        return logger

    return EventIdLogAdapter(logger, extra)


class EventIdLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        msg, kwargs = super().process(msg, kwargs)
        extra = kwargs.get('extra', {})
        annotations = (f"[{k}: {v}]" for k, v in extra.items()
                       if v is not None)
        msg = ' '.join((*annotations, msg))
        return msg, kwargs

    def addHandler(self, *args, **kw):
        return self.logger.addHandler(*args, **kw)


class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        rec = super().format(record)
        ret = []
        # Save the existing message and re-use this record object to
        # format each line.
        saved_msg = record.message
        for i, line in enumerate(rec.split('\n')):
            if i:
                record.message = '  ' + line
                ret.append(self.formatMessage(record))
            else:
                ret.append(line)
        # Restore the message
        record.message = saved_msg
        return '\n'.join(ret)
