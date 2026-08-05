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
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v1.src.core.session import SessionManager
class QOSWorkflow:
    def __init__(self, session_mgr: SessionManager):
        self.session_mgr = session_mgr

    def create_qos(self,  payload):
        try:
            resp = self.session_mgr.rest_client.post("/qos", payload)
            return resp
        except HPEStorageException as e:
            raise
    def modify_qos(self, name, params):
        try:
            response = self.session_mgr.rest_client.put(f"/qos/vvset:{name}", params)
            return response
        except HPEStorageException as e:
            raise

    def delete_qos(self, name):
        try:
            response = self.session_mgr.rest_client.delete(f"/qos/{name}")
            return response
        except HPEStorageException as e:
            raise

    def get_qos(self, name):
        try:
            response = self.session_mgr.rest_client.get(f"/qos/vvset:{name}")
            return response
        except HPEStorageException as e:
            raise

    def list_qos(self):
        try:
            resp = self.session_mgr.rest_client.get("/qos")
            return resp.get("members", [])
        except HPEStorageException as e:
            raise
