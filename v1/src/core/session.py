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
from hpe_storage_flowkit_py.v1.src.core.rest_client import RESTClient



import hashlib
import threading
import time

class SessionManager:
    _session_cache = {}
    _lock = threading.Lock()
    _SESSION_TIMEOUT = 14 * 60  # 14 minutes in seconds

    def __init__(self, api_url, username, password):
        self.api_url = api_url
        self.username = username
        self.password = password
        self._session_key = self._make_session_key(api_url, username)
        self.rest_client = RESTClient(api_url)
        self.session = self.rest_client.session
        self.token = None
       
        self.session.headers.update({'Content-Type': 'application/json'})
        self._session_created = None
        self._ensure_singleton_session()

    @staticmethod
    def _make_session_key(api_url, username):
        key_str = f"{api_url}|{username}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _ensure_singleton_session(self):
        with SessionManager._lock:
            cached = SessionManager._session_cache.get(self._session_key)
            now = time.time()
            if cached:
                # Check expiry
                if now - cached['created'] < SessionManager._SESSION_TIMEOUT:
                    # Use cached session
                    self.token = cached['token']
                    self.session = cached['session']
                    self.rest_client.session = self.session
                    self.session.headers.update({'X-HP3PAR-WSAPI-SessionKey': f'{self.token}'})
                    self._session_created = cached['created']
                    return
                else:
                    # Expired, delete old session
                    try:
                        self.rest_client.delete(f"/credentials/{cached['token']}")
                    except Exception:
                        pass
                    del SessionManager._session_cache[self._session_key]
            # Create new session
            self.login()
            SessionManager._session_cache[self._session_key] = {
                'token': self.token,
                'session': self.session,
                'created': time.time()
            }
            self._session_created = SessionManager._session_cache[self._session_key]['created']

    def login(self):
        response = self.rest_client.post("/credentials", {"user": self.username, "password": self.password})
        self.token = response.get("key")
        if self.token:
            self.session.headers.update({'X-HP3PAR-WSAPI-SessionKey': f'{self.token}'})
        else:
            raise Exception("Failed to obtain session token.")
        return self.token


    def get_token(self):
        now = time.time()
        # Refresh if expired
        if not self.token or (self._session_created and now - self._session_created > SessionManager._SESSION_TIMEOUT):
            with SessionManager._lock:
                self.login()
                SessionManager._session_cache[self._session_key] = {
                    'token': self.token,
                    'session': self.session,
                    'created': time.time()
                }
                self._session_created = SessionManager._session_cache[self._session_key]['created']
        return self.token


    def ensure_session(self):
        return self.get_token()


    def get_session(self):
        return self.session


    def delete_session(self):
        with SessionManager._lock:
            if self.token:
                self.rest_client.delete(f"/credentials/{self.token}")
                self.token = None
                if self._session_key in SessionManager._session_cache:
                    del SessionManager._session_cache[self._session_key]


    def set(self, key, value):
        if not hasattr(self, 'session_data'):
            self.session_data = {}
        self.session_data[key] = value


    def get(self, key, default=None):
        if not hasattr(self, 'session_data'):
            self.session_data = {}
        return self.session_data.get(key, default)


    def clear(self):
        if hasattr(self, 'session_data'):
            self.session_data.clear()
