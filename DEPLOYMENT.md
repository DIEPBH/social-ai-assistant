# Hướng Dẫn Đóng Gói & Triển Khai (Social AI Assistant)

Tài liệu này hướng dẫn chi tiết cách đóng gói, cấu hình và triển khai dự án **Social AI Assistant** trên môi trường Production (VPS, Cloud Server, On-Premise) cũng như môi trường Development.

---

## 🏗 Kiến trúc Hệ thống Triển khai

Dự án được đóng gói thành các dịch vụ Docker độc lập:

- **Web Application (`web`)**: Ứng dụng Django chạy qua Gunicorn (WSGI server).
- **Background Worker (`celery_worker`)**: Tiến trình Celery xử lý các tác vụ bất đồng bộ (gọi Gemini AI, xử lý tin nhắn, xuất báo cáo).
- **Scheduler (`celery_beat`)**: Tiến trình định kỳ Celery Beat (làm mới Zalo Token, dọn dẹp log, gửi báo cáo hàng ngày).
- **Database (`db`)**: PostgreSQL 15 lưu trữ dữ liệu.
- **Cache & Message Broker (`redis`)**: Redis 7 làm bộ đệm và Broker cho Celery.
- **Reverse Proxy (`nginx`)**: Phục vụ file tĩnh (`/static/`), file tải lên (`/media/`) và proxy HTTP request tới `web`.

---

## 📋 Yêu cầu Môi trường Server Target

- **Hệ điều hành**: Ubuntu 20.04 / 22.04 LTS, Debian, CentOS hoặc bất kỳ Linux server nào hỗ trợ Docker.
- **Phần mềm yêu cầu**:
  - Docker engine (`>= 20.10`)
  - Docker Compose (`>= v2.0`)
  - Git

---

## 🚀 Triển khai Nhanh (Quick Start)

### 1. Cloned Dự án về Server
```bash
git clone <repository_url> social_ai_assistant
cd social_ai_assistant
```

### 2. Thiết lập Biến môi trường
Tạo tệp cấu hình từ tệp mẫu `.env.example`:
```bash
mkdir -p env
cp .env.example env/.env
```

Chỉnh sửa thông tin cấu hình cho môi trường mới:
```bash
nano env/.env
```
*(Cần lưu ý thay đổi các thông tin: `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `GEMINI_API_KEY`, `ZALO_*`, `FACEBOOK_*`)*

### 3. Thực thi Triển khai với 1 lệnh
```bash
./deploy.sh
```
Hoặc chạy trực tiếp bằng Docker Compose:
```bash
docker compose up -d --build
```

---

## 📦 Đóng gói & Triển khai Đa Môi trường (Docker Registry & CI/CD)

Nếu bạn muốn đóng gói hệ thống thành các Docker Image độc lập và đưa lên Registry (Docker Hub hoặc GitHub Container Registry - GHCR) để kéo về triển khai ở nhiều nơi mà không cần compile lại source code:

### 1. Đóng gói & Push Image lên Docker Hub
```bash
# Đăng nhập Docker Hub
docker login

# Build image với tag phiên bản
docker build -t your-username/social-ai-assistant:v1.0.0 .
docker tag your-username/social-ai-assistant:v1.0.0 your-username/social-ai-assistant:latest

# Push image lên Registry
docker push your-username/social-ai-assistant:v1.0.0
docker push your-username/social-ai-assistant:latest
```

### 2. Triển khai ở máy khách từ Image trên Registry
Trên server khách hàng, cập nhật `docker-compose.yml` sử dụng `image` thay vì `build`:
```yaml
services:
  web:
    image: your-username/social-ai-assistant:latest
    container_name: social_ai_web
    ...
```

Sau đó chỉ cần chạy:
```bash
docker compose up -d
```

---

## 🛠 Triển khai trên Môi trường Development (Local Dev)

Nếu muốn phát triển và kiểm thử giao diện trực tiếp với hot-reloading:
```bash
docker compose -f docker-compose.dev.yml up --build
```
Ứng dụng sẽ chạy ở chế độ Django Debug trên cổng `8000` (`http://localhost:8000`).

---

## 🔐 Cấu hình SSL / HTTPS cho Nginx

Để kích hoạt HTTPS với Certbot Let's Encrypt trên server Production:

1. **Sử dụng Nginx Proxy Manager / Cloudflare**: Trỏ tên miền về IP server và bật SSL Proxy.
2. **Sử dụng Certbot trực tiếp trên host**:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

---

## 🛠 Quản trị & Vận hành Thường nhật

### 1. Xem nhật ký hệ thống (Logs)
```bash
# Xem log toàn bộ hệ thống
docker compose logs -f

# Xem log riêng từng dịch vụ
docker compose logs -f web
docker compose logs -f celery_worker
```

### 2. Tạo tài khoản Admin (Superuser)
```bash
docker compose exec web python manage.py createsuperuser
```

### 3. Khởi chạy lại hoặc Dừng hệ thống
```bash
# Khởi chạy lại
docker compose restart

# Dừng hệ thống
docker compose down
```

### 4. Sao lưu & Khôi phục Dữ liệu (Backup & Restore)

#### Sao lưu Database PostgreSQL:
```bash
docker compose exec db pg_dump -U diepbh social_ai_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

#### Khôi phục Database:
```bash
cat backup_file.sql | docker compose exec -T db psql -U diepbh -d social_ai_db
```

#### Sao lưu dữ liệu tải lên (Media Uploads):
```bash
docker run --rm --volumes-from social_ai_web -v $(pwd):/backup ubuntu tar cvzf /backup/media_backup.tar.gz /app/media
```

---

## 🎯 Danh sách các cổng mạng (Ports) mở mặc định
- **HTTP**: `80` (Phục vụ Nginx Reverse Proxy)
- **Django App (Internal)**: `8000`
- **PostgreSQL (Internal)**: `5432`
- **Redis (Internal)**: `6379`
