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
from hpe_storage_flowkit_py.v1.src.utils.snapshot_utils import convert_to_hours

def preprocess_create_schedule(expiration_time,retention_time,expiration_unit,retention_unit):
    expiration_hours = convert_to_hours(expiration_time, expiration_unit)
    retention_hours = convert_to_hours(retention_time, retention_unit)
    if expiration_hours <= retention_hours:
        return 0,0
    return expiration_hours,retention_hours

