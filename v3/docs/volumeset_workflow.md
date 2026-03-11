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

# Volume Set Workflow Documentation

## Overview
The `VolumeSetWorkflow` class in the HPE Storage Flowkit provides comprehensive methods to manage volume sets (application sets) on HPE 3PAR/Alletra storage systems using the v3 WSAPI. It handles parameter validation, payload construction, API communication, and intelligent member management.

## Class: `VolumeSetWorkflow`

### Initialization
```python
VolumeSetWorkflow(session_mgr: SessionManager)
```
- **session_mgr**: Instance of `SessionManager` to manage REST API sessions with the storage array.

### Methods

---

#### `create_volumeset(name, appSetType, **kwargs)`
Creates a new volume set with the specified parameters.

**Required Parameters:**
- **name** (string): Name of the volume set to be created
  - Must be 1-27 characters in length
  - Must be unique within the storage system
- **appSetType** (string): Application set type for the volume set
  - Required only during creation
  - Must be a non-empty string

**Optional Parameters (`**kwargs`):**
- **domain** (string): Domain for the volume set
- **comments** (string): Descriptive comments for the volume set
- **setmembers** (list): Initial list of volume members to add to the set
  - Each member must be a non-empty string
  - Volume names that should be part of this volume set

**Returns:**
- API response from the `/applicationsets` endpoint on success
- Raises `VolumeSetAlreadyExists` if a volume set with the same name already exists

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
response = workflow.create_volumeset(
    name="AppSet1",
    appSetType="vvol",
    domain="domain1",
    comments="Production application set",
    setmembers=["vol1", "vol2", "vol3"]
)
```

**Workflow Steps:**
1. Validates all parameters using `validate_volumeset_params`
2. Checks if volume set already exists
3. Builds payload with `appSetName`, `appSetType`, and optional parameters
4. Sends POST request to `/applicationsets`
5. Logs creation success or failure

---

#### `delete_volumeset(name)`
Deletes an existing volume set from the storage system.

**Parameters:**
- **name** (string): Name of the volume set to delete
  - Must be a non-empty string

**Returns:**
- API response from the `/applicationsets/{uid}` endpoint on success
- Raises `VolumeSetDoesNotExist` if the volume set is not found

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
response = workflow.delete_volumeset(name="AppSet1")
```

**Workflow Steps:**
1. Validates volume set name
2. Checks if volume set exists
3. Retrieves volume set UID from the storage system
4. Sends DELETE request to `/applicationsets/{uid}`
5. Logs deletion success or failure

---

#### `modify_volumeset(name, newName=None, comments=None)`
Modifies an existing volume set's properties.

**Parameters:**
- **name** (string, required): Current name of the volume set
- **newName** (string, optional): New name for the volume set
  - Must be 1-27 characters if provided
- **comments** (string, optional): New or updated comments for the volume set

**Returns:**
- API response from the `/applicationsets/{uid}` endpoint on success
- Raises `VolumeSetDoesNotExist` if the volume set is not found

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
response = workflow.modify_volumeset(
    name="AppSet1",
    newName="ProductionAppSet",
    comments="Updated production environment"
)
```

**Workflow Steps:**
1. Validates parameters (name, newName, comments)
2. Checks if volume set exists
3. Retrieves volume set UID
4. Builds payload with only provided parameters
5. Sends PATCH request to `/applicationsets/{uid}`
6. Logs modification success or failure

---

#### `add_volumes_to_volumeset(name, setmembers)`
Adds volumes to an existing volume set with intelligent duplicate detection.

**Parameters:**
- **name** (string): Name of the volume set
- **setmembers** (list): List of volume names to add to the set
  - Cannot be null
  - Each member must be a non-empty string
  - Duplicates are automatically filtered

**Returns:**
- API response from the `/applicationsets/{uid}` endpoint on success
- Returns early (no API call) if all members already present
- Raises `VolumeSetDoesNotExist` if the volume set is not found

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
response = workflow.add_volumes_to_volumeset(
    name="AppSet1",
    setmembers=["vol4", "vol5", "vol6"]
)
```

**Workflow Steps:**
1. Validates volume set name and setmembers parameter
2. Checks if volume set exists
3. Retrieves current volume set information including existing members
4. Filters out volumes that are already members
5. Logs and skips volumes already present
6. If all volumes are already present, returns early with info message
7. Constructs updated member list (existing + new)
8. Sends PATCH request to `/applicationsets/{uid}` with complete member list
9. Logs addition success with list of newly added members

**Intelligent Behavior:**
- Only adds volumes that aren't already members
- Logs which volumes are being skipped
- Prevents unnecessary API calls if all volumes already present

---

#### `remove_volumes_from_volumeset(name, setmembers)`
Removes volumes from an existing volume set with intelligent filtering.

**Parameters:**
- **name** (string): Name of the volume set
- **setmembers** (list): List of volume names to remove from the set
  - Cannot be null
  - Each member must be a non-empty string

**Returns:**
- API response from the `/applicationsets/{uid}` endpoint on success
- Returns early (no API call) if none of the members are present
- Raises `VolumeSetDoesNotExist` if the volume set is not found

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
response = workflow.remove_volumes_from_volumeset(
    name="AppSet1",
    setmembers=["vol4", "vol5"]
)
```

**Workflow Steps:**
1. Validates volume set name and setmembers parameter
2. Checks if volume set exists
3. Retrieves current volume set information including existing members
4. Identifies which volumes are actually present to remove
5. Logs and skips volumes that aren't present
6. If no volumes to remove, returns early with info message
7. Constructs updated member list (excluding removed volumes)
8. Sends PATCH request to `/applicationsets/{uid}` with updated member list
9. Logs removal success with list of removed members

**Intelligent Behavior:**
- Only removes volumes that are actually members
- Logs which volumes are being skipped (already removed or not members)
- Prevents unnecessary API calls if no valid volumes to remove

---

#### `volumeset_exists(name)`
Utility method to check if a volume set exists on the storage system.

**Parameters:**
- **name** (string): Name of the volume set to check
  - Must be a non-empty string

**Returns:**
- `True` if the volume set exists
- `False` if the volume set does not exist

**Example:**
```python
workflow = VolumeSetWorkflow(session_mgr)
if workflow.volumeset_exists("AppSet1"):
    print("Volume set exists")
else:
    print("Volume set does not exist")
```

**Workflow Steps:**
1. Validates volume set name is non-empty
2. Calls `_get_volumeset_info()` internally
3. Returns True if info found, False otherwise

---

## Internal Helper Methods

### `_build_create_payload(name, appSetType, **kwargs)`
Constructs the JSON payload for volume set creation.

**Payload Mapping:**
- `name` → `appSetName`
- `appSetType` → `appSetType`
- `domain` → `domain` (optional)
- `comments` → `appSetComments` (optional)
- `setmembers` → `members` (optional)

### `_get_volumesets_info()`
Retrieves information about all volume sets from the storage system.

**Returns:**
- Full API response from `/applicationsets` endpoint containing all volume sets

### `_get_volumeset_info(name)`
Retrieves detailed information about a specific volume set.

**Returns:**
- Dictionary with volume set details (uid, appSetName, members, etc.)
- Empty list `[]` if volume set not found

**Note:** Uses the UID field for PATCH and DELETE operations.

---

## Validation

The workflow uses `validate_volumeset_params` from the validators module to enforce:

**Name Validation:**
- Cannot be null
- Must be a non-empty string
- Length must be between 1 and 27 characters

**appSetType Validation:**
- Required only during create operations
- Must be a non-empty string when provided

**Optional Parameter Validation:**
- **domain**: Must be a non-empty string if provided
- **comments**: Must be a string if provided
- **newName**: Must be a non-empty string if provided
- **setmembers**: Must be a list of non-empty strings if provided
- Unsupported parameters raise `ValueError`

**Context-Aware Validation:**
- Validator accepts an `operation` parameter to apply different rules
- `operation='create'` enforces appSetType requirement
- Other operations have relaxed appSetType validation

---

## API Endpoints

The workflow interacts with the following WSAPI v3 endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/applicationsets` | Create new volume set |
| GET | `/applicationsets` | List all volume sets |
| GET | `/applicationsets/{uid}` | Get specific volume set details |
| PATCH | `/applicationsets/{uid}` | Modify volume set or update members |
| DELETE | `/applicationsets/{uid}` | Delete volume set |

**Note:** All modify operations (rename, comment update, add/remove members) use PATCH with different payload structures.

---

## Exception Handling

The workflow raises custom exceptions for common error scenarios:

### `VolumeSetAlreadyExists`
Raised when attempting to create a volume set that already exists.
```python
raise exceptions.VolumeSetAlreadyExists(name=name)
```

### `VolumeSetDoesNotExist`
Raised when attempting to operate on a non-existent volume set.
```python
raise exceptions.VolumeSetDoesNotExist(name=name)
```

### `ValueError`
Raised for validation failures (null parameters, invalid types, etc.)
```python
raise ValueError("Volume set name cannot be null")
```

### General Exception Handling
All operations catch and log exceptions before re-raising them for upstream handling.

---

## Logging

The workflow uses the `Logger` class from `core.logger` to provide detailed operational logging:

**Log Levels:**
- **INFO**: Successful operations, member additions/removals, skipped operations
- **ERROR**: Failed operations with exception details
- **DEBUG**: (via logger) Existence check failures

**Example Log Messages:**
```
INFO: Creating volume set 'AppSet1' with payload: {...}
INFO: Volume set 'AppSet1' created successfully
INFO: Volume 'vol2' is already a member of volume set 'AppSet1' so skipping it
INFO: Adding ['vol4', 'vol5'] members to volume set 'AppSet1'
INFO: Members ['vol4', 'vol5'] added to volume set 'AppSet1' successfully
ERROR: Volume set creation failed for 'AppSet1': Volume set 'AppSet1' already exists
```

---

## Integration with AnsibleClient

The `AnsibleClient` wraps the workflow to provide Ansible-compatible return tuples:

```python
def create_volumeset(self, name, appSetType=None, **kwargs):
    try:
        resp = self.volumeset_workflow.create_volumeset(name, appSetType, **kwargs)
        return (True, True, f"Volume set {name} created successfully")
    except exceptions.VolumeSetAlreadyExists as ve:
        return (True, False, str(ve), {})
    except Exception as e:
        return (False, False, f"Volume set {name} creation failed | {e}", {})
```

**Return Tuple Format:** `(success, changed, message, data)`
- **success**: Operation succeeded (API call successful)
- **changed**: System state was modified
- **message**: Human-readable result message
- **data**: Additional response data (usually empty dict)

---

## Complete Usage Example

```python
from src.core.session import SessionManager
from src.workflows.volumeset import VolumeSetWorkflow

# Initialize session and workflow
api_url = "https://10.201.5.12/api/v3"
session_mgr = SessionManager(api_url, "username", "password")
workflow = VolumeSetWorkflow(session_mgr)

# Create a volume set
try:
    response = workflow.create_volumeset(
        name="AppSet1",
        appSetType="vvol",
        domain="domain1",
        comments="Production application set",
        setmembers=["vol1", "vol2", "vol3"]
    )
    print("Volume set created successfully")
except Exception as e:
    print(f"Failed to create volume set: {e}")

# Add volumes to existing set
try:
    response = workflow.add_volumes_to_volumeset(
        name="AppSet1",
        setmembers=["vol4", "vol5"]
    )
    print("Volumes added to volume set")
except Exception as e:
    print(f"Failed to add volumes: {e}")

# Modify volume set
try:
    response = workflow.modify_volumeset(
        name="AppSet1",
        newName="ProductionAppSet",
        comments="Updated production environment"
    )
    print("Volume set modified successfully")
except Exception as e:
    print(f"Failed to modify volume set: {e}")

# Remove volumes from set
try:
    response = workflow.remove_volumes_from_volumeset(
        name="ProductionAppSet",
        setmembers=["vol5"]
    )
    print("Volumes removed from volume set")
except Exception as e:
    print(f"Failed to remove volumes: {e}")

# Check if volume set exists
exists = workflow.volumeset_exists("ProductionAppSet")
print(f"Volume set exists: {exists}")

# Delete volume set
try:
    response = workflow.delete_volumeset(name="ProductionAppSet")
    print("Volume set deleted successfully")
except Exception as e:
    print(f"Failed to delete volume set: {e}")
```

---

## Best Practices

1. **Always check existence before deletion:** Use `volumeset_exists()` to verify before deleting
2. **Handle exceptions appropriately:** Catch specific exceptions like `VolumeSetAlreadyExists` separately
3. **Use meaningful names:** Volume set names should be descriptive and within 1-27 characters
4. **Leverage intelligent filtering:** The workflow automatically filters duplicate members during add/remove
5. **Monitor logs:** Check logs for skipped operations and detailed error messages
6. **Session management:** Reuse SessionManager instances to leverage session caching
7. **Validate early:** Provide all required parameters to catch validation errors early

---

## Differences from Legacy Implementation

This v3 consolidated implementation:
- Uses PATCH instead of PUT for modify operations
- Uses UID-based endpoints instead of name-based
- Provides intelligent member filtering (prevents duplicates)
- Returns early when no changes needed (optimization)
- Combines member addition/removal into single PATCH operations
- Enhanced logging for better debugging
- Context-aware validation (operation parameter)

---

For more details, see the source code in [src/workflows/volumeset.py](../src/workflows/volumeset.py) and [src/validators/volumeset_validator.py](../src/validators/volumeset_validator.py).
