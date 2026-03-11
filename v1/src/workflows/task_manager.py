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
from hpe_storage_flowkit_py.v1.src.utils.task_utils import Task
from hpe_storage_flowkit_py.v1.src.utils.task_utils import TASK_ACTIVE, TASK_CANCELLED, TASK_DONE, TASK_FAILED
from hpe_storage_flowkit_py.v1.src.core.exceptions import HPEStorageException
import time

class TaskManager:
    def __init__(self, session_mgr):
        self.session_mgr = session_mgr
    
    def getTask(self, taskId):
        response = self.session_mgr.rest_client.get(f'/tasks/{taskId}')
        return response
        
    def getTaskinfo(self, taskId):
        return Task(self.getTask(taskId))
    
    def waitForTaskToEnd(self, taskId, pollRateSecs=15):
        task = self.getTaskinfo(taskId)
        while task is not None:
            state = task.status
            if state == TASK_DONE:
                break
            elif state == TASK_CANCELLED:
                break
            elif state == TASK_FAILED:
                msg = "Task '%s' has FAILED!!!" % task.task_id
                raise Exception(msg)
            elif state == TASK_ACTIVE:
                time.sleep(pollRateSecs)
                task = self.getTaskinfo(task.task_id)

        if (task is not None and task.status is not None and task.status == TASK_DONE):
            return True
        else:
            return False
        
    def findTask(self, name, active=True):
        
        response=self.session_mgr.rest_client.get('/tasks/')

        task_type = {1: 'vv_copy', 2: 'phys_copy_resync', 3: 'move_regions',
                     4: 'promote_sv', 5: 'remote_copy_sync',
                     6: 'remote_copy_reverse', 7: 'remote_copy_failover',
                     8: 'remote_copy_recover', 18: 'online_vv_copy'}

        status = {1: 'done', 2: 'active', 3: 'cancelled', 4: 'failed'}

        priority = {1: 'high', 2: 'med', 3: 'low'}

        for task_obj in response['members']:
            if(task_obj['name'] == name):
                if(active and task_obj['status'] != 2):
                    # if active flag is True, but status of task is not True
                    # then it means task got completed/cancelled/failed
                    return None

                task_details = []
                task_details.append(task_obj['id'])

                value = task_obj['type']
                if value in task_type:
                    type_str = task_type[value]
                else:
                    type_str = 'n/a'
                task_details.append(type_str)

                task_details.append(task_obj['name'])

                value = task_obj['status']
                task_details.append(status[value])

                # Phase and Step feilds are not found
                task_details.append('---')
                task_details.append('---')
                task_details.append(task_obj['startTime'])
                task_details.append(task_obj['finishTime'])

                if('priority' in task_obj):
                    value = task_obj['priority']
                    task_details.append(priority[value])
                else:
                    task_details.append('n/a')

                task_details.append(task_obj['user'])

                return task_details
            
    def getTasks(self):
        try:
            response = self.session_mgr.rest_client.get(f"/tasks")
            return response
        except HPEStorageException as e:
            raise

    
    def cancelTask(self, taskId):
        info = {'action': 1}
        try:
            response = self.session_mgr.rest_client.put(f"/tasks/{taskId}", info)
            return response
        except HPEStorageException as e:
            # it means task cannot be cancelled,
            # because it is 'done' or already 'cancelled'
            pass