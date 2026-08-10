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
def build_payload(volume_name, host_name, lun, autolun, node_val=None, slot=None, card_port=None):
    """
    build_payload
    """
    port_pos = None
    if node_val is not None and slot is not None and card_port is not None:
        port_pos = {"node": node_val, "slot": slot, "cardPort": card_port}
    if autolun:
        payload = {"volumeName": volume_name, "hostname": host_name, "autoLun": autolun, "lun": 0}
        if port_pos:
            payload["portPos"] = port_pos
    else:
        if lun is None:
            raise ValueError("LUN ID is required when autolun is disabled")
        payload = {"volumeName": volume_name, "lun": lun, "hostname": host_name, "autoLun": autolun}
        if port_pos:
            payload["portPos"] = port_pos
    return payload


def find_vlun(vluns, volume_name, host_name, lun=None, port_pos=None):
    """
    find_vlun
    """
    for vlun in vluns:
        if vlun.get("volumeName") == volume_name and vlun.get("hostname") == host_name:
            if lun is None or vlun.get("lun") == lun:
                if port_pos is None or vlun.get("portPos") == port_pos:
                    return vlun
    return None
