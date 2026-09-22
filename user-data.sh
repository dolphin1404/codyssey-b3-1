#!/bin/bash
set -euo pipefail
dnf install -y nginx
cat > /etc/nginx/conf.d/codyssey.conf <<'NGINX'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/codyssey;
    location = /health {
        default_type text/plain;
        return 200 "OK\n";
    }
    location / {
        try_files $uri $uri/ =404;
    }
}
NGINX
# 배포판 기본 server 블록의 루트도 같은 페이지를 표시하도록 배치한다.
mkdir -p /usr/share/nginx/codyssey
cat > /usr/share/nginx/codyssey/index.html <<'HTML'
<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Hello Cloud</title>
<style>body{font:18px system-ui;max-width:720px;margin:12vh auto;padding:24px;background:#f5f7fb;color:#15263e}h1{font-size:48px}a{color:#2456b8}</style>
<h1>Hello Cloud</h1><p>서울 리전의 VPC와 EC2에서 제공하는 웹페이지입니다.</p>
<p><a href="/health">서비스 상태 확인</a></p></html>
HTML
# 기본 설정 대신 실습용 server 한 개만 로드한다.
cat > /etc/nginx/nginx.conf <<'NGINX'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    access_log /var/log/nginx/access.log;
    include /etc/nginx/conf.d/*.conf;
}
NGINX
nginx -t
systemctl enable --now nginx
curl --fail --max-time 10 http://localhost/health
