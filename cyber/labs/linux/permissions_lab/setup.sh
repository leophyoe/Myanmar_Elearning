#!/bin/bash
set -e

# Start SSH daemon for external student VPN connections
if [ -x /usr/sbin/sshd ]; then
    /usr/sbin/sshd
fi

# Write the dynamic flag from environment into protected target location
FLAG="${FTCR_FLAG:-FTCR{linux_permissions_default_flag_test}}"

# Place flag in root-only accessible log file
echo "[LOG RECORD 2026-09-17 00:00:01] System booted." > /var/log/secret_service.log
echo "[SECRET_BACKUP] FLAG: ${FLAG}" >> /var/log/secret_service.log
echo "[LOG RECORD 2026-09-17 00:00:02] Service online." >> /var/log/secret_service.log

chmod 0600 /var/log/secret_service.log
chown root:root /var/log/secret_service.log

# Switch to student user
exec su - student

