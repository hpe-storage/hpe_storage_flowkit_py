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
"""DNS Configuration Validator.

This module provides validation functions for DNS and network configuration parameters.
"""

import ipaddress
from hpe_storage_flowkit_py.v3.src.core import exceptions


def validate_ipv4_address(address):
    """Validate IPv4 address format.
    
    Args:
        address (str): IPv4 address to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not address:
        return
        
    if not isinstance(address, str):
        raise exceptions.InvalidInput("IPv4 address must be a string")
    
    try:
        ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError:
        raise exceptions.InvalidInput(f"Invalid IPv4 address format: {address}")


def validate_ipv6_address(address):
    """Validate IPv6 address format.
    
    Args:
        address (str): IPv6 address to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not address:
        return
        
    if not isinstance(address, str):
        raise exceptions.InvalidInput("IPv6 address must be a string")
    
    try:
        ipaddress.IPv6Address(address)
    except ipaddress.AddressValueError:
        raise exceptions.InvalidInput(f"Invalid IPv6 address format: {address}")


def validate_ipv4_subnet_mask(mask):
    """Validate IPv4 subnet mask format.
    
    Args:
        mask (str): IPv4 subnet mask to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not mask:
        return
        
    if not isinstance(mask, str):
        raise exceptions.InvalidInput("IPv4 subnet mask must be a string")
    
    try:
        # Validate as IPv4 address first
        ipaddress.IPv4Address(mask)
        
        # Additional subnet mask validation - check for contiguous 1s followed by 0s
        mask_int = int(ipaddress.IPv4Address(mask))
        
        # Convert to binary and check if it's a valid netmask pattern
        binary_mask = bin(mask_int)[2:].zfill(32)  # Remove '0b' prefix and pad to 32 bits
        
        # Check if mask has contiguous 1s followed by contiguous 0s
        if '01' in binary_mask:  # Invalid pattern - 0 followed by 1
            raise exceptions.InvalidInput(f"Invalid subnet mask format: {mask}")
            
    except ipaddress.AddressValueError:
        raise exceptions.InvalidInput(f"Invalid IPv4 subnet mask format: {mask}")


def validate_ipv6_prefix_length(prefix_len):
    """Validate IPv6 prefix length.
    
    Args:
        prefix_len (str or int): IPv6 prefix length to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not prefix_len:
        return
        
    try:
        prefix_int = int(prefix_len)
        if prefix_int < 0 or prefix_int > 128:
            raise exceptions.InvalidInput(f"IPv6 prefix length must be between 0 and 128: {prefix_len}")
    except ValueError:
        raise exceptions.InvalidInput(f"IPv6 prefix length must be a valid integer: {prefix_len}")


def validate_dns_addresses(dns_addresses):
    """Validate DNS server addresses.
    
    Args:
        dns_addresses (list): List of DNS server addresses to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not dns_addresses:
        raise exceptions.InvalidInput("DNS addresses are required")
        
    if not isinstance(dns_addresses, list):
        raise exceptions.InvalidInput("DNS addresses must be a list")
    
    if len(dns_addresses) == 0:
        raise exceptions.InvalidInput("At least one DNS address must be provided")
    
    if len(dns_addresses) > 3:
        raise exceptions.InvalidInput("Maximum of 3 DNS addresses can be specified")
    
    for addr in dns_addresses:
        if not isinstance(addr, str) or not addr.strip():
            raise exceptions.InvalidInput("All DNS addresses must be non-empty strings")
        
        # Validate as either IPv4 or IPv6 address
        try:
            ipaddress.ip_address(addr)
        except ipaddress.AddressValueError:
            raise exceptions.InvalidInput(f"Invalid DNS address format: {addr}")


def validate_proxy_parameters(proxy_params):
    """Validate proxy configuration parameters.
    
    Args:
        proxy_params (dict): Proxy parameters to validate
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    if not proxy_params:
        return
        
    if not isinstance(proxy_params, dict):
        raise exceptions.InvalidInput("Proxy parameters must be a dictionary")
    
    # Validate authenticationRequired
    auth_required = proxy_params.get('authenticationRequired')
    if auth_required and auth_required not in ['enabled', 'disabled']:
        raise exceptions.InvalidInput("authenticationRequired must be 'enabled' or 'disabled'")

    # Validate proxyPort
    proxy_port = proxy_params.get('proxyPort')
    if proxy_port is not None:
        try:
            port_int = int(proxy_port)
            if port_int < 1 or port_int > 65535:
                raise exceptions.InvalidInput("Proxy port must be between 1 and 65535")
        except ValueError:
            raise exceptions.InvalidInput("Proxy port must be a valid integer")

    # Validate proxyProtocol
    proxy_protocol = proxy_params.get('proxyProtocol')
    if proxy_protocol and proxy_protocol not in ['HTTP', 'NTLM']:
        raise exceptions.InvalidInput("Proxy protocol must be 'HTTP' or 'NTLM'")

    # Validate proxyServer
    proxy_server = proxy_params.get('proxyServer')
    if proxy_server and not isinstance(proxy_server, str):
        raise exceptions.InvalidInput("Proxy server must be a string")

    proxy_user = proxy_params.get('proxyUser')
    proxy_password = proxy_params.get('proxyPassword')
    proxy_user_domain = proxy_params.get('proxyUserDomain')

    # If authentication is enabled, require user/pass, and only allow domain for NTLM
    if auth_required == 'enabled':
        if not proxy_user:
            raise exceptions.InvalidInput("proxyUser is required when authentication is enabled")
        if not proxy_password:
            raise exceptions.InvalidInput("proxyPassword is required when authentication is enabled")
        if proxy_protocol == 'NTLM':
            if not proxy_user_domain:
                raise exceptions.InvalidInput("proxyUserDomain is required for NTLM authentication")
        elif proxy_protocol == 'HTTP' and proxy_user_domain:
            raise exceptions.InvalidInput("proxyUserDomain must not be provided for HTTP proxy authentication")


def validate_dns_network_params(dns_addresses=None, ipv4_address=None, ipv4_gateway=None, 
                               ipv4_subnet_mask=None, ipv6_address=None, ipv6_gateway=None, 
                               ipv6_prefix_len=None, proxy_params=None, commit_change=None, 
                               slaac_enable=None):
    """Validate all DNS and network configuration parameters.
    
    Args:
        dns_addresses (list): List of DNS server addresses
        ipv4_address (str): IPv4 address for the system
        ipv4_gateway (str): IPv4 gateway address
        ipv4_subnet_mask (str): IPv4 subnet mask
        ipv6_address (str): IPv6 address for the system
        ipv6_gateway (str): IPv6 gateway address
        ipv6_prefix_len (str): IPv6 prefix length
        proxy_params (dict): Proxy configuration parameters
        commit_change (bool): Whether to commit network changes
        slaac_enable (bool): Enable/disable IPv6 SLAAC
        
    Raises:
        exceptions.InvalidInput: If validation fails
    """
    # DNS addresses are required
    validate_dns_addresses(dns_addresses)
    
    # At least IPv4 or IPv6 address must be provided
    if not ipv4_address and not ipv6_address:
        raise exceptions.InvalidInput("At least IPv4 or IPv6 address must be provided")
    
    # IPv4 validation
    if ipv4_address:
        validate_ipv4_address(ipv4_address)
        
        # If IPv4 address is specified, gateway and subnet mask are required
        if not ipv4_gateway:
            raise exceptions.InvalidInput("IPv4 gateway is required when IPv4 address is specified")
        if not ipv4_subnet_mask:
            raise exceptions.InvalidInput("IPv4 subnet mask is required when IPv4 address is specified")
        
        validate_ipv4_address(ipv4_gateway)
        validate_ipv4_subnet_mask(ipv4_subnet_mask)
    
    # IPv6 validation
    if ipv6_address:
        validate_ipv6_address(ipv6_address)
        
        # If IPv6 address is specified, gateway and prefix length are required
        if not ipv6_gateway:
            raise exceptions.InvalidInput("IPv6 gateway is required when IPv6 address is specified")
        if not ipv6_prefix_len:
            raise exceptions.InvalidInput("IPv6 prefix length is required when IPv6 address is specified")
        
        validate_ipv6_address(ipv6_gateway)
        validate_ipv6_prefix_length(ipv6_prefix_len)
    
    # Validate proxy parameters if provided
    validate_proxy_parameters(proxy_params)
    
    # Validate boolean parameters
    if commit_change is not None and not isinstance(commit_change, bool):
        raise exceptions.InvalidInput("commitChange must be a boolean value")
    
    if slaac_enable is not None and not isinstance(slaac_enable, bool):
        raise exceptions.InvalidInput("slaacEnable must be a boolean value")