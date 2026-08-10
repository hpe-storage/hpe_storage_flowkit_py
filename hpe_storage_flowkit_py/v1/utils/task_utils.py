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
TASK_DONE = 1
TASK_ACTIVE = 2
TASK_CANCELLED = 3
TASK_FAILED = 4

class Task(object):
    
    def __init__(self, object_hash):
        if object_hash is None:
            return
    
        self.task_id = object_hash.get('id')
    
        self.status = object_hash.get('status')
    
        self.name = object_hash.get('name')
    
        self.type = object_hash.get('type')
		