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

class VolumeWorkflow:

	def __init__(self, session_mgr: SessionManager):
		self.session_mgr = session_mgr

	def create_volume(self, name,cpg,sizeMiB,params=None):
		"""
		Create volume with pre-validated payload.
		"""
		payload={"name":name,"cpg":cpg,"sizeMiB":sizeMiB}
		if params:
			payload.update(params)
		try:
			response = self.session_mgr.rest_client.post("/volumes", payload)
			return response
		except HPEStorageException as e:
			raise

	def modify_volume(self, name, volume_mods, app_type=None):
		"""
		Modify a volume's attributes.
		"""
		
		try:
			response = self.session_mgr.rest_client.put(f"/volumes/{name}", payload=volume_mods)
			# Optionally set metadata if app_type is provided
			# (requires additional endpoint logic)
			return response
		except exceptions.HTTPBadRequest:
			raise
		except exceptions.HTTPConflict:
			raise
		except exceptions.HTTPNotFound:
			raise
		except HPEStorageException as e:
			raise

	def grow_volume(self,name,new_size):
		"""
		Grow an existing volume by 'amount' MiB.
		"""

		info = {'action':3,"sizeMiB": int(new_size)}
		try:
			response = self.session_mgr.rest_client.put(f"/volumes/{name}", payload=info)
			return response
		except exceptions.HTTPForbidden:
			raise
		except HPEStorageException as e:
			raise

	def delete_volume(self, name):
		"""
		Delete volume.
		"""
		try:
			response = self.session_mgr.rest_client.delete(f"/volumes/{name}")
			return response
		except exceptions.HTTPBadRequest:
			raise
		except exceptions.HTTPConflict:
			raise
		except exceptions.HTTPNotFound:
			raise
		except HPEStorageException as e:
			raise

	def get_volume(self, name):
		"""
		Get volume information.
		"""
		try:
			response = self.session_mgr.rest_client.get(f"/volumes/{name}")
			return response
		except exceptions.HTTPNotFound as e:
			raise
		except HPEStorageException as e:
			raise

	def list_volumes(self):
		try:
			response = self.session_mgr.rest_client.get("/volumes")
			return response.get("members", [])
		except HPEStorageException as e:
			raise
	
	def tune_volume(self, name, info):
		"""
		Tune volume with pre-built info payload.
		"""
		try:
			response = self.session_mgr.rest_client.put(f"/volumes/{name}", payload=info)
			return response
		except HPEStorageException as e:
			raise




	def list_volumes_from_cpg(self, cpg_name):
		try:
			uri = '/volumes?query="userCPG EQ %s"' % (cpg_name)
			response = self.session_mgr.rest_client.get(uri)
			return response.get("members", [])
		except HPEStorageException as e:
			raise

	def copy_volume(self, src_name, dest_name, dest_cpg, optional=None):
		parameters = {'destVolume': dest_name,
					  'destCPG': dest_cpg}
		if dest_cpg is None:
			parameters.pop('destCPG', None)
		if optional:
			parameters.update(optional)
		info = {'action': 'createPhysicalCopy',
				'parameters': parameters}
		try:
			response = self.session_mgr.rest_client.post("/volumes/%s" % src_name, info)
			# sample response is ... {'taskid': 20762}
			return response
		except HPEStorageException as e:
			raise

	def setVolumeMetaData(self, name, key, value):
		"""This is used to set a key/value pair metadata into a volume.
		If the key already exists on the volume the value will be updated.

		:param name: the volume name
		:type name: str
		:param key: the metadata key name
		:type key: str
		:param value: the metadata value
		:type value: str

		"""
		key_exists = False
		info = {
			'key': key,
			'value': value
		}

		try:
			#response, body = self.http.post('/volumes/%s/objectKeyValues' %
			#								name, body=info)
			response = self.session_mgr.rest_client.post('/volumes/%s/objectKeyValues' %
											name, info)
		#except exceptions.HTTPConflict:
		except HPEStorageException as e:
			key_exists = True
		except Exception:
			raise

		if key_exists:
			info = {
				'value': value
			}
			#response, body = self.http.put(
			#	'/volumes/%(name)s/objectKeyValues/%(key)s' %
			#	{'name': name, 'key': key}, body=info)
			response = self.session_mgr.rest_client.put(
				'/volumes/%(name)s/objectKeyValues/%(key)s' %
				{'name': name, 'key': key}, info)

		return response

	def getVolumeMetaData(self, name, key):
		"""This is used to get a key/value pair metadata from a volume.

		:param name: the volume name
		:type name: str
		:param key: the metadata key name
		:type key: str

		:returns: dict with the requested key's data.

		.. code-block:: python

			data = {
				# time of creation in seconds format
				'creationTimeSec': 1406074222
				# the date/time the key was added
				'date_added': 'Mon Jul 14 16:09:36 PDT 2014',
				'value': 'data'	 # the value associated with the key
				'key': 'key_name'   # the key name
				# time of creation in date format
				'creationTime8601': '2014-07-22T17:10:22-07:00'
			}


		"""
		#response, body = self.http.get(
		#	'/volumes/%(name)s/objectKeyValues/%(key)s' %
		#	{'name': name, 'key': key})
		#return body
		try:
			response = self.session_mgr.rest_client.get(f"/volumes/{name}/objectKeyValues/{key}")
			return response
		except exceptions.HTTPNotFound as e:
			raise
		except HPEStorageException as e:
			raise

	def getAllVolumeMetaData(self, name):
		"""This is used to get all key/value pair metadata from a volume.

		:param name: the volume name
		:type name: str

		:returns: dict with all keys and associated data.

		.. code-block:: python

			keys = {
				'total': 2,
				'members': [
					{
						# time of creation in seconds format
						'creationTimeSec': 1406074222
						# the date/time the key was added
						'date_added': 'Mon Jul 14 16:09:36 PDT 2014',
						'value': 'data'	 # the value associated with the key
						'key': 'key_name'   # the key name
						# time of creation in date format
						'creationTime8601': '2014-07-22T17:10:22-07:00'
					},
					{
						# time of creation in seconds format
						'creationTimeSec': 1406074222
						# the date/time the key was added
						'date_added': 'Mon Jul 14 16:09:36 PDT 2014',
						'value': 'data'	 # the value associated with the key
						'key': 'key_name_2' # the key name
						# time of creation in date format
						'creationTime8601': '2014-07-22T17:10:22-07:00'
					}
				]
			}

		"""
		#response, body = self.http.get('/volumes/%s/objectKeyValues' % name)
		try:
			response = self.session_mgr.rest_client.get(f"/volumes/{name}/objectKeyValues")
			return response
		except HPEStorageException as e:
			raise

	def removeVolumeMetaData(self, name, key):
		"""This is used to remove a metadata key/value pair from a volume.

		:param name: the volume name
		:type name: str
		:param key: the metadata key name
		:type key: str

		:returns: None

		"""
		#response, body = self.http.delete(
		#	'/volumes/%(name)s/objectKeyValues/%(key)s' %
		#	{'name': name, 'key': key})
		try:
			response = self.session_mgr.rest_client.delete(
				f"/volumes/%(name)s/objectKeyValues/%(key)s" %
				{'name': name, 'key': key})
			return response
		except HPEStorageException as e:
			raise

	def findVolumeMetaData(self, name, key, value):
		"""Determines whether a volume contains a specific key/value pair.

		:param name: the volume name
		:type name: str
		:param key: the metadata key name
		:type key: str
		:param value: the metadata value
		:type value: str

		:returns: bool

		"""
		try:
			contents = self.getVolumeMetaData(name, key)
			if contents['value'] == value:
				return True
		except Exception:
			pass

		return False

