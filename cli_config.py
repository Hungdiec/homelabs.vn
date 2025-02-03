#!/usr/bin/env python3
import json

# Default configuration template
default_config = {
    "log_level": "ERROR",
    "mysql": {
        "host": "192.168.10.216",
        "port": 3306,
        "user": "npm",
        "password": "npm",
        "database": "npm"
    },
    "cloudflare": {
        "dns_record_type": "A",
        "cf_comment": "Managed by DDNS script",
        "domains": [
            {
                "name": "example.com",
                "cf_token": "YOUR_CLOUDFLARE_TOKEN",
                "zone_id": "YOUR_ZONE_ID"
            }
        ]
    },
    "paths": {
        "ip_file_path": "current_ip.txt",
        "log_file": "ddns_debug.log",
        "lock_file": "/tmp/ddns_update.lock",
        "last_hosts_file": "last_hosts.txt"
    }
}

def get_input(prompt, default):
    user_input = input(f"{prompt} [{default}]: ")
    return user_input if user_input.strip() else default

def main():
    print("==== DDNS Configuration Setup ====")
    default_config['log_level'] = get_input("Log level", default_config['log_level'])
    
    # MySQL configuration
    mysql = default_config['mysql']
    mysql['host'] = get_input("MySQL host", mysql['host'])
    mysql['port'] = int(get_input("MySQL port", mysql['port']))
    mysql['user'] = get_input("MySQL user", mysql['user'])
    mysql['password'] = get_input("MySQL password", mysql['password'])
    mysql['database'] = get_input("MySQL database", mysql['database'])
    
    # Cloudflare configuration
    cf = default_config['cloudflare']
    cf['dns_record_type'] = get_input("DNS record type", cf['dns_record_type'])
    cf['cf_comment'] = get_input("Cloudflare comment", cf['cf_comment'])
    num_domains = int(get_input("Number of Cloudflare domains to configure", "1"))
    domains = []
    for i in range(num_domains):
        print(f"--- Domain #{i+1} ---")
        domain_name = get_input("Domain name", "example.com")
        cf_token = get_input("Cloudflare API token", "YOUR_CLOUDFLARE_TOKEN")
        zone_id = get_input("Cloudflare zone ID", "YOUR_ZONE_ID")
        domains.append({"name": domain_name, "cf_token": cf_token, "zone_id": zone_id})
    cf['domains'] = domains

    # Write the configuration to config.json
    with open("ddns/config.json", "w") as f:
        json.dump(default_config, f, indent=4)
    
    print("Configuration complete. Saved to ddns/config.json.")

if __name__ == "__main__":
    main()
