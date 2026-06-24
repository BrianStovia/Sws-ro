#!/usr/bin/env bash
{
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
    local cache_buster="?v=$(date +%s)"
    wget -q -O "${dest_path}" "${hosting}/${source_name}${cache_buster}"
    if [ $? -ne 0 ]; then
        wget -q -O "${dest_path}" "${hosting}/file/${source_name}${cache_buster}"
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

# 1. Auto Backup V2Ray Configuration
if [ -f "/usr/local/etc/v2ray/config.json" ]; then
    echo -e "${blue}[1/7] Mencadangkan akun V2Ray otomatis...${NC}"
    cp /usr/local/etc/v2ray/config.json /root/v2ray_backup_before_update.json
    echo -e "${green}Backup disimpan di /root/v2ray_backup_before_update.json${NC}"
else
    echo -e "${blue}[1/7] Tidak ada konfigurasi V2Ray untuk dicadangkan.${NC}"
fi

# 2. Update install.sh and uninstall.sh
echo -e "${blue}[2/7] Mengunduh script installer & uninstaller baru...${NC}"
get_file "install.sh" "/usr/local/sbin/install.sh"
chmod +x /usr/local/sbin/install.sh
get_file "uninstall.sh" "/usr/local/sbin/uninstall.sh"
chmod +x /usr/local/sbin/uninstall.sh

# 3. Update Menu Scripts
echo -e "${blue}[3/7] Memperbarui menu sbin...${NC}"
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

# 4. Update Binaries and Helper Scripts
echo -e "${blue}[4/7] Memperbarui binari sistem...${NC}"
get_file "server" "/usr/bin/server"
chmod +x /usr/bin/server
get_file "proxy" "/usr/local/bin/proxy"
chmod +x /usr/local/bin/proxy
get_file "ssh-limit" "/usr/local/sbin/ssh-limit"
chmod +x /usr/local/sbin/ssh-limit
ln -sf /usr/local/sbin/ssh-limit /usr/bin/ssh-limit

# 5. Update Configuration Files while preserving Reality Keys
echo -e "${blue}[5/7] Memperbarui file konfigurasi...${NC}"

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

# Clean up any leftover broken store_gzipped directives from previous runs
if [ -f "/etc/nginx/nginx.conf" ]; then
    sed -i '/store_gzipped on;/d' /etc/nginx/nginx.conf
fi

# Ensure Nginx Netdata configuration is added
if [ -f "/etc/nginx/nginx.conf" ] && ! grep -q "location /netdata/" /etc/nginx/nginx.conf; then
    echo -e "${blue}Menambahkan konfigurasi Netdata ke Nginx...${NC}"
    sed -i '/# ----- Rest API -----/i \        # ----- Netdata Dashboard -----\n        location = /netdata {\n            return 301 /netdata/;\n        }\n        location /netdata/ {\n            auth_basic "Netdata Dashboard Login";\n            auth_basic_user_file /etc/nginx/.htpasswd;\n            proxy_pass http://127.0.0.1:19999/;\n            proxy_set_header Host $host;\n            proxy_set_header X-Forwarded-Host $host;\n            proxy_set_header X-Forwarded-Server $host;\n            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n            proxy_http_version 1.1;\n            proxy_pass_request_headers on;\n            proxy_set_header Connection "keep-alive";\n        }\n' /etc/nginx/nginx.conf
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
    
    # Check if WARP SOCKS5 proxy was enabled in backup config
    warp_enabled=0
    if grep -q -E '"port"\s*:\s*40000' /usr/local/etc/v2ray/config.json.bak 2>/dev/null; then
        warp_enabled=1
    fi
    
    # Download clean config.json
    get_file "config.json" "/usr/local/etc/v2ray/config.json"
    
    # Run merge script to preserve existing accounts
    if [ -f "/usr/local/sbin/merge_config.py" ]; then
        python3 /usr/local/sbin/merge_config.py
    fi
    
    # Restore WARP SOCKS5 proxy if it was enabled
    if [ "$warp_enabled" -eq 1 ]; then
        echo "Restoring Cloudflare WARP proxy outbound..."
        python3 /usr/local/sbin/toggle_warp.py enable
    fi
    
    # Verify configuration syntax
    if [ -f "/usr/local/bin/xray" ]; then
        /usr/local/bin/xray -test -config /usr/local/etc/v2ray/config.json &>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${red}Error: Konfigurasi baru V2Ray tidak valid! Mengembalikan ke konfigurasi sebelumnya...${NC}"
            cp /usr/local/etc/v2ray/config.json.bak /usr/local/etc/v2ray/config.json
        fi
    fi
fi

# 6. Reload services
echo -e "${blue}[6/7] Memulai ulang layanan...${NC}"
systemctl daemon-reload
systemctl restart udp-custom &>/dev/null
systemctl restart badvpn-7100 &>/dev/null
systemctl restart badvpn-7200 &>/dev/null
systemctl restart badvpn-7300 &>/dev/null
systemctl restart badvpn &>/dev/null
systemctl restart v2ray &>/dev/null
# Check if V2Ray running successfully, if not auto rollback to pre-update backup
sleep 1.5
if ! systemctl is-active --quiet v2ray; then
    echo -e "${red}Error: Layanan V2Ray gagal berjalan dengan konfigurasi baru!${NC}"
    if [ -f "/root/v2ray_backup_before_update.json" ]; then
        echo -e "${blue}Mengembalikan konfigurasi cadangan secara otomatis...${NC}"
        cp /root/v2ray_backup_before_update.json /usr/local/etc/v2ray/config.json
        systemctl restart v2ray &>/dev/null
        if systemctl is-active --quiet v2ray; then
            echo -e "${green}Berhasil memulihkan layanan V2Ray menggunakan cadangan sebelum update!${NC}"
        else
            echo -e "${red}Fatal: V2Ray tetap gagal berjalan bahkan setelah memulihkan cadangan!${NC}"
        fi
    fi
fi
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

# 7. Self Update update.sh
echo -e "${blue}[7/7] Memperbarui script update...${NC}"
get_file "update.sh" "/usr/local/sbin/update.tmp"
chmod +x /usr/local/sbin/update.tmp
mv -f /usr/local/sbin/update.tmp /usr/local/sbin/update
ln -sf /usr/local/sbin/update /usr/bin/update

echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "$green               Update Berhasil Selesai!               	$NC"
echo -e "\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
exit 0
}
