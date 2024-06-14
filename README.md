# MikroTik Static DNS Synchronizer

MikroTik Static DNS Synchronizer is a Python script designed to automate the synchronization of static DNS entries between a configuration file (`config.ini`) and a MikroTik router. It supports both CNAME and A record types and ensures that your MikroTik router's DNS entries reflect the latest configuration defined in the `config.ini` file.

## Features

- **Two-way Synchronization**: Adds new DNS entries from `config.ini` to the router and deletes entries from the router that are missing in `config.ini`.
- **Supports CNAME and A Records**: Automatically identifies and handles CNAME (domain name) and A (IP address) record types.
- **Debugging Mode**: Provides optional debugging output for detailed insight into synchronization actions.
- **Clear Summary**: Displays a summary after synchronization, showing added and deleted records.

## How it Works

The script operates in the following steps:

1. **Load Configuration**: Reads the `config.ini` file for router connection details (`address`, `username`, `password`) and DNS records to synchronize.
2. **Retrieve Existing Records**: Queries the MikroTik router for existing static DNS records.
3. **Synchronize Records**:
   - **Add New Records**: Adds DNS records from `config.ini` that are not present on the router.
   - **Delete Missing Records**: Deletes DNS records from the router that are not defined in `config.ini`.
   - **Update Changed Records**: Updates IP addresses or CNAMEs for existing records if they have changed in `config.ini`.
4. **Summary**: Prints a summary of added and deleted records after synchronization.

## Setup

### Prerequisites

- Python 3.x installed on your system.
- `requests` library for Python. Install it using:

### Configuration (config.ini)

Create a `config.ini` file in the script's directory with the following structure:

```ini
[Router]
address = <Router IP address>
username = <Router username>
password = <Router password>

[DNSRecords]
<hostname> = <IP address or CNAME>
```
```
To specify multiple IP addresses for Round Robin DNS (RRDNS) or dual stacked IPv4 and IPv6 records, use comma-separated values.
```

Replace **< Router IP address >**, **< Router username >**, and **< Router password >** with your MikroTik router's details. Add DNS records under **[DNSRecords]** section where **< hostname >** is the DNS hostname and **< IP address(es) or CNAME >** is the corresponding **IP address** or **CNAME**.

Example `config.ini`:

```
[Router]
address = 192.168.88.1
username = autodns
password = dnsrocks

[DNSRecords]
ns.example.com = 198.51.100.1, 203.0.113.1, 2001:DB8::1
v6.example.com = 2001:DB8::2
myrecord.example.com = router.example.com
```

### Usage

Run the script using Python:

```
python3 mikrotik-dns-sync.py --address <Router IP> --user <Router username> --password <Router password>
```

Alternatively, you can set these parameters directly in the script or use environment variables:

    MIKROTIK_ADDRESS: Router IP address
    MIKROTIK_USER: Router username
    MIKROTIK_PASS: Router password

### Debug Mode

Enable debug mode to see detailed logging of synchronization actions:

```
python3 mikrotik-dns-sync.py --address <Router IP> --user <Router username> --password <Router password> --debug
```

### Contributing

Contributions are welcome! Fork the repository, make your changes, and submit a pull request.

### License

This project is licensed under the MIT License - see the LICENSE file for details.


