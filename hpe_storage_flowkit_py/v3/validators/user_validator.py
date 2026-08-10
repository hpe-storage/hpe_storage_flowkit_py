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
"""Validator for user-related parameters."""

from hpe_storage_flowkit_py.v3.src.core import exceptions

# Valid privilege values as per HPE API specification
VALID_PRIVILEGES = ['super', 'service', 'security_admin', 'edit', 'create', 'browse', 'basic_edit']


def validate_user_params(name=None, password=None, domain_privileges=None, **kwargs):
    """Validate user creation/modification parameters.
    
    Args:
        name (str): User name
        password (str or list): User password
        domain_privileges (list): Domain privilege assignments
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    # Validate user name
    if name is not None:
        if not isinstance(name, str):
            raise exceptions.InvalidInput("User name must be a string")
        
        if not name.strip():
            raise exceptions.InvalidInput("User name cannot be empty")
        
        # Check for invalid characters (basic validation)
        if any(char in name for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            raise exceptions.InvalidInput("User name contains invalid characters")
    
    # Validate password
    if password is not None:
        if not isinstance(password, (str, list)):
            raise exceptions.InvalidInput("Password must be a string or list of characters")
        
        if isinstance(password, str):
            if not password:
                raise exceptions.InvalidInput("Password cannot be empty")
            
            # Basic password strength validation
            if len(password) < 8:
                raise exceptions.InvalidInput("Password must be at least 8 characters long")
                
        elif isinstance(password, list):
            if len(password) == 0:
                raise exceptions.InvalidInput("Password cannot be empty")
            
            # Validate each character in the list
            for char in password:
                if not isinstance(char, str) or len(char) != 1:
                    raise exceptions.InvalidInput("Password list must contain single character strings")
            
            # Check password strength for list format
            if len(password) < 8:
                raise exceptions.InvalidInput("Password must be at least 8 characters long")
    
    # Validate domain privileges
    if domain_privileges is not None:
        if not isinstance(domain_privileges, list):
            raise exceptions.InvalidInput("domain_privileges must be a list")
        
        if len(domain_privileges) == 0:
            raise exceptions.InvalidInput("At least one domain privilege must be specified")
        
        # Validate each domain privilege entry
        for i, dp in enumerate(domain_privileges):
            if not isinstance(dp, dict):
                raise exceptions.InvalidInput(f"Domain privilege entry {i+1} must be a dictionary")
            
            # Check required fields
            if 'name' not in dp:
                raise exceptions.InvalidInput(f"Domain privilege entry {i+1} is missing 'name' field")
            
            if 'privilege' not in dp:
                raise exceptions.InvalidInput(f"Domain privilege entry {i+1} is missing 'privilege' field")
            
            # Validate domain name
            domain_name = dp['name']
            if not isinstance(domain_name, str):
                raise exceptions.InvalidInput(f"Domain name in entry {i+1} must be a string")
            
            if not domain_name.strip():
                raise exceptions.InvalidInput(f"Domain name in entry {i+1} cannot be empty")
            
            # Validate privilege value
            privilege = dp['privilege']
            if not isinstance(privilege, str):
                raise exceptions.InvalidInput(f"Privilege in entry {i+1} must be a string")
            
            if privilege not in VALID_PRIVILEGES:
                raise exceptions.InvalidInput(
                    f"Invalid privilege '{privilege}' in entry {i+1}. "
                    f"Must be one of: {', '.join(VALID_PRIVILEGES)}"
                )
        
        # Check for duplicate domains (same user can't have multiple privileges for same domain)
        domain_names = [dp['name'] for dp in domain_privileges]
        if len(domain_names) != len(set(domain_names)):
            duplicates = [name for name in domain_names if domain_names.count(name) > 1]
            raise exceptions.InvalidInput(f"Duplicate domain names found: {', '.join(set(duplicates))}")


def validate_password_change_params(current_password=None, new_password=None):
    """Validate parameters for password change operations.
    
    Args:
        current_password (str): Current password
        new_password (str): New password
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if new_password and not current_password:
        raise exceptions.InvalidInput("currentPassword is required when changing password")
    
    if current_password and not new_password:
        raise exceptions.InvalidInput("newPassword is required when currentPassword is provided")
    
    # Validate both passwords if provided
    if current_password:
        validate_user_params(password=current_password)
    
    if new_password:
        validate_user_params(password=new_password)
        
        # Check that new password is different from current password
        if current_password == new_password:
            raise exceptions.InvalidInput("New password must be different from the current password")


def validate_modify_user_params(current_password=None, new_password=None, domain_privileges=None):
    """Validate parameters for modify user operations.
    
    Args:
        current_password (str, optional): Current password
        new_password (str, optional): New password
        domain_privileges (list, optional): Domain privileges
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    # Validate: if changing password, current_password is required
    if new_password and not current_password:
        raise exceptions.InvalidInput("currentPassword is required when changing password")
    
    # Validate both passwords if provided
    if current_password:
        validate_user_params(password=current_password)
    
    if new_password:
        validate_user_params(password=new_password)
        
        # Check that new password is different from current password
        if current_password == new_password:
            raise exceptions.InvalidInput("New password must be different from the current password")
    
    # Validate domain privileges if provided
    if domain_privileges:
        validate_user_params(domain_privileges=domain_privileges)


def validate_modify_payload(payload):
    """Validate that modify payload has at least one parameter.
    
    Args:
        payload (dict): Modification payload
        
    Raises:
        exceptions.InvalidInput: If payload is empty
    """
    if not payload:
        raise exceptions.InvalidInput("At least one parameter (password or domain_privileges) must be provided for modification")


def validate_user_uid(uid, name):
    """Validate that user has a valid UID.
    
    Args:
        uid (str): User UID
        name (str): User name
        
    Raises:
        exceptions.HPEStorageException: If UID is missing
    """
    if not uid:
        raise exceptions.HPEStorageException(f"User '{name}' found but has no UID")


def validate_user_operation_params(operation, **params):
    """Validate parameters for specific user operations.
    
    Args:
        operation (str): Operation type (create, modify, delete, get, get_all)
        **params: Operation-specific parameters
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    valid_operations = ['create', 'modify', 'delete', 'get', 'get_all']
    
    if operation not in valid_operations:
        raise exceptions.InvalidInput(f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}")
    
    # Operation-specific validation
    if operation == 'create':
        required_params = ['name', 'password', 'domain_privileges']
        for param in required_params:
            if param not in params or params[param] is None:
                raise exceptions.InvalidInput(f"Parameter '{param}' is required for create operation")
    
    elif operation == 'modify':
        # Either uid or name is required
        if not params.get('uid') and not params.get('name'):
            raise exceptions.InvalidInput("Either 'uid' or 'name' is required for modify operation")
        
        # At least one modifiable parameter should be provided
        modifiable_params = ['current_password', 'new_password', 'domain_privileges']
        if not any(params.get(param) is not None for param in modifiable_params):
            raise exceptions.InvalidInput("At least one of the following parameters is required for modify operation: " + 
                                        ', '.join(modifiable_params))
    
    elif operation in ['delete', 'get']:
        # Either uid or name is required
        if not params.get('uid') and not params.get('name'):
            raise exceptions.InvalidInput(f"Either 'uid' or 'name' is required for {operation} operation")
    
    elif operation == 'get_all':
        # No specific parameters required for get_all
        pass