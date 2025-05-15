// Copyright 2025 Acme Gating, LLC
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

import React, { useState } from 'react'
import PropTypes from 'prop-types'
import { useDispatch, useSelector } from 'react-redux'

import {
  Button,
  Checkbox,
  FormGroup,
  Modal,
  ModalVariant,
  TextInput,
} from '@patternfly/react-core'

import { addApiError } from '../../actions/notifications'
import { setTenantState } from '../../api'

function PauseModal({isOpen, setOpen}) {
  const tenant = useSelector((state) => state.tenant)
  const [reason, setReason] = useState("")
  const [pauseTriggerQueue, setPauseTriggerQueue] = useState(false)
  const [pauseResultQueue, setPauseResultQueue] = useState(false)
  const dispatch = useDispatch()

  return (
    <Modal
      variant={ModalVariant.small}
      isOpen={isOpen}
      title="Pause Tenant Event Processing"
      onClose={() => { setOpen(false) }}
      actions={[
        <Button key="confirm" variant="primary"
                onClick={() => {
                  setOpen(false)
                  setTenantState(tenant.apiPrefix,
                                 pauseTriggerQueue,
                                 pauseResultQueue,
                                 reason)
                    .catch(error => {
                      dispatch(addApiError(error))
                    })
                }}>
          Confirm
        </Button>,
        <Button key="cancel" variant="link"
                onClick={() => { setOpen(false) }}>
          Cancel</Button>,
      ]}>
      <p>You can pause trigger or result event processing for this tenant.  Trigger events cause new items to appear in pipelines.  Result events cause item results to be reported (and potentially, changes merged).</p>

      <FormGroup
        label="Pause"
        fieldId="pause-form-trigger-queue-paused">
        <Checkbox
          id="pause-form-trigger-queue-paused"
          label="Pause trigger queue"
          isChecked={pauseTriggerQueue}
          onChange={(checked) => {setPauseTriggerQueue(checked)}}
        />
        <Checkbox
          id="pause-form-result-queue-paused"
          label="Pause result queue"
          isChecked={pauseResultQueue}
          onChange={(checked) => {setPauseResultQueue(checked)}}
        />
      </FormGroup>
      <FormGroup
        label="Reason"
        fieldId="pause-form-reason"
        helperText="This explanation will appear on the status page.">
        <TextInput
          value={reason}
          isRequired
          type="text"
          id="pause-form-reason"
          name="pauseReason"
          onChange={(value) => { setReason(value) }}
        />
      </FormGroup>
    </Modal>
  )
}

PauseModal.propTypes = {
  isOpen: PropTypes.bool,
  setOpen: PropTypes.object,
}

export default (PauseModal)
