# サーバーセットアップ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

このガイドでは、COMETボットを運用するためのサーバーセットアップ手順を詳しく説明します。ハードウェア要件、OS設定、セキュリティ設定、ネットワーク設定など、本番環境での安定運用に必要な全ての要素をカバーします。

## ハードウェア要件

### 最小要件

| 項目 | 最小要件 | 推奨要件 |
|------|----------|----------|
| CPU | 1 vCPU (2.0GHz) | 2 vCPU (2.4GHz以上) |
| メモリ | 1GB RAM | 2GB RAM以上 |
| ストレージ | 10GB SSD | 20GB SSD以上 |
| ネットワーク | 100Mbps | 1Gbps |
| 帯域幅 | 無制限 | 無制限 |

### 推奨サーバー仕様

#### 小規模運用 (1-5サーバー)
- **CPU**: 2 vCPU
- **メモリ**: 2GB RAM
- **ストレージ**: 20GB SSD
- **OS**: Ubuntu 22.04 LTS

#### 中規模運用 (5-20サーバー)
- **CPU**: 4 vCPU
- **メモリ**: 4GB RAM
- **ストレージ**: 40GB SSD
- **OS**: Ubuntu 22.04 LTS

#### 大規模運用 (20+サーバー)
- **CPU**: 8 vCPU
- **メモリ**: 8GB RAM
- **ストレージ**: 80GB SSD
- **OS**: Ubuntu 22.04 LTS

## OS セットアップ

### 1. Ubuntu 22.04 LTS インストール

```bash
# システムの更新
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール
sudo apt install -y \
    curl \
    wget \
    git \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    htop \
    nano \
    vim \
    tmux \
    fail2ban \
    ufw \
    logrotate \
    cron

# システムの再起動
sudo reboot
```

### 2. ユーザー管理

```bash
# 専用ユーザーの作成
sudo useradd -m -s /bin/bash comet
sudo usermod -aG sudo comet

# SSH キーの設定
sudo mkdir -p /home/comet/.ssh
sudo chmod 700 /home/comet/.ssh

# 公開鍵の追加（管理者の公開鍵を設定）
sudo nano /home/comet/.ssh/authorized_keys
sudo chmod 600 /home/comet/.ssh/authorized_keys
sudo chown -R comet:comet /home/comet/.ssh

# sudoers の設定
echo "comet ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/comet
```

### 3. セキュリティ設定

#### SSH設定の強化

```bash
# SSH設定ファイルの編集
sudo nano /etc/ssh/sshd_config
```

```bash
# /etc/ssh/sshd_config の推奨設定
Port 22
Protocol 2
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

# 認証設定
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# セキュリティ設定
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
MaxStartups 10:30:60

# 許可ユーザーの制限
AllowUsers comet

# ログ設定
SyslogFacility AUTH
LogLevel INFO
```

```bash
# SSH設定の再読み込み
sudo systemctl restart ssh
```

#### ファイアウォール設定

```bash
# UFWの有効化
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 必要なポートの開放
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw allow 8001/tcp comment 'Bot Health Check'

# ファイアウォールの有効化
sudo ufw --force enable

# 状態確認
sudo ufw status verbose
```

#### Fail2Ban設定

```bash
# Fail2Ban設定ファイルの作成
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600
```

```bash
# Fail2Banの開始
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
sudo systemctl status fail2ban
```

## Python環境のセットアップ

### 1. Python 3.11のインストール

```bash
# Python 3.11のインストール
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# デフォルトPythonの設定
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# pipの更新
python -m pip install --upgrade pip
```

### 2. 仮想環境の作成

```bash
# プロジェクトディレクトリの作成
sudo mkdir -p /opt/comet-bot
sudo chown comet:comet /opt/comet-bot

# ユーザーの切り替え
sudo su - comet

# 仮想環境の作成
cd /opt/comet-bot
python -m venv venv

# 仮想環境の有効化
source venv/bin/activate

# 基本パッケージのインストール
pip install --upgrade pip setuptools wheel
```

## データベースセットアップ

### 1. SQLite設定（開発・小規模運用）

```bash
# SQLiteの確認
sqlite3 --version

# データベースディレクトリの作成
mkdir -p /opt/comet-bot/data
chmod 755 /opt/comet-bot/data
```

### 2. PostgreSQL設定（大規模運用）

```bash
# PostgreSQLのインストール
sudo apt install -y postgresql postgresql-contrib

# PostgreSQLの開始
sudo systemctl start postgresql
sudo systemctl enable postgresql

# データベースとユーザーの作成
sudo -u postgres psql << EOF
CREATE DATABASE comet_bot;
CREATE USER comet_user WITH ENCRYPTED PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE comet_bot TO comet_user;
\q
EOF

# 接続テスト
psql -h localhost -U comet_user -d comet_bot -c "SELECT version();"
```

## Webサーバーセットアップ

### 1. Nginxのインストールと設定

```bash
# Nginxのインストール
sudo apt install -y nginx

# Nginxの開始
sudo systemctl start nginx
sudo systemctl enable nginx

# 設定ファイルの作成
sudo nano /etc/nginx/sites-available/comet-bot
```

```nginx
# /etc/nginx/sites-available/comet-bot
server {
    listen 80;
    server_name your-domain.com;
    
    # ヘルスチェックエンドポイント
    location /health {
        proxy_pass http://127.0.0.1:8001/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # メトリクスエンドポイント
    location /metrics {
        proxy_pass http://127.0.0.1:8001/metrics;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 基本認証（オプション）
        auth_basic "Metrics";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
    
    # 静的ファイル
    location /static/ {
        alias /opt/comet-bot/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # セキュリティヘッダー
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

```bash
# サイトの有効化
sudo ln -s /etc/nginx/sites-available/comet-bot /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# 設定テスト
sudo nginx -t

# Nginxの再起動
sudo systemctl restart nginx
```

### 2. SSL証明書の設定

```bash
# Certbotのインストール
sudo apt install -y certbot python3-certbot-nginx

# SSL証明書の取得
sudo certbot --nginx -d your-domain.com

# 自動更新の設定
sudo crontab -e
```

```bash
# crontabに追加
0 12 * * * /usr/bin/certbot renew --quiet
```

## 監視システムのセットアップ

### 1. システム監視

```bash
# htopとiotopのインストール
sudo apt install -y htop iotop nethogs

# システム情報収集スクリプト
sudo nano /usr/local/bin/system-info.sh
```

```bash
#!/bin/bash
# /usr/local/bin/system-info.sh

echo "=== System Information ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo "Load Average: $(cat /proc/loadavg)"
echo "Memory Usage:"
free -h
echo "Disk Usage:"
df -h
echo "Network Connections:"
ss -tuln
echo "Top Processes:"
ps aux --sort=-%cpu | head -10
```

```bash
# スクリプトの実行権限付与
sudo chmod +x /usr/local/bin/system-info.sh
```

### 2. ログ管理

```bash
# ログローテーション設定
sudo nano /etc/logrotate.d/comet-bot
```

```bash
# /etc/logrotate.d/comet-bot
/opt/comet-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 comet comet
    postrotate
        systemctl reload comet-bot
    endscript
}
```

### 3. 自動バックアップ

```bash
# バックアップスクリプトの作成
sudo nano /usr/local/bin/backup-comet.sh
```

```bash
#!/bin/bash
# /usr/local/bin/backup-comet.sh

BACKUP_DIR="/opt/backups/comet-bot"
DATE=$(date +%Y%m%d_%H%M%S)
BOT_DIR="/opt/comet-bot"

# バックアップディレクトリの作成
mkdir -p $BACKUP_DIR

# データベースのバックアップ
if [ -f "$BOT_DIR/data/bot.db" ]; then
    cp "$BOT_DIR/data/bot.db" "$BACKUP_DIR/bot_db_$DATE.db"
fi

# 設定ファイルのバックアップ
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$BOT_DIR" config/

# ログファイルのバックアップ
if [ -d "$BOT_DIR/logs" ]; then
    tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" -C "$BOT_DIR" logs/
fi

# 古いバックアップの削除（30日以上）
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# スクリプトの実行権限付与
sudo chmod +x /usr/local/bin/backup-comet.sh

# 定期実行の設定
sudo crontab -e
```

```bash
# crontabに追加（毎日午前2時にバックアップ）
0 2 * * * /usr/local/bin/backup-comet.sh >> /var/log/backup-comet.log 2>&1
```

## ネットワーク設定

### 1. DNS設定

```bash
# DNS設定の確認
cat /etc/resolv.conf

# 信頼できるDNSサーバーの設定
sudo nano /etc/systemd/resolved.conf
```

```ini
[Resolve]
DNS=1.1.1.1 8.8.8.8
FallbackDNS=1.0.0.1 8.8.4.4
Domains=~.
DNSSEC=yes
DNSOverTLS=yes
Cache=yes
```

```bash
# systemd-resolvedの再起動
sudo systemctl restart systemd-resolved
```

### 2. NTP設定

```bash
# NTPの設定
sudo nano /etc/systemd/timesyncd.conf
```

```ini
[Time]
NTP=ntp.nict.jp pool.ntp.org
FallbackNTP=time.cloudflare.com
RootDistanceMaxSec=5
PollIntervalMinSec=32
PollIntervalMaxSec=2048
```

```bash
# タイムゾーンの設定
sudo timedatectl set-timezone Asia/Tokyo

# NTPの有効化
sudo timedatectl set-ntp true

# 時刻同期の確認
timedatectl status
```

## パフォーマンス最適化

### 1. カーネルパラメータの調整

```bash
# sysctl設定の追加
sudo nano /etc/sysctl.d/99-comet-bot.conf
```

```bash
# /etc/sysctl.d/99-comet-bot.conf

# ネットワーク最適化
net.core.rmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_default = 262144
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# ファイルディスクリプタ制限
fs.file-max = 65536

# プロセス制限
kernel.pid_max = 65536

# メモリ管理
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

```bash
# 設定の適用
sudo sysctl -p /etc/sysctl.d/99-comet-bot.conf
```

### 2. リソース制限の設定

```bash
# limits.confの編集
sudo nano /etc/security/limits.conf
```

```bash
# /etc/security/limits.conf に追加
comet soft nofile 65536
comet hard nofile 65536
comet soft nproc 32768
comet hard nproc 32768
```

## セキュリティ強化

### 1. 自動セキュリティ更新

```bash
# unattended-upgradesのインストール
sudo apt install -y unattended-upgrades

# 設定ファイルの編集
sudo nano /etc/apt/apt.conf.d/50unattended-upgrades
```

```bash
// /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
```

### 2. 侵入検知システム

```bash
# RKHunterのインストール
sudo apt install -y rkhunter

# 設定ファイルの編集
sudo nano /etc/rkhunter.conf
```

```bash
# /etc/rkhunter.conf の主要設定
MAIL-ON-WARNING=admin@your-domain.com
MAIL_CMD=mail -s "[rkhunter] Warnings found for ${HOST_NAME}"
UPDATE_MIRRORS=1
MIRRORS_MODE=0
WEB_CMD=""
```

```bash
# データベースの更新
sudo rkhunter --update
sudo rkhunter --propupd

# 定期スキャンの設定
echo "0 3 * * * root /usr/bin/rkhunter --cronjob --update --quiet" | sudo tee -a /etc/crontab
```

---

## 関連ドキュメント

- [監視・アラート](02-monitoring-alerts.md)
- [バックアップ・復旧](03-backup-recovery.md)
- [トラブルシューティング](04-troubleshooting.md)
- [デプロイガイド](../05-development/03-deployment-guide.md)
