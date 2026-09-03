import logging
from typing import Any, Dict, List, Optional, Tuple
from django.contrib.auth.models import User
from django.utils import timezone

from social_messages.models import IntakeSubmission, Message
from social_messages.services.admin_guard import AdminGuard

logger = logging.getLogger(__name__)


class AdminSubmissionService:
    def __init__(self):
        self.guard = AdminGuard()

    def get_submissions_queryset(self, user: Optional[User]):
        """
        Trả về QuerySet các hồ sơ mà user được phép xem.
        - Quản trị viên: Tất cả hồ sơ.
        - Chuyên viên: Chỉ các hồ sơ được phân công cho mình.
        - Khác: Rỗng.
        """
        if not user or not user.is_active:
            return IntakeSubmission.objects.none()

        if self.guard.is_admin_user(user):
            return IntakeSubmission.objects.all().select_related(
                "category", "conversation", "conversation__channel"
            ).prefetch_related("assignments__user").order_by("-created_at")

        if self.guard.is_specialist_user(user):
            return IntakeSubmission.objects.filter(
                assignments__user=user
            ).select_related(
                "category", "conversation", "conversation__channel"
            ).prefetch_related("assignments__user").distinct().order_by("-created_at")

        return IntakeSubmission.objects.none()

    def get_submission_stats(self, user: Optional[User]) -> Dict[str, int]:
        role = self.guard.get_user_role(user)
        if role == "unauthorized":
            return {}

        now = timezone.localtime()
        today = now.date()

        if role == "admin":
            base_qs = IntakeSubmission.objects.all()
            return {
                "unassigned": base_qs.filter(processing_status="unassigned").count(),
                "pending": base_qs.filter(processing_status="pending").count(),
                "in_progress": base_qs.filter(processing_status="in_progress").count(),
                "today": base_qs.filter(created_at__date=today).count(),
                "urgent": base_qs.filter(priority__in=["high", "urgent"]).exclude(processing_status="completed").count(),
            }

        if role == "specialist":
            my_qs = IntakeSubmission.objects.filter(assignments__user=user)
            return {
                "pending": my_qs.filter(assignments__status="pending").distinct().count(),
                "in_progress": my_qs.filter(assignments__status="in_progress").distinct().count(),
                "today": my_qs.filter(created_at__date=today).distinct().count(),
                "urgent": my_qs.filter(priority__in=["high", "urgent"]).exclude(assignments__status="completed").distinct().count(),
            }

        return {}

    def format_submissions_list(
        self,
        user: Optional[User],
        filter_type: str = "default",
        target_date=None,
        limit: int = 5,
    ) -> str:
        """
        Định dạng danh sách hồ sơ tóm tắt gửi qua Zalo OA.
        Kết hợp Phương án 1 (Lọc thông minh theo trạng thái/ngày) và Phương án 3 (Thống kê tổng quan).
        """
        role = self.guard.get_user_role(user)
        if role == "unauthorized":
            return "⛔ Bạn không có quyền truy cập danh sách hồ sơ trên hệ thống."

        now = timezone.localtime()
        today = now.date()
        base_qs = self.get_submissions_queryset(user)

        header_title = ""
        is_default = False

        if filter_type == "unassigned":
            if role != "admin":
                return "⛔ Chuyên viên chỉ xem được hồ sơ được phân công cho mình. Lệnh xem hồ sơ chưa phân công chỉ dành cho Quản trị viên."
            qs = base_qs.filter(processing_status="unassigned")
            header_title = "📋 HỒ SƠ CHƯA PHÂN CÔNG"

        elif filter_type == "pending":
            if role == "admin":
                qs = base_qs.filter(processing_status="pending")
            else:
                qs = base_qs.filter(assignments__status="pending")
            header_title = "📋 HỒ SƠ CHƯA XỬ LÝ (CHỜ XỬ LÝ)"

        elif filter_type == "in_progress":
            if role == "admin":
                qs = base_qs.filter(processing_status="in_progress")
            else:
                qs = base_qs.filter(assignments__status="in_progress")
            header_title = "📋 HỒ SƠ ĐANG XỬ LÝ"

        elif filter_type == "today":
            qs = base_qs.filter(created_at__date=today)
            header_title = f"📋 HỒ SƠ PHÁT SINH HÔM NAY ({today.strftime('%d/%m/%Y')})"

        elif filter_type == "yesterday":
            from datetime import timedelta
            yesterday = today - timedelta(days=1)
            qs = base_qs.filter(created_at__date=yesterday)
            header_title = f"📋 HỒ SƠ PHÁT SINH HÔM QUA ({yesterday.strftime('%d/%m/%Y')})"

        elif filter_type == "specific_date":
            if not target_date:
                return "❌ Ngày tra cứu không hợp lệ."
            qs = base_qs.filter(created_at__date=target_date)
            header_title = f"📋 HỒ SƠ PHÁT SINH NGÀY {target_date.strftime('%d/%m/%Y')}"

        elif filter_type == "urgent":
            if role == "admin":
                qs = base_qs.filter(priority__in=["high", "urgent"]).exclude(processing_status="completed")
            else:
                qs = base_qs.filter(priority__in=["high", "urgent"]).exclude(assignments__status="completed")
            header_title = "📋 HỒ SƠ KHẨN CẤP / ƯU TIÊN CAO"

        else:
            is_default = True
            if role == "admin":
                action_qs = base_qs.filter(processing_status__in=["unassigned", "pending"])
                qs = action_qs if action_qs.exists() else base_qs.exclude(processing_status="completed")
                header_title = "📋 VIỆC CẦN XỬ LÝ NGAY (ƯU TIÊN)"
            else:
                action_qs = base_qs.filter(assignments__status__in=["pending", "in_progress"])
                qs = action_qs if action_qs.exists() else base_qs
                header_title = "📋 HỒ SƠ CẦN XỬ LÝ CỦA BẠN"

        total_count = qs.count()
        lines = []

        # Phương án 3: Bảng thống kê nhanh tình hình khi dùng lệnh mặc định
        if is_default:
            stats = self.get_submission_stats(user)
            if role == "admin":
                lines.extend([
                    "📊 TỔNG QUAN HỒ SƠ TOÀN HỆ THỐNG",
                    f"• Chưa phân công: {stats.get('unassigned', 0)}",
                    f"• Chờ xử lý: {stats.get('pending', 0)}",
                    f"• Đang xử lý: {stats.get('in_progress', 0)}",
                    f"• Mới hôm nay: {stats.get('today', 0)}",
                    f"• Khẩn cấp: {stats.get('urgent', 0)}",
                    "──────────────────",
                ])
            else:
                lines.extend([
                    "📊 TỔNG QUAN HỒ SƠ CỦA BẠN",
                    f"• Chờ xử lý: {stats.get('pending', 0)}",
                    f"• Đang xử lý: {stats.get('in_progress', 0)}",
                    f"• Được giao hôm nay: {stats.get('today', 0)}",
                    f"• Khẩn cấp: {stats.get('urgent', 0)}",
                    "──────────────────",
                ])

        if total_count == 0:
            if is_default:
                lines.append(f"{header_title}: Hiện không có hồ sơ nào tồn đọng! 🎉")
            else:
                lines.append(f"{header_title}: Không tìm thấy hồ sơ nào.")
            lines.append("")
            lines.append("💡 Lệnh tra cứu khác:")
            lines.append("• 'hồ sơ hôm nay' | 'hồ sơ chưa xử lý'")
            lines.append("• 'hồ sơ ngày DD/MM/YYYY' (VD: hồ sơ ngày 02/09/2026)")
            return "\n".join(lines).strip()

        items = list(qs[:limit])
        lines.append(f"{header_title} ({len(items)}/{total_count} hồ sơ)")
        lines.append("──────────────────")

        for s in items:
            category_name = s.category.name if s.category else (s.intent or "Chưa phân loại")
            citizen_str = s.citizen_name or "Chưa rõ người gửi"
            status_display = s.get_processing_status_display() or "Chưa xử lý"

            raw_summary = (s.summary or s.content or "").strip().replace("\n", " ")
            short_summary = raw_summary[:70] + "..." if len(raw_summary) > 70 else raw_summary

            entry = [
                f"🔹 Mã hồ sơ: #{s.id}",
                f"   • Phân loại: {category_name}",
                f"   • Người gửi: {citizen_str}",
                f"   • Trạng thái: {status_display}",
            ]

            if s.priority in ["high", "urgent"]:
                entry.append(f"   • Độ ưu tiên: ⚡ {s.priority.upper()}")

            if role == "admin":
                assignments = list(s.assignments.all())
                if assignments:
                    handlers = [f"{a.user.first_name or a.user.username} ({a.get_role_display()})" for a in assignments]
                    entry.append(f"   • Cán bộ: {', '.join(handlers)}")
                else:
                    entry.append("   • Cán bộ: Chưa phân công ⚠️")
            elif role == "specialist":
                my_assignment = next((a for a in s.assignments.all() if a.user_id == user.id), None)
                if my_assignment:
                    entry.append(f"   • Vai trò: {my_assignment.get_role_display()} ({my_assignment.get_status_display()})")

            if short_summary:
                entry.append(f"   • Tóm tắt: {short_summary}")

            lines.append("\n".join(entry))
            lines.append("")

        lines.append("──────────────────")
        lines.append("💡 Lệnh gợi ý tra cứu:")
        if role == "admin":
            lines.append("• 'hồ sơ chưa phân công' | 'hồ sơ chưa xử lý'")
        else:
            lines.append("• 'hồ sơ chưa xử lý' | 'hồ sơ đang xử lý'")
        lines.append("• 'hồ sơ hôm nay' | 'hồ sơ khẩn cấp'")
        lines.append("• 'hồ sơ ngày DD/MM/YYYY' (VD: hồ sơ ngày 02/09/2026)")
        lines.append("• 'xem hồ sơ [mã]' để xem chi tiết & nhận file đính kèm.")
        return "\n".join(lines).strip()

    def get_submission_detail(
        self, user: Optional[User], submission_id: int
    ) -> Tuple[bool, str, Optional[IntakeSubmission]]:
        """
        Lấy chi tiết hồ sơ và kiểm tra quyền của user.
        Trả về: (has_access: bool, message_text: str, submission: Optional[IntakeSubmission])
        """
        role = self.guard.get_user_role(user)
        if role == "unauthorized":
            return False, "⛔ Bạn không có quyền truy cập hồ sơ trên hệ thống.", None

        submission = IntakeSubmission.objects.filter(id=submission_id).select_related(
            "category", "conversation", "conversation__channel", "message"
        ).prefetch_related("assignments__user").first()

        if not submission:
            return False, f"❌ Không tìm thấy hồ sơ với mã #{submission_id}.", None

        # Kiểm tra quyền: Admin được xem tất cả, Chuyên viên chỉ xem hồ sơ được giao
        if role == "specialist":
            is_assigned = submission.assignments.filter(user=user).exists()
            if not is_assigned:
                return (
                    False,
                    f"⛔ Bạn không có quyền xem hồ sơ #{submission_id} do chưa được phân công xử lý hồ sơ này.",
                    None,
                )

        # Định dạng thông tin chi tiết
        category_name = submission.category.name if submission.category else (submission.intent or "Chưa rõ")
        citizen_name = submission.citizen_name or "Chưa cung cấp"
        phone = submission.phone_number or "Chưa cung cấp"
        address = submission.address or "Chưa cung cấp"
        event_time = submission.event_time or "Chưa cung cấp"
        location = submission.event_location or "Chưa cung cấp"
        related = submission.related_person or "Không có"
        urgency = submission.urgency_level or "Bình thường"
        priority = submission.priority or "normal"
        status_display = submission.get_processing_status_display() or "Chưa xử lý"

        # Cán bộ xử lý
        assignments = list(submission.assignments.all())
        if assignments:
            handlers_text = ", ".join(
                f"{a.user.last_name} {a.user.first_name}".strip() or a.user.username + f" ({a.get_role_display()})"
                for a in assignments
            )
        else:
            handlers_text = "Chưa phân công"

        created_time_str = timezone.localtime(submission.created_at).strftime("%d/%m/%Y %H:%M")

        attachments = self.collect_submission_attachments(submission)
        att_count = len(attachments)

        detail_text = f"""📋 CHI TIẾT HỒ SƠ #{submission.id}
──────────────────
📁 Phân loại: {category_name}
👤 Người trình báo: {citizen_name}
📞 Số điện thoại: {phone}
📍 Địa chỉ: {address}
⏱ Thời gian xảy ra: {event_time}
🗺 Địa điểm: {location}
👥 Người liên quan: {related}
⚡ Mức độ khẩn: {urgency} (Độ ưu tiên: {priority})
📊 Trạng thái: {status_display}
👮 Cán bộ phụ trách: {handlers_text}
📅 Tiếp nhận lúc: {created_time_str}

📝 Tóm tắt:
{submission.summary or 'Chưa có tóm tắt'}

📄 Nội dung phản ánh:
{submission.content or 'Không có nội dung'}

📎 Tài liệu đính kèm: {att_count} tệp/hình ảnh/video."""

        if att_count > 0:
            detail_text += "\n\n(Hệ thống đang gửi kèm các tài liệu, hình ảnh bên dưới...)"
        else:
            detail_text += "\n\n(Hồ sơ không có tệp hoặc hình ảnh đính kèm)"

        return True, detail_text.strip(), submission

    def collect_submission_attachments(self, submission: IntakeSubmission) -> List[Dict[str, Any]]:
        """
        Thu thập toàn bộ tệp, hình ảnh, video đính kèm liên quan đến hồ sơ.
        """
        attachments: List[Dict[str, Any]] = []
        seen_urls = set()

        def add_att(att_dict: Dict[str, Any]):
            if not isinstance(att_dict, dict):
                return
            url = att_dict.get("url") or att_dict.get("link")
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            att_type = att_dict.get("type") or "file"
            thumbnail = att_dict.get("thumbnail") or url
            name = att_dict.get("name") or att_dict.get("filename") or ""
            attachments.append({
                "type": att_type,
                "url": url,
                "thumbnail": thumbnail,
                "name": name,
            })

        # 1. Từ submission.message nếu có
        if submission.message and submission.message.attachments:
            for item in submission.message.attachments:
                add_att(item)

        # 2. Từ cuộc hội thoại (Conversation)
        if submission.conversation_id:
            # Xác định phạm vi thời gian để tránh lấy nhầm tệp của hồ sơ khác trong cùng hội thoại
            prev_sub = (
                IntakeSubmission.objects.filter(
                    conversation=submission.conversation,
                    created_at__lt=submission.created_at,
                )
                .order_by("-created_at")
                .first()
            )
            next_sub = (
                IntakeSubmission.objects.filter(
                    conversation=submission.conversation,
                    created_at__gt=submission.created_at,
                )
                .order_by("created_at")
                .first()
            )

            messages_qs = Message.objects.filter(
                conversation=submission.conversation,
            ).exclude(attachments=[])

            if prev_sub:
                messages_qs = messages_qs.filter(sent_at__gte=prev_sub.created_at)
            if next_sub:
                messages_qs = messages_qs.filter(sent_at__lt=next_sub.created_at)

            for msg in messages_qs.order_by("sent_at"):
                for item in (msg.attachments or []):
                    add_att(item)

        # 3. Từ raw_extracted_data nếu có
        raw_data = submission.raw_extracted_data or {}
        extra_data = raw_data.get("extra_data") or {}
        if isinstance(extra_data, dict):
            extra_atts = extra_data.get("attachments") or []
            if isinstance(extra_atts, list):
                for item in extra_atts:
                    if isinstance(item, dict):
                        add_att(item)

        return attachments
