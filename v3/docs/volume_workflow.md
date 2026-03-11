<!--
(c) Copyright 2026 Hewlett Packard Enterprise Development LP
All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.
-->
# Volume Workflow Documentation

## Overview
The `VolumeWorkflow` class in the HPE Storage Flowkit provides methods to create volumes on HPE 3PAR storage systems using the v3 WSAPI. It handles parameter validation, payload construction, and API communication.

## Class: `VolumeWorkflow`

### Initialization
```python
VolumeWorkflow(session_mgr: SessionManager)
```
- **session_mgr**: Instance of `SessionManager` to manage REST API sessions.

### Methods

#### `create_volume(name, cpg, size, **kwargs)`
Creates a new volume with the specified parameters.
- **name**: Name of the volume to be created (string, required)
- **cpg**: User CPG (Common Provisioning Group) for the volume (string, required)
- **size**: Size of the volume (int, required, in MiB)
- **kwargs**: Optional parameters (see below)

##### Optional Parameters
- **comments**: Comments for the volume
- **count**: Number of volumes to create
- **dataReduction**: Data reduction setting
- **expireSecs**: Expiration value for volume snapshot
- **ransomWare**: Enable/disable ransomware policy
- **retainSecs**: Retention value for volume snapshot
- **userAllocWarning**: Allocation warning threshold

##### Returns
- API response from the `/volumes` endpoint
- On failure: `(False, False, error_message, {})`

#### Internal Method: `_execute_create_volume(name, cpg, size, **kwargs)`
Handles validation and payload construction for volume creation.
- Validates required and optional parameters
- Converts size to MiB if needed
- Logs payload and errors
- Sends POST request to `/volumes`

## Validation
- Uses `validate_volume_params` for required parameters
- Uses `validate_optional_params` for optional parameters

## Logging
- Logs payload and errors using the `Logger` class

## Example Usage
```python
workflow = VolumeWorkflow(session_mgr)
response = workflow.create_volume(
    name="vol1",
    cpg="UserCPG",
    size=10240,
    comments="Test volume",
    dataReduction=True
)
```

## Error Handling
- Errors are logged and returned in the response tuple
- Raises `HPEStorageException` for known storage errors

---
For more details, see the source code in `src/workflows/volume.py`.
