import hashlib
import logging
import re
import urllib.parse
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.db.models import Count, Q
from django.utils import timezone

from social_messages.models import AdministrativeArea, IntakeSubmission

logger = logging.getLogger(__name__)


class CivicHeatmapService:
    """
    Dịch vụ Giám sát Không gian Bản đồ GIS & Định vị Tọa độ Hồ sơ Tiếp nhận:
    1. Định vị chuẩn xác theo địa chỉ thực tế (Tỉnh Thái Nguyên, Hà Nội và toàn quốc).
    2. Hỗ trợ VietMap Geocoding API (Make-in-Vietnam) + Gazetteer đa tầng độ chính xác cao.
    3. Trích xuất hồ sơ thật (Tin báo tội phạm & Khiếu nại) phục vụ chỉ huy tuần tra, phòng ngừa nghiệp vụ.
    """

    # Bộ nhớ đệm Geocoding nội bộ để tối ưu hiệu năng và hạn chế gọi lặp lại API
    _GEOCACHE: Dict[str, Tuple[float, float, str]] = {}
    _PLACE_CACHE: Dict[str, Tuple[float, float, str]] = {}

    # Từ điển Tỉnh/Thành phố Việt Nam (Tọa độ trung tâm)
    VIETNAM_PROVINCES: Dict[str, Tuple[float, float]] = {
        "thái nguyên": (21.5928, 105.8442),
        "thai nguyen": (21.5928, 105.8442),
        "hà nội": (21.0285, 105.8542),
        "ha noi": (21.0285, 105.8542),
        "hồ chí minh": (10.7769, 106.6958),
        "tp.hcm": (10.7769, 106.6958),
        "sài gòn": (10.7769, 106.6958),
        "đà nẵng": (16.0544, 108.2022),
        "hải phòng": (20.8449, 106.6881),
        "cần thơ": (10.0452, 105.7469),
        "lâm đồng": (11.9404, 108.4583),
        "đắk nông": (12.0000, 107.6833),
        "cao bằng": (22.6667, 106.2500),
        "hưng yên": (20.6464, 106.0511),
        "phú thọ": (21.3228, 105.2280),
        "bắc ninh": (21.1861, 106.0763),
        "thái bình": (20.4463, 106.3366),
        "nghệ an": (18.6796, 105.6813),
        "kiên giang": (10.0139, 105.0809),
        "phú quốc": (10.2289, 103.9572),
        "bắc kạn": (22.1469, 105.8347),
        "lạng sơn": (21.8533, 106.7618),
        "tuyên quang": (21.8236, 105.2181),
        "vĩnh phúc": (21.3609, 105.5474),
        "bắc giang": (21.2731, 106.1946),
        "quảng ninh": (20.9505, 107.0734),
        "hà nam": (20.5453, 105.9126),
        "nam định": (20.4345, 106.1776),
        "ninh bình": (20.2506, 105.9745),
        "thanh hóa": (19.8067, 105.7852),
        "hà tĩnh": (18.3560, 105.9058),
        "quảng bình": (17.4690, 106.6226),
        "quảng trị": (16.7456, 107.1855),
        "thừa thiên huế": (16.4637, 107.5909),
        "quảng nam": (15.5394, 108.0190),
        "quảng ngãi": (15.1205, 108.7923),
        "bình định": (14.1667, 108.9000),
        "phú yên": (13.0882, 109.0929),
        "khánh hòa": (12.2388, 109.1967),
        "ninh thuận": (11.5647, 108.9882),
        "bình thuận": (11.0904, 108.0722),
        "kon tum": (14.3497, 108.0005),
        "gia lai": (13.9833, 108.0000),
        "đắk lắk": (12.6667, 108.0333),
        "bình phước": (11.7511, 106.9042),
        "tây ninh": (11.3104, 106.0983),
        "bình dương": (11.1667, 106.6667),
        "đồng nai": (11.0500, 107.1667),
        "bà rịa": (10.4962, 107.1685),
        "vũng tàu": (10.3460, 107.0843),
        "long an": (10.5333, 106.4167),
        "tiền giang": (10.4167, 106.3333),
        "bến tre": (10.2434, 106.3756),
        "trà vinh": (9.9347, 106.3455),
        "vĩnh long": (10.2537, 105.9722),
        "đồng tháp": (10.4578, 105.6328),
        "an giang": (10.3708, 105.4372),
        "hậu giang": (9.7844, 105.4701),
        "sóc trăng": (9.6033, 105.9800),
        "bạc liêu": (9.2941, 105.7278),
        "cà mau": (9.1769, 105.1524),
        "hòa bình": (20.8172, 105.3376),
        "sơn la": (21.3283, 103.9148),
        "điện biên": (21.3869, 103.0232),
        "lai châu": (22.3964, 103.4684),
        "lào cai": (22.4856, 103.9707),
        "yên bái": (21.7167, 104.8667),
        "hà giang": (22.8233, 104.9836),
    }

    # Gazetteer chi tiết các địa bàn trọng điểm chuẩn hóa theo mô hình 2 cấp: Tỉnh - Xã (không còn cấp huyện)
    LOCALITY_GAZETTEER = [
        # --- Tuyến đường, ngõ xóm & địa danh -> Xã/Phường/Thị trấn cụ thể tại Tỉnh Thái Nguyên ---
        (["gang thép", "thpt gang thép", "tích lương", "tich luong"], "Phường Tích Lương (Thái Nguyên)", 21.5520, 105.8600),
        (["dương tự minh", "quan triều", "quan trieu", "tân long", "cầu tân long"], "Phường Quan Triều (Thái Nguyên)", 21.6250, 105.8200),
        (["nguyễn đình chiểu", "phan đình phùng", "phan dinh phung", "hoàng văn thụ", "lương ngọc quyến"], "Phường Phan Đình Phùng (Thái Nguyên)", 21.5870, 105.8360),
        (["linh sơn", "linh son"], "Phường Linh Sơn (Thái Nguyên)", 21.6150, 105.8750),
        (["quyết thắng", "quyet thang"], "Phường Quyết Thắng (Thái Nguyên)", 21.5790, 105.8010),
        (["gia sàng", "gia sang"], "Phường Gia Sàng (Thái Nguyên)", 21.5750, 105.8550),
        (["bá xuyên", "ba xuyen"], "Phường Bá Xuyên (Thái Nguyên)", 21.5050, 105.8400),
        (["bách quang", "bach quang"], "Phường Bách Quang (Thái Nguyên)", 21.4800, 105.8500),
        (["sông công", "song cong", "thắng lợi", "kho j&t sông công"], "Phường Sông Công (Thái Nguyên)", 21.4925, 105.8193),
        (["phổ yên", "pho yen", "ba hàng", "ba hang"], "Phường Phổ Yên (Thái Nguyên)", 21.4187, 105.8741),
        (["phúc thuận", "phuc thuan"], "Phường Phúc Thuận (Thái Nguyên)", 21.4400, 105.7800),
        (["trung thành", "trung thanh"], "Phường Trung Thành (Thái Nguyên)", 21.3800, 105.8700),
        (["vạn xuân", "van xuan"], "Phường Vạn Xuân (Thái Nguyên)", 21.4250, 105.8650),
        (["bắc kạn", "bac kan"], "Phường Bắc Kạn (Thái Nguyên)", 22.1469, 105.8347),
        (["đức xuân", "duc xuan"], "Phường Đức Xuân (Thái Nguyên)", 22.1550, 105.8450),
        
        # --- Các Xã trong 92 đơn vị chính thức của Tỉnh Thái Nguyên ---
        (["trại cài", "trại cau", "trai cau"], "Xã Trại Cau (Thái Nguyên)", 21.6700, 105.9100),
        (["khe mo"], "Xã Văn Hán (Thái Nguyên)", 21.6500, 105.9500),
        (["nam hoà", "nam hòa"], "Xã Nam Hòa (Thái Nguyên)", 21.6150, 105.9150),
        (["hóa thượng", "đồng hỷ", "dong hy"], "Xã Đồng Hỷ (Thái Nguyên)", 21.6350, 105.8820),
        (["la hiên", "la hien", "xóm phố"], "Xã La Hiên (Thái Nguyên)", 21.7100, 105.9600),
        (["thần sa", "than sa"], "Xã Thần Sa (Thái Nguyên)", 21.7850, 105.8900),
        (["đình cả", "võ nhai", "vo nhai"], "Xã Võ Nhai (Thái Nguyên)", 21.7583, 105.9922),
        (["tràng xá", "trang xa"], "Xã Tràng Xá (Thái Nguyên)", 21.6800, 106.0400),
        (["dân tiến", "dan tien"], "Xã Dân Tiến (Thái Nguyên)", 21.6800, 105.9800),
        (["nghinh tường", "nghinh tuong"], "Xã Nghinh Tường (Thái Nguyên)", 21.8500, 105.9800),
        (["sảng mộc", "sang moc"], "Xã Sảng Mộc (Thái Nguyên)", 21.9100, 105.9600),
        (["khuôn muống", "khuon muong"], "Xã Phú Xuyên (Thái Nguyên)", 21.6787, 105.5177),
        (["phú xuyên", "phu xuyen"], "Xã Phú Xuyên (Thái Nguyên)", 21.6641, 105.5541),
        (["yên lãng", "yen lang"], "Xã Phú Xuyên (Thái Nguyên)", 21.6849, 105.5171),
        (["kiến linh", "phú lạc", "phúc lạc", "phu lac"], "Xã Phú Lạc (Thái Nguyên)", 21.6873, 105.6072),
        (["đại phúc", "phúc xuân", "xac đại phúc"], "Xã Đại Phúc (Thái Nguyên)", 21.5800, 105.7400),
        (["tân cương", "tan cuong"], "Xã Tân Cương (Thái Nguyên)", 21.5400, 105.7700),
        (["hùng sơn", "đại từ", "dai tu"], "Xã Đại Từ (Thái Nguyên)", 21.6384, 105.6375),
        (["an khánh", "an khanh"], "Xã An Khánh (Thái Nguyên)", 21.6200, 105.7100),
        (["la bằng", "la bang"], "Xã La Bằng (Thái Nguyên)", 21.6000, 105.5900),
        (["quân chu", "quan chu"], "Xã Quân Chu (Thái Nguyên)", 21.5000, 105.7000),
        (["chợ chu", "cho chu", "định hoá", "định hóa", "dinh hoa"], "Xã Định Hóa (Thái Nguyên)", 21.9080, 105.6480),
        (["bình thành", "binh thanh"], "Xã Bình Thành (Thái Nguyên)", 21.8200, 105.7100),
        (["bình yên", "binh yen"], "Xã Bình Yên (Thái Nguyên)", 21.8700, 105.6500),
        (["trung hội", "trung hoi"], "Xã Trung Hội (Thái Nguyên)", 21.8850, 105.6650),
        (["lam vỹ", "lam vy"], "Xã Lam Vỹ (Thái Nguyên)", 21.9550, 105.6350),
        (["kim phượng", "kim phuong"], "Xã Kim Phượng (Thái Nguyên)", 21.9200, 105.6700),
        (["phú đình", "phu dinh"], "Xã Phú Đình (Thái Nguyên)", 21.8500, 105.6200),
        (["đu", "giang tiên", "phú lương", "phu luong"], "Xã Phú Lương (Thái Nguyên)", 21.7500, 105.7500),
        (["vô tranh", "vo tranh"], "Xã Vô Tranh (Thái Nguyên)", 21.7100, 105.8100),
        (["hợp thành", "hop thanh"], "Xã Hợp Thành (Thái Nguyên)", 21.7300, 105.7900),
        (["hương sơn", "phú bình", "phu binh", "la sơn"], "Xã Phú Bình (Thái Nguyên)", 21.4833, 105.9833),
        (["kha sơn", "kha son"], "Xã Kha Sơn (Thái Nguyên)", 21.4600, 106.0100),
        (["điềm thụy", "diem thuy"], "Xã Điềm Thụy (Thái Nguyên)", 21.4700, 105.9200),
        (["tân khánh", "tan khanh"], "Xã Tân Khánh (Thái Nguyên)", 21.5400, 106.0400),
        (["thành công", "thanh cong"], "Xã Thành Công (Thái Nguyên)", 21.3650, 105.8400),
        
        # --- Các Xã khu vực Bắc Kạn sáp nhập ---
        (["chợ rã", "cho ra", "đồng tâm"], "Xã Chợ Rã (Thái Nguyên)", 22.4200, 105.7100),
        (["chợ mới", "cho moi", "đèo vai"], "Xã Chợ Mới (Thái Nguyên)", 21.8500, 105.7800),
        (["chợ đồn", "cho don"], "Xã Chợ Đồn (Thái Nguyên)", 22.1500, 105.6000),
        (["ba bể", "ba be"], "Xã Ba Bể (Thái Nguyên)", 22.4100, 105.7000),
        (["bạch thông", "bach thong"], "Xã Bạch Thông (Thái Nguyên)", 22.2500, 105.8400),
        (["na rì", "na ri"], "Xã Na Rì (Thái Nguyên)", 22.1500, 106.0500),
        (["ngân sơn", "ngan son"], "Xã Ngân Sơn (Thái Nguyên)", 22.4200, 105.9800),
        (["thượng quan", "thuong quan"], "Xã Thượng Quan (Thái Nguyên)", 22.2500, 105.9500),
        (["đồng phúc", "dong phuc", "lủng mình"], "Xã Đồng Phúc (Thái Nguyên)", 22.1800, 105.8500),

        # --- Các Xã / Phường tại Thành phố Hà Nội ---
        (["dương liễu", "dương hòa", "hoài đức"], "Xã Dương Liễu (Hà Nội)", 21.0180, 105.7050),
        (["hát môn", "hiệp lộc", "phúc thọ"], "Xã Hát Môn (Hà Nội)", 21.0920, 105.5780),
        (["sóc sơn", "soc son", "tiên dược"], "Xã Tiên Dược (Hà Nội)", 21.2850, 105.8450),
        (["flc garden city", "đại mỗ", "nam từ liêm"], "Phường Đại Mỗ (Hà Nội)", 20.9950, 105.7520),
        (["dịch vọng hậu", "duy tân"], "Phường Dịch Vọng Hậu (Hà Nội)", 21.0365, 105.7865),
        (["mai dịch", "hồ tùng mậu"], "Phường Mai Dịch (Hà Nội)", 21.0410, 105.7760),
        (["dịch vọng", "thành thái"], "Phường Dịch Vọng (Hà Nội)", 21.0315, 105.7940),
        (["nghĩa tân", "tô hiệu"], "Phường Nghĩa Tân (Hà Nội)", 21.0450, 105.7920),
        (["yên hòa", "trung kính"], "Phường Yên Hòa (Hà Nội)", 21.0180, 105.7950),
        (["trung hòa", "trần duy hưng"], "Phường Trung Hòa (Hà Nội)", 21.0080, 105.8010),

        # --- Các Xã / Phường tại các Tỉnh thành khác ---
        (["bạch đằng", "hoà an", "cao bằng"], "Xã Bạch Đằng (Cao Bằng)", 22.6667, 106.2500),
        (["đắk ri", "krông nô", "lâm đồng"], "Xã Đắk Ri (Lâm Đồng)", 11.9404, 108.4583),
        (["ân thi", "gia ngọc", "hưng yên"], "Xã Gia Ngọc (Hưng Yên)", 20.8200, 106.0900),
        (["tu vũ", "vườn vua", "phú thọ"], "Xã Tu Vũ (Phú Thọ)", 21.1800, 105.3200),
        (["diên hồng", "tp.hcm", "hồ chí minh", "sài gòn"], "Phường Diên Hồng (TP.HCM)", 10.7769, 106.6670),
        (["nguyễn trung trực", "phú quốc"], "Phường Dương Đông (Kiên Giang)", 10.2289, 103.9572),
        (["bến xe thái bình"], "Phường Bồ Xuyên (Thái Bình)", 20.4463, 106.3366),
        (["bắc ninh"], "Phường Vũ Ninh (Bắc Ninh)", 21.1861, 106.0763),
        (["bùi dương lịch", "thành phố vinh"], "Phường Quán Bàu (Nghệ An)", 18.6796, 105.6813),
    ]

    STREET_AREA_MAPPING = {
        "CG_MD": [
            "doãn kế thiện", "doan ke thien", "hồ tùng mậu", "ho tung mau",
            "lê đức thọ", "le duc tho", "mai dịch", "mai dich", "phạm văn đồng", "pham van dong"
        ],
        "CG_DVH": [
            "duy tân", "duy tan", "trần thái tông", "tran thai tong",
            "xuân thủy", "xuan thuy", "dịch vọng hậu", "dich vong hau", "phạm hùng", "pham hung", "tôn thất thuyết"
        ],
        "CG_DV": [
            "cầu giấy", "cau giay", "thành thái", "thanh thai", "khúc thừa dụ", "khuc thua du",
            "dịch vọng", "dich vong", "trương công giai", "nguyễn văn huyên"
        ],
        "CG_NT": [
            "tô hiệu", "to hieu", "nghĩa tân", "nghia tan", "hoàng quốc việt", "hoang quoc viet",
            "nguyễn phong sắc", "nguyen phong sac", "trần cung"
        ],
        "CG_YHO": [
            "trung kính", "trung kinh", "yên hòa", "yen hoa", "dương đình nghệ", "duong dinh nghe",
            "hạ yên quyết", "hoa bằng", "vũ phạm hàm"
        ],
        "CG_TRH": [
            "trần duy hưng", "tran duy hung", "hoàng đạo thúy", "hoang dao thuy",
            "nguyễn thị định", "nguyen thi dinh", "trung hòa", "trung hoa", "nguyễn chánh", "vũ phạm hàm"
        ],
    }

    @classmethod
    def _geocode_via_vietmap(cls, query: str, api_key: str) -> Optional[Tuple[float, float, str]]:
        """
        Gọi VietMap Search API v3 & Place API (Bản đồ số Việt Nam) để phân giải tọa độ chính xác.
        Có cache nội bộ để hạn chế gọi trùng lặp và tiết kiệm quota.
        """
        if not query or not api_key:
            return None

        clean_query = re.sub(r"[^\w\s\-\,\.\/]", " ", query).strip()
        if len(clean_query) < 3:
            return None

        cache_key = hashlib.md5(f"{clean_query}_{api_key[:6]}".encode("utf-8")).hexdigest()
        if cache_key in cls._GEOCACHE:
            return cls._GEOCACHE[cache_key]

        try:
            url = f"https://maps.vietmap.vn/api/search/v3?apikey={api_key.strip()}&text={urllib.parse.quote(clean_query)}"
            resp = requests.get(url, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("data") or data.get("results") or []

                for item in items:
                    lat = item.get("lat") or item.get("latitude")
                    lng = item.get("lng") or item.get("longitude")
                    display = item.get("display") or item.get("name") or clean_query

                    # 1. Nếu item có lat và lng trực tiếp
                    if lat and lng:
                        lat_f = float(lat)
                        lng_f = float(lng)
                        cls._GEOCACHE[cache_key] = (lat_f, lng_f, display)
                        return (lat_f, lng_f, display)

                    # 2. VietMap Search v3 trả về ref_id -> Gọi Place API để lấy tọa độ chuẩn xác
                    ref_id = item.get("ref_id")
                    if ref_id:
                        if ref_id in cls._PLACE_CACHE:
                            cached_res = cls._PLACE_CACHE[ref_id]
                            cls._GEOCACHE[cache_key] = cached_res
                            return cached_res

                        p_url = f"https://maps.vietmap.vn/api/place/v3?apikey={api_key.strip()}&refid={ref_id}"
                        p_resp = requests.get(p_url, timeout=2.5)
                        if p_resp.status_code == 200:
                            p_data = p_resp.json()
                            p_lat = p_data.get("lat") or p_data.get("latitude")
                            p_lng = p_data.get("lng") or p_data.get("longitude")
                            p_display = p_data.get("display") or p_data.get("name") or display
                            if p_lat and p_lng:
                                lat_f = float(p_lat)
                                lng_f = float(p_lng)
                                res = (lat_f, lng_f, p_display)
                                cls._PLACE_CACHE[ref_id] = res
                                cls._GEOCACHE[cache_key] = res
                                return res
        except Exception as e:
            logger.warning("Lỗi gọi VietMap Geocoding API cho '%s': %s", clean_query, e)

        return None

    @classmethod
    def resolve_submission_coordinates(
        cls,
        submission: IntakeSubmission,
        vietmap_api_key: str = ""
    ) -> Tuple[float, float, str]:
        """
        Xác định tọa độ GPS và tên địa bàn chuẩn xác cho hồ sơ phản ánh:
        1. Ưu tiên tọa độ GPS có sẵn trong raw_extracted_data.
        2. Nếu có địa chỉ/địa điểm cụ thể (thôn, xóm, tuyến đường...):
           Thử phân giải qua VietMap API v3 hoặc Gazetteer chi tiết để lấy tọa độ chính xác.
        3. Nếu hồ sơ đã gán sẵn AdministrativeArea: sử dụng tọa độ chuẩn của xã/phường.
        4. Gazetteer từ điển đa tầng bao phủ tỉnh Thái Nguyên, Hà Nội và 63 tỉnh thành.
        5. Tự động định vị đúng địa bàn cho vụ việc báo án qua mạng xã hội.
        """
        # 1. Tọa độ có sẵn trong raw_extracted_data
        raw_data = submission.raw_extracted_data or {}
        if isinstance(raw_data, dict):
            lat = raw_data.get("latitude") or raw_data.get("lat")
            lng = raw_data.get("longitude") or raw_data.get("lng")
            if lat and lng:
                try:
                    return (float(lat), float(lng), submission.address or "Tọa độ GPS hồ sơ")
                except (ValueError, TypeError):
                    pass

        # Thu thập các chuỗi địa chỉ
        loc_str = (submission.event_location or "").strip()
        addr_str = (submission.address or "").strip()
        content_str = (submission.content or "")[:300].strip()
        summary_str = (submission.summary or "").strip()

        # Tổng hợp văn bản để phân tích địa bàn
        combined_text = f"{loc_str} {addr_str} {summary_str} {content_str}".lower()

        # Danh sách từ khóa mơ hồ không phải địa chỉ thực địa
        vague_keywords = [
            "mạng xã hội", "mxh", "facebook", "tiktok", "tik tok", "zalo", "mess", "messenger",
            "chưa xảy ra", "chua xay ra", "không rõ", "khong ro", "không có", "khong co",
            "chưa rõ", "chua ro", "không gian mạng", "khong gian mang", "online", "tại nhà", "ở nhà",
            "nhà riêng", "qua mạng", "trên mạng", "qua tin nhắn", "live", "qua nhóm", "hội nhóm"
        ]

        # 2. Thử phân giải địa chỉ chi tiết bằng VietMap API v3 nếu có cấu hình key
        if vietmap_api_key:
            candidate_queries = []
            for q in [addr_str, loc_str]:
                if not q or len(q) < 4:
                    continue
                q_lower = q.lower()
                # Bỏ qua hoàn toàn nếu chứa từ khóa không gian mạng / mơ hồ
                if any(kw in q_lower for kw in vague_keywords):
                    continue
                # Bỏ qua nếu chỉ là số điện thoại hoặc giờ
                if re.match(r"^(\d{9,11}|\d{1,2}[:h]\d{1,2})$", q.strip()):
                    continue

                candidate_queries.append(q)

                # Sinh biến thể tinh gọn loại bỏ các từ nhiễu hành chính như "đặc khu", "khu phố X", "kp X"
                cleaned_q = re.sub(r"\b(đặc khu|khu phố\s*\d+|kp\s*\d+)\b", "", q, flags=re.IGNORECASE)
                cleaned_q = re.sub(r"\s+", " ", cleaned_q).strip()
                # Xử lý đặc thù Phú Quốc (người dân hay viết nhầm 'đặc khu phú quốc, an giang' thay vì Kiên Giang)
                if "phú quốc" in q_lower:
                    cleaned_pq = re.sub(r"\ban giang\b", "", cleaned_q, flags=re.IGNORECASE).strip().strip(",")
                    cleaned_pq = re.sub(r"\s+", " ", cleaned_pq).strip()
                    if cleaned_pq and cleaned_pq not in candidate_queries:
                        candidate_queries.append(cleaned_pq)
                        candidate_queries.append(f"{cleaned_pq}, Kiên Giang")
                elif cleaned_q != q and len(cleaned_q) >= 4 and cleaned_q not in candidate_queries:
                    candidate_queries.append(cleaned_q)

                # Nếu có submission.area và query chưa có tên tỉnh, bổ sung context để Geocode chuẩn
                if submission.area and "thái nguyên" not in q_lower:
                    candidate_queries.append(f"{q}, {submission.area.name}, Thái Nguyên")
                elif "thái nguyên" not in q_lower and not any(p in q_lower for p in cls.VIETNAM_PROVINCES) and "phú quốc" not in q_lower:
                    candidate_queries.append(f"{q}, Thái Nguyên")

            for query in candidate_queries:
                geo_res = cls._geocode_via_vietmap(query, vietmap_api_key)
                if geo_res:
                    lat_res, lng_res, display_res = geo_res
                    display_lower = display_res.lower()

                    # Kiểm tra xung đột địa danh then chốt:
                    # Nếu query công dân có nhắc đến Phú Quốc nhưng kết quả VietMap không thuộc Phú Quốc / Kiên Giang (ví dụ trả về Bến Lức, Long An)
                    if "phú quốc" in query.lower() and not any(k in display_lower for k in ["phú quốc", "phu quoc", "kiên giang", "kien giang"]):
                        continue

                    if submission.area:
                        # Kiểm tra tính tương thích địa lý (trong phạm vi ~35km của xã/tỉnh)
                        dist_lat = abs(lat_res - submission.area.latitude)
                        dist_lng = abs(lng_res - submission.area.longitude)
                        if dist_lat < 0.35 and dist_lng < 0.35:
                            return geo_res
                    else:
                        # Nếu chưa có submission.area:
                        # Chỉ chấp nhận nếu nằm trong tỉnh Thái Nguyên hoặc có địa danh ngoại tỉnh rõ ràng
                        is_other_province = any(
                            p in query.lower() for p in cls.VIETNAM_PROVINCES
                            if p not in ["thái nguyên", "thai nguyen"]
                        ) or ("phú quốc" in query.lower())
                        in_tn = (21.2 <= lat_res <= 22.8) and (105.4 <= lng_res <= 106.6)
                        if in_tn or is_other_province:
                            return geo_res

        # 3. Nếu hồ sơ đã gán sẵn area trong DB (ví dụ test case hoặc đã phân vùng)
        if submission.area:
            return (submission.area.latitude, submission.area.longitude, submission.area.name)

        # 4. Phân giải qua Gazetteer chi tiết (Thái Nguyên, Hà Nội, các địa bàn xuất hiện trong hồ sơ)
        for kws, name, lat, lng in cls.LOCALITY_GAZETTEER:
            if any(kw in combined_text for kw in kws):
                return (lat, lng, name)

        # 5. Phân giải qua tên Tỉnh/Thành phố toàn quốc (63 tỉnh thành)
        for prov_name, (lat, lng) in cls.VIETNAM_PROVINCES.items():
            if prov_name in combined_text:
                return (lat, lng, f"Tỉnh/TP {prov_name.title()}")

        # 6. Kiểm tra tên đường Cầu Giấy (hỗ trợ dữ liệu demo Cầu Giấy)
        for code, keywords in cls.STREET_AREA_MAPPING.items():
            if any(kw in combined_text for kw in keywords):
                area = AdministrativeArea.objects.filter(code=code, is_active=True).first()
                if area:
                    return (area.latitude, area.longitude, area.name)

        # 7. Nhận diện tin báo không gian mạng / chưa xác định địa bàn cụ thể:
        is_online_report = any(vp in combined_text for vp in [
            "mạng xã hội", "mxh", "facebook", "tiktok", "zalo", "mess",
            "online", "không gian mạng", "qua mạng", "trên mạng"
        ])
        if is_online_report and not submission.area:
            return (21.5950, 105.8410, "Chưa xác định địa bàn cụ thể (Không gian mạng)")

        # 8. Mặc định cấp Xã trọng tâm địa bàn phục vụ:
        # Nếu văn bản có nhắc đến Hà Nội thì về Phường Dịch Vọng Hậu, ngược lại về Phường Hoàng Văn Thụ (Thái Nguyên)
        if any(h in combined_text for h in ["hà nội", "ha noi", "cầu giấy", "cau giay"]):
            return (21.0365, 105.7865, "Phường Dịch Vọng Hậu (Hà Nội)")

        return (21.5950, 105.8410, "Phường Hoàng Văn Thụ (Thái Nguyên)")

    @classmethod
    def resolve_area(
        cls,
        text: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[AdministrativeArea]:
        """
        Nhận diện tự động địa bàn hành chính cấp Xã (Phường / Xã):
        - Mô hình 2 cấp: Tỉnh - Xã.
        - TUYỆT ĐỐI KHÔNG GÁN ÉP: Nếu tin báo phát sinh trên không gian mạng,
          hoặc không chứa dữ liệu địa chỉ xã/phường cụ thể -> trả về None (Chưa xác định địa bàn).
        """
        # 1. Kiểm tra GPS Point-in-Polygon nếu có tọa độ chính xác
        if latitude is not None and longitude is not None:
            area = cls._find_area_by_coordinates(latitude, longitude)
            if area:
                return area

        if not text or not isinstance(text, str):
            return None

        clean_text = text.lower()

        # 2. Kiểm tra loại trừ: Nếu tin báo chỉ nói về mạng xã hội, không gian mạng, chưa xảy ra
        vague_patterns = [
            "chưa xảy ra", "chua xay ra", "không rõ", "khong ro",
            "không gian mạng", "khong gian mang", "qua mạng", "qua mang",
            "trên mạng", "tren mang", "online", "facebook", "tiktok", "zalo",
            "mxh", "trao đổi qua mxh", "tại nhà riêng tại tỉnh tochigi", "nước ngoài"
        ]

        # Kiểm tra xem có từ khóa địa danh cụ thể nào trong Gazetteer không
        has_specific_locality = False
        for keywords, target_name, _, _ in cls.LOCALITY_GAZETTEER:
            # Bỏ qua từ khóa tỉnh chung chung như "thái nguyên", "hà nội"
            if keywords in (["thái nguyên", "thai nguyen"], ["hà nội", "ha noi"]):
                continue
            if any(kw in clean_text for kw in keywords):
                has_specific_locality = True
                clean_name = re.sub(r"\s*\(.*?\)", "", target_name).strip()
                area = AdministrativeArea.objects.filter(name__iexact=clean_name, is_active=True).first()
                if area:
                    return area

        # Nếu không có địa danh cụ thể và có dấu hiệu tin báo trên mạng/không rõ nơi xảy ra
        if not has_specific_locality and any(vp in clean_text for vp in vague_patterns):
            return None

        # 3. Đối chiếu tên đường / phố đặc thù (hỗ trợ Cầu Giấy demo nếu có)
        for code, keywords in cls.STREET_AREA_MAPPING.items():
            if any(kw in clean_text for kw in keywords):
                area = AdministrativeArea.objects.filter(code=code, is_active=True).first()
                if area:
                    return area

        # 4. Đối chiếu trực tiếp với toàn bộ Phường / Xã trong DB
        all_areas = AdministrativeArea.objects.filter(is_active=True)
        for area in all_areas:
            # Tên đầy đủ
            if area.name.lower() in clean_text:
                return area
            # Tên bỏ tiền tố "Phường", "Xã", "Thị trấn"
            core_name = re.sub(r"^(phường|xã|thị trấn)\s+", "", area.name, flags=re.IGNORECASE).strip().lower()
            if len(core_name) >= 4 and core_name in clean_text:
                # Tránh các từ ngắn thông dụng gây dương tính giả
                if core_name not in ["thắng", "minh", "yên", "bình", "phương", "hòa", "hùng", "long"]:
                    return area

        # 5. Nếu chỉ nhắc đến Tỉnh Thái Nguyên hoặc Hà Nội mà không có Xã/Phường cụ thể:
        # TUYỆT ĐỐI KHÔNG ÉP GÁN VỀ HOÀNG VĂN THỤ HOẶC DỊCH VỌNG HẬU!
        # Trả về None để ghi nhận là Chưa xác định địa bàn cụ thể
        return None

    @classmethod
    def _find_area_by_coordinates(cls, lat: float, lng: float) -> Optional[AdministrativeArea]:
        """Kiểm tra điểm (lat, lng) nằm trong đa giác GeoJSON nào (Ray Casting)."""
        areas = AdministrativeArea.objects.filter(is_active=True)
        for area in areas:
            poly = area.geojson_polygon
            if not poly or poly.get("type") != "Polygon":
                continue
            coords = poly.get("coordinates", [])
            if not coords or not coords[0]:
                continue
            ring = coords[0]  # List of [lng, lat]
            if cls._point_in_polygon(lng, lat, ring):
                return area
        return None

    @staticmethod
    def _point_in_polygon(x: float, y: float, poly: List[List[float]]) -> bool:
        """Thuật toán Ray-Casting kiểm tra điểm (x=lng, y=lat) nằm trong đa giác."""
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @classmethod
    def get_heatmap_data(cls, days: int = 7, category_filter: str = "all") -> Dict[str, Any]:
        """
        Trích xuất dữ liệu không gian Tin báo Tội phạm & Khiếu nại từ hồ sơ thực tế
        trong model IntakeSubmission, hỗ trợ hiển thị chấm tròn trên bản đồ VietMap
        định vị chuẩn xác tại Thái Nguyên, Hà Nội và toàn quốc.
        """
        from social_messages.models import SystemConfig
        import os

        # 1. Đọc API Key VietMap
        vietmap_cfg = SystemConfig.objects.filter(key="VIETMAP_API_KEY", is_active=True).first()
        vietmap_api_key = (vietmap_cfg.value.strip() if vietmap_cfg else "") or os.getenv("VIETMAP_API_KEY", "")

        now = timezone.now()

        # 2. Truy vấn hồ sơ thực tế thuộc 2 nhóm nghiệp vụ: Tin báo tội phạm & Khiếu nại
        qs = IntakeSubmission.objects.filter(
            Q(category__code__in=["crime_report", "complaint"]) |
            Q(intent__in=["crime_report", "complaint"])
        )

        if days > 0:
            start_time = now - timedelta(days=days)
            qs = qs.filter(created_at__gte=start_time)

        # Lọc theo loại nghiệp vụ nếu có yêu cầu
        if category_filter == "crime":
            qs = qs.filter(Q(category__code="crime_report") | Q(intent="crime_report"))
        elif category_filter == "complaint":
            qs = qs.filter(Q(category__code="complaint") | Q(intent="complaint"))
        elif category_filter == "completed":
            qs = qs.filter(processing_status="completed")

        subs = list(qs.select_related("category", "area").order_by("-created_at"))

        incidents = []
        crime_count = 0
        complaint_count = 0
        urgent_count = 0
        completed_count = 0

        # Thống kê theo từng địa bàn (khởi tạo với các AdministrativeArea có sẵn trong DB)
        areas = list(AdministrativeArea.objects.filter(is_active=True).order_by("name"))
        area_stat_map = {
            a.id: {
                "id": a.id,
                "name": a.name,
                "code": a.code,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "crime_count": 0,
                "complaint_count": 0,
                "completed_count": 0,
                "total": 0,
            }
            for a in areas
        }

        # Từ điển thống kê động theo địa bàn phát hiện thực tế
        dynamic_area_stats: Dict[str, Dict[str, Any]] = {}

        # 24 Khung giờ xảy ra sự việc (phục vụ tuần tra khép kín)
        hourly_counts = [0] * 24

        for s in subs:
            # Phân loại nghiệp vụ
            is_crime = (s.category and s.category.code == "crime_report") or (s.intent == "crime_report")
            incident_type = "crime" if is_crime else "complaint"
            type_label = "🚨 Tin báo tội phạm" if is_crime else "⚠️ Khiếu nại / Tố giác"

            if is_crime:
                crime_count += 1
            else:
                complaint_count += 1

            is_urgent = (s.urgency_level in ["high", "urgent", "critical"]) or (s.priority in ["high", "urgent", "critical"])
            if is_urgent:
                urgent_count += 1

            is_completed = (s.processing_status == "completed")
            if is_completed:
                completed_count += 1

            # Xác định màu sắc chấm (Incident Dot)
            if is_completed:
                dot_color = "#00e676"  # 🟢 Xanh lục - Đã giải quyết xong
                status_label = "Đã giải quyết"
            elif is_crime or is_urgent:
                dot_color = "#ff1744"  # 🔴 Đỏ neon - Tin tội phạm / Khẩn cấp
                status_label = "Khẩn cấp - Cần xử lý" if is_urgent else "Đang thụ lý"
            else:
                dot_color = "#ffab00"  # 🟡 Vàng hổ phách - Khiếu nại đang thụ lý
                status_label = "Đang xác minh" if s.processing_status == "in_progress" else "Chờ phân công"

            # Tên người dân bảo vệ theo Nghị định 13
            masked_name = s.citizen_name or "Người dân"
            if len(masked_name) > 3:
                masked_name = masked_name[:2] + "***" + masked_name[-1:]

            # Xác định địa bàn & Tọa độ ghim điểm chính xác (Định vị Thái Nguyên / Toàn quốc)
            base_lat, base_lng, area_name = cls.resolve_submission_coordinates(s, vietmap_api_key)

            # Cập nhật số liệu vào AdministrativeArea nếu hồ sơ có liên kết
            if s.area and s.area.id in area_stat_map:
                if is_crime:
                    area_stat_map[s.area.id]["crime_count"] += 1
                else:
                    area_stat_map[s.area.id]["complaint_count"] += 1
                if is_completed:
                    area_stat_map[s.area.id]["completed_count"] += 1
                area_stat_map[s.area.id]["total"] += 1

            # Cập nhật vào thống kê địa bàn thực tế
            if area_name not in dynamic_area_stats:
                dynamic_area_stats[area_name] = {
                    "id": len(dynamic_area_stats) + 100,
                    "name": area_name,
                    "code": f"AREA_{len(dynamic_area_stats) + 1}",
                    "latitude": base_lat,
                    "longitude": base_lng,
                    "crime_count": 0,
                    "complaint_count": 0,
                    "completed_count": 0,
                    "total": 0,
                }
            if is_crime:
                dynamic_area_stats[area_name]["crime_count"] += 1
            else:
                dynamic_area_stats[area_name]["complaint_count"] += 1
            if is_completed:
                dynamic_area_stats[area_name]["completed_count"] += 1
            dynamic_area_stats[area_name]["total"] += 1

            # Hash deterministic jitter nhẹ (chỉ khoảng 30m - 60m)
            # để các vụ việc cùng một tuyến đường / xã không bị đè khít lên một điểm
            offset_lat = (((s.id * 37) % 80) - 40) / 100000.0
            offset_lng = (((s.id * 61) % 80) - 40) / 100000.0
            point_lat = round(base_lat + offset_lat, 6)
            point_lng = round(base_lng + offset_lng, 6)

            # Thống kê khung giờ 24h
            local_dt = timezone.localtime(s.created_at)
            hourly_counts[local_dt.hour] += 1

            # Tạo hiển thị địa điểm chi tiết, trực quan cho cán bộ tiếp nhận / chỉ huy
            if s.event_location and s.address and s.event_location.lower() not in s.address.lower():
                if any(v == s.event_location.lower() for v in ["tại nhà", "ở nhà", "nhà riêng"]):
                    location_display = f"{s.address} ({s.event_location})"
                else:
                    location_display = f"{s.event_location}, {s.address}"
            else:
                location_display = s.address or s.event_location or area_name

            incidents.append({
                "id": s.id,
                "type": incident_type,
                "type_label": type_label,
                "title": s.topic or (s.category.name if s.category else "Vụ việc ANTT"),
                "citizen": masked_name,
                "phone": (s.phone_number[:3] + "****" + s.phone_number[-3:]) if len(s.phone_number) > 6 else s.phone_number,
                "location": location_display,
                "area_name": area_name,
                "summary": s.summary or (s.content[:120] + "..."),
                "urgency_level": s.urgency_level or "normal",
                "processing_status": s.processing_status,
                "status_label": status_label,
                "time": local_dt.strftime("%H:%M %d/%m"),
                "dot_color": dot_color,
                "latitude": point_lat,
                "longitude": point_lng,
                "admin_url": f"/admin/social_messages/intakesubmission/{s.id}/change/",
            })

        # Tổng hợp danh sách thống kê địa bàn:
        # Nếu có địa bàn thực tế phát sinh, ưu tiên lấy các địa bàn có số vụ việc cao nhất
        sorted_dynamic = sorted(dynamic_area_stats.values(), key=lambda x: x["total"], reverse=True)
        if sorted_dynamic:
            area_stats = sorted_dynamic[:12]
        else:
            area_stats = list(area_stat_map.values())

        # Xác định tọa độ trung tâm khuyến nghị (Ưu tiên Thái Nguyên nếu có nhiều vụ việc ở Thái Nguyên)
        center_lat = 21.5928
        center_lng = 105.8442
        if incidents:
            center_lat = incidents[0]["latitude"]
            center_lng = incidents[0]["longitude"]

        return {
            "status": "success",
            "vietmap_api_key": vietmap_api_key,
            "has_vietmap": bool(vietmap_api_key),
            "time_window_days": days,
            "category_filter": category_filter,
            "center": {
                "latitude": center_lat,
                "longitude": center_lng,
            },
            "summary": {
                "total_incidents": len(subs),
                "crime_count": crime_count,
                "complaint_count": complaint_count,
                "urgent_count": urgent_count,
                "completed_count": completed_count,
            },
            "incidents": incidents,
            "area_stats": area_stats,
            "hourly_trend": {
                "labels": [f"{h:02d}:00" for h in range(24)],
                "counts": hourly_counts,
            },
        }
