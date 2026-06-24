import sys
import os
import re
import json
import urllib.request
import urllib.parse
import subprocess
import time

# Set encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Paths
BOT_KEY_PATH = "/usr/local/etc/v2ray/bot.key"
CLIENT_ID_PATH = "/usr/local/etc/v2ray/client.id"
SELLERS_PATH = "/etc/telegram_sellers.json"

# Load bot details
def load_config():
    token = ""
    owner_id = ""
    if os.path.exists(BOT_KEY_PATH):
        with open(BOT_KEY_PATH, "r") as f:
            token = f.read().strip()
    if os.path.exists(CLIENT_ID_PATH):
        with open(CLIENT_ID_PATH, "r") as f:
            owner_id = f.read().strip()
    return token, owner_id

token, owner_id = load_config()

# Load sellers
def load_sellers():
    if os.path.exists(SELLERS_PATH):
        try:
            with open(SELLERS_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_sellers(sellers):
    with open(SELLERS_PATH, "w") as f:
        json.dump(sellers, f)

sellers = load_sellers()

def is_authorized(chat_id):
    chat_str = str(chat_id)
    return chat_str == str(owner_id) or chat_str in sellers

def clean_ansi(text):
    ansi_escape = re.compile(r'(?:\x1B|\033)(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    data = urllib.parse.urlencode(params).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("Failed to send message:", e)

def answer_callback_query(callback_query_id):
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    data = urllib.parse.urlencode({
        "callback_query_id": callback_query_id
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("Failed to answer callback query:", e)

def set_bot_commands():
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    commands = [
        {"command": "menu", "description": "Tampilkan Menu Utama"},
        {"command": "ssh", "description": "Menu SSH & OVPN"},
        {"command": "vmess", "description": "Menu Vmess"},
        {"command": "vless", "description": "Menu Vless"},
        {"command": "trojan", "description": "Menu Trojan"},
        {"command": "wg", "description": "Menu Wireguard"},
        {"command": "system", "description": "Menu System & Status"},
        {"command": "help", "description": "Bantuan & Format Perintah"}
    ]
    data = json.dumps({"commands": commands}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        print("Bot commands menu registered successfully!")
    except Exception as e:
        print("Failed to set bot commands:", e)

# --- System Information & Resource Helpers ---
cached_ip = None
cached_isp = None
cached_os = None
cached_v2ray_version = None
cached_domain = None
cached_tram = None

def get_static_sysinfo():
    global cached_ip, cached_isp, cached_os, cached_v2ray_version, cached_domain, cached_tram
    # Read Domain
    if not cached_domain:
        if os.path.exists("/usr/local/etc/v2ray/domain"):
            try:
                with open("/usr/local/etc/v2ray/domain", "r") as f:
                    cached_domain = f.read().strip()
            except Exception:
                cached_domain = "Unknown"
        else:
            cached_domain = "Unknown"
    # OS
    if not cached_os:
        cached_os = run_bash_cmd("echo \"$(lsb_release -ds) [ $(uname -m) ]\"")
        if not cached_os or cached_os.startswith("Error"):
            cached_os = "Unknown OS"
    # RAM Total
    if not cached_tram:
        cached_tram = run_bash_cmd("free -m | awk 'NR==2 {print $2}'")
        if not cached_tram or cached_tram.startswith("Error"):
            cached_tram = "0"
    # V2Ray Version
    if not cached_v2ray_version:
        cached_v2ray_version = run_bash_cmd("v2ray version | grep 'V2Ray' | awk '{print $2}'")
        if not cached_v2ray_version or cached_v2ray_version.startswith("Error"):
            cached_v2ray_version = "Unknown"
    # Public IP
    if not cached_ip:
        cached_ip = run_bash_cmd("curl -s http://checkip.amazonaws.com")
        if not cached_ip or cached_ip.startswith("Error"):
            cached_ip = "Unknown"
    # ISP Info
    if not cached_isp or cached_isp == "Unknown ISP" or cached_isp.startswith("Error"):
        if cached_ip and cached_ip != "Unknown":
            cached_isp = run_bash_cmd(f"timeout 5 curl -s \"http://ip-api.com/json/{cached_ip}\" | jq -r '.isp // \"Unknown ISP\"'")
        else:
            cached_isp = "Unknown ISP"
    return cached_os, cached_ip, cached_tram, cached_isp, cached_domain, cached_v2ray_version

def draw_emoji_bar(percent):
    width = 10
    filled = int(percent * width / 100)
    if filled > 10: filled = 10
    if filled < 0: filled = 0
    empty = width - filled
    if percent <= 50:
        char = "🟩"
    elif percent <= 80:
        char = "🟨"
    else:
        char = "🟥"
    bar = char * filled + "⬜" * empty
    return f"{bar} {percent}%"

def check_service_status(s):
    res = subprocess.run(f"systemctl is-active {s}", shell=True, capture_output=True, text=True)
    return "✅ ON" if res.stdout.strip() == "active" else "❌ OFF"

# --- Dynamic Keyboard Menus ---
def send_menu(chat_id):
    # Fetch static sys info
    os_name, ip_addr, ram_tot, isp, dom, v_version = get_static_sysinfo()
    
    # Calculate Resource usage
    cpu_val = run_bash_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}' | cut -d. -f1")
    cpu_percent = int(cpu_val) if cpu_val.isdigit() else 0
    
    ram_u = run_bash_cmd("free -m | awk 'NR==2 {print $3}'")
    ram_t = int(ram_tot) if ram_tot.isdigit() else 0
    ram_used_val = int(ram_u) if ram_u.isdigit() else 0
    ram_percent = (ram_used_val * 100 // ram_t) if ram_t > 0 else 0
    
    disk_val = run_bash_cmd("df -h / | awk 'NR==2 {print $5}' | tr -d '%'")
    disk_percent = int(disk_val) if disk_val.isdigit() else 0

    # Total Accounts
    shc = run_bash_cmd("awk -F: '$3 >= 1000 && $1 != \"nobody\" {print $1}' /etc/passwd | wc -l")
    trojan = run_bash_cmd("cat /usr/local/etc/v2ray/config.json | grep '#!' | sort | uniq | wc -l")
    vless = run_bash_cmd("cat /usr/local/etc/v2ray/config.json | grep '#&' | sort | uniq | wc -l")
    vmess = run_bash_cmd("cat /usr/local/etc/v2ray/config.json | grep '###' | sort | uniq | wc -l")

    # Services
    sv2ray = check_service_status("v2ray")
    snginx = check_service_status("nginx")
    sslh = check_service_status("sslh")

    menu_text = (
        "🤖 <b>VPN SELLER BOT MAIN MENU</b> 🤖\n"
        "───────────────────────\n"
        f"<b>OS:</b> {os_name}\n"
        f"<b>IP:</b> {ip_addr}\n"
        f"<b>Ram:</b> {ram_tot} MB\n"
        f"<b>ISP:</b> {isp}\n"
        f"<b>Domain:</b> {dom}\n"
        f"<b>V2ray Version:</b> {v_version}\n"
        "───────────────────────\n"
        "<b>System Resource Usage:</b>\n"
        f"• CPU Load : {draw_emoji_bar(cpu_percent)}\n"
        f"• RAM Usage: {draw_emoji_bar(ram_percent)}\n"
        f"• Disk Used: {draw_emoji_bar(disk_percent)}\n"
        "───────────────────────\n"
        "<b>Total Account:</b>\n"
        f"• SSH        : {shc}\n"
        f"• Vmess      : {vmess}\n"
        f"• Vless      : {vless}\n"
        f"• Trojan     : {trojan}\n"
        "───────────────────────\n"
        "<b>Active Ports:</b>\n"
        "• SSH WS TLS & V2Ray TLS : 443\n"
        "• SSH WS HTTP           : 80, 2080, 2082\n"
        "• OpenSSH               : 22, 109, 3303\n"
        "• Dropbear              : 69, 143\n"
        "• UDP Custom            : 1-65535 & 36712\n"
        "• SlowDNS               : 53\n"
        "───────────────────────\n"
        f"V2ray: {sv2ray}   Nginx: {snginx}   SSLH: {sslh}\n"
        "───────────────────────\n"
        "Silakan pilih opsi menu di bawah ini:"
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔑 SSH Menu", "callback_data": "/menu_ssh"},
                {"text": "🛡️ Vmess Menu", "callback_data": "/menu_vmess"}
            ],
            [
                {"text": "⚡ Vless Menu", "callback_data": "/menu_vless"},
                {"text": "🔒 Trojan Menu", "callback_data": "/menu_trojan"}
            ],
            [
                {"text": "📡 Wireguard Menu", "callback_data": "/menu_wg"},
                {"text": "⚙️ System Menu", "callback_data": "/menu_system"}
            ],
            [
                {"text": "🔄 Update Script", "callback_data": "/update_script"}
            ]
        ]
    }
    send_message(chat_id, menu_text, reply_markup=json.dumps(keyboard))

def send_menu_ssh(chat_id):
    text = "🔑 <b>SSH & OVPN PANEL</b> 🔑\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "➕ Create SSH", "callback_data": "/addssh"},
                {"text": "❌ Delete SSH", "callback_data": "/delssh"}
            ],
            [
                {"text": "🔄 Renew SSH", "callback_data": "/renewssh"},
                {"text": "👥 List SSH", "callback_data": "/listssh"}
            ],
            [
                {"text": "🔍 Check Login", "callback_data": "/cekssh"},
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def send_menu_vmess(chat_id):
    text = "🛡️ <b>XRAY VMESS PANEL</b> 🛡️\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "➕ Create Vmess", "callback_data": "/addvmess"},
                {"text": "❌ Delete Vmess", "callback_data": "/delvmess"}
            ],
            [
                {"text": "🔄 Renew Vmess", "callback_data": "/renewvmess"},
                {"text": "👥 Check User", "callback_data": "/cekvmess"}
            ],
            [
                {"text": "📊 Traffic Vmess", "callback_data": "/trafikvmess"},
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def send_menu_vless(chat_id):
    text = "⚡ <b>XRAY VLESS PANEL</b> ⚡\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "➕ Create Vless", "callback_data": "/addvless"},
                {"text": "❌ Delete Vless", "callback_data": "/delvless"}
            ],
            [
                {"text": "🔄 Renew Vless", "callback_data": "/renewvless"},
                {"text": "👥 Check User", "callback_data": "/cekvless"}
            ],
            [
                {"text": "📊 Traffic Vless", "callback_data": "/trafikvless"},
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def send_menu_trojan(chat_id):
    text = "🔒 <b>XRAY TROJAN PANEL</b> 🔒\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "➕ Create Trojan", "callback_data": "/addtrojan"},
                {"text": "❌ Delete Trojan", "callback_data": "/deltrojan"}
            ],
            [
                {"text": "🔄 Renew Trojan", "callback_data": "/renewtrojan"},
                {"text": "👥 Check User", "callback_data": "/cektrojan"}
            ],
            [
                {"text": "📊 Traffic Trojan", "callback_data": "/trafiktrojan"},
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def send_menu_wg(chat_id):
    text = "📡 <b>WIREGUARD PANEL</b> 📡\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "➕ Create WG", "callback_data": "/addwg"},
                {"text": "❌ Delete WG", "callback_data": "/delwg"}
            ],
            [
                {"text": "🔄 Renew WG", "callback_data": "/renewwg"},
                {"text": "👥 Check User", "callback_data": "/cekwg"}
            ],
            [
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def send_menu_system(chat_id):
    text = "⚙️ <b>SYSTEM CONFIGURATION PANEL</b> ⚙️\n───────────────────────"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 VPS Status", "callback_data": "/status"},
                {"text": "🔄 Restart Services", "callback_data": "/restart"}
            ],
            [
                {"text": "🚀 Speedtest VPS", "callback_data": "/speedtest"},
                {"text": "🌐 Change Domain", "callback_data": "/changedomain"}
            ],
            [
                {"text": "💾 Backup DB", "callback_data": "/backup"},
                {"text": "📂 Restore DB", "callback_data": "/restore"}
            ],
            [
                {"text": "⬅️ Back", "callback_data": "/menu"}
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=json.dumps(keyboard))

def run_bash_cmd(cmd_str):
    try:
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=30)
        return clean_ansi(res.stdout + "\n" + res.stderr).strip()
    except subprocess.TimeoutExpired:
        return "Error: Command timed out!"
    except Exception as e:
        return f"Error: {e}"

user_states = {}

def handle_state_input(chat_id, text):
    state = user_states.get(chat_id)
    if not state:
        return
    
    action = state["action"]
    step = state["step"]
    
    if action == "addssh":
        if step == "username":
            username = text.strip()
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                send_message(chat_id, "❌ Username hanya boleh huruf, angka, dan underscore (_).\n\nMasukkan kembali Username:")
                return
            state["data"]["username"] = username
            state["step"] = "password"
            send_message(chat_id, "🔑 Masukkan Password:")
        elif step == "password":
            password = text.strip()
            if not password:
                send_message(chat_id, "❌ Password tidak boleh kosong.\n\nMasukkan kembali Password:")
                return
            state["data"]["password"] = password
            state["step"] = "days"
            send_message(chat_id, "🔑 Masukkan Masa Aktif (Hari) (contoh: 30):")
        elif step == "days":
            days = text.strip()
            if not days.isdigit() or int(days) <= 0:
                send_message(chat_id, "❌ Masa aktif harus berupa angka positif.\n\nMasukkan kembali Masa Aktif (Hari):")
                return
            username = state["data"]["username"]
            password = state["data"]["password"]
            if chat_id in user_states:
                del user_states[chat_id]
            send_message(chat_id, f"⏳ Sedang membuat akun SSH untuk <code>{username}</code>...")
            cmd_str = f'printf "{username}\\n{password}\\n2\\n{days}\\n" | bash /usr/local/sbin/add-ssh'
            out = run_bash_cmd(cmd_str)
            send_message(chat_id, f"<pre>{out}</pre>")
            
    elif action in ["addvmess", "addvless", "addtrojan"]:
        if step == "username":
            username = text.strip()
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                send_message(chat_id, "❌ Username hanya boleh huruf, angka, dan underscore (_).\n\nMasukkan kembali Username:")
                return
            state["data"]["username"] = username
            state["data"]["secret"] = ""  # Otomatis UUID / password random
            state["step"] = "days"
            send_message(chat_id, "📆 Masukkan Masa Aktif (Hari) (contoh: 30):")
        elif step == "days":
            days = text.strip()
            if not days.isdigit() or int(days) <= 0:
                send_message(chat_id, "❌ Masa aktif harus berupa angka positif.\n\nMasukkan kembali Masa Aktif (Hari):")
                return
            username = state["data"]["username"]
            secret = state["data"].get("secret", "")
            if chat_id in user_states:
                del user_states[chat_id]
            proto_name = "Vmess" if action == "addvmess" else ("Vless" if action == "addvless" else "Trojan")
            script_name = "add-vmess" if action == "addvmess" else ("add-vless" if action == "addvless" else "add-tr")
            send_message(chat_id, f"⏳ Sedang membuat akun {proto_name} untuk <code>{username}</code>...")
            cmd_str = f'printf "{username}\\n{days}\\n{secret}\\n" | bash /usr/local/sbin/{script_name}'
            out = run_bash_cmd(cmd_str)
            send_message(chat_id, f"<pre>{out}</pre>")
            

    elif action == "addwg":
        if step == "username":
            username = text.strip()
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                send_message(chat_id, "❌ Username hanya boleh huruf, angka, dan underscore (_).\n\nMasukkan kembali Username:")
                return
            state["data"]["username"] = username
            state["step"] = "days"
            send_message(chat_id, "📆 Masukkan Masa Aktif (Hari) (contoh: 30):")
        elif step == "days":
            days = text.strip()
            if not days.isdigit() or int(days) <= 0:
                send_message(chat_id, "❌ Masa aktif harus berupa angka positif.\n\nMasukkan kembali Masa Aktif (Hari):")
                return
            username = state["data"]["username"]
            if chat_id in user_states:
                del user_states[chat_id]
            send_message(chat_id, f"⏳ Sedang membuat akun WireGuard untuk <code>{username}</code>...")
            cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/add-wg'
            out = run_bash_cmd(cmd_str)
            send_message(chat_id, f"<pre>{out}</pre>")

    elif action == "changedomain":
        domain = text.strip()
        if not domain:
            send_message(chat_id, "❌ Domain tidak boleh kosong.\n\nMasukkan kembali Domain:")
            return
        if chat_id in user_states:
            del user_states[chat_id]
        send_message(chat_id, f"⏳ Sedang memproses ganti domain ke <code>{domain}</code>... (Proses SSL certificate mungkin membutuhkan waktu)")
        cmd_str = f'printf "{domain}\\n" | bash /usr/local/sbin/change-domain'
        out = run_bash_cmd(cmd_str)
        send_message(chat_id, f"<pre>{out}</pre>")

    elif action.startswith("del_"):
        proto = action[4:]
        username = text.strip()
        if not username:
            send_message(chat_id, "❌ Username tidak boleh kosong.\n\nMasukkan kembali Username:")
            return
        if chat_id in user_states:
            del user_states[chat_id]
        send_message(chat_id, f"⏳ Sedang menghapus akun {proto.upper()} untuk <code>{username}</code>...")
        if proto == "ssh":
            cmd_str = f'printf "{username}\\n" | bash /usr/local/sbin/del-ssh'
        elif proto == "vmess":
            cmd_str = f'printf "{username}\\n" | bash /usr/local/sbin/del-vmess'
        elif proto == "vless":
            cmd_str = f'printf "{username}\\n" | bash /usr/local/sbin/del-vless'
        elif proto == "trojan":
            cmd_str = f'printf "{username}\\n" | bash /usr/local/sbin/del-tr'
        elif proto == "wg":
            cmd_str = f'printf "{username}\\n" | bash /usr/local/sbin/del-wg'
        out = run_bash_cmd(cmd_str)
        send_message(chat_id, f"<pre>{out}</pre>")

    elif action.startswith("renew_"):
        proto = action[6:]
        if step == "username":
            username = text.strip()
            state["data"]["username"] = username
            state["step"] = "days"
            send_message(chat_id, "📆 Masukkan Jumlah Hari Perpanjangan:")
        elif step == "days":
            days = text.strip()
            if not days.isdigit() or int(days) <= 0:
                send_message(chat_id, "❌ Jumlah hari harus berupa angka positif.\n\nMasukkan kembali Hari:")
                return
            username = state["data"]["username"]
            if chat_id in user_states:
                del user_states[chat_id]
            send_message(chat_id, f"⏳ Sedang memperpanjang akun {proto.upper()} untuk <code>{username}</code>...")
            if proto == "ssh":
                cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/renew-ssh'
            elif proto == "vmess":
                cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/renew-vmess'
            elif proto == "vless":
                cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/renew-vless'
            elif proto == "trojan":
                cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/renew-tr'
            elif proto == "wg":
                cmd_str = f'printf "{username}\\n{days}\\n" | bash /usr/local/sbin/renew-wg'
            out = run_bash_cmd(cmd_str)
            send_message(chat_id, f"<pre>{out}</pre>")

def handle_command(chat_id, text):
    chat_str = str(chat_id)
    parts = text.split()
    if not parts:
        return
    
    cmd = parts[0].lower()
    
    if cmd == "/start" or cmd == "/menu":
        if not is_authorized(chat_id):
            send_message(chat_id, "❌ <b>Akses Ditolak:</b> ID Anda belum terdaftar sebagai Seller.")
            return
        send_menu(chat_id)
        return

    # Submenus routing
    if cmd == "/ssh" or cmd == "/menu_ssh":
        send_menu_ssh(chat_id)
        return
    elif cmd == "/vmess" or cmd == "/menu_vmess":
        send_menu_vmess(chat_id)
        return
    elif cmd == "/vless" or cmd == "/menu_vless":
        send_menu_vless(chat_id)
        return
    elif cmd == "/trojan" or cmd == "/menu_trojan":
        send_menu_trojan(chat_id)
        return
    elif cmd == "/wg" or cmd == "/menu_wg":
        send_menu_wg(chat_id)
        return
    elif cmd == "/system" or cmd == "/menu_system":
        send_menu_system(chat_id)
        return
        
    if cmd == "/help":
        if not is_authorized(chat_id):
            send_message(chat_id, "❌ <b>Akses Ditolak:</b> ID Anda belum terdaftar sebagai Seller.")
            return
        help_text = (
            "🤖 <b>VPN Seller Telegram Bot Help</b> 🤖\n"
            "───────────────────────\n"
            "Gunakan tombol menu atau ketik perintah ini:\n"
            "• <code>/ssh</code> - Menu SSH & OVPN\n"
            "• <code>/vmess</code> - Menu XRAY Vmess\n"
            "• <code>/vless</code> - Menu XRAY Vless\n"
            "• <code>/trojan</code> - Menu XRAY Trojan\n"
            "• <code>/wg</code> - Menu Wireguard\n"
            "• <code>/system</code> - Menu Management System\n"
            "───────────────────────\n"
        )
        if chat_str == str(owner_id):
            help_text += (
                "<b>Perintah Owner Only:</b>\n"
                "• <code>/addseller &lt;chat_id&gt;</code> - Tambah seller baru\n"
                "• <code>/delseller &lt;chat_id&gt;</code> - Hapus seller\n"
                "• <code>/listsellers</code> - Daftar semua seller\n"
                "───────────────────────\n"
            )
        send_message(chat_id, help_text)
        return
        
    if not is_authorized(chat_id):
        send_message(chat_id, "❌ <b>Akses Ditolak:</b> ID Anda belum terdaftar sebagai Seller.")
        return
        
    if cmd == "/addssh":
        user_states[chat_id] = {"action": "addssh", "step": "username", "data": {}}
        send_message(chat_id, "➕ <b>Pembuatan Akun SSH</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")
        
    elif cmd == "/addvmess":
        user_states[chat_id] = {"action": "addvmess", "step": "username", "data": {}}
        send_message(chat_id, "➕ <b>Pembuatan Akun Vmess</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")
        
    elif cmd == "/addvless":
        user_states[chat_id] = {"action": "addvless", "step": "username", "data": {}}
        send_message(chat_id, "➕ <b>Pembuatan Akun Vless</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")
        
    elif cmd == "/addtrojan":
        user_states[chat_id] = {"action": "addtrojan", "step": "username", "data": {}}
        send_message(chat_id, "➕ <b>Pembuatan Akun Trojan</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")
        
    elif cmd == "/addwg":
        user_states[chat_id] = {"action": "addwg", "step": "username", "data": {}}
        send_message(chat_id, "➕ <b>Pembuatan Akun WireGuard</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")

    elif cmd == "/changedomain":
        user_states[chat_id] = {"action": "changedomain", "step": "domain", "data": {}}
        send_message(chat_id, "🌐 <b>Ganti Domain VPS</b>\n\nMasukkan Domain Baru:\n(Ketik /cancel untuk membatalkan)")

    # Deletions
    elif cmd in ["/delssh", "/delvmess", "/delvless", "/deltrojan", "/delwg"]:
        proto = cmd[4:]
        user_states[chat_id] = {"action": f"del_{proto}", "step": "username", "data": {}}
        send_message(chat_id, f"❌ <b>Hapus Akun {proto.upper()}</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")

    # Renewals
    elif cmd in ["/renewssh", "/renewvmess", "/renewvless", "/renewtrojan", "/renewwg"]:
        proto = cmd[6:]
        user_states[chat_id] = {"action": f"renew_{proto}", "step": "username", "data": {}}
        send_message(chat_id, f"🔄 <b>Perpanjang Akun {proto.upper()}</b>\n\nMasukkan Username:\n(Ketik /cancel untuk membatalkan)")
        
    elif cmd == "/status":
        send_message(chat_id, "⏳ Mengambil status VPS...")
        def get_service_status(s):
            res = subprocess.run(f"systemctl is-active {s}", shell=True, capture_output=True, text=True)
            return "✅ ON" if res.stdout.strip() == "active" else "❌ OFF"
            
        v2ray_st = get_service_status("v2ray")
        nginx_st = get_service_status("nginx")
        sslh_st = get_service_status("sslh")
        udp_st = get_service_status("udp-custom")
        proxy_st = get_service_status("proxy")
        
        mem_out = run_bash_cmd("free -h | awk 'NR==2 {print $3 \" / \" $2}'")
        cpu_out = run_bash_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'") + "%"
        disk_out = run_bash_cmd("df -h / | awk 'NR==2 {print $3 \" / \" $2 \" ( \" $5 \" )\"}'")
        uptime_out = run_bash_cmd("uptime -p")
        
        status_text = (
            "⚙️ <b>VPS STATUS INFO</b> ⚙️\n"
            "───────────────────────\n"
            f"<b>CPU Usage  :</b> <code>{cpu_out}</code>\n"
            f"<b>Memory     :</b> <code>{mem_out}</code>\n"
            f"<b>Disk Space :</b> <code>{disk_out}</code>\n"
            f"<b>Uptime     :</b> <code>{uptime_out}</code>\n"
            "───────────────────────\n"
            "<b>SERVICES STATUS:</b>\n"
            f"• <b>V2Ray Core  :</b> {v2ray_st}\n"
            f"• <b>Nginx Server :</b> {nginx_st}\n"
            f"• <b>SSLH Proxy   :</b> {sslh_st}\n"
            f"• <b>UDP Custom   :</b> {udp_st}\n"
            f"• <b>Proxy SSHWS  :</b> {proxy_st}\n"
            "───────────────────────\n"
        )
        send_message(chat_id, status_text)
        
    elif cmd == "/listssh":
        send_message(chat_id, "⏳ Mengambil daftar akun SSH...")
        out = run_bash_cmd("awk -F: '$3 >= 1000 && $1 != \"nobody\" {print $1}' /etc/passwd")
        send_message(chat_id, f"👥 <b>Daftar Akun SSH Aktif:</b>\n<pre>{out if out else 'Tidak ada akun'}</pre>")

    # Checks & Logins
    elif cmd == "/cekssh":
        send_message(chat_id, "⏳ Memeriksa login SSH...")
        out = run_bash_cmd("bash /usr/local/sbin/cek-ssh")
        send_message(chat_id, f"<pre>{out if out else 'Tidak ada log login'}</pre>")
    elif cmd == "/cekvmess":
        send_message(chat_id, "⏳ Memeriksa login Vmess...")
        out = run_bash_cmd("bash /usr/local/sbin/cek-vmess")
        send_message(chat_id, f"<pre>{out if out else 'Tidak ada log login'}</pre>")
    elif cmd == "/cekvless":
        send_message(chat_id, "⏳ Memeriksa login Vless...")
        out = run_bash_cmd("bash /usr/local/sbin/cek-vless")
        send_message(chat_id, f"<pre>{out if out else 'Tidak ada log login'}</pre>")
    elif cmd == "/cektrojan":
        send_message(chat_id, "⏳ Memeriksa login Trojan...")
        out = run_bash_cmd("bash /usr/local/sbin/cek-tr")
        send_message(chat_id, f"<pre>{out if out else 'Tidak ada log login'}</pre>")
    elif cmd == "/cekwg":
        send_message(chat_id, "⏳ Memeriksa login Wireguard...")
        out = run_bash_cmd("bash /usr/local/sbin/cek-wg")
        send_message(chat_id, f"<pre>{out if out else 'Tidak ada log login'}</pre>")
        
    elif cmd == "/trafikvmess":
        send_message(chat_id, "⏳ Mengambil trafik Vmess...")
        out = run_bash_cmd("bash /usr/local/sbin/trafik-vmess")
        send_message(chat_id, f"<pre>{out}</pre>")
    elif cmd == "/trafikvless":
        send_message(chat_id, "⏳ Mengambil trafik Vless...")
        out = run_bash_cmd("bash /usr/local/sbin/trafik-vless")
        send_message(chat_id, f"<pre>{out}</pre>")
    elif cmd == "/trafiktrojan":
        send_message(chat_id, "⏳ Mengambil trafik Trojan...")
        out = run_bash_cmd("bash /usr/local/sbin/trafik-tr")
        send_message(chat_id, f"<pre>{out}</pre>")

    # System actions
    elif cmd == "/restart":
        send_message(chat_id, "⏳ Sedang me-restart semua service...")
        cmd_str = "systemctl daemon-reload ; pkill sslh ; systemctl restart v2ray proxy danted badvpn udp-custom nginx sslh wg-quick@wg0 netdata"
        run_bash_cmd(cmd_str)
        send_message(chat_id, "✅ Semua service berhasil di-restart!")
    elif cmd == "/speedtest":
        send_message(chat_id, "⏳ Menjalankan Speedtest di VPS...")
        out = run_bash_cmd("speedtest-cli --simple || speedtest || echo 'Speedtest Gagal'")
        send_message(chat_id, f"🚀 <b>Hasil Speedtest:</b>\n<pre>{out}</pre>")
    elif cmd == "/backup":
        send_message(chat_id, "⏳ Menjalankan Backup database VPS...")
        out = run_bash_cmd("bash /usr/local/sbin/backup")
        send_message(chat_id, f"<pre>{out}</pre>")
    elif cmd == "/restore":
        send_message(chat_id, "⏳ Menjalankan Restore database VPS...")
        out = run_bash_cmd("bash /usr/local/sbin/restore")
        send_message(chat_id, f"<pre>{out}</pre>")
    elif cmd == "/update_script":
        send_message(chat_id, "🔄 <b>Mengupdate Autoscript VPS...</b>\nBot panel terhenti sejenak dan me-restart otomatis.")
        subprocess.Popen("sleep 2 && update", shell=True)
        
    elif cmd == "/addseller":
        if chat_str != str(owner_id):
            send_message(chat_id, "❌ Perintah ini hanya khusus untuk Owner!")
            return
        if len(parts) < 2:
            send_message(chat_id, "💡 Format: <code>/addseller &lt;chat_id&gt;</code>")
            return
        new_seller = parts[1]
        sellers_list = load_sellers()
        if new_seller not in sellers_list:
            sellers_list.append(new_seller)
            save_sellers(sellers_list)
            send_message(chat_id, f"✅ Sukses menambahkan <code>{new_seller}</code> sebagai Seller baru.")
        else:
            send_message(chat_id, f"ℹ️ ID <code>{new_seller}</code> sudah terdaftar.")
            
    elif cmd == "/delseller":
        if chat_str != str(owner_id):
            send_message(chat_id, "❌ Perintah ini hanya khusus untuk Owner!")
            return
        if len(parts) < 2:
            send_message(chat_id, "💡 Format: <code>/delseller &lt;chat_id&gt;</code>")
            return
        del_seller = parts[1]
        sellers_list = load_sellers()
        if del_seller in sellers_list:
            sellers_list.remove(del_seller)
            save_sellers(sellers_list)
            send_message(chat_id, f"✅ Sukses menghapus <code>{del_seller}</code> dari daftar Seller.")
        else:
            send_message(chat_id, f"ℹ️ ID <code>{del_seller}</code> tidak ditemukan.")
            
    elif cmd == "/listsellers":
        if chat_str != str(owner_id):
            send_message(chat_id, "❌ Perintah ini hanya khusus untuk Owner!")
            return
        sellers_list = load_sellers()
        out = "\n".join([f"• <code>{s}</code>" for s in sellers_list])
        send_message(chat_id, f"👤 <b>Daftar Seller Terdaftar:</b>\n{out if out else 'Tidak ada seller lain'}")

# Main Polling Loop
def main_loop():
    print("Telegram Bot daemon started successfully!")
    set_bot_commands()
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=30"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=35) as response:
                res = json.loads(response.read().decode("utf-8"))
                if "result" in res:
                    for update in res["result"]:
                        offset = update["update_id"] + 1
                        if "message" in update and "text" in update["message"]:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            text = msg["text"].strip()
                            
                            if not is_authorized(chat_id):
                                send_message(chat_id, "❌ <b>Akses Ditolak:</b> ID Anda belum terdaftar sebagai Seller.")
                                continue
                            
                            if text.startswith("/"):
                                if chat_id in user_states:
                                    del user_states[chat_id]
                                if text.lower() == "/cancel":
                                    send_message(chat_id, "❌ Pembuatan akun dibatalkan.")
                                    continue
                                handle_command(chat_id, text)
                            else:
                                if chat_id in user_states:
                                    handle_state_input(chat_id, text)
                                else:
                                    send_message(chat_id, "Gunakan tombol menu atau command /menu untuk memulai.")
                        elif "callback_query" in update:
                            cb = update["callback_query"]
                            chat_id = cb["message"]["chat"]["id"]
                            cb_data = cb["data"]
                            answer_callback_query(cb["id"])
                            if not is_authorized(chat_id):
                                send_message(chat_id, "❌ <b>Akses Ditolak:</b> ID Anda belum terdaftar sebagai Seller.")
                                continue
                            if chat_id in user_states:
                                del user_states[chat_id]
                            handle_command(chat_id, cb_data)
        except Exception as e:
            print("Loop error:", e)
            time.sleep(5)

if __name__ == "__main__":
    if not token:
        print("Error: Bot Token not found in /usr/local/etc/v2ray/bot.key")
        sys.exit(1)
    main_loop()
