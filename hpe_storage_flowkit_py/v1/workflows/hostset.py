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
from hpe_storage_flowkit_py.v1.src.validators.hostset_validator import validate_hostset_params
from hpe_storage_flowkit_py.v1.src.core import exceptions
from hpe_storage_flowkit_py.v1.src.utils import hostset_utils


class HostSetWorkflow:
    """Workflow for host set operations.

    Success path returns underlying REST response (or None when API returns no body).
    Non-changed idempotent situations raise specific exceptions that the Ansible
    module maps to an unchanged result.
    """

    def __init__(self, session_client):
        self.session_client = session_client

    # ---- Helpers ----
    def hostset_exists(self, name):
        validate_hostset_params(name=name)
        try:
            self.session_client.rest_client.get(f"/hostsets/{name}")
            return True
        except exceptions.HTTPNotFound:
            return False

    def get_hostset(self, name):
        validate_hostset_params(name=name)
        return self.session_client.rest_client.get(f"/hostsets/{name}")

    # ---- CRUD ----
    def create_hostset(self, name, payload_params):
        payload = {"name": name}
        if payload_params:
            payload.update(payload_params)
        return self.session_client.rest_client.post("/hostsets", payload)

    def delete_hostset(self, name):
        return self.session_client.rest_client.delete(f"/hostsets/{name}")

    def add_hosts_to_hostset(self, name, setmembers):
        payload = {"action": hostset_utils.HOSTSET_ACTION_ADD, "setmembers": setmembers}
        return self.session_client.rest_client.put(f"/hostsets/{name}", payload)
        
    
    def remove_hosts_from_hostset(self, name, setmembers):
        validate_hostset_params(name=name, setmembers=setmembers)
        if not self.hostset_exists(name):
            raise exceptions.HostSetDoesNotExist(name)
        current = self.get_hostset(name)
        existing = set(current.get('setmembers', []) or [])
        to_remove = existing & set(setmembers)
        if not to_remove:
            raise exceptions.NoMembersToRemove(name)
        payload = {"action": hostset_utils.HOSTSET_ACTION_REMOVE, "setmembers": list(to_remove)}
        return self.session_client.rest_client.put(f"/hostsets/{name}", payload)
