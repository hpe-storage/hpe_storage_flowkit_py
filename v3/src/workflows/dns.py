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
"""DNS workflow implementation for HPE Alletra MP storage systems.

This module provides DNS and network configuration operations:
  - Configure DNS servers
  - Set system IPv4/IPv6 network settings
  - Configure proxy parameters
  - Enable/disable IPv6 SLAAC

Endpoint: POST /api/v3/systems/{uid} with CONFIGURENETWORK action

Return convention:
  On success: raw RESTClient parsed response
  On failure (caught exception): raises appropriate exception
"""

from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.validators.dns_validator import validate_dns_network_params
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response
import copy
logger = Logger()


class DNSWorkflow:
    """Workflow encapsulating DNS and network configuration operations."""

    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    def _build_configure_network_payload(self, dns_addresses=None, ipv4_address=None, 
                                       ipv4_gateway=None, ipv4_subnet_mask=None, 
                                       ipv6_address=None, ipv6_gateway=None, 
                                       ipv6_prefix_len=None, proxy_params=None, 
                                       commit_change=None, slaac_enable=None):
        """Build payload for CONFIGURENETWORK action.
        
        Args:
            dns_addresses (list): List of DNS server addresses
            ipv4_address (str): IPv4 address for the system
            ipv4_gateway (str): IPv4 gateway address
            ipv4_subnet_mask (str): IPv4 subnet mask
            ipv6_address (str): IPv6 address for the system
            ipv6_gateway (str): IPv6 gateway address
            ipv6_prefix_len (str): IPv6 prefix length
            proxy_params (dict): Proxy configuration parameters
            commit_change (bool): Whether to commit network changes
            slaac_enable (bool): Enable/disable IPv6 SLAAC
            
        Returns:
            dict: API payload
        """
        payload = {
            "action": "CONFIGURENETWORK",
            "parameters": {}
        }
        
        # Add DNS addresses (required)
        if dns_addresses:
            payload["parameters"]["dnsAddresses"] = dns_addresses
            
        # Add IPv4 parameters
        if ipv4_address:
            payload["parameters"]["ipv4Address"] = ipv4_address
        if ipv4_gateway:
            payload["parameters"]["ipv4Gateway"] = ipv4_gateway
        if ipv4_subnet_mask:
            payload["parameters"]["ipv4SubnetMask"] = ipv4_subnet_mask
            
        # Add IPv6 parameters
        if ipv6_address:
            payload["parameters"]["ipv6Address"] = ipv6_address
        if ipv6_gateway:
            payload["parameters"]["ipv6Gateway"] = ipv6_gateway
        if ipv6_prefix_len:
            payload["parameters"]["ipv6PrefixLen"] = str(ipv6_prefix_len)
            
        # Add proxy parameters
        if proxy_params:
            # If authentication is disabled, remove authentication fields from payload
            if proxy_params.get('authenticationRequired') == 'disabled':
                proxy_params.pop('proxyUser', None)
                proxy_params.pop('proxyPassword', None)
                proxy_params.pop('proxyUserDomain', None)
            
            payload["parameters"]["proxyParams"] = proxy_params

            
        # Add optional boolean parameters
        if commit_change is not None:
            payload["parameters"]["commitChange"] = commit_change
        if slaac_enable is not None:
            payload["parameters"]["slaacEnable"] = slaac_enable
            
        return payload

    # ---- CRUD ----
    def _execute_configure_network(self, dns_addresses, ipv4_address=None, ipv4_gateway=None, 
                                 ipv4_subnet_mask=None, ipv6_address=None, ipv6_gateway=None, 
                                 ipv6_prefix_len=None, proxy_params=None, commit_change=None, 
                                 slaac_enable=None):
        """Execute configure network operation."""
        logger.info(f"Starting DNS and network configuration")
        
        # Validate input parameters
        logger.debug(f"Validating DNS and network parameters")
        validate_dns_network_params(
            dns_addresses=dns_addresses,
            ipv4_address=ipv4_address,
            ipv4_gateway=ipv4_gateway,
            ipv4_subnet_mask=ipv4_subnet_mask,
            ipv6_address=ipv6_address,
            ipv6_gateway=ipv6_gateway,
            ipv6_prefix_len=ipv6_prefix_len,
            proxy_params=proxy_params,
            commit_change=commit_change,
            slaac_enable=slaac_enable
        )
        
        # Fetch system_uid
        logger.debug(f"Fetching system UID")
        system_uid = self._fetch_system_uid()
        
        # Build the payload
        payload = self._build_configure_network_payload(
            dns_addresses=dns_addresses,
            ipv4_address=ipv4_address,
            ipv4_gateway=ipv4_gateway,
            ipv4_subnet_mask=ipv4_subnet_mask,
            ipv6_address=ipv6_address,
            ipv6_gateway=ipv6_gateway,
            ipv6_prefix_len=ipv6_prefix_len,
            proxy_params=proxy_params,
            commit_change=commit_change,
            slaac_enable=slaac_enable
        )
        
        try:
            # Make the API call
            endpoint = f"/systems/{system_uid}"
            # Redact sensitive fields before logging
            sanitized_payload = copy.deepcopy(payload)
            if sanitized_payload.get("parameters", {}).get("proxyParams"):
                sanitized_payload["parameters"]["proxyParams"] = "***MASKED***"
            logger.info(f"Making POST request to {endpoint} with payload: {sanitized_payload}")
            response = self.session_mgr.rest_client.post(endpoint, payload)
            result = handle_async_response(self.task_manager, "network configuration", system_uid, response)
            logger.info(f"Successfully configured network settings for system {system_uid}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to configure network settings for system {system_uid}: {str(e)}")
            raise

    def configure_network(self, dns_addresses, ipv4_address=None, ipv4_gateway=None, 
                         ipv4_subnet_mask=None, ipv6_address=None, ipv6_gateway=None, 
                         ipv6_prefix_len=None, proxy_params=None, commit_change=None, 
                         slaac_enable=None):
        """Configure DNS and network settings for the storage system."""
        logger.info(f">>>>>>>Entered configure_network")
        try:
            return self._execute_configure_network(dns_addresses, ipv4_address, ipv4_gateway, 
                                                 ipv4_subnet_mask, ipv6_address, ipv6_gateway, 
                                                 ipv6_prefix_len, proxy_params, commit_change, 
                                                 slaac_enable)
        except Exception as e:
            logger.exception(f"Failed to configure network due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited configure_network")

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
    
    # ---- Helpers ----
    def _fetch_system_uid(self):
        """Extract system UID from system info.
        
        Returns:
            str: System UID
            
        Raises:
            exceptions.InvalidInput: If system UID cannot be determined
            exceptions.HPEStorageException: For other API errors
        """
        try:
            systems_response = self._execute_get_system_info(None)
            if isinstance(systems_response, dict) and 'uid' in systems_response:
                # Single system response
                return systems_response['uid']
            elif isinstance(systems_response, dict) and 'members' in systems_response and systems_response['members']:
                # Multiple systems response - get first system's uid
                first_member = list(systems_response['members'].values())[0]
                return first_member.get('uid')
            elif isinstance(systems_response, list) and len(systems_response) > 0 and 'uid' in systems_response[0]:
                # List response
                return systems_response[0]['uid']
            else:
                raise exceptions.InvalidInput("Could not determine system UID from system info")
        except Exception as e:
            error_details = f"Exception type: {type(e).__name__}, Message: {str(e)}"
            raise exceptions.HPEStorageException(f"Failed to fetch system UID: {error_details}")