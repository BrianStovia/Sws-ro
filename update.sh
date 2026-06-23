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

# Install speedtest-cli if missing
if ! command -v speedtest-cli &> /dev/null && ! command -v speedtest &> /dev/null; then
    echo -e "${blue}Menginstal speedtest-cli...${NC}"
    apt-get update &>/dev/null
    apt-get install -y speedtest-cli &>/dev/null
fi

# Install netdata if missing
if ! command -v netdata &> /dev/null; then
    echo -e "${blue}Menginstal Netdata Web Dashboard...${NC}"
    wget -O /tmp/netdata-kickstart.sh https://get.netdata.cloud/kickstart.sh && sh /tmp/netdata-kickstart.sh --non-interactive --disable-telemetry || true
    
    # Configure Netdata to bind only to 127.0.0.1
    if [ -f "/etc/netdata/netdata.conf" ]; then
        if grep -q "\[web\]" /etc/netdata/netdata.conf; then
            sed -i '/\[web\]/a \    bind to = 127.0.0.1' /etc/netdata/netdata.conf
        else
            echo -e "\n[web]\n    bind to = 127.0.0.1" >> /etc/netdata/netdata.conf
        fi
    fi
fi

# Ensure Nginx Netdata configuration is added
if [ -f "/etc/nginx/nginx.conf" ] && ! grep -q "location /netdata/" /etc/nginx/nginx.conf; then
    echo -e "${blue}Menambahkan konfigurasi Netdata ke Nginx...${NC}"
    sed -i '/# ----- Rest API -----/i \        # ----- Netdata Dashboard -----\n        location = /netdata {\n            return 301 /netdata/;\n        }\n        location /netdata/ {\n            auth_basic "Netdata Dashboard Login";\n            auth_basic_user_file /etc/nginx/.htpasswd;\n            proxy_pass http://127.0.0.1:19999/;\n            proxy_set_header Host $host;\n            proxy_set_header X-Forwarded-Host $host;\n            proxy_set_header X-Forwarded-Server $host;\n            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n            proxy_http_version 1.1;\n            proxy_pass_request_headers on;\n            proxy_set_header Connection "keep-alive";\n            store_gzipped on;\n        }\n' /etc/nginx/nginx.conf
fi

# Ensure Netdata Basic Auth password file exists
if [ ! -f "/etc/nginx/.htpasswd" ]; then
    if [ -f "/usr/local/etc/v2ray/domain" ]; then
        domain=$(cat /usr/local/etc/v2ray/domain)
    else
        domain="domain"
    fi
    netdata_pass="admin$(echo "$domain" | tr -d '.')"
    pass_hash=$(openssl passwd -1 "$netdata_pass")
    echo "admin:$pass_hash" > /etc/nginx/.htpasswd
fi

# Update Xray config.json
if [ -f "/usr/local/etc/v2ray/config.json" ]; then
    # Backup existing config
    cp /usr/local/etc/v2ray/config.json /usr/local/etc/v2ray/config.json.bak
    
    # Download clean config.json
    get_file "config.json" "/usr/local/etc/v2ray/config.json"
    
    # Restore Reality keypair from backup or reality.conf
    if [ -f "/usr/local/etc/v2ray/reality.conf" ]; then
        source /usr/local/etc/v2ray/reality.conf
        reality_dest="$REALITY_DEST"
        reality_sni="$REALITY_SNI"
        priv_key="$REALITY_PRIV"
        short_id="$REALITY_SID"
    else
        # Strip comments first to let jq parse the backup config
        clean_bak=$(grep -v -E '^[[:space:]]*(#|//)' /usr/local/etc/v2ray/config.json.bak)
        reality_dest=$(echo "$clean_bak" | jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.dest' 2>/dev/null)
        priv_key=$(echo "$clean_bak" | jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.privateKey' 2>/dev/null)
        short_id=$(echo "$clean_bak" | jq -r '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.shortIds[0]' 2>/dev/null)
        
        # Parse SNIs as a raw comma-separated string
        snis_json=$(echo "$clean_bak" | jq -c '.inbounds[] | select(.protocol=="vless" and .streamSettings.security=="reality") | .streamSettings.realitySettings.serverNames' 2>/dev/null)
        reality_sni=$(echo "$snis_json" | tr -d '[]"' | tr '\n' ',' | sed 's/,$//')
    fi
    
    if [ -n "$priv_key" ] && [ "$priv_key" != "null" ]; then
        # Convert comma-separated string to json array format
        reality_snis_json=$(echo "${reality_sni:-yahoo.com}" | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')
        
        # Run sed replacements on the fresh config.json
        sed -i "s|REALITY_DEST|${reality_dest:-yahoo.com:443}|g" /usr/local/etc/v2ray/config.json
        sed -i "s|REALITY_SNIS|${reality_snis_json}|g" /usr/local/etc/v2ray/config.json
        sed -i "s/REALITY_PRIVATE_KEY/${priv_key}/g" /usr/local/etc/v2ray/config.json
        sed -i "s/REALITY_SHORT_ID/${short_id}/g" /usr/local/etc/v2ray/config.json
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
systemctl restart netdata &>/dev/null

# Update Telegram bot if installed
if [ -f "/etc/systemd/system/vpn-bot.service" ]; then
    echo -e "${blue}Memperbarui & me-restart Telegram Bot Panel...${NC}"
    cp /usr/local/sbin/vpn_telegram_bot.py /usr/bin/vpn_telegram_bot.py 2>/dev/null
    chmod +x /usr/bin/vpn_telegram_bot.py
    systemctl restart vpn-bot &>/dev/null
fi

# 6. Self Update update.sh
echo -e "${blue}[6/6] Memperbarui script update...${NC}"
get_file "update.sh" "/usr/local/sbin/update"
chmod +x /usr/local/sbin/update
ln -sf /usr/local/sbin/update /usr/bin/update

echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "$green               Update Berhasil Selesai!               	$NC"
echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
exit 0
