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
VVSET = 1
SYS = 2

def preprocess_createqos(name,params):
    payload = {
            "name": name,
            "type": VVSET,
            "enable": params.get("enable", True)
            }
    if "maxIOPS" in params:
        payload["ioMaxLimit"] = params["maxIOPS"]
    if "maxBWS" in params:
        payload["bwMaxLimitKB"] = params["maxBWS"]
    return payload

def preprocess_modifyqos(name,params):
    payload = {
            "enable": params.get("enable", False)
            }
    if "maxIOPS" in params:
        payload["ioMaxLimit"] = params["maxIOPS"]
    if "maxBWS" in params:
        payload["bwMaxLimitKB"] = params["maxBWS"]
    return payload