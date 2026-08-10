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

class CloneWorkflow:

    def __init__(self, session_mgr: SessionManager):
        self.session_mgr = session_mgr
 
    def copyVolume(self, src_name,info):

        try:
            response = self.session_mgr.rest_client.post(f'/volumes/{src_name}',info)
            return response
        except HPEStorageException as e:
             raise
        
    def stopOfflinePhysicalCopy(self, name,info):

        try:
            response=self.session_mgr.rest_client.put(f'/volumes{name}',info)
            return response
        except HPEStorageException as e:
            raise
    
    def resyncPhysicalCopy(self, volume_name,info):

        try:
            response = self.session_mgr.rest_client.put(f"/volumes/{volume_name}",info)
            return response
        except HPEStorageException as e:
            raise