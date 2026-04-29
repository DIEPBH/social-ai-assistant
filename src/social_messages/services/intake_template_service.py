class IntakeTemplateService:
    MAIN_MENU = (
    "CÔNG AN TỈNH THÁI NGUYÊN\n"
    "Hệ thống tiếp nhận và hỗ trợ thông tin\n\n"
    "Vui lòng chọn nhóm nội dung cần hỗ trợ:\n\n"
    "1. Khiếu nại\n"
    "2. Tin báo tội phạm\n"
    "3. Hỏi thủ tục hành chính\n\n"
    "Vui lòng trả lời bằng số 1, 2 hoặc 3."
)

    MAIN_MENU_BUTTONS = [
        {
            "title": "Khiếu nại",
            "type": "oa.query.show",
            "payload": "1",
        },
        {
            "title": "Tin báo tội phạm",
            "type": "oa.query.show",
            "payload": "2",
        },
        {
            "title": "Hỏi thủ tục hành chính",
            "type": "oa.query.show",
            "payload": "3",
        },
    ]

    INVALID_MENU = (
        "Lựa chọn chưa hợp lệ.\n\n"
        "Vui lòng chọn một trong các nội dung sau:\n"
        "1. Khiếu nại\n"
        "2. Tin báo tội phạm\n"
        "3. Hỏi thủ tục hành chính\n\n"
        "Bạn chỉ cần trả lời bằng số 1, 2 hoặc 3."
    )

    TEMPLATES = {
        "complaint": (
            "MẪU TIẾP NHẬN KHIẾU NẠI\n\n"
            "Vui lòng cung cấp thông tin theo mẫu dưới đây:\n\n"
            "1. Họ và tên:\n"
            "2. Số điện thoại:\n"
            "3. Địa chỉ liên hệ:\n"
            "4. Nội dung khiếu nại:\n"
            "5. Thời gian xảy ra vụ việc:\n"
            "6. Địa điểm xảy ra vụ việc:\n"
            "7. Tài liệu, hình ảnh đính kèm nếu có:\n\n"
            "Bạn có thể sao chép mẫu này và điền thông tin trực tiếp vào tin nhắn."
        ),

        "crime_report": (
            "MẪU TIẾP NHẬN TIN BÁO TỘI PHẠM\n\n"
            "Vui lòng cung cấp thông tin càng đầy đủ càng tốt:\n\n"
            "1. Họ và tên người báo tin:\n"
            "2. Số điện thoại liên hệ:\n"
            "3. Địa chỉ liên hệ:\n"
            "4. Nội dung vụ việc:\n"
            "5. Thời gian phát hiện hoặc xảy ra vụ việc:\n"
            "6. Địa điểm xảy ra vụ việc:\n"
            "7. Đối tượng liên quan nếu biết:\n"
            "8. Mức độ khẩn cấp:\n"
            "9. Tài liệu, hình ảnh, video đính kèm nếu có:\n\n"
            "Trường hợp vụ việc đang diễn ra hoặc có nguy hiểm trực tiếp, vui lòng liên hệ ngay cơ quan công an gần nhất."
        ),

        "admin_procedure": (
            "MẪU HỎI THỦ TỤC HÀNH CHÍNH\n\n"
            "Vui lòng cung cấp thông tin theo mẫu dưới đây:\n\n"
            "1. Họ và tên:\n"
            "2. Số điện thoại:\n"
            "3. Thủ tục cần hỏi:\n"
            "4. Nội dung cần hỗ trợ:\n"
            "5. Đơn vị hoặc địa phương liên quan:\n\n"
            "Hệ thống sẽ tiếp nhận và phân loại nội dung để hỗ trợ bạn."
        ),
    }

    @classmethod
    def get_main_menu(cls):
        return cls.MAIN_MENU

    @classmethod
    def get_invalid_menu(cls):
        return cls.INVALID_MENU

    @classmethod
    def get_template(cls, intent: str):
        return cls.TEMPLATES.get(intent, cls.INVALID_MENU)
    
    @classmethod
    def get_main_menu_buttons(cls):
        return cls.MAIN_MENU_BUTTONS