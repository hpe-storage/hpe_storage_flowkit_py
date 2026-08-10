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
from hpe_storage_flowkit_py.v1.src.utils import remote_copy_utils
from hpe_storage_flowkit_py.v1.src.validators.remote_copy_validator import *
from hpe_storage_flowkit_py.v1.src.utils.utils import mergeDict
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException

class RemoteCopyGroupWorkflow:
	def __init__(self, session_client, ssh_client):
		self.session_client = session_client
		self.ssh = ssh_client

		

	def remote_copy_group_status(self, remote_copy_group_name):
		"""Get remote copy group status (reuse GET)."""
		return self.session_client.rest_client.get(f'/remotecopygroups/{remote_copy_group_name}')

	def start_remote_copy_service(self):
		"""Start remote copy service via SSH CLI if not already started.

		Uses 'startrcopy' command, similar to link admit logic.
		"""
		cmd = ['startrcopy']
		self.ssh.open()
		return self.ssh.run(cmd)
	
	def show_remote_copy_service(self):
		"""Show remote copy service status via SSH CLI.
		"""
		cmd = ['showrcopy']
		self.ssh.open()
		return self.ssh.run(cmd)

	def start_remote_copy_group(self, remote_copy_group_name, payload_params=None):
		"""Start a remote copy group (action=3). payload_params carries optional keys.
		Expects keys: skipInitialSync (bool), targetName (str), startingSnapshots (list of dicts)
		"""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}'
		payload = {'action': 3}
		if payload_params is not None:
			payload.update(payload_params)
		return self.session_client.rest_client.put(endpoint, payload)

	def stop_remote_copy_group(self, remote_copy_group_name, payload_params=None):
		"""Stop a remote copy group (action=4). payload_params carries optional keys.
		Expects keys: noSnapshot (bool), targetName (str)
		"""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}'
		payload = {'action': 4}
		if payload_params is not None:
			payload.update(payload_params)
		return self.session_client.rest_client.put(endpoint, payload)

	def synchronize_remote_copy_group(self, remote_copy_group_name, payload_params):
		"""Synchronize a remote copy group (action=5). Optional keys: noResyncSnapshot, targetName, fullSync."""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}'
		payload = {'action': 5}
		payload.update(payload_params)
		return self.session_client.rest_client.put(endpoint, payload)

	def admit_remote_copy_links(self, target_name, source_target_port_pair):
		"""Admit remote copy links between source/target ports."""
		cmd = ['admitrcopylink', target_name, source_target_port_pair]
		self.ssh.open()
		return self.ssh.run(cmd)

	
	def dismiss_remote_copy_links(self, target_name, source_target_port_pair):
		"""Dismiss remote copy links between source/target ports."""
		cmd = ['dismissrcopylink', target_name, source_target_port_pair]
		self.ssh.open()
		return self.ssh.run(cmd)
	
	def get_rcopy_links(self):
		cmd = ['showrcopy', 'links']
		self.ssh.open()
		return self.ssh.run(cmd)

	def get_remote_copy_group_volume_info(self, remote_copy_group_name, volume_name):
		"""Get volumes in a remote copy group."""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}/volumes/{volume_name}'
		return self.session_client.rest_client.get(endpoint)
		
	
	def add_volume_to_remote_copy_group(self, remote_copy_group_name, volume_name, admit_volume_targets, payload_params):
		"""Add a volume to a remote copy group.

		Payload is expected to contain keys: volumeName, admitVolumeTargets and optional flags."""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}/volumes'
		payload = {
			'volumeName': volume_name,
			'targets': admit_volume_targets
		}
		payload.update(payload_params)
		return self.session_client.rest_client.post(endpoint, payload)

	def remove_volume_from_remote_copy_group(self, remote_copy_group_name, volume_name, option=None):
		"""Remove a volume from a remote copy group."""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}/volumes/{volume_name}'
		if option:
			endpoint += '?%s=true' % option
		return self.session_client.rest_client.delete(endpoint)
	
	def remove_volume_from_remote_copy_group_overload(self, name, volumeName,
                                        optional=None,
                                        removeFromTarget=False,
                                        useHttpDelete=True):
		if not useHttpDelete:
			parameters = {'action': 2,
                              'volumeName': volumeName}
			if optional:
				parameters = mergeDict(parameters, optional)

			response = self.session_client.rest_client.put(f"/remotecopygroups/{name}",
                                           parameters)
			return response

		else:
			option = None
			if optional and optional.get('keepSnap') and removeFromTarget:
				raise Exception("keepSnap and removeFromTarget cannot be both\
                    true while removing the volume from remote copy group")
			elif optional and optional.get('keepSnap'):
				option = 'keepSnap'
			elif removeFromTarget:
				option = 'removeSecondaryVolume'
			
			delete_url = f"/remotecopygroups/{name}/volumes/{volumeName}"
			if option:
				delete_url += '?%s=true' % option

			try:
				response = self.session_client.rest_client.delete(delete_url)
				return response
			except HPEStorageException as e:
				raise
	
	def get_remote_copy_group(self, remote_copy_group_name):
		"""Get details of a specific remote copy group."""
		try:
			return self.session_client.rest_client.get(f'/remotecopygroups/{remote_copy_group_name}')
			
		except exceptions.HTTPNotFound as e:
			raise

	def get_remote_copy_groups(self):
		"""Get all remote copy groups."""
		return self.session_client.rest_client.get('/remotecopygroups')
		

	def remote_copy_group_exists(self, remote_copy_group_name):
		"""Check if a remote copy group exists."""
		try:
			self.get_remote_copy_group(remote_copy_group_name)
		except exceptions.HTTPNotFound:
			return False
		return True

	def create_remote_copy_group(self, remote_copy_group_name, remote_copy_targets, payload_params):
		"""Create a remote copy group."""
		payload = {
			'name': remote_copy_group_name,
			'targets': remote_copy_targets
		}
		payload.update(payload_params)
		return self.session_client.rest_client.post('/remotecopygroups', payload)

	def delete_remote_copy_group(self, remote_copy_group_name, keep_snap=False):
		"""Delete a remote copy group.

		keep_snap: if True, retain resynchronization snapshot (passed as query param if supported)
		"""
		params = {}
		if keep_snap:
			params['keepSnap'] = 'true'
		endpoint = f'/remotecopygroups/{remote_copy_group_name}'
		return self.session_client.rest_client.delete(endpoint, params=params or None)
	
	def delete_remote_copy_group_overload(self, name, keep_snap=False):
		if keep_snap:
			snap_query = 'true'
		else:
			snap_query = 'false'

		try:
			response = self.session_client.rest_client.delete(f"/remotecopygroups/{name}?keepSnap={snap_query}")
			return response
		except HPEStorageException as e:
			raise

	def modify_remote_copy_group(self, remote_copy_group_name, payload):
		"""Modify a remote copy group."""
		endpoint = f'/remotecopygroups/{remote_copy_group_name}'
		return self.session_client.rest_client.put(endpoint, payload)
	
	def admit_remote_copy_target(self, remote_copy_group_name, target_name, target_mode, source_target_volume_pair_list):
		cmd= ['admitrcopytarget', "-f", target_name,target_mode, remote_copy_group_name]
		cmd.extend(source_target_volume_pair_list)
		self.ssh.open()
		return self.ssh.run(cmd)

	def dismiss_remote_copy_target(self, remote_copy_group_name, target_name):
		"""Removing target from remote copy group
        :param targetName - The name of target system
        :type - string
        :remote_copy_group_name
        :type - string
        """
		option = '-f'
		cmd = ['dismissrcopytarget', option, target_name,
               remote_copy_group_name]
		self.ssh.open()
		return self.ssh.run(cmd)
	

	def recover_remote_copy_group_from_disaster(self, name, action, optional=None):
		parameters = {'action': action}
		if optional:
			parameters = mergeDict(parameters, optional)

		try:
			response = self.session_client.rest_client.post(f"/remotecopygroups/{name}", parameters)
			return response
		except HPEStorageException as e:
			raise

	def toggle_remote_copy_config_mirror(self, target, mirror_config=True):
		obj = {'mirrorConfig': mirror_config}
		info = {'policies': obj}
		try:
			response = self.session_client.rest_client.put(f"/remotecopytargets/{target}", info)
			return response
		except HPEStorageException as e:
			pass
