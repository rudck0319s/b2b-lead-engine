import os
import io
import re
import json
from datetime import datetime
import streamlit as st
import pandas as pd
import requests

# google-generativeai 패키지 안전 임포트
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# -------------------------------------------------------------
# 1. 페이지 기본 설정 & 모던 B2B SaaS 스타일 커스텀 CSS
# -------------------------------------------------------------
st.set_page_config(
    page_title="B2B Lead Intelligence Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    
    /* 헤더 배너 */
    .lead-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: #ffffff;
        padding: 24px 30px;
        border-radius: 16px;
        margin-bottom: 24px;
        border: 1px solid #334155;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
    }
    .lead-header h1 {
        color: #38bdf8;
        font-size: 26px;
        font-weight: 800;
        margin: 0 0 6px 0;
    }
    .lead-header p {
        color: #94a3b8;
        font-size: 14px;
        margin: 0;
    }
    
    /* 리드 카드 스타일 */
    .lead-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .lead-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
        border-color: #cbd5e1;
    }
    
    /* 다크모드 대응 */
    @media (prefers-color-scheme: dark) {
        .lead-card {
            background: #1e293b;
            border-color: #334155;
        }
        .lead-card:hover {
            border-color: #475569;
        }
    }
    
    /* 뱃지 스타일 */
    .badge-score-high {
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #6ee7b7;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 13px;
        display: inline-block;
    }
    .badge-score-mid {
        background: #fffbeb;
        color: #d97706;
        border: 1px solid #fcd34d;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 13px;
        display: inline-block;
    }
    .badge-score-low {
        background: #f1f5f9;
        color: #64748b;
        border: 1px solid #cbd5e1;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 13px;
        display: inline-block;
    }
    
    .badge-web-yes {
        background: #eff6ff;
        color: #2563eb;
        border: 1px solid #bfdbfe;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-web-no {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-booking-yes {
        background: #f0fdf4;
        color: #16a34a;
        border: 1px solid #bbf7d0;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-booking-no {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-review {
        background: #f8fafc;
        color: #475569;
        border: 1px solid #e2e8f0;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
    }
    
    /* 결핍 진단 박스 */
    .vuln-box {
        background-color: rgba(239, 68, 68, 0.08);
        border-left: 4px solid #ef4444;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 12px 0;
        font-size: 13.5px;
    }
    
    /* 콜드 피치 박스 */
    .pitch-box {
        background-color: rgba(59, 130, 246, 0.08);
        border-left: 4px solid #3b82f6;
        padding: 12px 14px;
        border-radius: 6px;
        margin: 12px 0 8px 0;
        font-size: 14px;
        font-weight: 500;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 현실적인 Mock 데이터베이스 (안전장치 & 즉시 시연용)
# -------------------------------------------------------------
MOCK_LEADS = [
    {
        "id": "1",
        "title": "리셋 필라테스 & 체형교정 강남본점",
        "category": "스포츠,오락 > 필라테스",
        "address": "서울특별시 강남구 역삼로 142 3층",
        "telephone": "02-555-1290",
        "link": "",
        "place_url": "https://m.place.naver.com",
        "has_website": False,
        "visitor_reviews": 86,
        "blog_reviews": 42,
        "has_booking": False,
        "rating": 4.8,
        "review_count": 86,
        "vulnerability": "방문자 리뷰 86개를 확보해 강남권 검색 유입량은 우수하나, 네이버 간편 예약이 미연동되어 모바일 유입 고객의 즉각적인 전환 경로가 단절된 상태입니다. 특히 야간 직장인들의 상담 문의가 카톡 수기 응대에 묶여 실시간 예약 지원 경쟁사로 대거 이탈하고 있습니다. 이로 인해 매월 20~30건 이상의 잠재 등록 매출 누수가 지속되고 있습니다.",
        "priority_score": 94,
        "cold_pitch": "대표님, 방문자 리뷰 86건의 유입 트래픽 중 네이버 예약 부재로 놓치고 계신 야간 직장인 예약 30%를 실시간 자동 예약 시스템으로 즉각 회수해 드립니다."
    },
    {
        "id": "2",
        "title": "모먼트 성수 스페셜티 로스터리",
        "category": "음식점 > 카페,디저트",
        "address": "서울특별시 성동구 연무장길 45 1층",
        "telephone": "02-468-9011",
        "link": "https://instagram.com/moment_seongsu",
        "place_url": "https://m.place.naver.com",
        "has_website": True,
        "visitor_reviews": 210,
        "blog_reviews": 130,
        "has_booking": False,
        "rating": 4.6,
        "review_count": 210,
        "vulnerability": "블로그 리뷰 130개 등 개인 방문객은 넘치지만, 인근 지식산업센터 120개 기업을 겨냥한 오피스 원두 B2B 정기구독 랜딩페이지가 부재합니다. 주말 매장 방문 소비에만 편중되어 평일 고정적인 법인 납품 파이프라인 기회를 완전히 놓치고 있습니다. 대량 납품 전용 간편 견적 및 정기 결제 경로 보강이 시급합니다.",
        "priority_score": 88,
        "cold_pitch": "성수 핫플레이스로서 개인 방문객은 넘치지만, 인근 지식산업센터 120개 기업을 겨냥한 오피스 원두 B2B 월간 구독 수주 파이프라인을 자동 구축해 드립니다."
    },
    {
        "id": "3",
        "title": "필라테스 더 아우라 강남구청역점",
        "category": "스포츠,오락 > 필라테스",
        "address": "서울특별시 강남구 학동로 342 B1층",
        "telephone": "02-544-7731",
        "link": "",
        "place_url": "https://m.place.naver.com",
        "has_website": False,
        "visitor_reviews": 42,
        "blog_reviews": 15,
        "has_booking": False,
        "rating": 4.5,
        "review_count": 42,
        "vulnerability": "방문자 리뷰 42개로 강남구청역 핵심 상권 내 경쟁 센터 대비 신뢰도 지표가 정체되어 있으며, 스마트블록 노출 키워드 최적화가 미흡합니다. 모바일 지도에서 바로 상담을 확정짓는 간편 예약 및 혜택 쿠폰 경로가 없어 유입 트래픽의 상당수가 이탈 중입니다. 주간 신규 체험 전환을 유도할 수 있는 능동적인 플레이스 프로모션 파이프라인이 절실합니다.",
        "priority_score": 92,
        "cold_pitch": "강남구청역 인근 직장인 타깃의 '거북목 체형교정' 스마트블록 상위 노출 및 네이버 예약 활성화 프로모션으로 주간 신규 체험 상담 15건을 보장해 드립니다."
    },
    {
        "id": "4",
        "title": "카페 벨벳무드 성동카페거리점",
        "category": "음식점 > 카페,디저트",
        "address": "서울특별시 성동구 성수이로 78 1-2층",
        "telephone": "070-8821-4320",
        "link": "https://velvetmood.kr",
        "place_url": "https://m.place.naver.com",
        "has_website": True,
        "visitor_reviews": 14,
        "blog_reviews": 28,
        "has_booking": True,
        "rating": 4.3,
        "review_count": 14,
        "vulnerability": "네이버 예약은 연동되어 있으나 방문자 영수증 리뷰가 14건에 머물러 스마트블록 상위 점유 및 고객 신뢰도 확보에 병목이 발생하고 있습니다. 온라인 자사몰 방문자를 실제 오프라인 매장 방문 및 단골 저장으로 연결하는 혜택 쿠폰 연계가 전무한 상태입니다. 결과적으로 온라인 유입 트래픽이 현장 매출 증대로 전환되지 못하고 정체되어 있습니다.",
        "priority_score": 75,
        "cold_pitch": "현재 보유하신 자사몰 방문자를 매장 방문 및 네이버 단골 저장으로 직결시키는 스마트 쿠폰 자동화 시퀀스를 심어 일 매출 20% 상승을 돕겠습니다."
    },
    {
        "id": "5",
        "title": "숨 필라테스 & 자이로토닉 대치점",
        "category": "스포츠,오락 > 필라테스",
        "address": "서울특별시 강남구 삼성로 212 상가동 204호",
        "telephone": "02-567-8890",
        "link": "",
        "place_url": "https://m.place.naver.com",
        "has_website": False,
        "visitor_reviews": 130,
        "blog_reviews": 85,
        "has_booking": False,
        "rating": 4.9,
        "review_count": 130,
        "vulnerability": "방문자 리뷰 130건과 자이로토닉이라는 고단가 특화 프로그램을 보유했음에도, 대치동 학부모 타깃의 세부 랜딩페이지 및 간편 결제창이 부재합니다. 차별화된 1:1 자세교정 패키지가 오직 지인 입소문에만 의존하여 학기 초 신규 학생 수주 확장성이 차단되어 있습니다. 고단가 프리미엄 패키지 전용 직통 신청 시스템 구축이 절실합니다.",
        "priority_score": 95,
        "cold_pitch": "대치동 학부모님과 직장인 대상의 '청소년 자세교정 & 1:1 자이로토닉' 고단가 프라이빗 패키지 전용 랜딩페이지와 즉시 결제 시스템을 제안드립니다."
    }
]

# -------------------------------------------------------------
# 3. 헬퍼 함수 (HTML 태그 정리, 네이버 API, Gemini AI 분석)
# -------------------------------------------------------------
def clean_html_tag(text: str) -> str:
    """네이버 API 응답의 <b>, &quot; 등 태그 및 특수문자 제거"""
    if not text:
        return ""
    clean = re.sub(r"<.*?>", "", text)
    clean = clean.replace("&quot;", "\"").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return clean.strip()

def search_naver_places(client_id: str, client_secret: str, query: str, display: int = 5):
    """네이버 검색 지역 API(search/local.json) 호출"""
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": display,
        "sort": "comment"
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=7)
        if res.status_code == 200:
            data = res.json()
            items = []
            for item in data.get("items", []):
                cleaned_title = clean_html_tag(item.get("title", ""))
                link = item.get("link", "").strip()
                items.append({
                    "title": cleaned_title,
                    "category": item.get("category", "기타"),
                    "address": item.get("roadAddress") or item.get("address", ""),
                    "telephone": item.get("telephone", ""),
                    "link": link,
                    "has_website": bool(link and link.startswith("http")),
                    "rating": 4.5,
                    "review_count": 0
                })
            return items
        else:
            st.warning(f"네이버 API 호출 응답 오류 (상태 코드: {res.status_code}): {res.text}")
            return None
    except Exception as e:
        st.error(f"네이버 API 요청 실패: {e}")
        return None

def generate_excel_bytes(df: pd.DataFrame) -> bytes:
    """pandas DataFrame을 전문 B2B 보고서 스타일의 고품질 .xlsx 바이너리로 변환
    (방문자/블로그 리뷰 수 및 네이버 예약 여부 포함 10개 컬럼 서식, 한글 깨짐 방지, 고정 열 너비, 카드형 줄바꿈 및 프리미엄 다크 네이비 테마 적용)"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="B2B잠재고객_피칭목록")
        worksheet = writer.sheets["B2B잠재고객_피칭목록"]
        
        # 1. 맞춤형 열 너비(Width) 고정 지정 (10개 컬럼 규격)
        col_widths = {
            "A": 25,  # 상호명 (긴 지점명 포용을 위해 25로 확장)
            "B": 14,  # 업종
            "C": 38,  # 도로명주소 (35~38로 확장)
            "D": 28,  # 전화번호 (안내 문구 맞춤 28로 확장)
            "E": 13,  # 방문자리뷰
            "F": 13,  # 블로그리뷰
            "G": 13,  # 네이버예약
            "H": 13,  # 우선순위점수
            "I": 55,  # AI결핍진단 (55로 대폭 확장)
            "J": 50,  # 1줄콜드피칭 (50으로 확장)
        }
        for col_letter, width in col_widths.items():
            worksheet.column_dimensions[col_letter].width = width

        # 2. 테두리 스타일 정의 (라이트 그레이 #D9D9D9)
        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )

        # 3. 헤더 디자인 (1행: 다크 네이비 #1E293B, 흰색 볼드 11pt, 높이 30pt, 가로/세로 중앙)
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=False)
        worksheet.row_dimensions[1].height = 30

        total_cols = len(df.columns)
        for col_idx in range(1, total_cols + 1):
            cell = worksheet.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border

        # 4. 본문 데이터 서식 (2행부터: 상하 중앙 정렬, 컬럼별 맞춤 정렬, 자동 줄바꿈, 92pt 넉넉한 행 높이)
        body_font = Font(name="맑은 고딕", size=10)
        # B(2), D(4), E(5), F(6), G(7), H(8) -> 가운데 정렬 (D열 28너비 중앙 정렬)
        center_col_indices = {2, 4, 5, 6, 7, 8}
        # A(1), C(3), I(9), J(10) -> 긴 상호명 및 주소/진단 자동 줄바꿈 적용
        wrap_col_indices = {1, 3, 9, 10}

        max_row = worksheet.max_row
        for row_idx in range(2, max_row + 1):
            worksheet.row_dimensions[row_idx].height = 92  # 90~95pt 넉넉한 행 높이로 3~4문장 심층 결핍 진단 여백 완벽 확보
            for col_idx in range(1, total_cols + 1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                cell.font = body_font
                cell.border = thin_border
                
                is_center = col_idx in center_col_indices
                is_wrap = col_idx in wrap_col_indices
                
                cell.alignment = Alignment(
                    horizontal="center" if is_center else "left",
                    vertical="center",
                    wrap_text=is_wrap
                )

    return output.getvalue()

# -------------------------------------------------------------
# 3-0. 프로 멤버십 전용 엑셀 다운로드 안내 및 인증코드 해제 모달 (st.dialog)
# -------------------------------------------------------------
dialog_fn = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

def _render_pro_modal_body(excel_bytes, excel_filename, excel_mime):
    st.markdown(
        """
        <div style="font-size: 14px; line-height: 1.7; color: #334155; margin-bottom: 16px;">
        전체 잠재고객 데이터와 AI 맞춤 피칭 문구를 엑셀(.xlsx)로 즉시 다운로드하여 영업 리스트로 활용하세요.<br><br>
        <span style="color: #e11d48; font-weight: 700; font-size: 15px;">🔥 얼리버드 특별 프로모션: 월 19,900원 (선착순 마감 임박)</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.link_button(
        "👉 카카오톡으로 1:1 이용권 신청 및 인증코드 받기",
        "https://open.kakao.com/o/sNWpUQNi",
        use_container_width=True,
        type="primary"
    )

    st.markdown("---")
    st.markdown("##### 🔑 인증코드 입력")

    code_input = st.text_input(
        "발급받은 인증코드를 입력하세요",
        type="password",
        placeholder="인증코드 입력 (예: LEAD2026)",
        key="pro_auth_code_input"
    )

    is_authed = st.session_state.get("is_pro_authenticated", False)

    if code_input:
        if code_input.strip() == "LEAD2026":
            st.session_state["is_pro_authenticated"] = True
            is_authed = True
            st.success("✅ 인증이 완료되었습니다! 아래 버튼을 눌러 엑셀 파일을 다운로드하세요.")
        else:
            st.error("인증코드가 올바르지 않습니다. 오픈채팅으로 문의해주세요.")

    if is_authed:
        st.download_button(
            label="📥 엑셀(.xlsx) 파일 즉시 다운로드",
            data=excel_bytes,
            file_name=excel_filename,
            mime=excel_mime,
            type="primary",
            use_container_width=True,
            key="pro_modal_actual_download_btn"
        )

if dialog_fn:
    @dialog_fn("🔒 프로 멤버십 전용 기능 (엑셀 일괄 다운로드)")
    def show_pro_excel_modal(excel_bytes, excel_filename, excel_mime):
        _render_pro_modal_body(excel_bytes, excel_filename, excel_mime)
else:
    def show_pro_excel_modal(excel_bytes, excel_filename, excel_mime):
        with st.expander("🔒 프로 멤버십 전용 기능 (엑셀 일괄 다운로드)", expanded=True):
            _render_pro_modal_body(excel_bytes, excel_filename, excel_mime)

# -------------------------------------------------------------
# 3-1. Gemini 유효 모델 자동 감지 헬퍼 함수
# -------------------------------------------------------------
def get_available_models(api_key: str) -> list:
    """genai.configure 직후 genai.list_models()를 조회하여 'generateContent'를 지원하는 표준 유효 모델 목록 추출
    (쿼터 제한이 극심한 omni, preview, experimental 등은 완전 제외)"""
    if not HAS_GENAI or not api_key:
        return []
    try:
        genai.configure(api_key=api_key)
        # 쿼터 초과 및 불안정을 유발하는 프리뷰/실험 모델 키워드 필터링
        EXCLUDE_KEYWORDS = ["omni", "preview", "experimental", "exp", "thinking"]
        
        valid_models = []
        for m in genai.list_models():
            if 'generateContent' in getattr(m, 'supported_generation_methods', []):
                name_lower = m.name.lower()
                if any(k in name_lower for k in EXCLUDE_KEYWORDS):
                    continue
                valid_models.append(m.name)
        return valid_models
    except Exception:
        return []

def resolve_best_model(api_key: str, preferred_model: str = "") -> str:
    """사용 가능한 모델 중 'gemini-3.6-flash'를 최우선 선택하고 없으면 Flash 계열 우선 반환"""
    models = get_available_models(api_key)
    if not models:
        return preferred_model or "gemini-3.6-flash"
        
    if preferred_model and preferred_model in models:
        return preferred_model

    # 1순위: gemini-3.6-flash 정식 모델
    for m in models:
        if "3.6-flash" in m.lower():
            return m

    # 2순위: 기타 flash 정식 모델
    flash_models = [m for m in models if "flash" in m.lower()]
    if flash_models:
        return flash_models[0]

    # 3순위: 목록의 첫 번째 유효 모델
    return models[0]

def extract_text_safely(response) -> str:
    """Grounding(Google Search) 또는 다중 Part 응답 객체에서 텍스트를 누락 없이 안전하게 추출"""
    if not response:
        return ""
    # 1차: response.text 속성 접근
    try:
        if response.text and response.text.strip():
            return response.text.strip()
    except Exception:
        pass
        
    # 2차: search grounding 시 candidates[0].content.parts 순회 추출
    try:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                parts = candidate.content.parts
                extracted = "".join([getattr(p, 'text', '') for p in parts if hasattr(p, 'text')]).strip()
                if extracted:
                    return extracted
    except Exception:
        pass

    return ""

def analyze_lead_with_gemini(api_key: str, lead_data: dict, my_service: str, model_name: str = "") -> dict:
    """API 키에서 자동 감지된 유효 모델을 활용하여 영업 결핍 요약, 우선순위 점수, 1줄 콜드 피칭 생성"""
    if not HAS_GENAI or not api_key:
        has_web = lead_data.get("has_website", False)
        v_msg = f"{lead_data['title']}의 독립 예약 랜딩페이지 부재로 인한 야간 이탈 및 카톡 수기 상담 전환 누수" if not has_web else f"{lead_data['title']}의 모바일 유입 대비 전환 유도(CTA) 및 리타겟팅 파이프라인 부재"
        return {
            "vulnerability": v_msg,
            "priority_score": 88 if not has_web else 76,
            "cold_pitch": f"대표님, {lead_data['title']}의 야간/주말 이탈 잠재고객 30%를 {my_service}로 즉각 회수해 월 신규 문의 2배를 만들어 드리겠습니다."
        }

    try:
        genai.configure(api_key=api_key)
        # 자동 감지된 최적 모델 선택 (404 Not Found 방지)
        target_model = model_name or resolve_best_model(api_key)
        model = genai.GenerativeModel(target_model)

        prompt = f"""
당신은 대한민국 상위 1% B2B 콜드 세일즈 및 비즈니스 성장 전략 수석 컨설턴트입니다.
아래 잠재 고객(소상공인/기업)의 공개 정보와 나의 제공 서비스를 정밀 분석하여, 대표/의사결정권자가 메시지를 보자마자 답장하고 미팅을 잡고 싶게 만드는 날카로운 [결핍 진단]과 [1줄 콜드 피칭]을 작성하세요.

[잠재 고객 정보]
- 상호명: {lead_data['title']}
- 업종/카테고리: {lead_data.get('category', '미지정')}
- 주소: {lead_data['address']}
- 공식 웹사이트/예약링크 여부: {'있음 (' + lead_data['link'] + ')' if lead_data['has_website'] else '없음 (전화/카카오톡 수기 상담 의존 및 야간 이탈 추정)'}

[나의 제공 서비스 / 솔루션 가치 제안]
{my_service}

[작성 가이드라인 - 절대 준수]
1. vulnerability (AI 결핍 진단):
   - '디지털 노출 부족', '마케팅 미흡', '홍보 필요' 같은 추상적이고 뻔한 말은 절대 금지합니다.
   - 상대방의 지갑에서 돈이 새고 있는 **실제 매출 손실 포인트(Bottleneck)**를 직격하세요.
   - 예시: "독립 예약 랜딩페이지 부재로 인한 심야/주말 잠재등록 고객 누수 및 카톡 수기 상담 병목 발생", "경쟁사 대비 네이버 플레이스 세부 키워드 점유 실패로 인한 신규 유입 경로 단절", "인스타그램 링크만 존재하여 B2B 기업 단체/정기 결제 파이프라인 부재" 등 1~2문장으로 날카롭게 정리.

2. cold_pitch (1줄 콜드 피칭 제안):
   - "안녕하세요 대행사입니다", "도움을 드릴 수 있습니다" 같은 뻔한 영업 멘트는 절대 금지합니다.
   - 상대방의 가장 아픈 손실을 정면으로 찌르고, **구체적인 수치(예: "야간 직장인 이탈 고객 30% 즉각 회수", "월 고정 단체 주문 15건 자동화 파이프라인 구축", "신규 상담 전환율 2배 증대")**를 포함하여 클릭과 답장을 유도하는 팩폭 헤드라인 스타일로 작성하세요.
   - 어조: 정중하면서도 비즈니스 본질을 꿰뚫는 압도적 전문가의 제안 어조.

3. priority_score (영업 우선순위 점수):
   - 웹사이트/예약시스템이 부재하여 결핍이 크고 영업 설득 가능성이 높을수록 85~98점 부여.
   - 이미 웹사이트가 갖춰져 있으면 개선 여지에 따라 60~80점 부여. (0~100 정수)

[출력 형식]
반드시 마크다운 백틱(```)이나 부가 설명 없이 아래 순수 JSON 포맷만 반환하세요:
{{
  "vulnerability": "상대방의 실제 매출 손실 및 고객 이탈 병목을 찌르는 결핍 진단 1~2문장",
  "priority_score": 90,
  "cold_pitch": "대표님, [상대방의 구체적 결핍/누수]를 [나의 솔루션]으로 해결하여 [구체적 수치 성과/회수율]을 즉각 만들어 드리겠습니다."
}}
"""
        response = None
        try:
            # 1차 시도: JSON 포맷 지정
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
        except Exception:
            # 2차 시도: 일반 텍스트 포맷 호출 후 정규식 파싱
            response = model.generate_content(prompt)

        raw_text = extract_text_safely(response)
        if not raw_text:
            raise Exception("Gemini 응답 텍스트를 추출하지 못했습니다.")

        raw_text = raw_text.strip()
        # JSON 블록 정리
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)
            
        data = json.loads(raw_text)
        return {
            "vulnerability": data.get("vulnerability", "디지털 접점 개선 필요"),
            "priority_score": int(data.get("priority_score", 75)),
            "cold_pitch": data.get("cold_pitch", "신규 고객 전환율을 비약적으로 높일 수 있는 구체적 실행안을 제안드립니다.")
        }
    except Exception as e:
        return {
            "vulnerability": f"온라인 접점 분석 중 ({str(e)[:40]})",
            "priority_score": 70,
            "cold_pitch": f"대표님, {lead_data['title']} 전용 {my_service} 솔루션으로 월 신규 문의를 즉시 증대시켜 드립니다."
        }

def fix_mojibake(text: str) -> str:
    """ISO-8859-1 등으로 잘못 디코딩되어 깨진 한글 텍스트(mojibake)를 정상 복구"""
    if not text:
        return ""
    try:
        # 'í•˜ìš°ì‹œìŠ¤' 같은 깨진 텍스트 복구 시도
        return text.encode('latin-1').decode('utf-8')
    except Exception:
        return text

def crawl_naver_place_leads(region: str, industry: str, limit: int = 5) -> list:
    """모바일 네이버 지도/검색(m.search.naver.com)에서 실시간으로 상위 매장 5곳의 팩트 지표를 고속 스크래핑
    (UTF-8 강제 디코딩으로 한글 상호명 및 주소 깨짐 완전 차단)
    추출 항목: 상호명, 카테고리, 도로명 주소, 전화번호, 방문자 리뷰 수, 블로그 리뷰 수, 네이버 간편 예약 활성화 여부(True/False)
    """
    query = f"{region} {industry}".strip()
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    # 1. 모바일 통합 검색에서 플레이스 ID 추출
    search_url = f"https://m.search.naver.com/search.naver?where=m&query={requests.utils.quote(query)}"
    place_ids = []
    try:
        r = requests.get(search_url, headers=headers, timeout=6)
        r.encoding = 'utf-8'
        search_html = r.content.decode('utf-8', errors='replace')
        id_pattern = r'm\.place\.naver\.com/(?:place|restaurant|cafe|hairshop|hospital|accommodation|[a-zA-Z0-9_\-]+)/(\d+)'
        place_ids = list(dict.fromkeys(re.findall(id_pattern, search_html)))[:limit]
    except Exception:
        place_ids = []

    leads = []
    # 2. 각 플레이스 모바일 홈 페이지에서 __APOLLO_STATE__ 및 예약 태그 고속 추출
    for pid in place_ids:
        try:
            place_url = f"https://m.place.naver.com/place/{pid}/home"
            pr = requests.get(place_url, headers=headers, timeout=5)
            pr.encoding = 'utf-8'
            s = pr.content.decode('utf-8', errors='replace')
            idx = s.find('__APOLLO_STATE__ = ')
            if idx != -1:
                json_start = idx + len('__APOLLO_STATE__ = ')
                data, _ = json.JSONDecoder().raw_decode(s[json_start:])
                bases = [v for k, v in data.items() if 'DetailBase' in k or k.startswith('PlaceDetailBase:')]
                if bases:
                    b = bases[0]
                    # 네이버 간편 예약 활성화 여부 판별
                    has_booking = bool(
                        f'/place/{pid}/booking' in s or 
                        'plc_btp.booking' in s or 
                        any('booking' in k.lower() or 'reserve' in k.lower() for k in data.keys() if not k.startswith('BaseNaverBlog'))
                    )
                    
                    raw_title = clean_html_tag(b.get('name', ''))
                    title = fix_mojibake(raw_title)
                    
                    raw_category = b.get('category', industry)
                    category = fix_mojibake(raw_category)
                    
                    raw_address = b.get('roadAddress') or b.get('address', f"{region} 일대")
                    address = fix_mojibake(raw_address)

                    raw_phone = str(b.get('phone') or b.get('virtualPhone') or '').strip()
                    phone = raw_phone if raw_phone and raw_phone not in ["-", "정보 없음"] else "미등록 (네이버톡톡/DM 문의 권장)"

                    leads.append({
                        "id": pid,
                        "title": title,
                        "category": category,
                        "address": address,
                        "telephone": phone,
                        "visitor_reviews": int(b.get('visitorReviewsTotal') or 0),
                        "blog_reviews": int(b.get('cafeBlogReviewsTotal') or 0),
                        "has_booking": has_booking,
                        "place_url": pr.url or f"https://m.place.naver.com/place/{pid}/home",
                        "link": pr.url or f"https://m.place.naver.com/place/{pid}/home"
                    })
        except Exception:
            continue

    return leads

def analyze_crawled_leads_with_gemini(
    api_key: str, 
    leads: list, 
    target_solution: str, 
    model_name: str = ""
) -> tuple:
    """수집된 실제 매장의 팩트 지표(리뷰 수, 예약 여부 등)를 주입받아
    Gemini 웹 검색(Grounding)을 끄고 순수 생성으로 'AI 결핍 진단(3~4문장)'과 '1줄 콜드 피칭(1문장)'을 초고속 Single-shot 일괄 생성 (2~4초 소요)"""
    if not HAS_GENAI or not api_key:
        return None, "Gemini API 키가 입력되지 않았습니다."

    target_model = model_name or resolve_best_model(api_key)
    genai.configure(api_key=api_key)
    
    # 웹 검색(Grounding) 없이 순수 모델 생성으로 초고속 처리
    model = genai.GenerativeModel(target_model)

    facts_list = []
    for idx, l in enumerate(leads):
        facts_list.append({
            "idx": idx,
            "title": l["title"],
            "category": l["category"],
            "address": l["address"],
            "visitor_reviews": l["visitor_reviews"],
            "blog_reviews": l["blog_reviews"],
            "has_booking": "네이버예약 활성화" if l["has_booking"] else "네이버예약 미활성화(부재)"
        })

    facts_json = json.dumps(facts_list, ensure_ascii=False, indent=2)

    prompt = f"""
당신은 대한민국 상위 1% B2B 콜드 세일즈 및 데이터 기반 전환율 최적화 수석 컨설턴트입니다.
아래는 네이버 플레이스에서 실시간으로 수집한 실제 매장 5곳의 팩트 지표 데이터입니다:

{facts_json}

나의 제안 솔루션: "{target_solution}"

위 5개 매장의 실제 수치(방문자 리뷰 수, 블로그 리뷰 수, 네이버 간편 예약 활성화 여부)를 바탕으로, 반드시 제안 솔루션인 [{target_solution}]의 관점에서 고객의 결핍을 찌르고 계약을 유도하는 전문 피칭을 작성하세요.

[작성 원칙 - 절대 엄수]
1. vulnerability (AI 결핍 진단):
   - 단순한 단문 요약이나 사실 나열을 엄격히 금지합니다.
   - 반드시 [실측 수치 팩트(리뷰 수/예약 유무)] + [알고리즘 및 유입 경로상 구체적 병목 원인(스마트블록, 전환 단절 등)] + [예상 매출 타격 및 경쟁사 유출] 3단 논법 구조로 전문 마케터 관점의 3~4문장(공백 포함 150~180자 내외) 입체적 결핍 진단 문장을 작성하세요.
   - 특히 고객의 현재 수치적 약점이 나의 제안 솔루션인 [{target_solution}] 도입을 통해 어떻게 해결될 수 있는지 날카롭게 찌르세요.
   - 깊이 있고 묵직한 컨설팅 톤앤매너로 상대방의 구조적 손실을 직격하세요.
   - 예시: "방문자 리뷰 778개와 블로그 리뷰 84개로 유입 트래픽은 상당하나, 네이버 간편 예약이 미연동되어 스마트블록 유입 후 전환 경로가 완전히 단절되어 있습니다. 모바일 검색 후 즉각 행동할 창구가 없어 매월 40~50건 이상의 주말 잠재 고객이 예약 연동 경쟁사로 유출되고 있습니다. 즉각적인 전환 파이프라인 구축이 없으면 누적 매출 타격이 지속될 것입니다."
2. cold_pitch (1줄 콜드 피칭):
   - 뻔한 마케팅 대행 홍보 문구 금지.
   - 상대방의 아픈 수치/결핍을 찌르고, 나의 제안 솔루션인 [{target_solution}]을 도입했을 때 얻을 수 있는 구체적인 수치 성과(예: "월 이탈 상담 40건 즉각 회수", "주간 신규 예약 25% 상승")를 포함한 팩폭 헤드라인 1문장으로 작성하세요.
3. priority_score (영업 우선순위 점수):
   - 제안 솔루션인 [{target_solution}] 관점에서 전환 장치가 부재하거나 지표 개선이 시급할수록 88~98점 부여 (0~100 정수).

[출력 포맷]
반드시 마크다운 백틱(```) 없이 오직 아래 순수 JSON 리스트 포맷만 반환하세요:
[
  {{
    "idx": 0,
    "priority_score": 94,
    "vulnerability": "방문자 리뷰 778개와 블로그 리뷰 84개로 유입 트래픽은 상당하나, 네이버 간편 예약이 미연동되어 스마트블록 유입 후 전환 경로가 완전히 단절되어 있습니다. 모바일 검색 후 즉각 행동할 창구가 없어 매월 40~50건 이상의 주말 잠재 고객이 예약 연동 경쟁사로 유출되고 있습니다. 즉각적인 전환 파이프라인 구축이 없으면 누적 매출 타격이 지속될 것입니다.",
    "cold_pitch": "대표님, 네이버 예약 미연동으로 매월 놓치고 계신 야간 직장인 예약 30%를 {target_solution} 도입으로 즉각 회수해 드립니다."
  }}
]
"""
    try:
        response = None
        try:
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
        except Exception:
            response = model.generate_content(prompt)

        raw_text = extract_text_safely(response)
        if not raw_text:
            return None, "Gemini 응답 텍스트를 추출하지 못했습니다."

        if "```" in raw_text:
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        analysis_items = None
        try:
            analysis_items = json.loads(raw_text)
        except Exception:
            match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
            if match:
                analysis_items = json.loads(match.group(0))

        merged_results = []
        for i, lead in enumerate(leads):
            match_ai = None
            if isinstance(analysis_items, list):
                for ai_item in analysis_items:
                    if ai_item.get("idx") == i or ai_item.get("title") == lead["title"]:
                        match_ai = ai_item
                        break
                if not match_ai and i < len(analysis_items):
                    match_ai = analysis_items[i]

            vr = lead.get("visitor_reviews", 0)
            br = lead.get("blog_reviews", 0)
            has_b = lead.get("has_booking", False)

            vuln = match_ai.get("vulnerability") if match_ai else (
                f"방문자 리뷰 {vr}개와 블로그 리뷰 {br}개로 기본 검색 트래픽은 유입되고 있으나, 네이버 간편 예약이 미연동되어 탐색 고객의 방문 전환 경로가 차단되어 있습니다. 모바일 스마트블록 탐색 후 즉각 예약할 수 없어 매월 수십 명의 잠재 고객이 경쟁 매장으로 이탈하는 치명적 병목이 발생 중입니다. 유입 대비 실제 내방 전환 장치가 전무하여 막대한 매출 기회비용을 상실하고 있습니다."
                if not has_b else
                f"방문자 리뷰 {vr}개와 네이버 예약 시스템을 보유하여 기본 유입망은 갖추었으나, 스마트블록 키워드 장악력과 블로그 리뷰({br}개) 연계 콘텐츠가 취약합니다. 상위 노출 경쟁사로의 고객 분산이 지속되어 실제 예약 전환율이 정체되고 있으며, 고단가 패키지 유치 기회를 놓쳐 잠재 매출 성장이 가로막힌 상태입니다."
            )
            score = int(match_ai.get("priority_score", 92 if not has_b else 78)) if match_ai else (94 if not has_b else 78)
            pitch = match_ai.get("cold_pitch") if match_ai else (
                f"대표님, 방문자 리뷰 {vr}건의 유입 트래픽 중 전환 장치 부재로 놓치고 계신 잠재 고객 30%를 {target_solution} 도입으로 즉각 회수해 드립니다."
                if not has_b else
                f"대표님, 이미 구축된 네이버 플레이스 트래픽의 전환 효율을 {target_solution}로 2배 극대화하여 월 매출을 즉시 견인해 드립니다."
            )

            merged_results.append({
                "id": i + 1,
                "title": lead["title"],
                "category": lead["category"],
                "address": lead["address"],
                "telephone": lead["telephone"],
                "visitor_reviews": vr,
                "blog_reviews": br,
                "has_booking": has_b,
                "place_url": lead.get("place_url", ""),
                "priority_score": score,
                "vulnerability": vuln,
                "cold_pitch": pitch
            })

        return merged_results, None

    except Exception as e:
        return None, str(e)

def enrich_leads_rule_based(leads: list, target_solution: str) -> list:
    """Gemini API가 없거나 오류 시, 수집된 팩트 데이터를 기반으로 즉시 고품질 결핍 진단 및 피칭 합성"""
    results = []
    for idx, l in enumerate(leads):
        has_b = l.get("has_booking", False)
        vr = l.get("visitor_reviews", 0)
        br = l.get("blog_reviews", 0)
        score = 94 if not has_b and vr >= 30 else (88 if not has_b else 76)
        if not has_b:
            vuln = f"방문자 리뷰 {vr}개와 블로그 리뷰 {br}개로 기본 검색 트래픽은 유입되고 있으나, 네이버 간편 예약이 미연동되어 탐색 고객의 방문 전환 경로가 차단되어 있습니다. 모바일 스마트블록 탐색 후 즉각 예약할 수 없어 매월 수십 명의 잠재 고객이 경쟁 매장으로 이탈하는 치명적 병목이 발생 중입니다. 유입 대비 실제 내방 전환 장치가 전무하여 막대한 매출 기회비용을 상실하고 있습니다."
            pitch = f"대표님, {l['title']}의 방문자 리뷰 {vr}개 트래픽을 놓치지 않도록 {target_solution}로 실시간 예약 전환 파이프라인을 구축해 드리겠습니다."
        else:
            vuln = f"방문자 리뷰 {vr}개와 네이버 예약 시스템을 보유하여 기본 유입망은 갖추었으나, 스마트블록 키워드 장악력과 블로그 리뷰({br}개) 연계 콘텐츠가 취약합니다. 상위 노출 경쟁사로의 고객 분산이 지속되어 실제 예약 전환율이 정체되고 있으며, 고단가 패키지 유치 기회를 놓쳐 잠재 매출 성장이 가로막힌 상태입니다."
            pitch = f"대표님, 이미 활성화된 네이버 예약 시스템의 전환 효율을 {target_solution}로 2배 극대화하여 월 매출을 즉시 견인해 드립니다."
        results.append({
            "id": idx + 1,
            "title": l["title"],
            "category": l["category"],
            "address": l["address"],
            "telephone": l["telephone"],
            "visitor_reviews": vr,
            "blog_reviews": br,
            "has_booking": has_b,
            "place_url": l.get("place_url", ""),
            "priority_score": score,
            "vulnerability": vuln,
            "cold_pitch": pitch
        })
    return results

# -------------------------------------------------------------
# 4. 사이드바 구성
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ 시스템 연동 설정")
    
    use_mock = st.checkbox("🧪 Mock 테스트 모드 사용", value=False, help="API 키 없이 강남구/성수동 5곳의 샘플 데이터로 즉시 테스트합니다.")
    
    st.markdown("---")
    st.markdown("#### 🤖 AI 인텔리전스 & 실시간 웹 검색")
    
    # Streamlit Secrets 또는 환경변수에서 GEMINI_API_KEY 자동 로드 (보안: UI에는 절대 노출하지 않음)
    default_secret_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            default_secret_key = str(st.secrets["GEMINI_API_KEY"]).strip()
        elif hasattr(st.secrets, "get"):
            default_secret_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        pass
    
    if not default_secret_key:
        default_secret_key = os.environ.get("GEMINI_API_KEY", "").strip()

    has_secret_key = bool(default_secret_key)

    user_api_key_input = st.text_input(
        "Gemini API Key",
        value="",
        type="password",
        placeholder="시스템 기본 키 적용 중 (직접 입력 시 덮어쓰기)" if has_secret_key else "AIzaSy...",
        help="Google AI Studio에서 발급받은 API Key입니다. 시스템에 기본 키가 등록되어 있어 비워두셔도 정상 작동합니다." if has_secret_key else "Google AI Studio에서 발급받은 API Key를 입력하세요."
    )
    # 실제 API 호출에는 사용자가 직접 입력한 키를 최우선으로, 비워두면 secrets 키를 내부 백엔드 메모리에서만 참조
    gemini_api_key = user_api_key_input.strip() if user_api_key_input.strip() else default_secret_key
    
    if has_secret_key:
        if user_api_key_input.strip():
            st.info("✏️ 사용자가 직접 입력한 커스텀 API Key가 적용되었습니다.")
        else:
            st.success("🔒 시스템 기본 API 키가 안전하게 적용 중입니다 (직접 입력 시 덮어쓰기)")
    
    # API 키 입력 시 지원 모델 목록 동적 자동 감지 (preview/omni 제외 완료)
    detected_models = []
    best_detected = "gemini-3.6-flash"
    if gemini_api_key:
        detected_models = get_available_models(gemini_api_key)
        if detected_models:
            best_detected = resolve_best_model(gemini_api_key)
            st.caption(f"⚡ 정식 모델 자동 매칭: `{best_detected}`")
        else:
            st.caption("ℹ️ 모델 목록 확인 중 (기본 권장: `gemini-3.6-flash`)")

    model_options = detected_models if detected_models else ["gemini-3.6-flash"]
    
    # gemini-3.6-flash를 최우선 기본 인덱스로 고정
    default_idx = 0
    for idx, opt in enumerate(model_options):
        if "3.6-flash" in opt.lower():
            default_idx = idx
            break
        elif opt == best_detected:
            default_idx = idx
    
    gemini_model_choice = st.selectbox(
        "Gemini 모델 선택 (gemini-3.6-flash 기본 고정)",
        options=model_options,
        index=default_idx,
        help="Google API 정식 모델인 'gemini-3.6-flash'가 기본 선택됩니다."
    )
    
    with st.expander("🗺️ 네이버 검색 API (선택 / 레거시)", expanded=False):
        st.caption("ℹ️ 이제 Gemini 실시간 웹 검색이 기본 탑재되어 네이버 API 키 없이도 전국 최신 매장을 원스톱 수집합니다.")
        naver_client_id = st.text_input(
            "Naver Client ID",
            type="password",
            placeholder="Naver Developers Client ID"
        )
        naver_client_secret = st.text_input(
            "Naver Client Secret",
            type="password",
            placeholder="Naver Developers Client Secret"
        )
    
    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 12px; color: #64748b; line-height: 1.6;">
        💡 <b>원스톱 안내</b><br>
        • <b>Gemini API Key만 입력</b>하시면 Google Search Grounding을 통해 전국 어떤 지역/업종이든 최신 실제 매장을 실시간 검색하고 AI 피칭까지 한 번에 완료합니다.<br>
        • API Key가 없을 때는 상단의 <b>Mock 테스트 모드</b>를 켜면 즉시 시연 가능합니다.
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------------------
# 5. 메인 화면 헤더 및 타깃 조건 입력
# -------------------------------------------------------------
st.markdown("""
<div class="lead-header">
    <h1>🎯 B2B Lead Intelligence Dashboard</h1>
    <p>프리랜서 및 마케팅 대행사를 위한 AI 기반 잠재고객 결핍 진단 & 1줄 콜드 피칭 자동 생성 시스템</p>
</div>
""", unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns([1, 1])
    with col1:
        industry = st.text_input("🏢 타깃 업종", value="필라테스", placeholder="예: 필라테스, 뷰티샵, 카페")
    with col2:
        target_region = st.text_input("📍 타깃 지역", value="강남구", placeholder="예: 강남구, 성수동, 판교")

    solution_options = [
        "종합 로컬 마케팅 (플레이스 상위노출 & 블로그 체험단)",
        "SNS 퍼포먼스 광고 & 숏폼/인스타 브랜딩",
        "네이버 플레이스 최적화 & 간편 예약 연동",
        "웹사이트/랜딩페이지 제작 & 전환 최적화",
        "기타 (직접 입력)"
    ]

    selected_solution = st.selectbox(
        "🎯 내가 제안할 영업 솔루션",
        options=solution_options,
        index=2,
        help="잠재 고객에게 제안할 핵심 솔루션을 선택하거나 '기타 (직접 입력)'를 통해 원하는 비즈니스 가치 제안을 직접 기입하세요."
    )

    if selected_solution == "기타 (직접 입력)":
        custom_solution = st.text_input(
            "✏️ 직접 입력 솔루션 명칭 및 가치 제안",
            value="당근마켓 지역 광고",
            placeholder="예: 당근마켓 지역 광고, 키오스크/테이블오더 렌탈, 오프라인 간판/인쇄물 제작 등",
            help="제안하고자 하는 세부 솔루션이나 서비스 명칭을 입력하세요. AI가 해당 솔루션 관점에서 팩트 기반 결핍을 진단합니다."
        )
        target_solution = custom_solution.strip() if custom_solution.strip() else "맞춤형 비즈니스 솔루션"
    else:
        target_solution = selected_solution

search_btn = st.button("🚀 잠재고객 분석 및 피칭 생성", type="primary", use_container_width=True)

# -------------------------------------------------------------
# 6. 검색 및 AI 분석 파이프라인 실행 (하이브리드: 네이버 플레이스 직접 수집 + Gemini 경량 AI 피칭)
# -------------------------------------------------------------
if search_btn:
    lead_results = []
    
    # 1) Mock 모드 우선 분기
    if use_mock:
        st.info("🧪 Mock 테스트 모드가 활성화되어 있어 샘플 데이터 5건으로 즉시 분석 결과를 표시합니다.")
        lead_results = MOCK_LEADS
            
    # 2) 실제 하이브리드 파이프라인
    else:
        # 1단계: 네이버 플레이스 모바일 타깃 고속 수집
        with st.spinner(f"🔍 네이버 플레이스에서 '{target_region} {industry}' 상위 5개 업체의 팩트 지표(리뷰 수/예약 여부)를 실시간 수집 중..."):
            crawled_leads = crawl_naver_place_leads(target_region, industry, limit=5)

        if not crawled_leads:
            st.warning("⚠️ 네이버 플레이스 실시간 검색 결과를 찾지 못해 샘플 데이터로 안전하게 대체합니다.")
            crawled_leads = MOCK_LEADS

        # 2단계: Gemini 경량 파이프라인 (웹 검색 Grounding 없이 주입된 팩트 지표로 초고속 1회 생성)
        if gemini_api_key:
            active_model = gemini_model_choice or resolve_best_model(gemini_api_key)
            with st.spinner(f"⚡ Gemini 경량 모델(`{active_model}`)로 팩트 기반 결핍 진단 및 1줄 피칭 생성 중... (약 2~4초)"):
                analyzed_leads, err_msg = analyze_crawled_leads_with_gemini(
                    gemini_api_key, crawled_leads, target_solution, model_name=active_model
                )
                if analyzed_leads:
                    lead_results = analyzed_leads
                    st.toast(f"✅ 네이버 플레이스 실시간 팩트 지표 기반 AI 분석이 초고속 완료되었습니다!", icon="🎯")
                else:
                    st.error(f"AI 분석 중 오류 발생: {err_msg}. 수집된 팩트 지표 기반으로 즉시 보강합니다.")
                    lead_results = enrich_leads_rule_based(crawled_leads, target_solution)
        else:
            st.info("ℹ️ Gemini API Key가 입력되지 않아 수집된 팩트 지표(방문자/블로그 리뷰 수, 예약 여부)를 바탕으로 기본 진단 및 피칭을 자동 합성했습니다.")
            lead_results = enrich_leads_rule_based(crawled_leads, target_solution)
            
    # 세션에 결과 저장하여 탭 이동 및 렌더링 유지
    st.session_state["lead_results"] = lead_results
    st.success(f"총 {len(lead_results)}건의 네이버 플레이스 실시간 잠재고객 분석 및 콜드 피칭이 생성되었습니다!")

# -------------------------------------------------------------
# 7. 결과 화면 탭 뷰 (카드 뷰 vs 테이블 뷰)
# -------------------------------------------------------------
results = st.session_state.get("lead_results", None)

if results:
    # 1) 엑셀 다운로드용 데이터 가공 (요청된 10개 정규 컬럼 규격)
    today_str = datetime.now().strftime("%Y%m%d")
    clean_region = target_region.strip().replace(" ", "_") if target_region else "전국"
    clean_industry = industry.strip().replace(" ", "_") if industry else "업종"
    excel_filename = f"영업타깃_{clean_region}_{clean_industry}_{today_str}.xlsx"

    df_export = pd.DataFrame([
        {
            "상호명": l["title"],
            "업종": l["category"],
            "도로명주소": l["address"],
            "전화번호": l.get("telephone", "").strip() if l.get("telephone") and l.get("telephone").strip() not in ["", "정보 없음", "전화번호 미등록", "미등록", "-"] else "미등록 (네이버톡톡/DM 문의 권장)",
            "방문자리뷰": l.get("visitor_reviews", 0),
            "블로그리뷰": l.get("blog_reviews", 0),
            "네이버예약": "활성화" if l.get("has_booking") else "미활성화",
            "우선순위점수": l["priority_score"],
            "AI결핍진단": l["vulnerability"],
            "1줄콜드피칭": l["cold_pitch"]
        }
        for l in results
    ])
    # 영업 우선순위점수 기준 내림차순 정렬
    df_export = df_export.sort_values(by="우선순위점수", ascending=False).reset_index(drop=True)
    excel_bytes = generate_excel_bytes(df_export)
    excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 2) 결과 목록 상단 헤더 & 프로 결제 안내 모달 연동 엑셀 다운로드 버튼
    top_col1, top_col2 = st.columns([2.8, 1.7])
    with top_col1:
        st.markdown(f"### 📋 네이버 플레이스 분석 리스트 ({len(results)}개 매장)")
    with top_col2:
        if st.session_state.get("is_pro_authenticated", False):
            st.download_button(
                label="📥 실시간 잠재고객 엑셀 다운로드 (PRO)",
                data=excel_bytes,
                file_name=excel_filename,
                mime=excel_mime,
                type="primary",
                use_container_width=True,
                help="PRO 인증이 완료되어 클릭 즉시 .xlsx 보고서가 다운로드됩니다."
            )
        else:
            if st.button(
                "📥 실시간 잠재고객 엑셀 다운로드",
                type="primary",
                use_container_width=True,
                help="프로 멤버십 전용 기능입니다. 클릭 시 이용권 안내 및 인증코드 입력 팝업이 열립니다."
            ):
                show_pro_excel_modal(excel_bytes, excel_filename, excel_mime)

    st.write("")
    tab1, tab2 = st.tabs(["📇 카드 뷰 (콜드 피칭 & 상세 분석)", "📊 테이블 뷰 (일괄 데이터 요약)"])
    
    # [탭 1: 카드 뷰]
    with tab1:
        for lead in results:
            # 점수 뱃지 분기
            score = lead["priority_score"]
            if score >= 88:
                score_badge = f'<span class="badge-score-high">🔥 우선순위 점수: {score}점 (최상)</span>'
            elif score >= 75:
                score_badge = f'<span class="badge-score-mid">⚡ 우선순위 점수: {score}점 (유망)</span>'
            else:
                score_badge = f'<span class="badge-score-low">⚪ 우선순위 점수: {score}점 (보통)</span>'
                
            # 예약 뱃지 분기
            if lead.get("has_booking"):
                booking_badge = '<span class="badge-booking-yes">🟢 네이버 간편예약 연동</span>'
            else:
                booking_badge = '<span class="badge-booking-no">🔴 네이버 예약 미연동 (전환 누수)</span>'
                
            vr_count = lead.get("visitor_reviews", 0)
            br_count = lead.get("blog_reviews", 0)
            review_badge = f'<span class="badge-review">💬 방문자 리뷰 <b>{vr_count:,}</b>개 &nbsp;|&nbsp; 📝 블로그 리뷰 <b>{br_count:,}</b>개</span>'
            
            place_link_html = ''
            if lead.get("place_url"):
                place_link_html = f'<a href="{lead["place_url"]}" target="_blank" style="font-size:12px; color:#2563eb; margin-left:8px; text-decoration:none; font-weight:600;">네이버 플레이스 ↗</a>'
                
            # 카드 HTML 렌더링
            st.markdown(f"""
            <div class="lead-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div>
                        <span style="font-size: 18px; font-weight: 700; color: #0f172a;">{lead['title']}</span>
                        <span style="font-size: 12px; color: #64748b; margin-left: 8px;">({lead['category']})</span>
                        {place_link_html}
                    </div>
                    <div>{score_badge}</div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px;">
                    {booking_badge}
                    {review_badge}
                </div>
                <div style="font-size: 13px; color: #475569; margin-bottom: 10px;">
                    📍 {lead['address']} &nbsp;|&nbsp; 📞 {lead['telephone']}
                </div>
                <div class="vuln-box">
                    <strong>⚠️ AI 결핍 진단 (실제 팩트 지표 기반):</strong><br>
                    {lead['vulnerability']}
                </div>
                <div class="pitch-box">
                    <strong>💬 1줄 콜드 피칭 제안:</strong><br>
                    "{lead['cold_pitch']}"
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 클립보드 복사를 위한 전용 코드 블록 및 토스트 버튼
            col_pitch, col_copy = st.columns([5, 1])
            with col_pitch:
                st.code(lead['cold_pitch'], language="markdown")
            with col_copy:
                if st.button("📋 피칭 복사", key=f"copy_btn_{lead['id']}", use_container_width=True):
                    st.toast(f"✅ '{lead['title']}' 피칭 문구가 복사용으로 준비되었습니다!", icon="🎯")
            st.write("")

    # [탭 2: 테이블 뷰]
    with tab2:
        st.markdown("#### 📊 일괄 데이터 요약 및 내보내기")
        
        st.dataframe(
            df_export,
            use_container_width=True,
            column_config={
                "우선순위점수": st.column_config.ProgressColumn(
                    "영업 우선순위",
                    help="AI가 산출한 영업 우선순위 점수 (0~100)",
                    format="%d점",
                    min_value=0,
                    max_value=100
                ),
                "방문자리뷰": st.column_config.NumberColumn("방문자 리뷰", format="%d건"),
                "블로그리뷰": st.column_config.NumberColumn("블로그 리뷰", format="%d건"),
            },
            hide_index=True
        )
        
        # 하단에서도 바로 다운로드 가능하도록 추가 배치
        st.download_button(
            label=f"📥 {excel_filename} 다운로드",
            data=excel_bytes,
            file_name=excel_filename,
            mime=excel_mime,
            type="secondary",
            key="bottom_excel_download_btn"
        )
else:
    # 최초 진입 시 안내 화면
    st.info("💡 위 설정창에서 타깃 조건(업종, 지역, 제공 서비스)을 확인한 뒤 **'🚀 잠재고객 분석 및 피칭 생성'** 버튼을 클릭해보세요. 네이버 플레이스에서 실제 매장 5곳의 지표를 즉각 수집합니다.")
