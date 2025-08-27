# デプロイガイド

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

このガイドでは、COMETボットの本番環境へのデプロイプロセスを詳しく説明します。Docker、GitHub Actions、手動デプロイメント、監視設定など、様々なデプロイメント方法とベストプラクティスを提供します。

## デプロイメントアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                デプロイメントアーキテクチャ                   │
├─────────────────────────────────────────────────────────────┤
│  開発環境 (Development)                                     │
│  ├── ローカル開発                                            │
│  ├── テスト実行                                              │
│  ├── コード品質チェック                                      │
│  └── プルリクエスト作成                                      │
├─────────────────────────────────────────────────────────────┤
│  CI/CD パイプライン (GitHub Actions)                        │
│  ├── 自動テスト実行                                          │
│  ├── コード品質チェック                                      │
│  ├── セキュリティスキャン                                    │
│  ├── Docker イメージビルド                                  │
│  └── 自動デプロイメント                                      │
├─────────────────────────────────────────────────────────────┤
│  ステージング環境 (Staging)                                 │
│  ├── 本番環境と同等の設定                                    │
│  ├── 統合テスト                                              │
│  ├── パフォーマンステスト                                    │
│  └── 最終検証                                                │
├─────────────────────────────────────────────────────────────┤
│  本番環境 (Production)                                      │
│  ├── 高可用性設定                                            │
│  ├── 監視・アラート                                          │
│  ├── バックアップ・復旧                                      │
│  └── ログ管理                                                │
└─────────────────────────────────────────────────────────────┘
```

## 前提条件

### システム要件

- **OS**: Ubuntu 20.04 LTS 以上 / CentOS 8 以上 / Windows Server 2019 以上
- **Python**: 3.8 以上
- **メモリ**: 最小 512MB、推奨 1GB 以上
- **ディスク容量**: 最小 2GB、推奨 5GB 以上
- **ネットワーク**: インターネット接続（Discord API アクセス用）

### 必要なソフトウェア

- Git
- Python 3.8+
- pip
- Docker（Dockerデプロイの場合）
- systemd（Linuxサービス化の場合）

## 環境設定

### 1. 環境変数設定

```bash
# .env.production
# Discord Bot Configuration
BOT_TOKEN=your_production_bot_token_here
COMMAND_PREFIX=!

# Guild and Channel IDs
ADMIN_MAIN_GUILD_ID=123456789012345678
ADMIN_DEV_GUILD_ID=876543210987654321
ADMIN_STARTUP_CHANNEL_ID=111111111111111111
ADMIN_BUG_REPORT_CHANNEL_ID=222222222222222222
ADMIN_ERROR_LOG_CHANNEL_ID=333333333333333333

# Authentication
AUTH_TOKEN=your_production_auth_token_here
AUTH_URL=https://your-production-auth-endpoint.com/api

# External Services
SENTRY_DSN=your_production_sentry_dsn_here
WEBHOOK_URL=your_production_webhook_url_here

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_MONITORING=true
DEBUG_MODE=false

# Database Configuration
DATABASE_URL=sqlite:///config/bot.db
DATABASE_POOL_SIZE=10

# Monitoring
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8001
UPTIME_KUMA_URL=your_production_uptime_kuma_url

# Production Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 2. 設定ファイルの準備

```json
// config/bot.production.json
{
    "bot_info": {
        "name": "COMET",
        "version": "2.1.0",
        "description": "HFS専属BOT 総合ガイド",
        "author": "FreeWiFiTech",
        "support_server": "https://discord.gg/hfs"
    },
    "features": {
        "moderation": {
            "enabled": true,
            "auto_mod": true,
            "log_actions": true
        },
        "entertainment": {
            "enabled": true,
            "omikuji": true,
            "giveaway": true
        },
        "analytics": {
            "enabled": true,
            "user_tracking": true,
            "server_stats": true
        }
    },
    "limits": {
        "max_warnings": 3,
        "cooldown_duration": 300,
        "max_giveaway_entries": 1000
    },
    "production": {
        "auto_restart": true,
        "health_check_interval": 300,
        "backup_interval": 86400,
        "log_retention_days": 30
    }
}
```

## Dockerデプロイメント

### 1. Dockerfile の最適化

```dockerfile
# Dockerfile.production
FROM python:3.10.16-slim-bookworm

# システムパッケージの更新とクリーンアップ
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピー（キャッシュ効率化）
COPY requirements.txt .

# Python依存関係のインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルのコピー
COPY . .

# 非rootユーザーの作成
RUN useradd --create-home --shell /bin/bash comet && \
    chown -R comet:comet /app
USER comet

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

# ポートの公開
EXPOSE 8001

# 起動コマンド
CMD ["python", "main.py"]
```

### 2. Docker Compose設定

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  comet-bot:
    build:
      context: .
      dockerfile: Dockerfile.production
    container_name: comet-bot-prod
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    ports:
      - "8001:8001"
    networks:
      - comet-network
    depends_on:
      - prometheus
      - grafana
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  prometheus:
    image: prom/prometheus:latest
    container_name: comet-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    networks:
      - comet-network

  grafana:
    image: grafana/grafana:latest
    container_name: comet-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    networks:
      - comet-network

networks:
  comet-network:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
```

### 3. デプロイスクリプト

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "🚀 Starting COMET Bot deployment..."

# 環境変数の確認
if [ ! -f ".env.production" ]; then
    echo "❌ .env.production file not found"
    exit 1
fi

# 設定ファイルの確認
if [ ! -f "config/bot.production.json" ]; then
    echo "❌ Production configuration file not found"
    exit 1
fi

# 既存のコンテナを停止
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.production.yml down

# 最新のコードを取得
echo "📥 Pulling latest code..."
git pull origin main

# Dockerイメージのビルド
echo "🔨 Building Docker image..."
docker-compose -f docker-compose.production.yml build --no-cache

# データベースのバックアップ
echo "💾 Creating database backup..."
if [ -f "config/bot.db" ]; then
    cp config/bot.db "config/bot.db.backup.$(date +%Y%m%d_%H%M%S)"
fi

# コンテナの起動
echo "▶️ Starting containers..."
docker-compose -f docker-compose.production.yml up -d

# ヘルスチェック
echo "🏥 Performing health check..."
sleep 30

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Deployment successful! Bot is healthy."
else
    echo "❌ Health check failed. Rolling back..."
    docker-compose -f docker-compose.production.yml down
    exit 1
fi

echo "🎉 Deployment completed successfully!"
```

## GitHub Actions CI/CD

### 1. ワークフロー設定

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run tests
      run: |
        python -m pytest tests/ --cov=cogs --cov=utils --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run security scan
      uses: securecodewarrior/github-action-add-sarif@v1
      with:
        sarif-file: 'security-scan-results.sarif'

  build-and-deploy:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Login to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v3
      with:
        context: .
        file: ./Dockerfile.production
        push: true
        tags: |
          ghcr.io/${{ github.repository }}:latest
          ghcr.io/${{ github.repository }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
    
    - name: Deploy to server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USERNAME }}
        port: ${{ secrets.SSH_PORT }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        passphrase: ${{ secrets.SSH_PRIVATE_KEY_PASS }}
        script: |
          cd ${{ secrets.SERVER_DEPLOY_DIR }}
          
          # 環境変数の設定
          echo "${{ secrets.ENV_PRODUCTION }}" > .env.production
          
          # 最新のコードを取得
          git pull origin main
          
          # デプロイスクリプトの実行
          chmod +x scripts/deploy.sh
          ./scripts/deploy.sh
          
          # クリーンアップ
          docker system prune -f
    
    - name: Notify deployment status
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        channel: '#deployments'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
      if: always()
```

### 2. 環境固有のワークフロー

```yaml
# .github/workflows/staging-deploy.yml
name: Deploy to Staging

on:
  pull_request:
    branches: [ main ]
    types: [ opened, synchronize ]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to staging environment
      run: |
        echo "Deploying to staging..."
        # ステージング環境へのデプロイロジック
    
    - name: Run integration tests
      run: |
        echo "Running integration tests..."
        # 統合テストの実行
    
    - name: Comment PR with staging URL
      uses: actions/github-script@v6
      with:
        script: |
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: '🚀 Staging deployment completed! Test at: https://staging.comet-bot.example.com'
          })
```

## 手動デプロイメント

### 1. サーバー準備

```bash
# サーバーセットアップスクリプト
#!/bin/bash
# scripts/server-setup.sh

echo "🔧 Setting up COMET Bot server..."

# システムの更新
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    unzip \
    systemd \
    nginx \
    certbot \
    python3-certbot-nginx

# Dockerのインストール
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Composeのインストール
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# ユーザーとディレクトリの作成
sudo useradd -m -s /bin/bash comet
sudo mkdir -p /opt/comet-bot
sudo chown comet:comet /opt/comet-bot

echo "✅ Server setup completed!"
```

### 2. アプリケーションデプロイ

```bash
#!/bin/bash
# scripts/manual-deploy.sh

set -e

DEPLOY_DIR="/opt/comet-bot"
SERVICE_NAME="comet-bot"
BACKUP_DIR="/opt/comet-bot/backups"

echo "🚀 Starting manual deployment..."

# バックアップディレクトリの作成
sudo mkdir -p $BACKUP_DIR

# 既存のサービスを停止
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "🛑 Stopping existing service..."
    sudo systemctl stop $SERVICE_NAME
fi

# 現在のデプロイのバックアップ
if [ -d "$DEPLOY_DIR/current" ]; then
    echo "💾 Creating backup..."
    sudo cp -r $DEPLOY_DIR/current $BACKUP_DIR/backup-$(date +%Y%m%d_%H%M%S)
fi

# 新しいデプロイディレクトリの作成
sudo mkdir -p $DEPLOY_DIR/releases/$(date +%Y%m%d_%H%M%S)
RELEASE_DIR=$DEPLOY_DIR/releases/$(date +%Y%m%d_%H%M%S)

# コードのクローン
echo "📥 Cloning repository..."
sudo git clone https://github.com/HolofanServer/comet.git $RELEASE_DIR
cd $RELEASE_DIR

# 依存関係のインストール
echo "📦 Installing dependencies..."
sudo python3 -m venv venv
sudo $RELEASE_DIR/venv/bin/pip install --upgrade pip
sudo $RELEASE_DIR/venv/bin/pip install -r requirements.txt

# 設定ファイルのコピー
echo "⚙️ Copying configuration..."
sudo cp /opt/comet-bot/config/.env.production $RELEASE_DIR/.env
sudo cp -r /opt/comet-bot/config $RELEASE_DIR/

# 権限の設定
sudo chown -R comet:comet $RELEASE_DIR

# シンボリックリンクの更新
sudo rm -f $DEPLOY_DIR/current
sudo ln -s $RELEASE_DIR $DEPLOY_DIR/current

# サービスの開始
echo "▶️ Starting service..."
sudo systemctl start $SERVICE_NAME
sudo systemctl enable $SERVICE_NAME

# ヘルスチェック
echo "🏥 Performing health check..."
sleep 30

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Deployment successful!"
    
    # 古いリリースのクリーンアップ（最新5つを保持）
    cd $DEPLOY_DIR/releases
    sudo ls -t | tail -n +6 | xargs -r rm -rf
else
    echo "❌ Health check failed. Rolling back..."
    
    # ロールバック
    if [ -d "$BACKUP_DIR" ]; then
        LATEST_BACKUP=$(ls -t $BACKUP_DIR | head -n 1)
        sudo rm -f $DEPLOY_DIR/current
        sudo ln -s $BACKUP_DIR/$LATEST_BACKUP $DEPLOY_DIR/current
        sudo systemctl start $SERVICE_NAME
    fi
    
    exit 1
fi

echo "🎉 Manual deployment completed!"
```

### 3. systemd サービス設定

```ini
# /etc/systemd/system/comet-bot.service
[Unit]
Description=COMET Discord Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=comet
Group=comet
WorkingDirectory=/opt/comet-bot/current
Environment=PATH=/opt/comet-bot/current/venv/bin
ExecStart=/opt/comet-bot/current/venv/bin/python main.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=comet-bot

# セキュリティ設定
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/comet-bot/current/logs /opt/comet-bot/current/config

[Install]
WantedBy=multi-user.target
```

## 監視とアラート

### 1. Prometheus設定

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'comet-bot'
    static_configs:
      - targets: ['comet-bot:8001']
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### 2. アラートルール

```yaml
# monitoring/alert_rules.yml
groups:
  - name: comet-bot-alerts
    rules:
      - alert: BotDown
        expr: up{job="comet-bot"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "COMET Bot is down"
          description: "COMET Bot has been down for more than 1 minute."

      - alert: HighErrorRate
        expr: rate(comet_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second."

      - alert: HighMemoryUsage
        expr: comet_memory_usage_bytes / comet_memory_limit_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is above 80%."

      - alert: DatabaseConnectionFailed
        expr: comet_database_connection_status == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection failed"
          description: "Cannot connect to the database."
```

### 3. Grafanaダッシュボード

```json
{
  "dashboard": {
    "title": "COMET Bot Monitoring",
    "panels": [
      {
        "title": "Bot Status",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"comet-bot\"}",
            "legendFormat": "Bot Status"
          }
        ]
      },
      {
        "title": "Commands per Second",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(comet_commands_total[1m])",
            "legendFormat": "Commands/sec"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(comet_errors_total[1m])",
            "legendFormat": "Errors/sec"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "comet_memory_usage_bytes",
            "legendFormat": "Memory Usage"
          }
        ]
      }
    ]
  }
}
```

## バックアップと復旧

### 1. バックアップスクリプト

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/opt/comet-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

echo "💾 Starting backup process..."

# バックアップディレクトリの作成
mkdir -p $BACKUP_DIR

# データベースのバックアップ
if [ -f "/opt/comet-bot/current/config/bot.db" ]; then
    echo "📊 Backing up database..."
    cp /opt/comet-bot/current/config/bot.db $BACKUP_DIR/bot_db_$DATE.db
fi

# 設定ファイルのバックアップ
echo "⚙️ Backing up configuration..."
tar -czf $BACKUP_DIR/config_$DATE.tar.gz -C /opt/comet-bot/current config/

# ログファイルのバックアップ
if [ -d "/opt/comet-bot/current/logs" ]; then
    echo "📝 Backing up logs..."
    tar -czf $BACKUP_DIR/logs_$DATE.tar.gz -C /opt/comet-bot/current logs/
fi

# 古いバックアップの削除
echo "🧹 Cleaning up old backups..."
find $BACKUP_DIR -name "*.db" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "✅ Backup completed: $DATE"
```

### 2. 復旧スクリプト

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_DIR="/opt/comet-bot/backups"
DEPLOY_DIR="/opt/comet-bot/current"

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_date>"
    echo "Available backups:"
    ls -la $BACKUP_DIR | grep -E "(bot_db_|config_|logs_)"
    exit 1
fi

BACKUP_DATE=$1

echo "🔄 Starting restore process for backup: $BACKUP_DATE"

# サービスの停止
echo "🛑 Stopping service..."
sudo systemctl stop comet-bot

# データベースの復旧
if [ -f "$BACKUP_DIR/bot_db_$BACKUP_DATE.db" ]; then
    echo "📊 Restoring database..."
    sudo cp $BACKUP_DIR/bot_db_$BACKUP_DATE.db $DEPLOY_DIR/config/bot.db
    sudo chown comet:comet $DEPLOY_DIR/config/bot.db
fi

# 設定ファイルの復旧
if [ -f "$BACKUP_DIR/config_$BACKUP_DATE.tar.gz" ]; then
    echo "⚙️ Restoring configuration..."
    sudo tar -xzf $BACKUP_DIR/config_$BACKUP_DATE.tar.gz -C $DEPLOY_DIR
    sudo chown -R comet:comet $DEPLOY_DIR/config
fi

# ログファイルの復旧
if [ -f "$BACKUP_DIR/logs_$BACKUP_DATE.tar.gz" ]; then
    echo "📝 Restoring logs..."
    sudo tar -xzf $BACKUP_DIR/logs_$BACKUP_DATE.tar.gz -C $DEPLOY_DIR
    sudo chown -R comet:comet $DEPLOY_DIR/logs
fi

# サービスの開始
echo "▶️ Starting service..."
sudo systemctl start comet-bot

# ヘルスチェック
echo "🏥 Performing health check..."
sleep 30

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Restore completed successfully!"
else
    echo "❌ Health check failed after restore."
    exit 1
fi
```

## トラブルシューティング

### 1. 一般的な問題と解決方法

#### ボットが起動しない

```bash
# ログの確認
sudo journalctl -u comet-bot -f

# 設定ファイルの確認
python3 -c "
import json
with open('config/bot.json') as f:
    config = json.load(f)
    print('Configuration loaded successfully')
"

# 依存関係の確認
pip list | grep discord
```

#### メモリ不足

```bash
# メモリ使用量の確認
free -h
ps aux | grep python

# スワップファイルの作成
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### データベース接続エラー

```bash
# データベースファイルの確認
ls -la config/bot.db
sqlite3 config/bot.db ".tables"

# 権限の確認
sudo chown comet:comet config/bot.db
sudo chmod 644 config/bot.db
```

### 2. パフォーマンス最適化

```bash
# システムリソースの監視
htop
iotop
nethogs

# Pythonプロファイリング
python3 -m cProfile -o profile.stats main.py

# ログレベルの調整
export LOG_LEVEL=WARNING
```

---

## 関連ドキュメント

- [開発環境セットアップ](01-development-setup.md)
- [テストフレームワーク](02-testing-framework.md)
- [貢献ガイドライン](04-contributing-guidelines.md)
- [監視Cogs](../03-cogs/08-monitoring-cogs.md)
