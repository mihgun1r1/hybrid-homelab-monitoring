#!/bin/bash
set -e

SAMBA_DOMAIN=${SAMBA_DOMAIN:-HOMELAB}
SAMBA_REALM=${SAMBA_REALM:-HOMELAB.LAN}
ADMIN_PASS=${ADMIN_PASS:-AdminPassword123!}

# Check if loop device / ext4 disk is needed or already initialized
if [ -f /var/lib/samba.img ] && ! mountpoint -q /var/lib/samba; then
    mount -o loop /var/lib/samba.img /var/lib/samba || true
fi

# Ensure directories exist
mkdir -p /var/lib/samba/private /etc/samba

# Check if domain was already provisioned
if [ ! -f /var/lib/samba/private/sam.ldb ]; then
    echo "[INFO] First start: Provisioning Samba AD Domain Controller..."
    
    # Remove any default/sample smb.conf so provision doesn't conflict
    rm -f /etc/samba/smb.conf

    samba-tool domain provision \
        --domain="${SAMBA_DOMAIN}" \
        --realm="${SAMBA_REALM}" \
        --adminpass="${ADMIN_PASS}" \
        --server-role=dc \
        --use-rfc2307

    # Link Kerberos config
    if [ -f /var/lib/samba/private/krb5.conf ]; then
        cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
    fi
    echo "[INFO] Provisioning completed successfully."
else
    echo "[INFO] Existing Samba AD directory database found."
fi

# Safety check: Verify server role inside smb.conf
if ! grep -q "server role = active directory domain controller" /etc/samba/smb.conf 2>/dev/null; then
    echo "[WARN] Fixing missing or incorrect 'server role' in /etc/samba/smb.conf..."
    cat << EOF > /etc/samba/smb.conf
[global]
    netbios name = SAMBA-DC
    realm = ${SAMBA_REALM}
    workgroup = ${SAMBA_DOMAIN}
    server role = active directory domain controller
    idmap_ldb:use rfc2307 = yes
    ldap server require strong auth = no
    ntlm auth = yes

[sysvol]
    path = /var/lib/samba/sysvol
    read only = No

[netlogon]
    path = /var/lib/samba/sysvol/${SAMBA_REALM,,}/scripts
    read only = No
EOF
fi

echo "[INFO] Starting Samba Active Directory Domain Controller..."
exec samba -i -M single