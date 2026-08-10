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
def validate_qos_params(name=None, maxIOPS=None, maxBWS=None, enable=None, **kwargs):
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("QOS name must be a non-empty string.")

    if maxIOPS is not None:
        if not isinstance(maxIOPS, int) or maxIOPS <= 0:
            raise ValueError("maxIOPS must be a positive integer.")

    if maxBWS is not None:
        if not isinstance(maxBWS, int) or maxBWS <= 0:
            raise ValueError("maxBWS must be a positive integer.")

    if enable is not None:
        if not isinstance(enable, bool):
            raise ValueError("enable must be a boolean.")