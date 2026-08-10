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
import re

from hpe_storage_flowkit_py.v1.src.core import exceptions
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v1.src.core.session import SessionManager
from hpe_storage_flowkit_py.v1.src.utils.snapshot_utils import PROMOTE_VIRTUAL_COPY
from hpe_storage_flowkit_py.v1.src.utils.utils import convert_to_hours

class SnapshotWorkflow:
	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr

	def create_snapshot(self, volume_name,snapshot_name,optional=None):

		parameters = {"name": snapshot_name}
		if optional:
			# cinder expects expirationTime and retentionTime and these are in hours by default
			parameters.update(optional)
		
		info = {'action': 'createSnapshot','parameters': parameters}
		try:
			response = self.session_mgr.rest_client.post(f"/volumes/{volume_name}", info)
			return response
		except exceptions.HTTPForbidden as e:
			raise
		except exceptions.HTTPNotFound as e:
			raise
		except HPEStorageException as e:
			raise

	def promoteVirtualCopy(self, name, params):
		"""
		Promote virtual copy with pre-built info payload.
		"""
		info={'action':PROMOTE_VIRTUAL_COPY}
		if params:
			if params["allowRemoteCopyParent"] is None:
				params["allowRemoteCopyParent"]=False
			info.update(params)
		try:
			response = self.session_mgr.rest_client.put(f'/volumes/{name}', info)
			return response
		except HPEStorageException as e: 
			raise

	def delete_snapshot(self, snapshot_name):
		"""
		Delete snapshot.
		"""
		try:
			response = self.session_mgr.rest_client.delete(f"/volumes/{snapshot_name}")
			return response
		except exceptions.HTTPForbidden as e:
			raise
		except exceptions.HTTPNotFound as e:
			raise
		except exceptions.HTTPConflict as e:
			raise
		except HPEStorageException as e:
			raise

	def get_snapshot(self, snapshot_name):
		"""
		Get snapshot information.
		"""
		try:
			response = self.session_mgr.rest_client.get(f"/volumes/{snapshot_name}")
			return response
		except HPEStorageException as e:
			raise

	def list_snapshots(self):
		"""
		List all snapshots.
		"""
		try:
			response = self.session_mgr.rest_client.get("/volumes")
			return response.get("members", [])
		except HPEStorageException as e:
			raise
	
	
	def getVolumeSnapshots(self, vol_name, live_test=True):
		"""
		Shows all snapshots associated with a given volume.
		:param vol_name: The volume name
		:type vol_name: str
		:returns: List of snapshot names
		"""

		try:
			uri = '/volumes?query="copyOf EQ %s"' % (vol_name)
			body = self.session_mgr.rest_client.get(uri)
			# print("response: ", body)
		except HPEStorageException as e:
			raise

		if live_test:
			snapshots = []
			for volume in body['members']:
				if 'copyOf' in volume:
					if (volume['copyOf'] == vol_name and
							volume['copyType'] == 3):
						snapshots.append(volume['name'])

			return snapshots
		else:
			snapshots = []
			for volume in body['members']:
				if re.match('SNAP', volume['name']):
					snapshots.append(volume['name'])

			return snapshots


