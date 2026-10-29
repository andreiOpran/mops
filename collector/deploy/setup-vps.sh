#!/usr/bin/env bash
# One-time VPS setup + collector install (Ubuntu 22.04/24.04 or Debian 12).
# Safe to re-run: on later runs it only updates the code and restarts the service.
#
# Usage (as root, from the repository checkout on the VPS):
#   sudo bash collector/deploy/setup-vps.sh <admin_user>
#
# <admin_user> is the non-root account you will log in with. It must already
# have an SSH key in ~/.ssh/authorized_keys (or root must have one, which is
# then copied). Password and root logins are disabled at the end.
set -euo pipefail

ADMIN_USER="${1:?usage: setup-vps.sh <admin_user>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$(dirname "$HERE")"
APP_DIR=/opt/stb-collector
SERVICE_USER=stbcollector

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -yq
apt-get install -yq python3 python3-venv ufw fail2ban python3-systemd unattended-upgrades

echo "== automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "== clock sync (timestamps in the archive depend on it)"
timedatectl set-ntp true

echo "== admin user $ADMIN_USER"
if ! id "$ADMIN_USER" &>/dev/null; then
    if getent group "$ADMIN_USER" >/dev/null; then
        echo "ABORT: '$ADMIN_USER' is already a group name (e.g. 'admin' on Ubuntu). Choose another user name."
        exit 1
    fi
    adduser --disabled-password --gecos "" "$ADMIN_USER"
    usermod -aG sudo "$ADMIN_USER"
    echo "Set a sudo password for $ADMIN_USER:"
    passwd "$ADMIN_USER"
fi
ADMIN_HOME="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"
if [[ ! -s "$ADMIN_HOME/.ssh/authorized_keys" ]]; then
    if [[ -s /root/.ssh/authorized_keys ]]; then
        install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$ADMIN_HOME/.ssh"
        install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "$ADMIN_HOME/.ssh/authorized_keys"
    else
        echo "ABORT: no SSH key for $ADMIN_USER or root. Add one first, or you will be locked out."
        exit 1
    fi
fi
if ! sudo -l -U "$ADMIN_USER" | grep -q "(ALL"; then
    echo "ABORT: $ADMIN_USER has no sudo rights. Run: usermod -aG sudo $ADMIN_USER && passwd $ADMIN_USER"
    exit 1
fi

echo "== SSH: keys only, no root login"
# 00- so it wins over cloud-init's 50-cloud-init.conf (sshd uses the first value it reads).
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
AllowUsers $ADMIN_USER
EOF
# Some provider images ship an sshd_config without the Include, so the drop-in would be ignored.
grep -qE '^\s*Include\s+/etc/ssh/sshd_config\.d/\*\.conf' /etc/ssh/sshd_config \
    || sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' /etc/ssh/sshd_config
sshd -t
sshd -T | grep -qx 'permitrootlogin no' && sshd -T | grep -qx 'passwordauthentication no' \
    || { echo "ABORT: SSH hardening not effective, check /etc/ssh/sshd_config"; exit 1; }
# Ubuntu 24.04+ starts sshd via ssh.socket, so the unit may be inactive.
systemctl try-reload-or-restart ssh 2>/dev/null || systemctl try-reload-or-restart sshd

echo "== firewall: only SSH in"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

echo "== fail2ban for SSH"
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "== collector"
id "$SERVICE_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
usermod -aG "$SERVICE_USER" "$ADMIN_USER"  # read access to the data, for rsync
install -d -m 755 "$APP_DIR"
install -m 644 "$SRC/archiver.py" "$SRC/requirements.txt" "$APP_DIR/"
[[ -x "$APP_DIR/venv/bin/python" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
install -m 644 "$HERE/stb-collector.service" /etc/systemd/system/stb-collector.service
systemctl daemon-reload
systemctl enable stb-collector
systemctl restart stb-collector

sleep 20
systemctl --no-pager status stb-collector | head -n 5
echo
echo "Done. Before closing this session, check in a NEW terminal that this works:"
echo "  ssh $ADMIN_USER@<vps-ip>"
