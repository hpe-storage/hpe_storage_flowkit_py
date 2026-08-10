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
HIGH = 1
MEDIUM = 2
LOW = 3
STOP_PHYSICAL_COPY = 1
RESYNC_PHYSICAL_COPY = 2

def preprocess_copyVolume(src_name, dest_name, dest_cpg, optional=None):

        if optional is not None:
            if 'priority' in optional:
                priority_map = {'HIGH': HIGH, 'MEDIUM': MEDIUM, 'LOW': LOW}
                if optional['priority'] in priority_map:
                    optional['priority'] = priority_map[optional['priority']]

            is_offline = optional.get('online', True) == False

            for attribute in ['compression', 'allowRemoteCopyParent', 'skipZero']:
                if attribute in optional.keys():
                    del optional[attribute]
        if optional and optional.get('online', True) == False:
            parameters = {'destVolume': dest_name}
        else:
            parameters = {'destVolume': dest_name, 'destCPG': dest_cpg}
        if optional:
            parameters.update(optional)
        info = {'action': 'createPhysicalCopy','parameters': parameters}
        return info
