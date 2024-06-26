#!/usr/bin/env python3

"""
MikroTik Static DNS Synchronizer

This Python script automates the synchronization of static DNS entries between a configuration
file (config.ini) and a MikroTik router, intelligently handling A, AAAA, and CNAME record types.
The configuration file serves as the source of truth, ensuring that the router's DNS settings
match the defined configuration.

**Features:**

* Adds new DNS entries (A, AAAA, and CNAME) from config.ini to the router.
* Deletes entries from the router that are missing in config.ini.
* Provides clear information on synchronization actions (added, deleted, unchanged entries).

This script simplifies static DNS management for your MikroTik router, ensuring it reflects
the latest configuration defined in the ini file.

Author: Simon Oakes
Date: 2024-06-14
"""

import argparse
import configparser

import requests
from requests.auth import HTTPBasicAuth

__version__ = "1.0.1"


def load_config(file_path):
    """
    Load configuration from a specified ini file.

    Args:
        file_path (str): Path to the configuration ini file.

    Returns:
        configparser.ConfigParser: Loaded configuration parser object.

    Raises:
        FileNotFoundError: If the specified config file is not found.
    """
    config = configparser.ConfigParser()
    try:
        with open(file_path, encoding='utf-8') as f:
            config.read_file(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Config file '{file_path}' not found.") from exc
    return config


def get_existing_dns_records(router_address, auth):
    """
    Retrieve existing DNS records from the MikroTik router.

    Args:
        router_address (str): IP address or hostname of the MikroTik router.
        auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP basic authentication.

    Returns:
        list: List of existing DNS records as JSON objects.

    Notes:
        This function retrieves the current static DNS entries configured on the MikroTik router
        using the '/rest/ip/dns/static' API endpoint.

    Raises:
        requests.exceptions.Timeout: If the request times out while communicating with the router.
        requests.exceptions.RequestException: If any other error occurs during the request.
    """
    try:
        response = requests.get(
            f"http://{router_address}/rest/ip/dns/static",
            auth=auth,
            timeout=10  # Set your desired timeout value in seconds
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        # Handle timeout error gracefully
        print(
            f"Timeout error occurred while retrieving existing DNS records from "
            f"{router_address}"
        )
        return []
    except requests.exceptions.RequestException as e:
        # Handle other request exceptions
        print(f"Error occurred while retrieving existing DNS records: {e}")
        return []


def add_dns_record(router_address, auth, record):
    """
    Add a DNS record to the MikroTik router.

    Args:
        router_address (str): IP address or hostname of the MikroTik router.
        auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP basic authentication.
        record (dict): Dictionary representing the DNS record to add. Should include 'name',
                       'address' (for A and AAAA records), 'cname' (for CNAME records), 'type'
                       (optional for CNAME records), and 'ttl' (time to live).

    Returns:
        requests.Response or None: Response object if the addition was successful, None otherwise.

    Notes:
        This function uses the '/rest/ip/dns/static' API endpoint of MikroTik router to add
        DNS records. It handles both A/AAAA and CNAME record types based on the provided record
        dictionary.

    """
    try:
        response = requests.put(
            f"http://{router_address}/rest/ip/dns/static",
            auth=auth,
            json=record,
            timeout=10
        )
        return response
    except requests.exceptions.Timeout:
        # Handle timeout error gracefully
        print(f"Timeout error occurred while adding DNS record {record}")
        return None


def delete_dns_record(router_address, auth, record_id):
    """
    Delete a DNS record from the MikroTik router.

    Args:
        router_address (str): IP address or hostname of the MikroTik router.
        auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP basic authentication.
        record_id (str): ID of the DNS record to delete.

    Returns:
        requests.Response or None: Response object if the deletion was successful, None otherwise.

    Raises:
        None: This function does not raise exceptions directly, but exceptions might be raised
              by functions called within (e.g., requests library for HTTP requests).
    """
    try:
        response = requests.delete(
            f"http://{router_address}/rest/ip/dns/static/{record_id}",
            auth=auth,
            timeout=10
        )
        return response
    except requests.exceptions.Timeout:
        # Handle timeout error gracefully
        print(f"Timeout error occurred while deleting DNS record {record_id}")
        return None


def dns_record_exists(existing_records, new_record):
    """
    Check if a given DNS record exists in the list of existing records.

    Args:
        existing_records (list): List of existing DNS records as JSON objects.
        new_record (dict): New DNS record to check existence for.

    Returns:
        tuple: A tuple where the first element is a boolean indicating if the record exists,
               and the second element is the ID of the existing record if found, None otherwise.

    Notes:
        This function compares 'name' and 'address' or 'cname' of the new record against
        'name' and 'address' or 'cname' of each existing record in the list.

    """
    for existing_record in existing_records:
        if "cname" in new_record:
            if (
                existing_record.get("name") == new_record["name"]
                and existing_record.get("cname") == new_record["cname"]
            ):
                return True, existing_record[".id"]
        else:
            if (
                existing_record.get("name") == new_record["name"]
                and existing_record.get("address") == new_record["address"]
            ):
                return True, existing_record[".id"]
    return False, None


def process_add_dns_record(router_address, auth, record, show_debug):
    """
    Process adding a DNS record to the MikroTik router.

    Args:
        router_address (str): IP address or hostname of the MikroTik router.
        auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP basic authentication.
        record (dict): DNS record to add.
        show_debug (bool): Flag to enable debug logging.
    """
    if "address" in record:
        response = add_dns_record(router_address, auth, record)
    else:
        cname_record = {
            "name": record["name"],
            "cname": record["cname"],
            "type": "CNAME",
            "ttl": record["ttl"],
        }
        response = add_dns_record(router_address, auth, cname_record)

    if response and response.status_code in {200, 201}:
        if show_debug:
            print(
                f"DNS record successfully added: {record['name']} -> "
                f"{record.get('address', record.get('cname'))}"
            )
        return record["name"]
    if response and response.status_code == 400 and "entry already exists" in response.text:
        if show_debug:
            print(
                f"DNS record already exists: {record['name']} -> "
                f"{record.get('address', record.get('cname'))}"
            )
        return None
    if show_debug:
        print(
            f"Failed to add DNS record: {record['name']} -> "
            f"{record.get('address', record.get('cname'))}. "
            f"Status code: {response.status_code}"
        )
        print(response.text)
    return None


def process_delete_dns_record(router_address, auth, record_id, existing_records, show_debug):
    """
    Process deleting a DNS record from the MikroTik router.

    Args:
        router_address (str): IP address or hostname of the MikroTik router.
        auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP basic authentication.
        record_id (str): ID of the DNS record to delete.
        existing_records (list): List of existing DNS records.
        show_debug (bool): Flag to enable debug logging.

    Returns:
        str or None: Name of the deleted DNS record, or None if deletion was not successful.
    """
    response = delete_dns_record(router_address, auth, record_id)
    if response and response.status_code == 204:
        deleted_record_name = next(
            (rec["name"] for rec in existing_records if rec[".id"] == record_id),
            None,
        )
        if deleted_record_name and show_debug:
            print(f"DNS record successfully deleted: {deleted_record_name}")
        return deleted_record_name
    if response and response.status_code == 404:
        if show_debug:
            print(f"DNS record not found for deletion. Record ID: {record_id}")
        return None
    if show_debug:
        print(
            f"Failed to delete DNS record. Record ID: {record_id}. "
            f"Status code: {response.status_code}"
        )
        print(response.text)
    return None

# pylint: disable=R0914
def synchronize_dns_records(config):
    """
    Synchronize DNS records between configuration and MikroTik router.

    Args:
        config (dict): Dictionary containing configuration parameters:
            - config_records (dict):
              Dictionary mapping DNS record names to lists of addresses or CNAMEs.
            - existing_records (list):
              List of existing DNS records fetched from the MikroTik router.
            - router_address (str): IP address or hostname of the MikroTik router.
            - auth (requests.auth.HTTPBasicAuth): Authentication object for HTTP
              basic authentication.
            - show_debug (bool, optional):
              Flag to enable debug logging (default is False).
            - show_summary (bool, optional):
              Flag to show synchronization summary (default is False).

    Raises:
        None: This function does not raise exceptions directly, but exceptions might be raised
              by functions called within (e.g., requests library for HTTP requests).

    """
    config_records = config.get('config_records')
    existing_records = config.get('existing_records')
    router_address = config.get('router_address')
    auth = config.get('auth')
    show_debug = config.get('show_debug', False)
    show_summary = config.get('show_summary', False)

    existing_record_ids = {record[".id"] for record in existing_records}

    added_records = []
    deleted_records = []

    records_to_delete = existing_record_ids.copy()

    for name, addresses in config_records.items():
        for address in addresses:
            record = (
                {"name": name, "address": address, "ttl": "1d"}
                if is_ip_address(address)
                else {"name": name, "cname": address, "type": "CNAME", "ttl": "1d"}
            )
            exists, record_id = dns_record_exists(existing_records, record)
            if exists:
                records_to_delete.discard(record_id)
            else:
                added_record_name = process_add_dns_record(router_address, auth, record, show_debug)
                if added_record_name:
                    added_records.append(added_record_name)

    for record_id in records_to_delete:
        deleted_record_name = process_delete_dns_record(
            router_address, auth, record_id, existing_records, show_debug
        )

        if deleted_record_name:
            deleted_records.append(deleted_record_name)

    if show_summary:
        print("\n-- Synchronization Summary --")
        print(f"Added {len(added_records)} records: {', '.join(added_records)}")
        print(f"Deleted {len(deleted_records)} records: {', '.join(deleted_records)}")


def is_ip_address(address):
    """
    Check if the given string is a valid IPv4 address.

    Args:
        address (str): The string to check.

    Returns:
        bool: True if the string is a valid IPv4 address, False otherwise.
    """
    if not address:
        return False
    # Simple function to determine if the address is an IP address
    parts = address.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return all(0 <= int(part) <= 255 for part in parts)
    return False

def main():
    """
    Main function to synchronize DNS records with a MikroTik router.

    This function handles argument parsing, loads configuration, retrieves existing DNS records,
    and synchronizes them with the configured DNS records from a specified config file or arguments.

    Command-line options:
    --version : Display version information.
    --debug   : Enable debugging mode for extra logging.
    --config  : Specify an alternative configuration file (default: config.ini).
    --address : Router IP address [$MIKROTIK_ADDRESS].
    --user    : Router username [$MIKROTIK_USER].
    --password: Router password [$MIKROTIK_PASS].

    Environment variables can also be used to provide configuration options.

    Raises:
        FileNotFoundError: If the specified config file is not found.
        NoSectionError: If the config file is invalid and missing required sections.
        Error: If there's any other configuration file format issue.

    """
    # Argument parsing
    parser = argparse.ArgumentParser(
        prog="mikrotik_dns_sync",
        description="Synchronize DNS records with MikroTik router.",
        epilog="Environment variables can also be used to provide configuration options.",
    )

    # Application options
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="display the version of mikrotik_dns_sync and exit",
    )
    parser.add_argument(
        "--debug", action="store_true", help="enable debugging (extra logging)"
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="config.ini",
        help="Specify an alternative configuration file (default: config.ini)",
    )
    parser.add_argument(
        "--address", metavar="ADDRESS", help="Router IP address [$MIKROTIK_ADDRESS]"
    )
    parser.add_argument(
        "--user", metavar="USERNAME", help="Router username [$MIKROTIK_USER]"
    )
    parser.add_argument(
        "--password", metavar="PASSWORD", help="Router password [$MIKROTIK_PASS]"
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
        address = args.address or config.get("Router", "address")
        username = args.user or config.get("Router", "username")
        password = args.password or config.get("Router", "password")
    # pylint: disable=W0612
    except FileNotFoundError as e:
        parser.error(f"Config file '{args.config}' not found.")
    except configparser.NoSectionError as e:
        parser.error(f"Invalid configuration file format - missing required section: {e}")
    except configparser.Error as e:
        parser.error(f"Invalid configuration file format: {e}")

    # Prepare auth
    auth = HTTPBasicAuth(username, password)

    # Load DNS records from config.ini if config file is used
    dns_records = {}
    if config:
        dns_records = {
            key: [value.strip() for value in values.split(",")]
            for key, values in config.items("DNSRecords")
        }

    try:
        # Get existing DNS records from the router
        existing_records = get_existing_dns_records(address, auth)

        # Define configuration object
        sync_config = {
            'config_records': dns_records,
            'existing_records': existing_records,
            'router_address': address,
            'auth': auth,
            'show_debug': args.debug,
            'show_summary': True,
        }

        # Synchronize records
        synchronize_dns_records(sync_config)

    except requests.RequestException as e:
        print(f"Exception occurred during DNS update: {e}")


if __name__ == "__main__":
    main()
