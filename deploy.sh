#!/bin/bash
set -e

echo "========================================================="
echo "   Triển khai Social AI Assistant (Production Deploy)"
echo "========================================================="

ENV_FILE="./env/.env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env" ]; then
        ENV_FILE=".env"
    else
        echo "⚠️ Không tìm thấy tệp môi trường ($ENV_FILE hoặc .env)."
        echo "==> Đang tự động tạo ./env/.env từ tệp mẫu .env.example..."
        mkdir -p env
        cp .env.example ./env/.env
        echo "💡 Vui lòng chỉnh sửa tệp ./env/.env với cấu hình thực tế của bạn và chạy lại ./deploy.sh"
        exit 1
    fi
fi

echo "🚀 Đang xây dựng & khởi chạy các dịch vụ Docker Container..."
docker compose down --remove-orphans
docker compose up -d --build

echo "⌛ Đang kiểm tra trạng thái dịch vụ..."
sleep 5
docker compose ps

echo "========================================================="
echo "✅ Triển khai hoàn tất! Hệ thống đã sẵn sàng."
echo "   Web App & Admin: http://<server-ip>/"
echo "   Logs: docker compose logs -f"
echo "========================================================="
