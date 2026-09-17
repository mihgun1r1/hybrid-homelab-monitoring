#!/bin/bash
set -e

SMB_CONF="/etc/samba/smb.conf"
SAMBA_DIR="/var/lib/samba"
IMAGE_FILE="/samba_fs.ext4"

# 1. Virtual ext4 disk initialization
if [ ! -f "$IMAGE_FILE" ]; then
    echo "[INFO] Allocating virtual ext4 disk..."
    fallocate -l 1G "$IMAGE_FILE" || dd if=/dev/zero of="$IMAGE_FILE" bs=1M count=1024
    mkfs.ext4 -F "$IMAGE_FILE"
fi

# 2. Mount with POSIX ACLs enabled
mkdir -p "$SAMBA_DIR"
if ! mountpoint -q "$SAMBA_DIR"; then
    mount -o loop,user_xattr,acl "$IMAGE_FILE" "$SAMBA_DIR"
fi

# 3. Domain provisioning
if [ ! -f "$SAMBA_DIR/private/sam.ldb" ]; then
    echo "[INFO] Provisioning Samba AD Domain..."
    rm -f "$SMB_CONF"

    samba-tool domain provision \
        --server-role=dc \
        --use-rfc2307 \
        --dns-backend=SAMBA_INTERNAL \
        --realm="${REALM:-HOMELAB.LAN}" \
        --domain="${DOMAIN:-HOMELAB}" \
        --adminpass="${ADMIN_PASS:-AdminPassword123!}" \
        --option="ldap server require strong auth = no" \
        --option="nsupdate command = /bin/true"

    echo "[INFO] Provisioning finished."
fi

# Ensure simple auth is active
if ! grep -q "ldap server require strong auth = no" "$SMB_CONF" 2>/dev/null; then
    sed -i '/\[global\]/a \        ldap server require strong auth = no' "$SMB_CONF" || true
fi

echo "nameserver 127.0.0.1" > /etc/resolv.conf 2>/dev/null || true

echo "[INFO] Starting Samba AD in standard mode..."
exec samba -i