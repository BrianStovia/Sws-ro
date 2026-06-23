#!/usr/bin/env bash

# Clear SUDO_USER to bypass acme.sh warnings under sudo
export SUDO_USER=""

# Define Colors
green="\e[1;32m"
red="\e[1;31m"
blue="\e[1;34m"
NC="\e[0m"

# Check if run as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${red}Error: Silakan jalankan script ini sebagai root (sudo bash update)${NC}"
    exit 1
fi

# Define Hosting
hosting="https://raw.githubusercontent.com/BrianStovia/Sws-ro/main"

# Get directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to get file from local workspace
get_file() {
    local source_name="$1"
    local dest_path="$2"
    wget -q -O "${dest_path}" "${hosting}/${source_name}"
    if [ $? -ne 0 ]; then
        wget -q -O "${dest_path}" "${hosting}/file/${source_name}"
        if [ $? -ne 0 ]; then
            echo -e "${red}Error: Gagal mengunduh ${source_name} dari hosting!${NC}"
            return 1
        fi
    fi
    return 0
}

clear
echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "$green              Updating Autoscript VPS/VPN               	$NC"
echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"

# 1. Update install.sh and uninstall.sh
echo -e "${blue}[1/6] Mengunduh script installer & uninstaller baru...${NC}"
get_file "install.sh" "/usr/local/sbin/install.sh"
chmod +x /usr/local/sbin/install.sh
get_file "uninstall.sh" "/usr/local/sbin/uninstall.sh"
chmod +x /usr/local/sbin/uninstall.sh

# 2. Update Menu Scripts
echo -e "${blue}[2/6] Memperbarui menu sbin...${NC}"
mkdir -p /usr/local/sbin
cd /usr/local/sbin
wget -q -O m.zip "${hosting}/main.zip"
if [ $? -eq 0 ]; then
    unzip -o m.zip &>/dev/null
    chmod +x *
    rm -f m.zip
    # Symlink custom scripts to /usr/bin
    for file in /usr/local/sbin/*; do
        if [ -f "$file" ]; then
            ln -sf "$file" "/usr/bin/$(basename "$file")"
        fi
    done
fi
cd

# 3. Update Binaries and Helper Scripts
echo -e "${blue}[3/6] Memperbarui binari sistem...${NC}"
get_file "server" "/usr/bin/server"
chmod +x /usr/bin/server
get_file "proxy" "/usr/local/bin/proxy"
chmod +x /usr/local/bin/proxy
get_file "ssh-limit" "/usr/local/sbin/ssh-limit"
chmod +x /usr/local/sbin/ssh-limit
ln -sf /usr/local/sbin/ssh-limit /usr/bin/ssh-limit

# 4. Update Configuration Files while preserving Reality Keys
echo -e "${blue}[4/6] Memperbarui file konfigurasi...${NC}"

# Update UDP Custom configuration
get_file "udp.json" "/etc/udp/config.json"
chmod 644 /etc/udp/config.json

# Update Xray config.json
if [ -f "/usr/local/etc/v2ray/config.json" ]; then
    # Backup existing config
    cp /usr/local/etc/v2ray/config.json /usr/local/etc/v2ray/config.json.bak
    
    # Download clean config.json
    get_file "config.json" "/usr/local/etc/v2ray/config.json"
    
    # Restore Reality keypair from backup or reality.conf
    if [ -f "/usr/local/etc/v2ray/reality.conf" ]; then
        source /usr/local/etc/v2ray/reality.conf
    else
        # Try to parse from backup
        reality_dest=$(jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.dest' /usr/local/etc/v2ray/config.json.bak 2>/dev/null)
        priv_key=$(jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.privateKey' /usr/local/etc/v2ray/config.json.bak 2>/dev/null)
        short_id=$(jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.shortIds[0]' /usr/local/etc/v2ray/config.json.bak 2>/dev/null)
        reality_snis_json=$(jq -c '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.serverNames' /usr/local/etc/v2ray/config.json.bak 2>/dev/null)
    fi
    
    if [ -n "$priv_key" ] && [ "$priv_key" != "null" ]; then
        # If we parsed snis as raw array, convert to sed compatible comma snis
        if [ -n "$reality_snis_json" ] && [ "$reality_snis_json" != "null" ]; then
            # Inject directly using jq
            jq --arg dest "$reality_dest" \
               --arg priv "$priv_key" \
               --arg sid "$short_id" \
               --argjson snis "$reality_snis_json" \
               '.inbounds[] |= if (.protocol=="vless" and .streamSettings.security=="reality") then 
                  .streamSettings.realitySettings.dest = $dest |
                  .streamSettings.realitySettings.privateKey = $priv |
                  .streamSettings.realitySettings.shortIds = [$sid] |
                  .streamSettings.realitySettings.serverNames = $snis
                else . end' /usr/local/etc/v2ray/config.json > /usr/local/etc/v2ray/config.json.tmp
            mv /usr/local/etc/v2ray/config.json.tmp /usr/local/etc/v2ray/config.json
        else
            # Fallback to sed
            sed -i "s|REALITY_DEST|${reality_dest:-yahoo.com:443}|g" /usr/local/etc/v2ray/config.json
            sed -i "s|REALITY_SNIS|\"yahoo.com\",\"www.yahoo.com\"|g" /usr/local/etc/v2ray/config.json
            sed -i "s/REALITY_PRIVATE_KEY/${priv_key}/g" /usr/local/etc/v2ray/config.json
            sed -i "s/REALITY_SHORT_ID/${short_id}/g" /usr/local/etc/v2ray/config.json
        fi
    fi
fi

# 5. Reload services
echo -e "${blue}[5/6] Memulai ulang layanan...${NC}"
systemctl daemon-reload
systemctl restart udp-custom &>/dev/null
systemctl restart badvpn-7100 &>/dev/null
systemctl restart badvpn-7200 &>/dev/null
systemctl restart badvpn-7300 &>/dev/null
systemctl restart badvpn &>/dev/null
systemctl restart v2ray &>/dev/null
systemctl restart nginx &>/dev/null
systemctl restart sslh &>/dev/null
systemctl restart proxy &>/dev/null
systemctl restart server &>/dev/null
systemctl restart cron &>/dev/null

# 6. Self Update update.sh
echo -e "${blue}[6/6] Memperbarui script update...${NC}"
get_file "update.sh" "/usr/local/sbin/update"
chmod +x /usr/local/sbin/update
ln -sf /usr/local/sbin/update /usr/bin/update

echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "$green               Update Berhasil Selesai!               	$NC"
echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
exit 0
