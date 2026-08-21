# Social AI Assistant

Một hệ thống trợ lý AI hỗ trợ tự động xử lý tin nhắn từ các nền tảng mạng xã hội.

## 🚀 Các chức năng chính (MVP)

*   **Tích hợp đa kênh**: 
    *   Nhận và xử lý tin nhắn từ Zalo OA.
    *   Nhận và xử lý tin nhắn từ Facebook Messenger.
*   **Lưu trữ dữ liệu**: Quản lý lịch sử tin nhắn và thông tin tương tác người dùng bằng PostgreSQL.
*   **Xử lý AI Tự động**: Tích hợp Google Gemini API để xử lý ngữ nghĩa và sinh câu trả lời tự động. Quá trình này được xử lý bất đồng bộ thông qua Celery để đảm bảo hiệu suất hệ thống.
*   **Quản trị & Báo cáo**:
    *   Trang quản trị (Admin Dashboard) giúp theo dõi và vận hành trực quan.
    *   Hỗ trợ trích xuất dữ liệu, xuất báo cáo dưới định dạng Excel.

## 🛠 Công nghệ sử dụng

*   **Backend**: Python, Django
*   **Database**: PostgreSQL
*   **Background Tasks**: Celery, Redis
*   **AI Integration**: Google Gemini API
*   **Infrastructure**: Docker, Docker Compose, Nginx, Gunicorn

## 📦 Đóng gói & Triển khai

Dự án đã được đóng gói hoàn chỉnh bằng Docker Container.

### Triển khai Nhanh (Production)
```bash
# 1. Tạo tệp cấu hình từ tệp mẫu
cp .env.example env/.env

# 2. Khởi chạy hệ thống 1-click
./deploy.sh
```

Chi tiết hướng dẫn đóng gói image, triển khai trên nhiều máy chủ, cấu hình SSL và sao lưu dữ liệu xem tại [DEPLOYMENT.md](file:///opt/social_ai_assistant/DEPLOYMENT.md).
