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
from hpe_storage_flowkit_py.v3.src.validators.hostset_validator import validate_hostset_params
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.core import exceptions
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.workflows.task import TaskManager
from hpe_storage_flowkit_py.v3.src.utils.utils import handle_async_response

logger = Logger()


class HostSetWorkflow:
    """Workflow for host set operations.

    Success path returns underlying REST response (or None when API returns no body).
    Non-changed idempotent situations raise specific exceptions that the Ansible
    module maps to an unchanged result.
    """

    def __init__(self, session_client: SessionManager, task_manager: TaskManager):
        self.session_client = session_client
        self.task_manager = task_manager

    def _build_create_payload(self, name: str, **kwargs):
        """Build create payload with mandatory name.

        Optional keys already validated by validator: domain, comment, members.
        We simply loop through kwargs and map them into the payload.
        """
        logger.debug("Building host set create payload")
        payload = {"name": name}
        for param, value in kwargs.items():
            if value is None:
                continue
            if param == "domain":
                payload["domain"] = value
            elif param == "comment":
                payload["comment"] = value
            elif param == "setmembers":
                payload["members"] = value
        logger.debug(f"Built create payload for host set '{name}': {payload}")
        return payload

    def _execute_create_hostset(self, name, **kwargs):
        logger.info(f"Starting host set creation for '{name}'")
        logger.debug(f"Validating host set parameters")
        validate_hostset_params(name=name, **kwargs)
        payload_params = self._build_create_payload(name, **kwargs)
        logger.debug(f"Checking if host set already exists")
        if self.hostset_exists(name):
            logger.error(f"Host set '{name}' already exists, cannot create")
            raise exceptions.HostSetAlreadyExists(name=name)
        logger.info(f"Creating host set '{name}'")
        response = self.session_client.rest_client.post("/hostsets", payload_params)
        result = handle_async_response(self.task_manager, "host set creation", name, response)
        logger.info(f"Host set '{name}' created successfully")
        return result

    def create_hostset(self, name, **kwargs):
        logger.info(f">>>>>>>Entered create_hostset: name='{name}'")
        try:
            return self._execute_create_hostset(name, **kwargs)
        except Exception as e:
            logger.exception(f"Failed to create hostset due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited create_hostset: name='{name}'")
    
    def _execute_delete_hostset(self, name):
        logger.info(f"Starting host set deletion for '{name}'")
        validate_hostset_params(name=name)
        logger.debug(f"Checking if host set exists")
        if not self.hostset_exists(name):
            logger.error(f"Host set '{name}' does not exist, cannot delete")
            raise exceptions.HostSetDoesNotExist(name=name)
        logger.debug(f"Retrieving host set UID")
        logger.info(f"Deleting host set '{name}'")
        hostset_info_uid = (self._get_hostset_info(name)).get("uid")
        logger.debug(f"Host set UID retrieved: {hostset_info_uid}")
        response = self.session_client.rest_client.delete(f"/hostsets/{hostset_info_uid}")
        result = handle_async_response(self.task_manager, "host set deletion", name, response)
        logger.info(f"Host set '{name}' deleted successfully")
        return result
    
    def delete_hostset(self, name):
        logger.info(f">>>>>>>Entered delete_hostset: name='{name}'")
        try:
            return self._execute_delete_hostset(name)
        except Exception as e:
            logger.exception(f"Failed to delete hostset due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited delete_hostset: name='{name}'")
    
    # ---- Helpers ----
    def _get_hostsets_info(self):
        try:
            logger.debug("Fetching all host sets information")
            resp = self.session_client.rest_client.get("/hostsets")
            logger.debug(f"Retrieved {len(resp.get('members', {}))} host sets")
            return resp
        except Exception as e:
            logger.exception(f"Failed to get host sets info: {e}")
            raise e

    def _get_hostset_info(self, name: str):
        try:
            logger.debug(f"Retrieving host set '{name}' info")
            hostsets_info = self._get_hostsets_info()
            for hostset_info in hostsets_info.get("members", []).values():
                if hostset_info.get("name") == name:
                    logger.debug(f"Found host set '{name}' with UID: {hostset_info.get('uid')}")
                    return hostset_info
            logger.debug(f"Host set '{name}' not found")
            return []
        except Exception as e:
            logger.exception(f"Failed to get host set info '{name}': {e}")
            raise e


    def hostset_exists(self, name: str) -> bool:
        try:
            # Validate only name presence
            if not isinstance(name, str) or not name.strip():
                logger.error(f"Invalid host set name provided: {name}")
                raise ValueError("Host set name must be a non-empty string")
            exists = self._get_hostset_info(name) != []
            logger.debug(f"Host set '{name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.debug(f"hostset_exists check failed for '{name}': {e}")
            raise

    def _execute_get_hostset(self, name):
        logger.info(f"Getting host set '{name}' information")
        validate_hostset_params(name=name)
        return self._get_hostset_info(name)

    def get_hostset(self, name):
        logger.info(f">>>>>>>Entered get_hostset: name='{name}'")
        try:
            return self._execute_get_hostset(name)
        except Exception as e:
            logger.exception(f"Failed to get hostset due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited get_hostset: name='{name}'")
    # ---- CRUD ----

    def _execute_add_hosts_to_hostset(self, name: str, setmembers):
        # Ensure variable exists for exception logging even if early validation fails
        new_members = []
        try:
            logger.info(f"Starting add hosts operation for host set '{name}'")
            logger.debug(f"Members to add: {setmembers}")
            if setmembers is None:
                logger.error(f"Setmembers parameter is null for host set '{name}'")
                raise ValueError("Setmembers cannot be null")
            validate_hostset_params(name=name, setmembers=setmembers)
            if not self.hostset_exists(name):
                logger.error(f"Host set '{name}' does not exist, cannot add hosts")
                raise exceptions.HostSetDoesNotExist(name=name)
            hostset_info = self._get_hostset_info(name)
            existing_hostset_members = hostset_info.get("members") or []
            logger.info(f"Existing members in host set '{name}': {existing_hostset_members}")
            for member in setmembers:
                if member not in existing_hostset_members:
                    new_members.append(member)
                else:
                    logger.info(f"Host '{member}' is already a member of host set '{name}' so skipping it")
            if len(new_members) == 0:
                logger.warning(f"All the members are already present in the host set '{name}'")
                raise exceptions.HostSetMembersAlreadyPresent(name=name)
            logger.info(f"Adding {new_members} members to host set '{name}'")
            members_list = existing_hostset_members + new_members
            payload = {"members": members_list}
            response = self.session_client.rest_client.patch(f"/hostsets/{hostset_info.get('uid')}", payload=payload)
            result = handle_async_response(self.task_manager, "add hosts to host set", name, response)
            logger.info(f"Successfully added {new_members} members to host set '{name}'")
            return result
        except Exception as e:
            logger.exception(f"Failed adding {new_members} members to host set '{name}': {e}")
            raise e

    def add_hosts_to_hostset(self, name: str, setmembers):
        logger.info(f">>>>>>>Entered add_hosts_to_hostset: name='{name}'")
        try:
            return self._execute_add_hosts_to_hostset(name, setmembers)
        except Exception as e:
            logger.exception(f"Failed to add hosts to hostset due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited add_hosts_to_hostset: name='{name}'")

    def _execute_remove_hosts_from_hostset(self, name: str, setmembers):
        members_to_remove = []
        try:
            logger.info(f"Starting remove hosts operation for host set '{name}'")
            logger.debug(f"Members to remove: {setmembers}")
            if setmembers is None:
                logger.error(f"Setmembers parameter is null for host set '{name}'")
                raise ValueError("Setmembers cannot be null")
            validate_hostset_params(name=name, setmembers=setmembers)
            if not self.hostset_exists(name):
                logger.error(f"Host set '{name}' does not exist, cannot remove hosts")
                raise exceptions.HostSetDoesNotExist(name=name)
            hostset_info = self._get_hostset_info(name)
            existing_hostset_members = hostset_info.get("members") or []
            logger.debug(f"Existing members in host set '{name}': {existing_hostset_members}")
            for member in setmembers:
                if member in existing_hostset_members:
                    members_to_remove.append(member)
                else:
                    logger.info(f"Host '{member}' is already removed or not a member of host set '{name}' so skipping it")
            members_list = [m for m in existing_hostset_members if m not in members_to_remove]
            if len(members_to_remove) == 0:
                logger.warning(f"All the members are already removed or not the members of the host set '{name}'")
                raise exceptions.HostSetMembersAlreadyRemoved(name=name)
            logger.info(f"Removing {members_to_remove} members from host set '{name}'")
            payload = {"members": members_list}
            response = self.session_client.rest_client.patch(f"/hostsets/{hostset_info.get('uid')}", payload=payload)
            result = handle_async_response(self.task_manager, "remove hosts from host set", name, response)
            logger.info(f"Successfully removed {members_to_remove} members from host set '{name}'")
            return result
        except Exception as e:
            logger.exception(f"Failed removing {members_to_remove} members from host set '{name}': {e}")
            raise e

    def remove_hosts_from_hostset(self, name: str, setmembers):
        logger.info(f">>>>>>>Entered remove_hosts_from_hostset: name='{name}'")
        try:
            return self._execute_remove_hosts_from_hostset(name, setmembers)
        except Exception as e:
            logger.exception(f"Failed to remove hosts from hostset due to error: {e}")
            raise
        finally:
            logger.info(f"<<<<<<<Exited remove_hosts_from_hostset: name='{name}'")