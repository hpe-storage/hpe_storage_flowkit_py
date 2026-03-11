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
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException, HTTPError
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
log=Logger()
class RESTClient:
    # Sensitive fields that should be masked in logs
    SENSITIVE_FIELDS = {'password', 'token', 'key', 'secret', 'authorization'}
    
    def __init__(self, api_url):
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
        self.verify_ssl = False

    def _mask_sensitive_data(self, data):
        """Recursively mask sensitive fields in dictionaries and lists for logging."""
        if isinstance(data, dict):
            masked_data = {}
            for key, value in data.items():
                if key.lower() in self.SENSITIVE_FIELDS:
                    masked_data[key] = '********'
                else:
                    masked_data[key] = self._mask_sensitive_data(value)
            return masked_data
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        else:
            return data

    def _make_url(self, endpoint):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        return f"{self.api_url}{endpoint}"

    def get(self, endpoint, **kwargs):
        url = self._make_url(endpoint)
        log.debug(f"GET request to: {url}")
        response = self.session.get(url, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        log.debug(f"GET response status: {response.status_code}")
        parsed_response = self._parse_response(response)
        log.debug(f"GET response data: {self._mask_sensitive_data(parsed_response)}")
        return parsed_response

    def post(self, endpoint, payload=None, **kwargs):
        url = self._make_url(endpoint)
        log.debug(f"POST request to: {url}")
        log.debug(f"POST payload: {self._mask_sensitive_data(payload)}")
        response = self.session.post(url, json=payload, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        log.debug(f"POST response status: {response.status_code}")
        parsed_response = self._parse_response(response)
        log.debug(f"POST response data: {self._mask_sensitive_data(parsed_response)}")
        return parsed_response

    def put(self, endpoint, payload=None, **kwargs):
        url = self._make_url(endpoint)
        log.debug(f"PUT request to: {url}")
        log.debug(f"PUT payload: {payload}")
        response = self.session.put(url, json=payload, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        log.debug(f"PUT response status: {response.status_code}")
        parsed_response = self._parse_response(response)
        log.debug(f"PUT response data: {self._mask_sensitive_data(parsed_response)}")
        return parsed_response
    def patch(self, endpoint, payload=None, **kwargs):
        url = self._make_url(endpoint)
        log.debug(f"PATCH request to: {url}")
        log.debug(f"PATCH payload: {payload}")
        response = self.session.patch(url, json=payload, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        log.debug(f"PATCH response status: {response.status_code}")
        parsed_response = self._parse_response(response)
        log.debug(f"PATCH response data: {self._mask_sensitive_data(parsed_response)}")
        return parsed_response
    def delete(self, endpoint, **kwargs):
        url = self._make_url(endpoint)
        log.debug(f"DELETE request to: {url}")
        response = self.session.delete(url, verify=self.verify_ssl, **kwargs)
        self._check_response(response)
        log.debug(f"DELETE response status: {response.status_code}")
        parsed_response = self._parse_response(response)
        log.debug(f"DELETE response data: {self._mask_sensitive_data(parsed_response)}")
        return parsed_response

    def _check_response(self, response):
        if not response.ok:
            log.error(f"HTTP {response.status_code} error: {response.text}")
            raise HTTPError(response.status_code, response.text)
    def _parse_response(self, response):
        if response.text:
            try:
                return response.json()
            except Exception:
                return response.text
        return None
