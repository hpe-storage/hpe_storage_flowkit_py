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
"""User workflow implementation for HPE Alletra MP storage systems.

This module provides user management operations:
  - Get all users (GET /api/v3/users)
  - Get single user by name (internally uses GET /api/v3/users/{uid})
  - Create new users (POST /api/v3/users)
  - Modify existing users by name (internally uses PATCH /api/v3/users/{uid})
  - Delete users by name (internally uses DELETE /api/v3/users/{uid})

All operations use user names as input. UIDs are resolved internally via GET /api/v3/users.

Return convention:
  On success: raw RESTClient parsed response
  On failure: raises appropriate exception
"""

from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.validators.user_validator import (validate_user_params, validate_modify_user_params, 
                                         validate_modify_payload, validate_user_uid)
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response

# HTTP Status Code Constants
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400
HTTP_CONFLICT = 409
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

logger = Logger()


class UserWorkflow:
    """Workflow for user operations.

    Success path returns underlying REST response (or None when API returns no body).
    Non-changed idempotent situations raise specific exceptions that the Ansible
    module maps to an unchanged result.
    """

    def __init__(self, session_mgr: SessionManager, task_manager: TaskManager):
        self.session_mgr = session_mgr
        self.task_manager = task_manager

    def _build_create_user_payload(self, name, password, domain_privileges):
        """Build payload for user creation (POST /api/v3/users).
        
        Args:
            name (str): User name
            password (str or list): Password (string or array of characters)
            domain_privileges (list): List of domain-privilege mappings
            
        Returns:
            dict: API payload
        """
        logger.debug("Building user create payload")
        # Convert password to list if it's a string (HPE API requirement)
        if isinstance(password, str):
            password_list = list(password)
        else:
            password_list = password
        
        # Build domainPrivileges array
        domain_privs = []
        for domain_priv in domain_privileges:
            domain_privs.append({
                "name": domain_priv['name'],
                "priv": domain_priv['privilege']
            })
        
        payload = {
            "name": name,
            "password": password_list,
            "domainPrivileges": domain_privs
        }
        # Mask sensitive data for logging
        masked_payload = {k: "***MASKED***" if k in ["password"] else v for k, v in payload.items()}
        logger.debug(f"Built create payload for user '{name}': {masked_payload}")
        return payload

    def _build_modify_user_payload(self, current_password=None, new_password=None, domain_privileges=None):
        """Build payload for user modification (PATCH /api/v3/users/{uid}).
        
        Args:
            current_password (str or list, optional): Current password
            new_password (str or list, optional): New password
            domain_privileges (list, optional): Updated domain privileges
            
        Returns:
            dict: API payload
        """
        logger.debug("Building user modify payload")
        payload = {}
        
        if current_password:
            # Convert password to list if it's a string
            if isinstance(current_password, str):
                current_password_list = list(current_password)
            else:
                current_password_list = current_password
            payload["currentPassword"] = current_password_list
            
        if new_password:
            # Convert password to list if it's a string
            if isinstance(new_password, str):
                new_password_list = list(new_password)
            else:
                new_password_list = new_password
            payload["newPassword"] = new_password_list
            
        if domain_privileges:
            domain_privs = []
            for domain_priv in domain_privileges:
                domain_privs.append({
                    "name": domain_priv['name'],
                    "priv": domain_priv['privilege']
                })
            payload["domainPrivileges"] = domain_privs
        
        # Mask sensitive data for logging
        masked_payload = {k: "***MASKED***" if k in ["currentPassword", "newPassword"] else v for k, v in payload.items()}
        logger.debug(f"Built modify payload: {masked_payload}")
        return payload

    def _parse_users_response(self, users_response):
        """Parse users API response into list of user dicts."""
        if isinstance(users_response, dict):
            if 'members' in users_response and users_response['members']:
                return list(users_response['members'].values())
            elif 'uid' in users_response:
                return [users_response]
        elif isinstance(users_response, list):
            return users_response
        return []

    # ---- Helpers ----
    def _fetch_user_uid_by_name(self, name):
        """Fetch user UID by name for modify/delete operations.
        
        Args:
            name (str): User name to lookup
            
        Returns:
            str: User UID
            
        Raises:
            exceptions.UserDoesNotExist: If user with name is not found
            exceptions.HPEStorageException: For other API errors
        """
        # TODO: Optimize this by using API filtering instead of fetching all users and looping.
        # Use API: api/v3/users?name=<user_name> with header "experimentalfilter": "true"
        # This will be addressed in the next phase for better performance.
        
        try:
            logger.debug(f"Fetching UID for user '{name}'")
            # Direct API call to get all users
            users_response = self.session_mgr.rest_client.get("/users")
            
            # Parse response into users list
            users_list = self._parse_users_response(users_response)
                
            # Search for user by name and extract UID
            for user in users_list:
                if isinstance(user, dict) and user.get('name') == name:
                    uid = user.get('uid')
                    validate_user_uid(uid, name)
                    logger.debug(f"Found UID '{uid}' for user '{name}'")
                    return uid
                        
            raise exceptions.UserDoesNotExist(f"User '{name}' not found")
            
        except exceptions.UserDoesNotExist:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch UID for user '{name}': {str(e)}")
            raise exceptions.HPEStorageException(f"Failed to fetch user UID: {str(e)}")

    def _execute_get_all_users(self):
        """Execute get all users operation."""
        logger.info("Getting all users")
        
        try:
            endpoint = "/users"
            logger.info(f"Making GET request to {endpoint}")
            response = self.session_mgr.rest_client.get(endpoint)
            logger.info("Successfully retrieved all users")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get all users: {str(e)}")
            
            if hasattr(e, 'status_code'):
                status = getattr(e, 'status_code')
                if status == HTTP_UNAUTHORIZED:
                    raise exceptions.AuthenticationError("Authentication failed")
                elif status == HTTP_FORBIDDEN:
                    raise exceptions.AuthenticationError("Insufficient privileges")
            
            raise exceptions.HPEStorageException(f"Failed to get all users: {str(e)}")

    def get_all_users(self):
        """Get all users (GET /api/v3/users)."""
        logger.info(f">>>>>>>Entered get_all_users")
        try:
            return self._execute_get_all_users()
        except Exception as e:
            logger.exception(f"Failed to get all users due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited get_all_users")

    def _execute_get_user_by_name(self, name):
        """Execute get user by name operation."""
        logger.info(f"Getting user '{name}' by name")
        
        # For get operations, name is required
        if name is None:
            raise exceptions.InvalidInput("User name is required")
        
        validate_user_params(name=name)
        
        # TODO: Optimize this by using API filtering instead of fetching all users and searching.
        # Use API: api/v3/users?name=<user_name> with header "experimentalfilter": "true"
        # This will be addressed in the next phase for better performance.
        
        # Direct API call to search for user
        users_response = self.session_mgr.rest_client.get("/users")
        
        # Parse response into users list
        users_list = self._parse_users_response(users_response)
            
        # Search for user by name and return directly
        for user in users_list:
            if isinstance(user, dict) and user.get('name') == name:
                logger.debug(f"Found user '{name}' with UID '{user.get('uid')}'")
                return user
                
        raise exceptions.UserDoesNotExist(f"User '{name}' not found")

    def get_user_by_name(self, name):
        """Get user by name (searches all users efficiently)."""
        logger.info(f">>>>>>>Entered get_user_by_name: name='{name}'")
        try:
            return self._execute_get_user_by_name(name)
        except Exception as e:
            logger.exception(f"Failed to get user by name due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited get_user_by_name: name='{name}'")

    def _execute_create_user(self, name, password, domain_privileges, **kwargs):
        """Execute create user operation."""
        logger.info(f"Starting user creation for '{name}'")
        logger.debug(f"Validating user parameters")
        
        # For create operations, name is required
        if name is None:
            raise exceptions.InvalidInput("User name is required for creation")
        
        validate_user_params(name=name, password=password, domain_privileges=domain_privileges)
        payload = self._build_create_user_payload(name, password, domain_privileges)
        
        logger.debug(f"Checking if user already exists")
        try:
            # Try to get UID - if found, user exists
            self._fetch_user_uid_by_name(name)
            logger.warning(f"User '{name}' already exists, cannot create")
            raise exceptions.UserAlreadyExists(name=name)
        except exceptions.UserDoesNotExist:
            # User doesn't exist, we can create it
            logger.debug(f"User '{name}' does not exist, proceeding with creation")
            
        logger.info(f"Creating user '{name}'")
        response = self.session_mgr.rest_client.post("/users", payload)
        result = handle_async_response(self.task_manager, "user creation", name, response)
        logger.info(f"User '{name}' created successfully")
        return result

    def create_user(self, name, password, domain_privileges, **kwargs):
        """Create a new user (POST /api/v3/users)."""
        logger.info(f">>>>>>>Entered create_user: name='{name}'")
        try:
            return self._execute_create_user(name, password, domain_privileges, **kwargs)
        except Exception as e:
            logger.exception(f"Failed to create user due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited create_user: name='{name}'")

    def _execute_modify_user_by_name(self, name, current_password=None, new_password=None, domain_privileges=None, **kwargs):
        """Execute modify user by name operation."""
        logger.info(f"Starting user modification for '{name}'")
        logger.debug(f"Validating user parameters")
        validate_user_params(name=name)
        
        # Validate modify-specific parameters
        validate_modify_user_params(current_password, new_password, domain_privileges)
        
        payload = self._build_modify_user_payload(current_password, new_password, domain_privileges)
        
        # Validate payload has content
        validate_modify_payload(payload)
        
        # Fetch UID (will raise UserDoesNotExist if user doesn't exist)
        uid = self._fetch_user_uid_by_name(name)
        logger.info(f"Found UID '{uid}' for user '{name}'")
        
        logger.info(f"Modifying user '{name}'")
        endpoint = f"/users/{uid}"
        logger.debug(f"Making PATCH request to {endpoint}")
        response = self.session_mgr.rest_client.patch(endpoint, payload)
        result = handle_async_response(self.task_manager, "user modification", name, response)
        logger.info(f"User '{name}' modified successfully")
        return result

    def modify_user_by_name(self, name, current_password=None, new_password=None, domain_privileges=None, **kwargs):
        """Modify user by name (internally converts name to UID)."""
        logger.info(f">>>>>>>Entered modify_user_by_name: name='{name}'")
        try:
            return self._execute_modify_user_by_name(name, current_password, new_password, domain_privileges, **kwargs)
        except Exception as e:
            logger.exception(f"Failed to modify user due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited modify_user_by_name: name='{name}'")

    def _execute_delete_user_by_name(self, name):
        """Execute delete user by name operation."""
        logger.info(f"Starting user deletion for '{name}'")
        
        # For delete operations, name is required
        if name is None:
            raise exceptions.InvalidInput("User name is required for deletion")
        
        validate_user_params(name=name)
        
        # Fetch UID (will raise UserDoesNotExist if user doesn't exist)
        uid = self._fetch_user_uid_by_name(name)
        logger.info(f"Found UID '{uid}' for user '{name}'")
        
        logger.info(f"Deleting user '{name}'")
        endpoint = f"/users/{uid}"
        logger.debug(f"Making DELETE request to {endpoint}")
        response = self.session_mgr.rest_client.delete(endpoint)
        result = handle_async_response(self.task_manager, "user deletion", name, response)
        logger.info(f"User '{name}' deleted successfully")
        return result

    def delete_user_by_name(self, name):
        """Delete user by name (internally converts name to UID)."""
        logger.info(f">>>>>>>Entered delete_user_by_name: name='{name}'")
        try:
            return self._execute_delete_user_by_name(name)
        except Exception as e:
            logger.exception(f"Failed to delete user due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited delete_user_by_name: name='{name}'")