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

# Host Set Workflow Documentation

## Overview
The `HostSetWorkflow` class in the HPE Storage Flowkit provides comprehensive methods to manage host sets on HPE 3PAR/Alletra storage systems using the v3 WSAPI. It handles parameter validation, payload construction, API communication, asynchronous task management, and intelligent member management.

## Class: `HostSetWorkflow`

### Initialization
```python
HostSetWorkflow(session_client: SessionManager)
```
- **session_client**: Instance of `SessionManager` to manage REST API sessions with the storage array.
- Automatically initializes a `TaskManager` for handling asynchronous operations.

### Methods

---

#### `create_hostset(name, **kwargs)`
Creates a new host set with the specified parameters. Supports both synchronous (201) and asynchronous (202) creation responses.

**Required Parameters:**
- **name** (string): Name of the host set to be created
  - Must be a non-empty string
  - Must be unique within the storage system

**Optional Parameters (`**kwargs`):**
- **domain** (string): Domain for the host set
- **comment** (string): Descriptive comments for the host set
- **members** (list): Initial list of host members to add to the set
  - Each member must be a non-empty string
  - Host names that should be part of this host set

**Returns:**
- API response from the `/hostsets` endpoint on success (201 response)
- Task completion result if the operation is asynchronous (202 response)
- Raises `HostSetAlreadyExists` if a host set with the same name already exists

**Example:**
```python
workflow = HostSetWorkflow(session_client)
response = workflow.create_hostset(
    name="HostSet1",
    domain="domain1",
    comment="Production host set",
    members=["host1", "host2", "host3"]
)
```

**Workflow Steps:**
1. Validates all parameters using `validate_hostset_params`
2. Checks if host set already exists
3. Builds payload with `name` and optional parameters (domain, comment, members)
4. Sends POST request to `/hostsets`
5. If response contains `resourceUri` (202 status):
   - Extracts the task URI from the response
   - Waits for task completion using `TaskManager.wait_for_task_to_end()`
   - Polls every 15 seconds until task completes
6. If immediate creation (201 status):
   - Returns the response directly
7. Logs creation success or failure

**Response Handling:**
- **201 Created**: Host set created immediately, returns host set details
- **202 Accepted**: Asynchronous task created, waits for completion
  ```json
  {
      "message": "Started task to execute create Host Set",
      "resourceUri": "/api/v3/tasks/f7d6e2ee7ed21bfe37e2a99948f8c2f6"
  }
  ```

---

#### `delete_hostset(name)`
Deletes an existing host set from the storage system using the host set's UID.

**Parameters:**
- **name** (string): Name of the host set to delete
  - Must be a non-empty string

**Returns:**
- API response from the `/hostsets/{uid}` endpoint on success
- Raises `HostSetDoesNotExist` if the host set is not found

**Example:**
```python
workflow = HostSetWorkflow(session_client)
response = workflow.delete_hostset(name="HostSet1")
```

**Workflow Steps:**
1. Validates host set name
2. Checks if host set exists
3. Retrieves host set information to get the UID
4. Sends DELETE request to `/hostsets/{uid}` (uses UID, not name)
5. Logs deletion success or failure

**Note:** The DELETE operation uses the host set's UID in the URL path, not the name, as the API requires the unique identifier for deletion.

---

#### `get_hostset(name)`
Retrieves information about a specific host set.

**Parameters:**
- **name** (string): Name of the host set to retrieve
  - Must be a non-empty string

**Returns:**
- Dictionary containing host set information including:
  - `name`: Host set name
  - `uid`: Unique identifier
  - `domain`: Domain name
  - `comment`: Comments
  - `members`: List of host members
- Empty list `[]` if host set not found

**Example:**
```python
workflow = HostSetWorkflow(session_client)
hostset_info = workflow.get_hostset(name="HostSet1")
print(f"Host set UID: {hostset_info.get('uid')}")
print(f"Members: {hostset_info.get('members')}")
```

**Workflow Steps:**
1. Validates host set name
2. Retrieves all host sets from `/hostsets`
3. Searches for matching host set by name
4. Returns host set information or empty list

---

#### `add_hosts_to_hostset(name, setmembers)`
Adds new host members to an existing host set. Intelligently detects and skips hosts that are already members.

**Parameters:**
- **name** (string, required): Name of the host set
- **setmembers** (list, required): List of host names to add
  - Cannot be null
  - Each member must be a non-empty string

**Returns:**
- API response from the `/hostsets/{uid}` endpoint on success
- Raises `HostSetDoesNotExist` if the host set is not found
- Raises `HostSetMembersAlreadyPresent` if all specified hosts are already members

**Example:**
```python
workflow = HostSetWorkflow(session_client)
response = workflow.add_hosts_to_hostset(
    name="HostSet1",
    setmembers=["host4", "host5", "host6"]
)
```

**Workflow Steps:**
1. Validates host set name and setmembers parameter
2. Checks if host set exists
3. Retrieves current host set members
4. Identifies which hosts are new (not already in the set)
5. If all hosts are already members, raises `HostSetMembersAlreadyPresent`
6. Builds new members list (existing + new members)
7. Sends PATCH request to `/hostsets/{uid}` with updated members list
8. Logs which members were added successfully

**Idempotency:**
- Automatically skips hosts that are already members
- Only adds truly new members
- Logs informational messages for skipped hosts
- Raises exception only if no new members need to be added

---

#### `remove_hosts_from_hostset(name, setmembers)`
Removes host members from an existing host set. Intelligently detects and skips hosts that are not members.

**Parameters:**
- **name** (string, required): Name of the host set
- **setmembers** (list, required): List of host names to remove
  - Cannot be null
  - Each member must be a non-empty string

**Returns:**
- API response from the `/hostsets/{uid}` endpoint on success
- Raises `HostSetDoesNotExist` if the host set is not found
- Raises `HostSetMembersAlreadyRemoved` if all specified hosts are already not members

**Example:**
```python
workflow = HostSetWorkflow(session_client)
response = workflow.remove_hosts_from_hostset(
    name="HostSet1",
    setmembers=["host4", "host5"]
)
```

**Workflow Steps:**
1. Validates host set name and setmembers parameter
2. Checks if host set exists
3. Retrieves current host set members
4. Identifies which hosts can be removed (currently in the set)
5. If no hosts need to be removed, raises `HostSetMembersAlreadyRemoved`
6. Builds new members list (excluding hosts to be removed)
7. Sends PATCH request to `/hostsets/{uid}` with updated members list
8. Logs which members were removed successfully

**Idempotency:**
- Automatically skips hosts that are not members
- Only removes hosts that are actually present
- Logs informational messages for skipped hosts
- Raises exception only if no members need to be removed

---

#### `hostset_exists(name)`
Helper method to check if a host set exists in the storage system.

**Parameters:**
- **name** (string): Name of the host set to check
  - Must be a non-empty string

**Returns:**
- `True` if the host set exists
- `False` if the host set does not exist

**Example:**
```python
workflow = HostSetWorkflow(session_client)
if workflow.hostset_exists("HostSet1"):
    print("Host set exists")
else:
    print("Host set not found")
```

---

## Error Handling

The workflow raises specific exceptions for different error scenarios:

### Custom Exceptions
- **`HostSetAlreadyExists`**: Raised when attempting to create a host set that already exists
- **`HostSetDoesNotExist`**: Raised when attempting to operate on a non-existent host set
- **`HostSetMembersAlreadyPresent`**: Raised when all hosts being added are already members
- **`HostSetMembersAlreadyRemoved`**: Raised when all hosts being removed are already not members
- **`HPEStorageException`**: Raised for general API errors

### Validation Errors
The `validate_hostset_params` function validates parameters before API calls:
- Ensures `name` is a non-empty string
- Validates optional parameters (domain, comment, members)
- Raises `ValueError` for invalid parameters

---

## Asynchronous Operations

The `HostSetWorkflow` automatically handles asynchronous operations for create operations:

### Task Detection
```python
if response and isinstance(response, dict) and "resourceUri" in response:
    # Async task detected (202 response)
    task_uri = response.get("resourceUri")
```

### Task Polling
- Uses `TaskManager.wait_for_task_to_end(task_uri)` (poll rate and timeout configured in utils.constants)
- Polls the task status every 15 seconds
- Waits until the task completes successfully or fails
- Logs progress and completion status

### Response Format for Async Tasks (202)
```json
{
    "message": "Started task to execute create Host Set",
    "resourceUri": "/api/v3/tasks/f7d6e2ee7ed21bfe37e2a99948f8c2f6"
}
```

---

## Helper Methods

### `_get_hostsets_info()`
Internal method to retrieve all host sets from the storage system.

**Returns:**
- Dictionary containing all host sets in `members` field

---

### `_get_hostset_info(name)`
Internal method to retrieve information for a specific host set by name.

**Parameters:**
- **name** (string): Host set name

**Returns:**
- Host set information dictionary if found
- Empty list `[]` if not found

---

### `_build_create_payload(name, **kwargs)`
Internal method to construct the payload for host set creation.

**Parameters:**
- **name** (string): Host set name
- **kwargs**: Optional parameters (domain, comment, members)

**Returns:**
- Dictionary payload ready for POST request

---

## Usage Examples

### Complete Workflow Example
```python
from src.ansible_client import AnsibleClient

# Initialize client
client = AnsibleClient(
    base_path="10.132.239.141:443",
    username="3paradm",
    password="your_password"
)

# Create a host set with members
try:
    result = client.create_hostset(
        name="ProductionHosts",
        domain="production",
        comment="Production environment hosts",
        members=["web-server-01", "web-server-02", "db-server-01"]
    )
    print("Host set created successfully")
except Exception as e:
    print(f"Error: {e}")

# Add more hosts to existing host set
try:
    result = client.add_hosts_to_hostset(
        name="ProductionHosts",
        setmembers=["app-server-01", "app-server-02"]
    )
    print("Hosts added successfully")
except Exception as e:
    print(f"Error: {e}")

# Remove hosts from host set
try:
    result = client.remove_hosts_from_hostset(
        name="ProductionHosts",
        setmembers=["web-server-02"]
    )
    print("Hosts removed successfully")
except Exception as e:
    print(f"Error: {e}")

# Get host set information
hostset_info = client.get_hostset(name="ProductionHosts")
print(f"Current members: {hostset_info.get('members')}")

# Delete host set
try:
    result = client.delete_hostset(name="ProductionHosts")
    print("Host set deleted successfully")
except Exception as e:
    print(f"Error: {e}")
```

---

## API Endpoints Used

- **POST /hostsets**: Create a new host set
- **GET /hostsets**: Retrieve all host sets
- **DELETE /hostsets/{uid}**: Delete a host set by UID
- **PATCH /hostsets/{uid}**: Update host set members

---

## Best Practices

1. **Always check existence before creation**: The workflow automatically checks if a host set exists before creating it
2. **Use meaningful names**: Host set names should be descriptive and follow your naming conventions
3. **Leverage idempotency**: Add/remove operations are idempotent and safe to retry
4. **Handle async operations**: The workflow automatically handles 202 responses and waits for task completion
5. **Use UIDs for deletion**: The delete operation uses the host set's UID, which is automatically retrieved
6. **Monitor logs**: The workflow provides detailed logging for troubleshooting
7. **Batch member operations**: Use add/remove operations to manage multiple hosts efficiently

---

## Related Components

- **`TaskManager`**: Handles asynchronous task polling and completion
- **`SessionManager`**: Manages REST API sessions and authentication
- **`validate_hostset_params`**: Validates host set parameters before API calls
- **`AnsibleClient`**: High-level facade for Ansible-style return tuples
