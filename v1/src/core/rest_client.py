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
import requests
from hpe_storage_flowkit_py.v1.src.core import exceptions

# HTTP status code constants (extend if more needed later)
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_CONFLICT = 409

class RESTClient:
    def __init__(self, api_url):
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
        self.verify_ssl = False

    def _make_url(self, endpoint):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        return f"{self.api_url}{endpoint}"

    def get(self, endpoint, **kwargs):
        url = self._make_url(endpoint)
        response = self.session.get(url, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        return self._parse_response(response)

    def get_api_version(self, endpoint, **kwargs):
        # Extract base host URL by removing '/api' and everything after it
        if '/api' in self.api_url:
            host_url = self.api_url.split('/api')[0]
        else:
            host_url = self.api_url
            
        # Ensure endpoint starts with '/'
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
            
        url = f"{host_url}{endpoint}"
        response = self.session.get(url, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        return self._parse_response(response)
    
    def post(self, endpoint, payload=None, **kwargs):
        url = self._make_url(endpoint)
        response = self.session.post(url, json=payload, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        return self._parse_response(response)

    def put(self, endpoint, payload=None, **kwargs):
        url = self._make_url(endpoint)
        response = self.session.put(url, json=payload, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        return self._parse_response(response)

    def delete(self, endpoint, **kwargs):
        url = self._make_url(endpoint)
        response = self.session.delete(url, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        return self._parse_response(response)

    def _check_response(self, response):
        if response.status_code == HTTP_STATUS_NOT_FOUND:
            # Special handling for code 187/102/23
            try:
                body = response.json()
                error_code = body.get("code")
                error_desc = body.get("desc") or ""
            except (ValueError, AttributeError):
                pass
            if error_code == 187:
                raise exceptions.HTTPNotFound(f"The Remote Copy group does not exist. Error code 187: {error_desc}")
            elif error_code == 102:
                raise exceptions.HTTPNotFound(f"The set does not exist. Error code 102: {error_desc}")
            elif error_code == 23:
                raise exceptions.HTTPNotFound(f"The storage volume does not exist. Error code 23: {error_desc}")
            raise exceptions.HTTPNotFound(f"{response.text}")
        elif response.status_code == HTTP_STATUS_FORBIDDEN:
            # Special handling for code 150/215
            try:
                body = response.json()
                error_code = body.get("code")
                error_desc = body.get("desc") or ""
            except (ValueError, AttributeError):
                pass
            if error_code == 150:
                raise exceptions.HTTPForbidden(f"Invalid operation: Cannot grow this type of volume. Error code 150: {error_desc}")
            elif error_code == 215:
                raise exceptions.HTTPForbidden(f"The Remote Copy group has already been started. Error code 215: {error_desc}")
            raise exceptions.HTTPForbidden(f"{response.text}")
        elif response.status_code == HTTP_STATUS_BAD_REQUEST:
            # Special handling for code 29/40
            try:
                body = response.json()
                error_code = body.get("code")
                error_desc = body.get("desc") or ""
            except (ValueError, AttributeError):
                pass
            if error_code == 29:
                raise exceptions.HTTPBadRequest(f"Bad Request. Error code 29: {error_desc}")
            elif error_code == 40:
                raise exceptions.HTTPBadRequest(f"Missing a required name-value pair. Error code 40: {error_desc}")
            raise exceptions.HTTPBadRequest(f"{response.text}")
        elif response.status_code == HTTP_STATUS_CONFLICT:
            # Special handling for code 34, 151, 32, 73
            try:
                body = response.json()
                error_code = body.get("code")
                error_desc = body.get("desc") or ""
            except (ValueError, AttributeError):
                pass
            if error_code == 34:
                 raise exceptions.HTTPConflict(f"Resource is in use. Error code 34: {error_desc}")
            if error_code == 151:
                raise exceptions.HTTPConflict(f"Volume tuning is in progress. Error code 151: {error_desc}")
            if error_code == 32:
                raise exceptions.HTTPConflict(f"Resource has a child. Error code 32: {error_desc}")
            if error_code == 73:
                raise exceptions.HTTPConflict(f"Host WWN/iSCSI name is already used by another host. Error code 73: {error_desc}")
            raise exceptions.HTTPConflict(f"{response.text}")
        elif not response.ok:
            raise exceptions.HPEStorageException(f"HTTP {response.status_code}: {response.text}")

    def _parse_response(self, response):
        if response.text:
            try:
                return response.json()
            except Exception:
                return response.text
        return None
