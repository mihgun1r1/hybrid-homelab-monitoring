import time
import os
from ldap3 import Server, Connection, ALL, SIMPLE
from prometheus_client import start_http_server, Gauge

AD_USERS_TOTAL = Gauge('ad_users_total', 'Total number of users in Active Directory', ['status'])
AD_GROUPS_TOTAL = Gauge('ad_groups_total', 'Total security groups in Active Directory')

LDAP_SERVER = os.getenv("LDAP_SERVER", "samba_ad")
LDAP_USER = os.getenv("LDAP_USER", "Administrator@HOMELAB.LAN")
LDAP_PASSWORD = os.getenv("LDAP_PASSWORD", "AdminPassword123!")

def collect_ad_metrics():
    try:
        server = Server(LDAP_SERVER, port=389, get_info=ALL)
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
            # Skip computer accounts (they have $ at the end of sAMAccountName)
            if str(entry.sAMAccountName).endswith('$'):
                continue

            uac = entry.userAccountControl.value
            # ACCOUNTDISABLE flag is 0x0002 (2)
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
        print(f"[WARN] Waiting for AD domain controller to initialize ({e})", flush=True)

if __name__ == '__main__':
    start_http_server(9150)
    print("AD Exporter started on port 9150", flush=True)
    while True:
        collect_ad_metrics()
        time.sleep(15)