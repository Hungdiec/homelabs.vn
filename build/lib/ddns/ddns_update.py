#!/usr/bin/env python3

import requests
import pymysql
import json
import os
import sys
import logging
import time

# === Determine Script Directory ===

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# === Load Configuration ===

CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')

try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"Configuration file {CONFIG_FILE} not found.")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Error parsing configuration file {CONFIG_FILE}: {e}")
    sys.exit(1)

# === Configuration Variables ===

LOG_LEVEL = config.get('log_level', 'INFO')

# MariaDB Configuration
MYSQL_CONFIG = config.get('mysql', {})
MYSQL_HOST = MYSQL_CONFIG.get('host', '127.0.0.1')
MYSQL_PORT = MYSQL_CONFIG.get('port', 3306)
MYSQL_USER = MYSQL_CONFIG.get('user', 'npm')
MYSQL_PASS = MYSQL_CONFIG.get('password', 'npm')
MYSQL_DB = MYSQL_CONFIG.get('database', 'npm')

# Cloudflare Configuration
CLOUDFLARE_CONFIG = config.get('cloudflare', {})
DNS_RECORD_TYPE = CLOUDFLARE_CONFIG.get('dns_record_type', 'A')
CF_COMMENT = CLOUDFLARE_CONFIG.get('cf_comment', 'Managed by DDNS script')
DOMAINS = CLOUDFLARE_CONFIG.get('domains', [])

# Paths
PATHS = config.get('paths', {})
IP_FILE_PATH = os.path.join(SCRIPT_DIR, PATHS.get('ip_file_path', 'current_ip.txt'))
LOG_FILE = os.path.join(SCRIPT_DIR, PATHS.get('log_file', 'ddns_debug.log'))
LOCKFILE = PATHS.get('lock_file', '/tmp/ddns_update.lock')  # Keeping /tmp as is
LAST_HOSTS_FILE = os.path.join(SCRIPT_DIR, PATHS.get('last_hosts_file', 'last_hosts.txt'))

# === Set up Logging ===

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.DEBUG),
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

def log(level, message):
    getattr(logging, level.lower())(message)

# === Functions ===

def perform_request(method, url, headers, data=None):
    """
    Performs an HTTP request with retries and error handling.
    """
    retries = 3
    wait = 5
    for attempt in range(1, retries + 1):
        try:
            log("debug", f"HTTP {method} Request to {url}")
            log("debug", f"Headers: {headers}")
            if data:
                log("debug", f"Data: {json.dumps(data)}")
            response = requests.request(method, url, headers=headers, json=data, timeout=10)
            log("debug", f"Response Status Code: {response.status_code}")
            log("debug", f"Response Body: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log("debug", f"Request failed for {url}. Attempt {attempt}/{retries}. Error: {e}")
            if attempt < retries:
                time.sleep(wait)
            else:
                log("error", f"Failed to perform request for {url} after {retries} attempts.")
                return None

def get_current_ip():
    """
    Retrieves the current public IP address.
    """
    try:
        response = requests.get('http://ipv4.icanhazip.com', timeout=10)
        log("debug", f"HTTP GET Request to http://ipv4.icanhazip.com")
        log("debug", f"Response Status Code: {response.status_code}")
        log("debug", f"Response Body: {response.text.strip()}")
        response.raise_for_status()
        current_ip = response.text.strip()
        if not current_ip.count('.') == 3:
            raise ValueError("Invalid IP address retrieved.")
        log("info", f"Current IP: {current_ip}")
        return current_ip
    except requests.exceptions.RequestException as e:
        log("error", f"Failed to get current IP address: {e}")
        sys.exit(1)
    except ValueError as ve:
        log("error", f"{ve}")
        sys.exit(1)

def get_proxy_domains():
    """
    Retrieves the list of proxy domains from the MariaDB database.
    """
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT domain_names FROM proxy_host WHERE is_deleted = 0;")
            rows = cursor.fetchall()
        connection.close()
        proxy_domains = set()
        for row in rows:
            domains = json.loads(row[0])
            for domain in domains:
                normalized = domain.lower().rstrip('.').strip()
                proxy_domains.add(normalized)
        log("info", "Current proxy domains:")
        for domain in proxy_domains:
            log("info", f" - {domain}")
        return proxy_domains
    except pymysql.MySQLError as e:
        log("error", f"Error fetching proxy domains: {e}")
        sys.exit(1)

def load_previous_hosts():
    """
    Loads the list of previously known proxy domains.
    """
    previous_hosts = set()
    if os.path.isfile(LAST_HOSTS_FILE):
        with open(LAST_HOSTS_FILE, 'r') as f:
            for line in f:
                previous_hosts.add(line.strip())
    return previous_hosts

def save_current_hosts(hosts):
    """
    Saves the current list of proxy domains to a file.
    """
    with open(LAST_HOSTS_FILE, 'w') as f:
        for host in hosts:
            f.write(f"{host}\n")

def update_dns_records(current_ip, proxy_domains, previous_hosts):
    """
    Updates, creates, or deletes DNS records on Cloudflare as needed.
    """
    if not DOMAINS:
        log("error", "No domain configurations found in config.json.")
        sys.exit(1)

    for domain_config in DOMAINS:
        domain_name = domain_config.get('name')
        cf_token = domain_config.get('cf_token')
        zone_id = domain_config.get('zone_id')

        if not domain_name or not cf_token or not zone_id:
            log("error", f"Incomplete domain configuration: {domain_config}")
            continue

        log("info", f"Processing domain: {domain_name} (Zone: {zone_id})")
        headers = {
            'Authorization': f'Bearer {cf_token}',
            'Content-Type': 'application/json'
        }

        # Get existing DNS records
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type={DNS_RECORD_TYPE}&per_page=100"
        response = perform_request('GET', url, headers)
        if not response or not response.get('success'):
            log("error", f"Failed to fetch DNS records for {domain_name}: {response}")
            continue

        existing_records = {}
        for record in response['result']:
            name = record['name'].lower().rstrip('.')
            existing_records[name] = record

        # Log the fetched DNS records
        log("debug", f"Existing DNS records for {domain_name}:")
        for name, record in existing_records.items():
            log("debug", f" - {name}: {record['content']}")

        # Update existing records if IP has changed
        needs_ip_update = False
        for name, record in existing_records.items():
            if name in proxy_domains:
                log("debug", f"Checking if {name} needs update:")
                log("debug", f" - Current IP: {current_ip}")
                log("debug", f" - DNS Record IP: {record['content']}")
                if record['content'] != current_ip:
                    log("info", f"Updating {name} from {record['content']} to {current_ip}")
                    update_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record['id']}"
                    data = {
                        "type": DNS_RECORD_TYPE,
                        "name": name,
                        "content": current_ip,
                        "ttl": 1,
                        "proxied": False,
                        "comment": CF_COMMENT
                    }
                    update_response = perform_request('PUT', update_url, headers, data)
                    if update_response and update_response.get('success'):
                        log("info", f"Successfully updated {name}")
                        needs_ip_update = True
                    else:
                        log("error", f"Failed to update {name}: {update_response.get('errors') if update_response else 'No response'}")
                else:
                    log("debug", f"No update needed for {name}. IPs match.")
            else:
                log("debug", f"{name} not in proxy domains. Skipping.")

        # Create new records for domains that don't exist
        for proxy_domain in proxy_domains:
            if proxy_domain.endswith(domain_name) and proxy_domain not in existing_records:
                log("info", f"Creating new DNS record: {proxy_domain} → {current_ip}")
                create_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
                data = {
                    "type": DNS_RECORD_TYPE,
                    "name": proxy_domain,
                    "content": current_ip,
                    "ttl": 1,
                    "proxied": False,
                    "comment": CF_COMMENT
                }
                create_response = perform_request('POST', create_url, headers, data)
                if create_response and create_response.get('success'):
                    log("info", f"Created {proxy_domain} with ID {create_response['result']['id']}")
                    needs_ip_update = True
                else:
                    log("error", f"Failed to create {proxy_domain}: {create_response.get('errors') if create_response else 'No response'}")

        # Delete records that are no longer in proxy domains
        deleted_hosts = previous_hosts - proxy_domains
        for host in deleted_hosts:
            if host.endswith(domain_name):
                record = existing_records.get(host)
                if record:
                    log("info", f"Deleting DNS record for removed host: {host}")
                    delete_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record['id']}"
                    delete_response = perform_request('DELETE', delete_url, headers)
                    if delete_response and delete_response.get('success'):
                        log("info", f"Successfully deleted {host}")
                        needs_ip_update = True
                    else:
                        log("error", f"Failed to delete {host}: {delete_response.get('errors') if delete_response else 'No response'}")
                else:
                    log("debug", f"No existing DNS record found for {host}. Skipping deletion.")

        # Update IP file if any changes were made
        if needs_ip_update:
            with open(IP_FILE_PATH, 'w') as f:
                f.write(current_ip)
            log("info", "Updated IP storage file")

def main():
    """
    Main execution flow of the script.
    """
    # Check for lockfile
    if os.path.exists(LOCKFILE):
        log("info", "Script is already running. Exiting.")
        sys.exit(1)
    try:
        # Create lockfile
        with open(LOCKFILE, 'w') as f:
            f.write(str(os.getpid()))
        # Get current IP
        current_ip = get_current_ip()
        # Get proxy domains from database
        proxy_domains = get_proxy_domains()
        # Load previous hosts
        previous_hosts = load_previous_hosts()
        # Update DNS records
        update_dns_records(current_ip, proxy_domains, previous_hosts)
        # Save current hosts
        save_current_hosts(proxy_domains)
        log("info", "Update complete. Cleaning up.")
    finally:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)

if __name__ == "__main__":
    main()
