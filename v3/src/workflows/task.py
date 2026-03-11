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
import time
from hpe_storage_flowkit_py.v3.src.core.exceptions import HPEStorageException
from hpe_storage_flowkit_py.v3.src.core.logger import Logger
from hpe_storage_flowkit_py.v3.src.core.session import SessionManager
from hpe_storage_flowkit_py.v3.src.utils.constants import TASK_POLL_RATE_SECS, TASK_TIMEOUT_SECS
logger = Logger()

class TaskManager:
    """Manages asynchronous task operations"""

    def __init__(self, session_mgr:SessionManager):
        self.session_mgr = session_mgr

    def wait_for_task_to_end(self, task_id):
        """
        Wait for a task to complete by polling its status
        
        Args:
            task_id: The task ID or UID to monitor
            
        Returns:
            dict: Final task response when completed
            
        Raises:
            HPEStorageException: If task fails or encounters an error
            
        Note:
            Polling rate and timeout are configured in utils.constants
        """
        logger.info(f"Waiting for task {task_id} to complete. Polling every {TASK_POLL_RATE_SECS} seconds")

        # Extract task ID from URI if full URI is provided
        if isinstance(task_id, str) and '/tasks/' in task_id:
            # Extract just the task ID from URI like '/api/v3/tasks/{id}'
            task_id = task_id.split('/tasks/')[-1]

        endpoint = f"/tasks/{task_id}"

        logger.debug(f"Task Poll Rate: {TASK_POLL_RATE_SECS} seconds, Timeout: {TASK_TIMEOUT_SECS} seconds")    
        max_attempts = int(TASK_TIMEOUT_SECS / TASK_POLL_RATE_SECS)
        attempts = 0
        start_time = time.time()
        
        while attempts < max_attempts:
            try:
                # Check if we've exceeded the timeout
                elapsed_time = time.time() - start_time
                if elapsed_time >= TASK_TIMEOUT_SECS:
                    timeout_msg = f"Task {task_id} did not complete within timeout period of {TASK_TIMEOUT_SECS} seconds"
                    logger.error(timeout_msg)
                    raise HPEStorageException(timeout_msg)
                
                # Get task status
                response = self.session_mgr.rest_client.get(endpoint)                
                status = response.get('status')
                percent_complete = response.get('percentComplete', 0)
                
                logger.info(f"Task {task_id}: status={status}, progress={percent_complete}%, elapsed={int(elapsed_time)}s")
                
                # Check if task is finished
                if status == 'STATE_FINISHED':
                    state = response.get('state', {})
                    overall_state = state.get('overall', 'STATE_NORMAL')
                    
                    if overall_state == 'STATE_NORMAL':
                        logger.info(f"Task {task_id} completed successfully in {int(elapsed_time)} seconds")
                        return response
                    else:
                        error_msg = f"Task {task_id} completed with state: {overall_state}"
                        logger.error(error_msg)
                        raise HPEStorageException(error_msg)
                
                # Check for failed/cancelled states
                elif status in ['STATE_CANCELLED', 'STATE_FAILED']:
                    details = response.get('detailsMap', {})
                    error_msg = f"Task {task_id} ended with status: {status}. Details: {details}"
                    logger.error(error_msg)
                    raise HPEStorageException(error_msg)
                
                # Task is still running, wait before next poll
                time.sleep(TASK_POLL_RATE_SECS)
                attempts += 1
                
            except HPEStorageException:
                raise
            except Exception as e:
                logger.exception(f"Error polling task {task_id}: {str(e) or repr(e)}")
                raise HPEStorageException(f"Failed to poll task status: {str(e)}")
        
        # Timeout reached (fallback - should be caught by elapsed time check above)
        timeout_msg = f"Task {task_id} did not complete within timeout period of {TASK_TIMEOUT_SECS} seconds"
        logger.error(timeout_msg)
        raise HPEStorageException(timeout_msg)

    def get_task(self, task_id):
        """
        Fetch a task by ID or full URI and return its current status.
        """
        # If a full URI is provided, use it directly; otherwise build the endpoint.
        if isinstance(task_id, str) and task_id.startswith('/api/'):
            endpoint = task_id
            logger.debug(f"Using full URI for task: {endpoint}")
        else:
            endpoint = f"/tasks/{task_id}"
            logger.debug(f"Built endpoint for task ID '{task_id}': {endpoint}")

        logger.info(f"Fetching task with endpoint={endpoint}")
        response = self.session_mgr.rest_client.get(endpoint)
        logger.debug(f"getTask response: {response}")
        return response

    def get_all_tasks(self):
        try:
            response = self.session_mgr.rest_client.get("/tasks")
            return response
        except Exception as e:      
            logger.error(f"Error getting all the tasks: {str(e) or repr(e)}")
            raise HPEStorageException(f"Failed to fetch all tasks: {str(e)}")

        