// Copyright 2018 Red Hat, Inc
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

import * as React from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import {
  Table,
  TableVariant,
  TableHeader,
  TableBody,
  ActionsColumn,
} from '@patternfly/react-table'
import * as moment_tz from 'moment-timezone'
import {
  PageSection,
  PageSectionVariants,
  ClipboardCopy,
} from '@patternfly/react-core'
import {
  BuildIcon,
  BundleIcon,
  FingerprintIcon,
  OutlinedCalendarAltIcon,
  RunningIcon,
  StreamIcon,
  TagIcon,
} from '@patternfly/react-icons'
import { IconProperty } from '../Misc'

import { deleteNodesetRequest } from '../api'
import { addNotification } from '../actions/notifications'
import { addApiError } from '../actions/adminActions'
import { fetchNodesetRequestsIfNeeded } from '../actions/nodesetRequests'
import { Fetchable } from '../containers/Fetching'


class NodesetRequestsPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    user: PropTypes.object,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  updateData = (force) => {
    this.props.dispatch(fetchNodesetRequestsIfNeeded(this.props.tenant, force))
  }

  componentDidMount () {
    document.title = 'Zuul Nodeset Requests'
    if (this.props.tenant.name) {
      this.updateData()
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData()
    }
  }

  handleDelete(requestId) {
    deleteNodesetRequest(this.props.tenant.apiPrefix, requestId)
      .then(() => {
        this.props.dispatch(addNotification(
          {
            text: 'Nodeset request deleted.',
            type: 'success',
            status: '',
            url: '',
          }))
        this.props.dispatch(fetchNodesetRequestsIfNeeded(this.props.tenant, true))
      })
      .catch(error => {
        this.props.dispatch(addApiError(error))
      })
  }

  render () {
    const { remoteData } = this.props
    const nodesetRequests = remoteData.requests

    const columns = [
      {
        title: (
          <IconProperty icon={<FingerprintIcon />} value="UUID" />
        ),
        dataLabel: 'uuid',
      },
      {
        title: (
          <IconProperty icon={<TagIcon />} value="Labels" />
        ),
        dataLabel: 'labels',
      },
      {
        title: (
          <IconProperty icon={<RunningIcon />} value="State" />
        ),
        dataLabel: 'state',
      },
      {
        title: (
          <IconProperty icon={<OutlinedCalendarAltIcon />} value="Age" />
        ),
        dataLabel: 'age',
      },
      {
        title: (
          <IconProperty icon={<BundleIcon />} value="Buildset" />
        ),
        dataLabel: 'buildset',
      },
      {
        title: (
          <IconProperty icon={<StreamIcon />} value="Pipeline" />
        ),
        dataLabel: 'pipeline',
      },
      {
        title: (
          <IconProperty icon={<BuildIcon />} value="Job" />
        ),
        dataLabel: 'provider',
      },
      {
        title: '',
        dataLabel: 'action',
      },
    ]
    let rows = []
    nodesetRequests.forEach((request) => {
      const r = [
        {title: request.uuid, props: {column: 'UUID'}},
        {title: request.labels.join(','), props: {column: 'Labels' }},
        {title: request.state, props: {column: 'State'}},
        {title: moment_tz.utc(request.request_time).fromNow(), props: {column: 'Age'}},
        {title: <ClipboardCopy hoverTip="Copy" clickTip="Copied" variant="inline-compact">{request.buildset_uuid}</ClipboardCopy>, props: {column: 'Buildset'}},
        {title: request.pipeline_name, props: {column: 'Pipeline'}},
        {title: request.job_name, props: {column: 'Job'}},
      ]

      if (this.props.user.isAdmin && this.props.user.scope.indexOf(this.props.tenant.name) !== -1) {
        r.push({title:
                <ActionsColumn items={[
                  {
                    title: 'Delete',
                    onClick: () => this.handleDelete(request.uuid)
                  },
                ]}/>
               })
      }
      rows.push({cells: r})
    })
    return (
      <PageSection variant={PageSectionVariants.light}>
        <PageSection style={{paddingRight: '5px'}}>
          <Fetchable
            isFetching={remoteData.isFetching}
            fetchCallback={this.updateData}
          />
        </PageSection>

        <Table
          aria-label="Nodeset Requests Table"
          variant={TableVariant.compact}
          cells={columns}
          rows={rows}
          className="zuul-table"
        >
          <TableHeader />
          <TableBody />
        </Table>
      </PageSection>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  remoteData: state.nodesetRequests,
  user: state.user,
}))(NodesetRequestsPage)
