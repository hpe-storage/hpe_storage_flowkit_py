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
"""NTP workflow implementation for HPE Alletra MP storage systems.

This module provides NTP and datetime configuration operations:
  - Configure NTP servers
  - Set system datetime  
  - Configure timezone settings

Endpoint: POST /api/v3/systems/{uid} with CONFIGUREDATETIME action

Return convention:
  On success: raw RESTClient parsed response
  On failure (caught exception): raises appropriate exception
"""

from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.validators.ntp_validator import validate_ntp_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response

logger = Logger()


class NTPWorkflow:
    """Workflow encapsulating NTP and datetime configuration operations."""

    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    def _build_configure_datetime_payload(self, date_time=None, ntp_addresses=None, timezone=None):
        """Build payload for CONFIGUREDATETIME action.
        
        Args:
            date_time (str, optional): ISO format datetime string
            ntp_addresses (list, optional): List of NTP server addresses
            timezone (str, optional): Timezone identifier
            
        Returns:
            dict: API payload
        """
        payload = {
            "action": "CONFIGUREDATETIME",
            "parameters": {}
        }
        
        if date_time:
            payload["parameters"]["dateTime"] = date_time
            
        if ntp_addresses:
            # Ensure ntp_addresses is a list
            if isinstance(ntp_addresses, str):
                ntp_addresses = [ntp_addresses]
            payload["parameters"]["ntpAddresses"] = ntp_addresses
            
        if timezone:
            payload["parameters"]["timezone"] = timezone
            
        return payload

    def _validate_configure_datetime_params(self, date_time, ntp_addresses, timezone):
        """Delegate validation to the shared validator module."""
        return validate_ntp_params(date_time=date_time, ntp_addresses=ntp_addresses, timezone=timezone)

    # ---- Helpers ----
    def _fetch_system_uid(self):
        """Fetch system UID from get_system_info.
        
        Returns:
            str: System UID
            
        Raises:
            exceptions.InvalidInput: If system UID cannot be determined
            exceptions.HPEStorageException: If system info retrieval fails
        """
        try:
            systems_response = self._execute_get_system_info(None)
            if isinstance(systems_response, dict) and 'uid' in systems_response:
                # Single system response
                system_uid = systems_response['uid']
            elif isinstance(systems_response, dict) and 'members' in systems_response and systems_response['members']:
                # Multiple systems response - get first system's uid
                first_member = list(systems_response['members'].values())[0]
                system_uid = first_member.get('uid')
            elif isinstance(systems_response, list) and len(systems_response) > 0 and 'uid' in systems_response[0]:
                # List response
                system_uid = systems_response[0]['uid']
            else:
                raise exceptions.InvalidInput("Could not determine system UID from system info")
                
            logger.info(f"Auto-fetched system UID: {system_uid}")
            return system_uid
        except Exception as e:
            error_details = f"Exception type: {type(e).__name__}, Message: {str(e)}"
            raise exceptions.HPEStorageException(f"Failed to fetch system UID: {error_details}")

    # ---- CRUD ----
    def _execute_configure_datetime(self, date_time=None, ntp_addresses=None, timezone=None):
        """Execute configure datetime operation."""
        logger.info(f"Starting datetime configuration")
        
        # Validate input parameters
        logger.debug(f"Validating datetime parameters")
        self._validate_configure_datetime_params(date_time, ntp_addresses, timezone)
        
        # Fetch system UID 
        logger.debug(f"Fetching system UID")
        system_uid = self._fetch_system_uid()
        
        # Build the payload
        payload = self._build_configure_datetime_payload(date_time, ntp_addresses, timezone)
        
        try:
            # Make the API call
            endpoint = f"/systems/{system_uid}"
            logger.info(f"Making POST request to {endpoint} with payload: {payload}")
            
            response = self.session_mgr.rest_client.post(endpoint, payload)
            result = handle_async_response(self.task_manager, "datetime configuration", system_uid, response)
            
            logger.info(f"Successfully configured datetime for system {system_uid}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to configure datetime for system {system_uid}: {str(e)}")
            raise

    def configure_datetime(self, date_time=None, ntp_addresses=None, timezone=None):
        """Configure NTP, datetime, and/or timezone settings."""
        logger.info(f">>>>>>>Entered configure_datetime")
        try:
            return self._execute_configure_datetime(date_time, ntp_addresses, timezone)
        except Exception as e:
            logger.exception(f"Failed to configure datetime due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited configure_datetime")

    def _execute_get_system_info(self, system_uid=None):
        """Execute get system info operation."""
        try:
            if system_uid:
                endpoint = f"/systems/{system_uid}"
                logger.info(f"Getting system info for {system_uid}")
            else:
                endpoint = "/systems"
                logger.info("Getting all systems info")
                
            response = self.session_mgr.rest_client.get(endpoint)
            logger.info("Successfully retrieved system information")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get system info: {str(e)}")
            raise

    def get_system_info(self, system_uid=None):
        """Get system information, optionally for a specific system."""
        logger.info(f">>>>>>>Entered get_system_info: system_uid='{system_uid}'")
        try:
            return self._execute_get_system_info(system_uid)
        except Exception as e:
            logger.exception(f"Failed to get system info due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited get_system_info: system_uid='{system_uid}'")
