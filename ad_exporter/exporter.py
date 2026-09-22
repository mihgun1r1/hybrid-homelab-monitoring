import time
import os
from ldap3 import Server, Connection, ALL, SIMPLE
from prometheus_client import start_http_server, Gauge

AD_USERS_TOTAL = Gauge('ad_users_total', 'Total number of users in Active Directory', ['status'])
AD_GROUPS_TOTAL = Gauge('ad_groups_total', 'Total security groups in Active Directory')

LDAP_SERVER = os.getenv("LDAP_SERVER", "samba_ad")
LDAP_USER = os.getenv("LDAP_USER", "Administrator@HOMELAB.LAN")
LDAP_PASSWORD = os.getenv("LDAP_PASSWORD", "AdminPassword123!")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9150"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))

def wait_for_ad():
    """Block execution until the Samba AD DC LDAP service is reachable."""
    print(f"[INFO] Checking connection to AD DC at {LDAP_SERVER}:389...", flush=True)
    while True:
        try:
            # Set a 3-second connect timeout so we don't hang indefinitely
            server = Server(LDAP_SERVER, port=389, get_info=ALL, connect_timeout=3)
            conn = Connection(
                server,
                user=LDAP_USER,
                password=LDAP_PASSWORD,
                authentication=SIMPLE,
                auto_bind=True,
                auto_referrals=False
            )
            conn.unbind()
            print("[INFO] Successfully established initial connection to Active Directory!", flush=True)
            break
        except Exception as e:
            print(f"[WARN] Samba AD DC not ready yet ({e}). Retrying in 5 seconds...", flush=True)
            time.sleep(5)

def collect_ad_metrics():
    """Query LDAP directory and update Prometheus metrics."""
    try:
        server = Server(LDAP_SERVER, port=389, get_info=ALL, connect_timeout=5)
        conn = Connection(
            server,
            user=LDAP_USER,
            password=LDAP_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True,
            auto_referrals=False
        )

        # Search for domain users
        conn.search('DC=homelab,DC=lan', '(objectClass=user)', attributes=['userAccountControl', 'sAMAccountName'])
        
        active_count = 0
        disabled_count = 0

        for entry in conn.entries:
            # Skip computer accounts (names ending with $)
            if str(entry.sAMAccountName).endswith('$'):
                continue

            uac = entry.userAccountControl.value
            # ACCOUNTDISABLE flag is bit 0x0002
            if uac and (int(uac) & 2):
                disabled_count += 1
            else:
                active_count += 1

        AD_USERS_TOTAL.labels(status='active').set(active_count)
        AD_USERS_TOTAL.labels(status='disabled').set(disabled_count)

        # Search for security groups
        conn.search('DC=homelab,DC=lan', '(objectClass=group)', attributes=['sAMAccountName'])
        AD_GROUPS_TOTAL.set(len(conn.entries))

        conn.unbind()
        print(f"[INFO] AD sync success: Active={active_count}, Disabled={disabled_count}, Groups={len(conn.entries)}", flush=True)

    except Exception as e:
        print(f"[ERROR] Failed to query Active Directory metrics: {e}", flush=True)

if __name__ == '__main__':
    # 1. Wait until Samba AD is completely initialized
    wait_for_ad()

    # 2. Perform initial metric scrape before exposing HTTP port
    collect_ad_metrics()

    # 3. Start Prometheus metrics HTTP server
    start_http_server(METRICS_PORT)
    print(f"[INFO] AD Exporter listening on port {METRICS_PORT}", flush=True)

    # 4. Main polling loop
    while True:
        time.sleep(POLL_INTERVAL)
        collect_ad_metrics()