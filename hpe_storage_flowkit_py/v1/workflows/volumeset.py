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
from hpe_storage_flowkit_py.v1.src.core import exceptions
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v1.src.core.session import SessionManager


class VolumeSetWorkflow:

    def __init__(self, session_client: SessionManager):
        self.session_client = session_client

    def volumeset_exists(self, name):
        try:
            self.session_client.rest_client.get(f"/volumesets/{name}")
            return True
        except exceptions.HTTPNotFound:
            return False

    def get_volumeset(self, name):
        return self.session_client.rest_client.get(f"/volumesets/{name}")

    def create_volumeset(self, name, payload_params):
        payload = {"name": name}
        payload.update(payload_params)
        return self.session_client.rest_client.post('/volumesets', payload)

    def delete_volumeset(self, name):
        """
        This removes a volume set. You must clear all QOS rules before a volume
        set can be deleted.

        """
        return self.session_client.rest_client.delete(f"/volumesets/{name}")

    def add_volumes_to_volumeset(self, name, setmembers):
        payload = {"action": 1, "setmembers": list(setmembers)}
        return self.session_client.rest_client.put(f"/volumesets/{name}", payload)

    def remove_volumes_from_volumeset(self, name, setmembers):
        if not self.volumeset_exists(name):
            raise exceptions.ResourceDoesNotExist(f"Volume set {name} does not exist")
        payload = {"action": 2, "setmembers": list(setmembers)}
        return self.session_client.rest_client.put(f"/volumesets/{name}", payload)


    # below functions called from cinder

    def createVolumeSet(self, name, domain=None, comment=None,
                        setmembers=None):
        info = {'name': name}

        if domain:
            info['domain'] = domain

        if comment:
            info['comment'] = comment

        if setmembers:
            members = {'setmembers': setmembers}
            info.update(members)

        # response, body = self.http.post('/volumesets', body=info)
        try:
            response = self.session_client.rest_client.post(f"/volumesets", info)
            return response
        except HPEStorageException as e:
            raise

    #def deleteVolumeSet(self, name):
    # covered above - delete_volumeset()

    def modifyVolumeSet(self, name, action=None, newName=None, comment=None,
                        flashCachePolicy=None, setmembers=None):
        """
        This modifies a volume set by adding or remove a volume from the volume
        set. action is 1 for ADD or 2 for REMOVE.

        """
        info = {}

        if action:
            info['action'] = action

        if newName:
            info['newName'] = newName

        if comment:
            info['comment'] = comment

        if flashCachePolicy:
            info['flashCachePolicy'] = flashCachePolicy

        if setmembers:
            members = {'setmembers': setmembers}
            info.update(members)

        try:
            response= self.session_client.rest_client.put(f'/volumesets/{name}', info)
            return response
        except exceptions.HTTPNotFound as e: 
            raise

    def addVolumeToVolumeSet(self, set_name, name):
        return self.modifyVolumeSet(set_name, action=1,
                                    setmembers=[name])

    def removeVolumeFromVolumeSet(self, set_name, name):
        return self.modifyVolumeSet(set_name, action=2,
                                    setmembers=[name])

    def createSnapshotOfVolumeSet(self, name, copyOfName, optional=None):
        """Create a snapshot of an existing Volume Set.

        :param name: Name of the Snapshot. The vvname pattern is described in
                     "VV Name Patterns" in the HPE 3PAR Command Line Interface
                     Reference, which is available at the following
                     website: http://www.hp.com/go/storage/docs
        :type name: str
        :param copyOfName: The volume set you want to snapshot
        :type copyOfName: str
        :param optional: Dictionary of optional params
        :type optional: dict

        .. code-block:: python

            optional = {
                'id': 12,                   # Specifies ID of the volume set
                                            # set, next by default
                'comment': "some comment",
                'readOnly': True,           # Read Only
                'expirationHours': 36,      # time from now to expire
                'retentionHours': 12        # time from now to expire
            }

        """

        parameters = {'name': name}
        if optional:
            parameters.update(optional)

        info = {'action': 'createSnapshot',
                'parameters': parameters}

        # response, body = self.http.post('/volumesets/%s' % copyOfName,
        #                                 body=info)
        try:
            response = self.session_client.rest_client.post(f"/volumesets/{copyOfName}", info)
            return response
        except HPEStorageException as e:
            raise

