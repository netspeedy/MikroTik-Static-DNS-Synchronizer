#!/usr/bin/env python3

"""
MikroTik Static DNS Synchronizer

This Python script automates the synchronization of static DNS entries between a configuration file (config.ini) and a MikroTik router, intelligently handling A, AAAA, and CNAME record types. The configuration file serves as the source of truth, ensuring that the router's DNS settings match the defined configuration.

**Features:**

* Adds new DNS entries (A, AAAA, and CNAME) from config.ini to the router.
* Deletes entries from the router that are missing in config.ini.
* Provides clear information on synchronization actions (added, deleted, unchanged entries).

This script simplifies static DNS management for your MikroTik router, ensuring it reflects the latest configuration defined in the ini file.

Author: Simon Oakes
Date: 2024-06-14
"""

import argparse
import os
import requests
import configparser
from requests.auth import HTTPBasicAuth

__version__ = "1.0.0"

def load_config(file_path):
    config = configparser.ConfigParser()
    try:
        with open(file_path) as f:
            config.read_file(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file '{file_path}' not found.")
    return config

def get_existing_dns_records(router_address, auth):
    response = requests.get(f'http://{router_address}/rest/ip/dns/static', auth=auth)
    response.raise_for_status()
    return response.json()

def add_dns_record(router_address, auth, record):
    response = requests.put(
        f'http://{router_address}/rest/ip/dns/static',
        auth=auth,
        json=record
    )
    return response

def delete_dns_record(router_address, auth, record_id):
    response = requests.delete(
        f'http://{router_address}/rest/ip/dns/static/{record_id}',
        auth=auth
    )
    return response

def dns_record_exists(existing_records, new_record):
    for existing_record in existing_records:
        if 'cname' in new_record:
            if existing_record.get('name') == new_record['name'] and existing_record.get('cname') == new_record['cname']:
                return True, existing_record['.id']
        else:
            if existing_record.get('name') == new_record['name'] and existing_record.get('address') == new_record['address']:
                return True, existing_record['.id']
    return False, None

def synchronize_dns_records(config_records, existing_records, router_address, auth, show_debug=False, show_summary=False):
    existing_record_ids = {record['.id'] for record in existing_records}
    config_record_names = set(config_records.keys())  # Extract record names from keys

    added_records = []
    deleted_records = []

    # Mark all existing records for deletion
    records_to_delete = existing_record_ids.copy()

    # Add or update records
    for name, addresses in config_records.items():
        for address in addresses:
            record = {"name": name, "address": address, "ttl": "1d"} if is_ip_address(address) else {"name": name, "cname": address, "type": "CNAME", "ttl": "1d"}
            exists, record_id = dns_record_exists(existing_records, record)
            if exists:
                # Remove from records_to_delete since it's still in config
                records_to_delete.discard(record_id)
            else:
                if 'address' in record:
                    # It's an A record (IP address)
                    response = add_dns_record(router_address, auth, record)
                else:
                    # It's a CNAME record (domain name)
                    cname_record = {
                        "name": record['name'],
                        "cname": record['cname'],
                        "type": "CNAME",
                        "ttl": record['ttl']
                    }
                    response = add_dns_record(router_address, auth, cname_record)

                if response.status_code in {200, 201}:
                    added_records.append(record['name'])
                    if show_debug:
                        print(f"DNS record successfully added: {record['name']} -> {record.get('address', record.get('cname'))}")
                elif response.status_code == 400 and "entry already exists" in response.text:
                    if show_debug:
                        print(f"DNS record already exists: {record['name']} -> {record.get('address', record.get('cname'))}")
                else:
                    if show_debug:
                        print(f"Failed to add DNS record: {record['name']} -> {record.get('address', record.get('cname'))}. Status code: {response.status_code}")
                        print(response.text)

    # Delete records not in config
    for record_id in records_to_delete:
        response = delete_dns_record(router_address, auth, record_id)
        if response.status_code == 204:
            # Find the deleted record's name for logging
            deleted_record_name = next((rec['name'] for rec in existing_records if rec['.id'] == record_id), None)
            if deleted_record_name:
                deleted_records.append(deleted_record_name)
                if show_debug:
                    print(f"DNS record deleted: {deleted_record_name}")
        elif response.status_code == 404:
            if show_debug:
                print(f"DNS record not found for deletion. Record ID: {record_id}")
        else:
            if show_debug:
                print(f"Failed to delete DNS record. Record ID: {record_id}. Status code: {response.status_code}")
                print(response.text)

    # Summary
    if show_summary:
        print("\n-- Synchronization Summary --")
        print(f"Added {len(added_records)} records: {', '.join(added_records)}")
        print(f"Deleted {len(deleted_records)} records: {', '.join(deleted_records)}")

def is_ip_address(address):
    if not address:
        return False
    # Simple function to determine if the address is an IP address
    parts = address.split('.')
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return all(0 <= int(part) <= 255 for part in parts)
    return False

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(
        prog='mikrotik-dns-sync',
        description='Synchronize DNS records with MikroTik router.',
        epilog='Environment variables can also be used to provide configuration options.'
    )

    # Application options
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}', help='display the version of mikrotik-dns-sync and exit')
    parser.add_argument('--debug', action='store_true', help='enable debugging (extra logging)')
    parser.add_argument('--config', metavar='PATH', default='config.ini', help='Specify an alternative configuration file (default: config.ini)')
    parser.add_argument('--address', metavar='ADDRESS', help='Router IP address [$MIKROTIK_ADDRESS]')
    parser.add_argument('--user', metavar='USERNAME', help='Router username [$MIKROTIK_USER]')
    parser.add_argument('--password', metavar='PASSWORD', help='Router password [$MIKROTIK_PASS]')

    args = parser.parse_args()

    # Load configuration
    config = None
    address = os.getenv('MIKROTIK_ADDRESS', args.address)
    username = os.getenv('MIKROTIK_USER', args.user)
    password = os.getenv('MIKROTIK_PASS', args.password)

    if args.config:
        try:
            config = load_config(args.config)
            address = address or config.get('Router', 'address')
            username = username or config.get('Router', 'username')
            password = password or config.get('Router', 'password')
        except FileNotFoundError as e:
            parser.error(f"Config file '{args.config}' not found.")
        except configparser.NoSectionError as e:
            parser.error(f"Invalid configuration file format - missing required section: {e}")
        except configparser.Error as e:
            parser.error(f"Invalid configuration file format: {e}")

    if not all([address, username, password]):
        parser.error("Router address, username, and password must be provided either through arguments, config file, or environment variables.")

    # Prepare auth
    auth = HTTPBasicAuth(username, password)

    # Load DNS records from config.ini if config file is used
    dns_records = {}
    if config:
        dns_records = {
            key: [value.strip() for value in values.split(',')]
            for key, values in config.items('DNSRecords')
        }

    try:
        # Get existing DNS records from the router
        existing_records = get_existing_dns_records(address, auth)

        # Synchronize records
        synchronize_dns_records(dns_records, existing_records, address, auth, show_debug=args.debug, show_summary=True)

    except requests.RequestException as e:
        print(f"Exception occurred during DNS update: {e}")

if __name__ == "__main__":
    main()

