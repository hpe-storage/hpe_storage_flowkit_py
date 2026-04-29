#    (c) Copyright 2026 Hewlett Packard Enterprise Development LP
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
from hpe_storage_flowkit_py.v3.src.validators.remote_copy_validator import (
    validate_admit_rcopy_host_params,
)
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.utils.constants import RC_GROUP_ADMIT_HOST
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response

logger = Logger()


class RemoteCopyGroupWorkflow:
    """Workflow for Remote Copy Group operations on V3 API."""

    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    # ---- Internal helpers ----

    def _get_rcg_info(self, name):
        """Get remote copy group info by name.

        Queries: GET /remotecopygroups?name=<name>
        Returns the matching member dict (with uid, name, etc.)
        or None if not found.

        The API returns an empty list when the RCG does not exist,
        or a list of length 1 when it does.
        """
        try:
            logger.debug(f"Fetching remote copy group info for '{name}'")
            #Use experimentalfilter header to support query filtering
            headers = {'experimentalfilter': 'true'}
            uri = f"/remotecopygroups?name={name}"
            response = self.session_mgr.rest_client.get(uri, headers=headers)
            if response:
                logger.info(f"Found RCG '{name}' with UID: {response[0].get('uid')}")
                return response[0]
            logger.info(f"Remote copy group '{name}' not found")
            return None
        except Exception as e:
            logger.exception(f"Failed to get RCG info for '{name}': {e}")
            raise

    def _get_rcg_uid(self, name):
        """Return the UID of a remote copy group by name, or raise if not found."""
        rcg_info = self._get_rcg_info(name)
        if not rcg_info:
            raise exceptions.RemoteCopyGroupDoesNotExist(name=name)
        uid = rcg_info.get('uid')
        return uid

    # ---- Public methods ----

    def get_rcg_info(self, name):
        """Get remote copy group information by name.

        V3 REST API:
            GET /remotecopygroups?name=<name>
            Headers: {'experimentalfilter': 'true'}

        :param name: Name of the remote copy group.
        :returns: Dictionary with RCG info including uid, policies, targets, etc., or None if not found.
        :raises HPEStorageException: If API call fails.
        """
        logger.info(f">>>>>>>Entered get_rcg_info: name='{name}'")
        try:
            return self._get_rcg_info(name)
        except Exception as e:
            logger.exception(f"Failed to get RCG info for '{name}': {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited get_rcg_info: name='{name}'")

    def _execute_admit_rcopy_host(self, rcg_name, proximity, **kwargs):
        """Execute admit host to remote copy group.

        Required parameters:
        - rcg_name: Name of the remote copy group
        - proximity: Proximity value - 'primary', 'secondary', or 'all'

        Optional kwargs 
        (mutually exclusive — pass either host_names or hostset_names,
        as both at a time is not supported by API):
        - host_names: List of host name strings
        - hostset_names: List of host set name strings
        """
        host_names = kwargs.get('host_names')
        hostset_names = kwargs.get('hostset_names')

        validate_admit_rcopy_host_params(rcg_name, proximity,
                                         host_names=host_names,
                                         hostset_names=hostset_names)

        rcg_uid = self._get_rcg_uid(rcg_name)
        logger.info(f" RCG '{rcg_name}'  UID is {rcg_uid}")

        parameters = {'proximity': proximity.lower()}
        if host_names:
            parameters['hostNames'] = host_names
        elif hostset_names:
            parameters['hostSetNames'] = hostset_names

        payload = {
            'action': RC_GROUP_ADMIT_HOST,
            'parameters': parameters,
        }
        logger.debug(f"Admit rcopy host payload: {payload}")

        endpoint = f"/remotecopygroups/{rcg_uid}"
        response = self.session_mgr.rest_client.post(endpoint, payload)
        result = handle_async_response(self.task_manager, "admit rcopy host", rcg_name, response)
        logger.info(f"Successfully admitted host(s)/hostset(s) {kwargs} to RCG '{rcg_name}' "
                    f"with proximity '{proximity}'")
        return result

    def admit_rcopy_host(self, rcg_name, proximity, **kwargs):
        """Admit host(s) and/or host set(s) to a remote copy group with proximity.

        Equivalent CLI: admitrcopyhost -proximity <primary|secondary|all> <rcg_name> <host>

        V3 REST API:
            POST /remotecopygroups/<rcg_uid>
            {
                "action": "RC_GROUP_ADMIT_HOST",
                "parameters": {
                    "hostNames": [...],
                    "hostSetNames": [...],
                    "proximity": "primary" | "secondary" | "all"
                }
            }

        :param rcg_name: Name of the remote copy group (required).
        :param proximity: Proximity value - 'primary', 'secondary', or 'all' (required).
        :param host_names: List of host name strings (optional, via kwargs).
        :param hostset_names: List of host set name strings (optional, via kwargs).
        :returns: REST API response.
        :raises ValueError: If parameters are invalid.
        :raises HPEStorageException: If RCG not found or API call fails.
        """
        logger.info(f">>>>>>>Entered admit_rcopy_host: rcg_name='{rcg_name}'")
        try:
            return self._execute_admit_rcopy_host(rcg_name, proximity, **kwargs)
        except Exception as e:
            logger.exception(f"Failed to admit rcopy hosts/hostsets {kwargs} to RCG '{rcg_name}' with proximity '{proximity}': {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited admit_rcopy_host: rcg_name='{rcg_name}'")
