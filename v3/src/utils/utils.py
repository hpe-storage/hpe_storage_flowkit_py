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
# utils helper file
# Add any utility functions or classes here that can be shared across modules
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
logger=Logger()
FINAL_TASK_STATES = {
        "STATE_FINISHED",
        "STATE_FAILED",
        "STATE_CANCELED",
}
def _convert_size_to_mib( size, size_unit=None):
		"""
		Convert size to MiB based on the provided unit.
		
		Parameters:
		- size: The size value to convert
		- size_unit: Optional unit ('GiB', 'TiB', 'MiB'). If not provided, auto-detection is used.
		
		Returns:
		- Size in MiB as an integer
		"""
		logger.debug(f"Converting size: size={size}, size_unit={size_unit}")
		
		if size_unit:
			if size_unit == 'GiB':
				size_mib = size * 1024
				logger.debug(f"Converted {size} GiB to {size_mib} MiB")
			elif size_unit == 'TiB':
				size_mib = size * 1048576
				logger.debug(f"Converted {size} TiB to {size_mib} MiB")
			elif size_unit == 'MiB':
				size_mib = size
				logger.debug(f"Size already in MiB: {size_mib}")
			else:
				logger.warning(f"Unknown size_unit '{size_unit}', defaulting to GiB.")
				size_mib = size * 1024  # Default to GiB if invalid unit
			return int(size_mib)
		else:
			# Auto-detect: if size > 1000, assume it's already in MiB, else convert from GiB
			result = size if isinstance(size, int) and size > 1000 else size * 1024
			logger.debug(f"Auto-detected size conversion: {size} -> {result} MiB")
			return result

def _convert_to_seconds(time, unit):
        logger.debug(f"Converting time: time={time}, unit={unit}")
        
        if time is None:
            logger.debug("Time is None, returning None")
            return None
        
        seconds = 0
        if unit == 'seconds':
            seconds = time
        elif unit == 'minutes':
            seconds = time * 60
        elif unit == 'hours':
            seconds = time * 3600
        elif unit == 'days':
            seconds = time * 86400
        else:
            logger.warning(f"Unknown time unit '{unit}', defaulting to seconds")
            seconds = time
        
        logger.debug(f"Converted {time} {unit} to {seconds} seconds")
        return seconds


def find_task_by_command(tasks_response, required_strings) :
        """
        Find and return the task whose command contains ALL required_strings.
        Command is searched inside detailsMap -> message -> default.
        """
        logger.info(f"Searching for task with required strings: {required_strings}")
        
        members = tasks_response.get("members", {})
        logger.debug(f"Total tasks to search: {len(members)}")

        for task_id, task in members.items():
            details_map = task.get("detailsMap", {})

            for detail_key, detail in details_map.items():
                message = detail.get("message", {}).get("default", "")

                if message and all(s in message for s in required_strings):
                    logger.debug(f"Found matching task: task_id={task_id}, message={message}")
                    return task

        logger.debug("No matching task found")
        return None
	
def is_task_completed(task):
        """
        Return True if the task is in a final state, else False
        """
        task_status = task.get("status")
        logger.info(f"Checking if task is completed: status={task_status}")
        
        is_completed = task_status in FINAL_TASK_STATES
        logger.info(f"Task completed: {is_completed}")
        
        return is_completed


def handle_async_response(task_manager, operation: str, name: str, resp: dict):
        """
        Common handler for API responses that may return a task or resource.

        If a taskUri or resourceUri is present, wait for completion; otherwise return the response as-is.
        
        Parameters:
        - task_manager: TaskManager instance to wait for task completion
        - operation: Operation name (e.g., "schedule creation", "CPG deletion")
        - name: Resource name being operated on
        - resp: API response dictionary
        
        Returns:
        - Task result if taskUri or resourceUri is present, otherwise the original response
        
        Example:
            resp = self.session_mgr.rest_client.delete(f"/cpgs/{uid}")
            return handle_async_response(self.task_manager, "CPG deletion", name, resp)
        """
        try:
                task_uri = resp.get('taskUri')
                if task_uri:
                        logger.info(f"Task created for {operation} '{name}', waiting for completion: {task_uri}")
                        task_result = task_manager.wait_for_task_to_end(task_uri)
                        logger.info(f"{operation.capitalize()} for '{name}' task completed: {task_result}")
                        return task_result

                resource_uri = resp.get('resourceUri')
                if resource_uri:
                        logger.info(f"Resource URI received for {operation} '{name}', waiting for completion: {resource_uri}")
                        resource_result = task_manager.wait_for_task_to_end(resource_uri)
                        logger.info(f"{operation.capitalize()} for '{name}' resource completed: {resource_result}")
                        return resource_result

                logger.info(f"{operation.capitalize()} for '{name}' completed with no task and no resourceUri. Returning immediate response.")
                return resp
        except Exception as e:
                logger.error(f"Error handling async response for {operation} '{name}': {str(e) or repr(e)}")
                raise e