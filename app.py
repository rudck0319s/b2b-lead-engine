import os
import io
import re
import json
import uuid
import hashlib
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
# 사용자 행동 측정 (Supabase REST API Telemetry Helper)
# -------------------------------------------------------------
def log_event(
    event_name: str,
    industry: str = None,
    target_region: str = None,
    target_solution: str = None,
    lead_count: int = None,
    auth_result: str = None
):
    """
    Supabase REST API를 통해 사용자 행동 이벤트를 안전하게 비동기/단기 타임아웃 전송.
    - secrets 미설정 시 조용히 무시 (오류 발생 차단)
    - 민감정보(API키, 전화번호, 상세주소, 업체명, 입력코드 평문 등) 절대 제외
    """
    try:
        supabase_url = ""
        supabase_key = ""
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            supabase_url = str(st.secrets["SUPABASE_URL"]).strip()
            supabase_key = str(st.secrets["SUPABASE_KEY"]).strip()
        elif hasattr(st.secrets, "get"):
            supabase_url = str(st.secrets.get("SUPABASE_URL", "")).strip()
            supabase_key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
        
        # 외부 설정이 준비되지 않은 상태에서는 조용히 리턴 (Zero-Crash)
        if not supabase_url or not supabase_key:
            return

        session_id = st.session_state.get("session_id", "unknown_session")

        payload = {
            "session_id": session_id,
            "event_name": event_name,
            "industry": industry,
            "target_region": target_region,
            "target_solution": target_solution,
            "lead_count": lead_count,
            "auth_result": auth_result,
        }

        endpoint = f"{supabase_url.rstrip('/')}/rest/v1/b2b_events"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        requests.post(endpoint, json=payload, headers=headers, timeout=2.0)
    except Exception:
        # 텔레메트리 전송 실패가 메인 기능을 절대 중단시키지 않음
        pass

# -------------------------------------------------------------
# 1. 페이지 기본 설정 & 모던 B2B SaaS 스타일 커스텀 CSS
# -------------------------------------------------------------
st.set_page_config(
    page_title="B2B Lead Intelligence Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 세션 식별자 및 최초 방문(session_start) 측정 (브라우저 세션당 1회)
if "session_id" not in st.session_state:
    st.session_state["session_id"] = uuid.uuid4().hex

if "session_started" not in st.session_state:
    st.session_state["session_started"] = True
    log_event("session_start")


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
        "vulnerability": "방문자 리뷰 86개로 강남권 상권 내 양호한 검색 유입을 확보하고 있으나, 네이버 간편 예약 및 인스타그램 연동 접점이 미비하여 모바일 탐색 고객의 방문 전환 경로 진단 시 이탈 가설이 도출됩니다. 특히 야간 직장인들의 상담 문의가 카카오톡 수기 응대에 묶여 즉각적 확정이 지연되는 흐름이 관측됩니다. 실시간 예약 파이프라인 보강 시 전환율의 뚜렷한 개선 여지가 있습니다.",
        "priority_score": 94,
        "pitch_fact": "대표님, 방문자 리뷰 86건의 유입 트래픽 중 예약 부재로 이탈하는 야간 직장인 문의를 실시간 간편 예약 시스템으로 즉각 흡수하는 구조를 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 기반으로 모바일 예약 전환과 신규 체험 상담을 2배 높일 수 있는 맞춤 진단 리포트를 무상으로 공유해 드리고자 합니다.",
        "pitch_dm": "원장님 안녕하세요! 센터 인테리어와 후기가 너무 좋아서 피드 눈여겨보고 있었습니다 😊 최근 네이버나 인스타를 통한 신규 상담 전환은 원활하신가요? 동종 업계 반응 좋았던 실무 팁을 가볍게 나누고 싶습니다!",
        "cold_pitch": "대표님, 방문자 리뷰 86건의 유입 트래픽 중 예약 부재로 이탈하는 야간 직장인 문의를 실시간 간편 예약 시스템으로 즉각 흡수하는 구조를 제안드립니다."
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
        "vulnerability": "블로그 리뷰 130개 및 주말 방문객 인지도는 매우 우수하나, 인근 지식산업센터 120여 개 기업을 타깃으로 하는 오피스 원두 B2B 정기구독 및 케이터링 랜딩 접점이 부재합니다. 현재의 개인 고객 중심 유입을 평일 고정적인 법인 정기 납품 매출로 락인(Lock-in)할 수 있는 채널 확장이 요구됩니다. 간편 법인 견적 및 납품 자동화 파이프라인 구축 시 객단가 상승이 기대됩니다.",
        "priority_score": 88,
        "pitch_fact": "대표님, 성수 핫플레이스 인지도를 기반으로 인근 120개 오피스를 겨냥한 B2B 원두 정기구독 및 납품 수주 파이프라인 구축을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 프리미엄 원두 브랜딩을 오피스 정기 납품 시장으로 확장하여 평일 고정 매출을 창출하는 B2B 전략 리포트를 무상 전달드리고자 연락드렸습니다.",
        "pitch_dm": "대표님 안녕하세요! 원두 라인업과 피드 감성이 너무 매력적이어서 오래 지켜보고 있었습니다 ☕ 혹시 인근 기업 오피스 구독이나 B2B 납품 문의도 활발하신가요? 유용한 B2B 확장 사례를 공유해드리고 싶어요!",
        "cold_pitch": "대표님, 성수 핫플레이스 인지도를 기반으로 인근 120개 오피스를 겨냥한 B2B 원두 정기구독 및 납품 수주 파이프라인 구축을 제안드립니다."
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
        "vulnerability": "방문자 리뷰 42개로 핵심 상권 내 초기 신뢰도 형성은 진행 중이나, 스마트블록 키워드 장악력과 플레이스 혜택 쿠폰 경로가 다소 미흡하여 탐색 고객의 방문 전환율 진단 시 개선 여지가 큽니다. 인근 직장인 타깃의 '거북목·체형교정' 전용 검색 유입 장치와 즉시 예약 파이프라인 보강이 권장됩니다. 모바일 지도 탐색에서 실제 체험으로 직결되는 전환 트리거가 필요합니다.",
        "priority_score": 92,
        "pitch_fact": "대표님, 강남구청역 직장인 타깃의 '체형교정' 스마트블록 최적화와 모바일 간편 예약 연동으로 주간 신규 체험 전환 15건을 달성하는 안을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 강남구청역 상권 경쟁 속에서 신규 회원 유치 단가를 낮추고 체험 예약율을 극대화할 수 있는 플레이스 최적화 진단 리포트를 무상으로 보내드리고자 합니다.",
        "pitch_dm": "원장님 안녕하세요! 센터 분위기가 깔끔하고 프라이빗해서 인상 깊었습니다 ✨ 최근 인근 직장인분들의 네이버 예약이나 신규 체험 문의 흐름은 만족스러우신가요?",
        "cold_pitch": "대표님, 강남구청역 직장인 타깃의 '체형교정' 스마트블록 최적화와 모바일 간편 예약 연동으로 주간 신규 체험 전환 15건을 달성하는 안을 제안드립니다."
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
        "vulnerability": "네이버 예약 시스템은 선제적으로 구축되었으나 영수증 리뷰가 14건으로 초기 형성 단계여서 모바일 스마트블록 상위 점유 및 방문 신뢰도 확보에 가설적 병목이 존재합니다. 온라인 자사몰 방문 고객을 오프라인 매장 방문 및 네이버 단골 저장으로 연결하는 크로스 프로모션 장치가 요구됩니다. 디지털 유입 고객의 현장 발걸음을 이끄는 브릿지 설계가 유효합니다.",
        "priority_score": 75,
        "pitch_fact": "대표님, 온라인 자사몰 방문자를 오프라인 매장 방문 및 단골 저장으로 직결시키는 스마트 쿠폰 연동 시스템 도입을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사 브랜드의 온라인 유입 트래픽을 오프라인 매장 방문 및 재구매로 연결하는 전환 최적화 리포트를 무상으로 공유해 드리고자 합니다.",
        "pitch_dm": "대표님 안녕하세요! 디저트 비주얼이 너무 예뻐서 저장해두고 있었어요 🍰 혹시 온라인 고객들의 오프라인 매장 방문 연계나 단골 쿠폰 프로모션은 어떻게 진행 중이신가요?",
        "cold_pitch": "대표님, 온라인 자사몰 방문자를 오프라인 매장 방문 및 단골 저장으로 직결시키는 스마트 쿠폰 연동 시스템 도입을 제안드립니다."
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
        "vulnerability": "방문자 리뷰 130건과 자이로토닉 특화 전문성을 바탕으로 기존 고객 만족도는 높으나, 대치동 학부모 및 직장인을 겨냥한 1:1 프라이빗 패키지 전용 랜딩 접점과 SNS 숏폼 채널 관리가 미흡합니다. 입소문에만 의존하던 기존 구조를 디지털 자동화 상담 및 고단가 회원 락인(Lock-in) 시스템으로 전환할 필요가 있습니다. 체계적인 온라인 신청 파이프라인 도입 시 안정적 고수익 구조 확립이 가능합니다.",
        "priority_score": 95,
        "pitch_fact": "대표님, 대치동 학부모 타깃의 '청소년 체형교정 & 자이로토닉' 고단가 프라이빗 세션 전용 랜딩페이지 및 자동 상담 시스템을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 차별화된 자이로토닉 프로그램을 기반으로 고단가 VIP 고객 유치를 자동화하는 프라이빗 마케팅 진단 리포트를 무상 제공해 드리고자 합니다.",
        "pitch_dm": "원장님 안녕하세요! 자이로토닉 전문 강사진 피드가 정말 전문적이고 멋지네요 👍 대치 상권에서 고단가 정기 세션 문의를 비약적으로 늘린 사례가 있어 가볍게 인사드립니다!",
        "cold_pitch": "대표님, 대치동 학부모 타깃의 '청소년 체형교정 & 자이로토닉' 고단가 프라이빗 세션 전용 랜딩페이지 및 자동 상담 시스템을 제안드립니다."
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
    """pandas DataFrame을 실무 영업 CRM 시트 스타일의 고품질 .xlsx 바이너리로 변환
    (12개 영업 CRM 컬럼 규격: 우선순위점수, 상호명, 업종, 전화번호, 주소, AI 진단 요약, 팩트 제안, 정중한 제안, DM 제안, 연락 일자, 영업 결과, 비고)"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="B2B_영업CRM_리드목록")
        worksheet = writer.sheets["B2B_영업CRM_리드목록"]
        
        # 1. 12개 영업 CRM 컬럼 너비(Width) 지정
        col_widths = {
            "A": 14,  # 우선순위점수
            "B": 25,  # 상호명
            "C": 15,  # 업종
            "D": 26,  # 전화번호
            "E": 36,  # 주소
            "F": 52,  # AI 진단 요약
            "G": 46,  # 팩트 제안 문구
            "H": 46,  # 정중한 제안 문구
            "I": 46,  # DM 제안 문구
            "J": 15,  # 연락 일자
            "K": 26,  # 영업 결과(부재/거절/상담예정/미팅성사)
            "L": 32,  # 비고 및 메모
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

        # 3. 헤더 디자인 (1행: 다크 네이비 #1E293B, 흰색 볼드 11pt, 높이 32pt, 가로/세로 중앙)
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=False)
        worksheet.row_dimensions[1].height = 32

        total_cols = len(df.columns)
        for col_idx in range(1, total_cols + 1):
            cell = worksheet.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border

        # 4. 본문 데이터 서식 (2행부터: 상하 중앙 정렬, 컬럼별 맞춤 정렬, 자동 줄바꿈, 92pt 넉넉한 행 높이)
        body_font = Font(name="맑은 고딕", size=10)
        # A(1), C(3), D(4), J(10), K(11) -> 가운데 정렬
        center_col_indices = {1, 3, 4, 10, 11}
        # B(2), E(5), F(6), G(7), H(8), I(9), L(12) -> 긴 텍스트 줄바꿈 및 좌측 정렬
        wrap_col_indices = {2, 5, 6, 7, 8, 9, 12}

        max_row = worksheet.max_row
        for row_idx in range(2, max_row + 1):
            worksheet.row_dimensions[row_idx].height = 92  # 3가지 피칭 및 심층 진단 여백 확보
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

def _render_pro_modal_body(excel_bytes, excel_filename, excel_mime, industry=None, target_region=None, target_solution=None, lead_count=None):
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
        placeholder="발급받은 인증코드를 입력하세요",
        key="pro_auth_code_input"
    )

    # 유효한 인증코드 목록: 하드코딩 제거 완료, st.secrets["AUTH_CODES"]로만 관리
    valid_codes = set()
    try:
        if "AUTH_CODES" in st.secrets:
            secret_codes = st.secrets["AUTH_CODES"]
            if isinstance(secret_codes, list):
                valid_codes.update([str(c).strip() for c in secret_codes if str(c).strip()])
            elif isinstance(secret_codes, str):
                valid_codes.update([c.strip() for c in secret_codes.split(",") if c.strip()])
    except Exception:
        pass

    is_authed = st.session_state.get("is_pro_authenticated", False)

    if code_input:
        cleaned_input = code_input.strip()
        input_hash = hashlib.sha256(cleaned_input.encode("utf-8")).hexdigest()
        last_checked_hash = st.session_state.get("_last_checked_auth_hash", None)
        # rerun 시 동일 코드의 중복 로깅 방지: 입력 해시값이 새로워졌을 때만 이벤트 발송
        if input_hash != last_checked_hash:
            st.session_state["_last_checked_auth_hash"] = input_hash
            log_event(
                "auth_attempt",
                industry=industry,
                target_region=target_region,
                target_solution=target_solution,
                lead_count=lead_count
            )
            if valid_codes and cleaned_input in valid_codes:
                st.session_state["is_pro_authenticated"] = True
                is_authed = True
                log_event(
                    "auth_success",
                    industry=industry,
                    target_region=target_region,
                    target_solution=target_solution,
                    lead_count=lead_count,
                    auth_result="SUCCESS"
                )
                st.success("✅ 인증이 완료되었습니다! 아래 버튼을 눌러 엑셀 파일을 다운로드하세요.")
            else:
                log_event(
                    "auth_fail",
                    industry=industry,
                    target_region=target_region,
                    target_solution=target_solution,
                    lead_count=lead_count,
                    auth_result="FAIL"
                )
                st.error("인증코드가 올바르지 않습니다. 오픈채팅으로 문의해주세요.")
        elif is_authed:
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
            key="pro_modal_actual_download_btn",
            on_click=log_event,
            args=("excel_download", industry, target_region, target_solution, lead_count)
        )

if dialog_fn:
    @dialog_fn("🔒 프로 멤버십 전용 기능 (엑셀 일괄 다운로드)")
    def show_pro_excel_modal(excel_bytes, excel_filename, excel_mime, industry=None, target_region=None, target_solution=None, lead_count=None):
        _render_pro_modal_body(excel_bytes, excel_filename, excel_mime, industry=industry, target_region=target_region, target_solution=target_solution, lead_count=lead_count)
else:
    def show_pro_excel_modal(excel_bytes, excel_filename, excel_mime, industry=None, target_region=None, target_solution=None, lead_count=None):
        with st.expander("🔒 프로 멤버십 전용 기능 (엑셀 일괄 다운로드)", expanded=True):
            _render_pro_modal_body(excel_bytes, excel_filename, excel_mime, industry=industry, target_region=target_region, target_solution=target_solution, lead_count=lead_count)


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
        vr = l.get("visitor_reviews", 0)
        br = l.get("blog_reviews", 0)
        has_b = l.get("has_booking", False)
        is_large = (vr >= 150 or br >= 50)
        facts_list.append({
            "idx": idx,
            "title": l["title"],
            "category": l["category"],
            "address": l["address"],
            "visitor_reviews": vr,
            "blog_reviews": br,
            "has_booking": "네이버 간편예약 활성화" if has_b else "네이버 간편예약 미연동(부재)",
            "scale_type": "대형/인기 매장 (고객 유입 풍부)" if is_large else "성장/초기 매장"
        })

    facts_json = json.dumps(facts_list, ensure_ascii=False, indent=2)

    prompt = f"""
당신은 대한민국 최상위 B2B 세일즈 전략 및 비즈니스 전환율 최적화 수석 컨설턴트입니다.
아래는 네이버 플레이스에서 실시간 수집한 실제 매장 5곳의 팩트 지표 데이터입니다:

{facts_json}

나의 제안 솔루션: "{target_solution}"

위 5개 매장의 실제 수치(방문자 리뷰 수, 블로그 리뷰 수, 예약 연동 여부, 매장 규모)를 바탕으로, 각 매장별 [객관적 결핍 진단]과 [3가지 맞춤 피칭 문구]를 작성하세요.

[핵심 작성 원칙 - 절대 엄수]
1. vulnerability (AI 진단 요약):
   - [어조 절대 주의]: "~때문에 망합니다", "매출 손실이 심각합니다" 같은 자극적/단정적 어그로성 표현을 완전히 배제하고, "공개 지표 기준 신규 고객 이탈 가설", "온라인 전환 경로 진단", "상담 동선 분석" 등 전문가적이고 객관적인 톤(3~4문장, 150~180자 내외)으로 작성하세요.
   - [대형/인기 매장 예외 처리]: 리뷰 수가 많거나 상위 노출 중인 매장(scale_type이 '대형/인기 매장')은 "손님이 없다"고 지적하지 말고, "고단가 프리미엄 전환", "수기 상담 자동화", "브랜드 락인(SNS 숏폼 브랜딩/VIP 정기 관리)" 중심의 사업 확장형 가치를 진단하세요.
   - [SNS 결핍 진단]: 플레이스 연동 인스타그램 및 SNS 숏폼 채널의 부재 또는 최신 비주얼 소통 결핍 가능성을 진단 포인트로 함께 점검하세요.

2. 3가지 피칭 문구 다변화:
   1) pitch_fact (팩트 제안형 - 문자/전화용):
      - 팩트 수치(리뷰 수, 예약 여부 등)를 근거로 핵심 전환 개선안을 짚어주는 명확하고 전문적인 1줄 문장.
   2) pitch_partner (정중한 파트너형 - 이메일용):
      - 무상 맞춤 진단 리포트 제공 및 파트너십을 제안하는 품격 있고 정중한 문장 (대표님께 거부감 없는 어조).
   3) pitch_dm (인스타 DM형 - SNS용):
      - 가벼운 안부와 칭찬으로 시작하여 질문을 던지는 친근하고 캐주얼한 소통 톤 (이모지 활용).

3. priority_score (영업 우선순위 점수):
   - 제안 솔루션 [{target_solution}] 도입을 통해 즉각적인 전환율 상승 및 사업 확장 여지가 클수록 85~98점 부여 (0~100 정수).

[출력 포맷]
반드시 마크다운 백틱(```) 없이 오직 아래 순수 JSON 리스트 포맷만 반환하세요:
[
  {{
    "idx": 0,
    "priority_score": 92,
    "vulnerability": "방문자 리뷰 130개와 인지도를 갖추어 기본 유입은 안정적이나, 네이버 간편 예약 미연동 및 SNS 비주얼 소통 창구의 부재로 모바일 탐색 고객의 방문 전환 경로 진단 시 이탈 가설이 도출됩니다. 특히 반복적인 단순 수기 문의를 자동화하고 고단가 회원으로 락인(Lock-in)할 수 있는 확장 파이프라인 보강이 권장됩니다.",
    "pitch_fact": "대표님, 방문자 리뷰 130건의 탐색 트래픽을 놓치지 않도록 실시간 간편 예약 및 전환 자동화 시스템 도입을 제안드립니다.",
    "pitch_partner": "대표님 안녕하십니까. 귀사의 탄탄한 인지도를 기반으로 온라인 예약 및 고단가 전환 효율을 높일 수 있는 맞춤 진단 리포트를 무상으로 공유해 드리고자 합니다.",
    "pitch_dm": "대표님 안녕하세요! 공간이 너무 멋져서 눈여겨보고 있었습니다 😊 최근 네이버나 SNS를 통한 신규 문의 전환은 원활하신가요? 실무 전환 팁을 가볍게 나누고 싶습니다!"
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
            is_large = (vr >= 150 or br >= 50)

            if match_ai:
                vuln = match_ai.get("vulnerability", "")
                score = int(match_ai.get("priority_score", 90))
                p_fact = match_ai.get("pitch_fact", match_ai.get("cold_pitch", ""))
                p_partner = match_ai.get("pitch_partner", "")
                p_dm = match_ai.get("pitch_dm", "")
            else:
                score = 92 if not has_b else 80
                if is_large:
                    vuln = f"방문자 리뷰 {vr}개와 블로그 리뷰 {br}개로 상권 내 탄탄한 브랜드 인지도를 확보하고 있으나, 수기 상담 의존도가 높고 SNS 숏폼 채널 연계가 부족하여 고단가 고객 락인(Lock-in) 및 예약 자동화 관점에서 추가 성장 여지가 진단됩니다."
                    p_fact = f"대표님, {lead['title']}의 높은 방문 트래픽을 고단가 정기 고객으로 락인하고 상담을 자동화하는 {target_solution} 구축을 제안드립니다."
                    p_partner = f"대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 바탕으로 상담 리소스를 50% 절감하고 VIP 전환율을 높이는 맞춤 리포트를 무상 제공해 드리고자 합니다."
                    p_dm = f"대표님 안녕하세요! {lead['title']} 인지도와 리뷰 평판이 너무 좋아 평소 관심 있게 지켜보고 있었습니다 ✨ 최근 예약 관리 및 고단가 고객 유입 동선은 만족스러우신가요?"
                else:
                    vuln = f"방문자 리뷰 {vr}개로 지역 검색 유입은 발생하고 있으나, 네이버 간편 예약 미연동 및 SNS 비주얼 소통 접점 부재로 모바일 탐색 고객의 실제 방문 전환 경로 진단 시 이탈 가설이 도출됩니다. 직관적인 예약 및 혜택 파이프라인 보강이 요구됩니다."
                    p_fact = f"대표님, {lead['title']}의 방문자 리뷰 {vr}개 유입 중 전환 장치 부재로 분산되는 잠재 고객을 {target_solution} 도입으로 즉각 흡수해 드립니다."
                    p_partner = f"대표님 안녕하십니까. {lead['title']}의 지역 플레이스 인지도를 바탕으로 온라인 예약 및 고객 전환율을 극대화하는 맞춤 진단 리포트를 무상 전달드리고자 합니다."
                    p_dm = f"대표님 안녕하세요! {lead['title']} 공간이 정말 매력적이어서 피드 구경하다 인사드려요 😊 최근 온라인 채널을 통한 신규 고객 문의는 원활하신가요?"

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
                "pitch_fact": p_fact,
                "pitch_partner": p_partner,
                "pitch_dm": p_dm,
                "cold_pitch": p_fact
            })

        return merged_results, None

    except Exception as e:
        return None, str(e)

def enrich_leads_rule_based(leads: list, target_solution: str) -> list:
    """Gemini API가 없거나 오류 시, 수집된 팩트 데이터를 기반으로 3종 맞춤 피칭 및 객관적 결핍 진단 합성"""
    results = []
    for idx, l in enumerate(leads):
        has_b = l.get("has_booking", False)
        vr = l.get("visitor_reviews", 0)
        br = l.get("blog_reviews", 0)
        is_large = (vr >= 150 or br >= 50)
        score = 94 if not has_b and vr >= 30 else (88 if not has_b else 78)
        
        if is_large:
            vuln = f"방문자 리뷰 {vr}개와 블로그 리뷰 {br}개로 상권 내 탄탄한 브랜드 인지도를 확보하고 있으나, 수기 상담 의존도가 높고 SNS 숏폼 채널 연계가 부족하여 고단가 고객 락인(Lock-in) 및 예약 자동화 관점에서 추가 성장 여지가 진단됩니다."
            p_fact = f"대표님, {l['title']}의 높은 방문 트래픽을 고단가 정기 고객으로 락인하고 상담을 자동화하는 {target_solution} 구축을 제안드립니다."
            p_partner = f"대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 바탕으로 상담 리소스를 50% 절감하고 VIP 전환율을 높이는 맞춤 리포트를 무상 제공해 드리고자 합니다."
            p_dm = f"대표님 안녕하세요! {l['title']} 인지도와 리뷰 평판이 너무 좋아 평소 관심 있게 지켜보고 있었습니다 ✨ 최근 예약 관리 및 고단가 고객 유입 동선은 만족스러우신가요?"
        else:
            if not has_b:
                vuln = f"방문자 리뷰 {vr}개로 지역 검색 유입은 발생하고 있으나, 네이버 간편 예약 미연동 및 SNS 비주얼 소통 접점 부재로 모바일 탐색 고객의 실제 방문 전환 경로 진단 시 이탈 가설이 도출됩니다. 직관적인 예약 및 혜택 파이프라인 보강이 요구됩니다."
                p_fact = f"대표님, {l['title']}의 방문자 리뷰 {vr}개 유입 중 전환 장치 부재로 분산되는 잠재 고객을 {target_solution} 도입으로 즉각 흡수해 드립니다."
                p_partner = f"대표님 안녕하십니까. {l['title']}의 지역 플레이스 인지도를 바탕으로 온라인 예약 및 고객 전환율을 극대화하는 맞춤 진단 리포트를 무상 전달드리고자 합니다."
                p_dm = f"대표님 안녕하세요! {l['title']} 공간이 정말 매력적이어서 피드 구경하다 인사드려요 😊 최근 온라인 채널을 통한 신규 고객 문의는 원활하신가요?"
            else:
                vuln = f"방문자 리뷰 {vr}개와 네이버 예약을 보유하여 기본 유입망은 갖추었으나, 스마트블록 키워드 장악력과 SNS 채널 연계 콘텐츠가 다소 취약합니다. 상위 노출 경쟁사 대비 실제 예약 전환율 정체를 해소하고 고단가 유치를 위한 유입 경로 최적화가 권장됩니다."
                p_fact = f"대표님, 이미 활성화된 네이버 예약 시스템의 전환 효율을 {target_solution}로 2배 극대화하여 월 매출 성장을 지원해 드립니다."
                p_partner = f"대표님 안녕하십니까. {l['title']}의 예약 시스템에 고단가 전환과 단골 락인을 더하는 실무 분석 리포트를 무상으로 전달드리고 싶습니다."
                p_dm = f"대표님 안녕하세요! {l['title']}의 예약 고객 재방문 및 객단가 상승을 돕는 유용한 인사이트를 공유해 드려도 될까요?"

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
            "pitch_fact": p_fact,
            "pitch_partner": p_partner,
            "pitch_dm": p_dm,
            "cold_pitch": p_fact
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
    log_event(
        "search_attempt",
        industry=industry.strip() if industry else None,
        target_region=target_region.strip() if target_region else None,
        target_solution=target_solution
    )
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
            with st.spinner("⚡ 실시간 네이버 데이터 분석 및 3개 채널별 맞춤 피칭 생성 중... (약 10~20초 소요)"):
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
    if lead_results:
        log_event(
            "search_success",
            industry=industry.strip() if industry else None,
            target_region=target_region.strip() if target_region else None,
            target_solution=target_solution,
            lead_count=len(lead_results)
        )
        st.success(f"총 {len(lead_results)}건의 네이버 플레이스 실시간 잠재고객 분석 및 콜드 피칭이 생성되었습니다!")
    else:
        log_event(
            "search_fail",
            industry=industry.strip() if industry else None,
            target_region=target_region.strip() if target_region else None,
            target_solution=target_solution,
            lead_count=0
        )
        st.warning("⚠️ 검색 결과를 가져오지 못했습니다. 업종 또는 지역을 확인해주세요.")

# -------------------------------------------------------------
# 7. 결과 화면 탭 뷰 (카드 뷰 vs 테이블 뷰)
# -------------------------------------------------------------
results = st.session_state.get("lead_results", None)

if results:
    # 1) 실무 영업 CRM 시트 규격 데이터 가공 (12개 컬럼)
    today_str = datetime.now().strftime("%Y%m%d")
    clean_region = target_region.strip().replace(" ", "_") if target_region else "전국"
    clean_industry = industry.strip().replace(" ", "_") if industry else "업종"
    excel_filename = f"영업CRM_{clean_region}_{clean_industry}_{today_str}.xlsx"

    df_export = pd.DataFrame([
        {
            "우선순위점수": l["priority_score"],
            "상호명": l["title"],
            "업종": l["category"],
            "전화번호": l.get("telephone", "").strip() if l.get("telephone") and l.get("telephone").strip() not in ["", "정보 없음", "전화번호 미등록", "미등록", "-"] else "미등록 (네이버톡톡/DM 권장)",
            "주소": l["address"],
            "AI 진단 요약": l["vulnerability"],
            "팩트 제안 문구": l.get("pitch_fact", l.get("cold_pitch", "")),
            "정중한 제안 문구": l.get("pitch_partner", ""),
            "DM 제안 문구": l.get("pitch_dm", ""),
            "연락 일자": "",
            "영업 결과(부재/거절/상담예정/미팅성사)": "",
            "비고 및 메모": f"방문자 리뷰 {l.get('visitor_reviews', 0)}개, 블로그 리뷰 {l.get('blog_reviews', 0)}개, 예약 {'연동' if l.get('has_booking') else '미연동'}"
        }
        for l in results
    ])
    # 영업 우선순위점수 기준 내림차순 정렬
    df_export = df_export.sort_values(by="우선순위점수", ascending=False).reset_index(drop=True)
    excel_bytes = generate_excel_bytes(df_export)
    excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 2) 결과 목록 상단 헤더 & 프로 결제 안내 모달 연동 엑셀 다운로드 버튼
    top_col1, top_col2 = st.columns([2.6, 1.8])
    with top_col1:
        st.markdown(f"### 📋 네이버 플레이스 영업 리스트 ({len(results)}개 매장)")
    with top_col2:
        if st.session_state.get("is_pro_authenticated", False):
            st.download_button(
                label="📥 영업 CRM 엑셀 다운로드 (PRO)",
                data=excel_bytes,
                file_name=excel_filename,
                mime=excel_mime,
                type="primary",
                use_container_width=True,
                key="top_pro_excel_download_btn",
                help="PRO 인증이 완료되어 클릭 즉시 12개 실무 CRM 컬럼 .xlsx 보고서가 다운로드됩니다.",
                on_click=log_event,
                args=("excel_download", clean_industry, clean_region, target_solution, len(results) if results else None)
            )
        else:
            if st.button(
                "📥 실시간 잠재고객 엑셀 다운로드",
                type="primary",
                use_container_width=True,
                help="프로 멤버십 전용 기능입니다. 클릭 시 이용권 안내 및 인증코드 입력 팝업이 열립니다."
            ):
                log_event(
                    "pro_modal_open",
                    industry=clean_industry,
                    target_region=clean_region,
                    target_solution=target_solution,
                    lead_count=len(results) if results else None
                )
                show_pro_excel_modal(
                    excel_bytes, excel_filename, excel_mime,
                    industry=clean_industry, target_region=clean_region, target_solution=target_solution, lead_count=len(results) if results else None
                )

    st.write("")
    tab1, tab2 = st.tabs(["📇 카드 뷰 (채널별 피칭 3종 & 상세 분석)", "📊 CRM 테이블 뷰 (실무 관리 시트)"])
    
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
                booking_badge = '<span class="badge-booking-no">🔴 네이버 예약 미연동 (전환 누수 가설)</span>'
                
            vr_count = lead.get("visitor_reviews", 0)
            br_count = lead.get("blog_reviews", 0)
            review_badge = f'<span class="badge-review">💬 방문자 리뷰 <b>{vr_count:,}</b>개 &nbsp;|&nbsp; 📝 블로그 리뷰 <b>{br_count:,}</b>개</span>'
            
            place_link_html = ''
            if lead.get("place_url"):
                place_link_html = f'<a href="{lead["place_url"]}" target="_blank" style="font-size:12px; color:#2563eb; margin-left:8px; text-decoration:none; font-weight:600;">네이버 플레이스 ↗</a>'
                
            # 카드 HTML 렌더링 (객관적/전문가적 어조 적용)
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
                    <strong>🔍 AI 온라인 전환 경로 진단 (팩트 지표 기반 분석):</strong><br>
                    {lead['vulnerability']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 3가지 피칭 문구 다변화 탭 (팩트 제안 / 정중한 파트너 / 인스타 DM)
            p_fact = lead.get('pitch_fact', lead.get('cold_pitch', ''))
            p_partner = lead.get('pitch_partner', '')
            p_dm = lead.get('pitch_dm', '')

            st.markdown("<div style='font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 4px;'>💬 채널별 맞춤 피칭 스크립트 (원클릭 복사):</div>", unsafe_allow_html=True)
            tab_p1, tab_p2, tab_p3 = st.tabs([
                "📱 팩트 제안형 (문자/전화)", 
                "✉️ 정중한 파트너형 (이메일)", 
                "📸 인스타 DM형 (SNS)"
            ])
            with tab_p1:
                st.caption("💡 실제 지표 팩트를 바탕으로 즉각적인 전환 개선안을 짚어주는 문자/유선 콜드콜용 스크립트입니다.")
                st.code(p_fact, language="markdown")
            with tab_p2:
                st.caption("💡 무료 맞춤 리포트 제공과 파트너십을 정중하게 권하는 공식 이메일/제안서용 멘트입니다.")
                st.code(p_partner, language="markdown")
            with tab_p3:
                st.caption("💡 가벼운 안부와 칭찬으로 대화를 열어 답장률을 극대화하는 인스타그램 DM/SNS용 멘트입니다.")
                st.code(p_dm, language="markdown")
            
            st.write("")

    # [탭 2: 테이블 뷰]
    with tab2:
        st.markdown("#### 📊 실무 영업 CRM 시트 요약 및 관리")
        st.caption("아래 12개 컬럼 전체가 엑셀(.xlsx)로 다운로드되어, 연락 일자와 영업 결과를 바로 기록 관리할 수 있습니다.")
        
        st.dataframe(
            df_export,
            use_container_width=True,
            column_config={
                "우선순위점수": st.column_config.ProgressColumn(
                    "우선순위",
                    help="AI가 산출한 영업 우선순위 점수 (0~100)",
                    format="%d점",
                    min_value=0,
                    max_value=100
                ),
            },
            hide_index=True
        )
        
        # 하단 다운로드 버튼 (PRO 게이팅 연동)
        if st.session_state.get("is_pro_authenticated", False):
            st.download_button(
                label=f"📥 {excel_filename} 다운로드 (PRO)",
                data=excel_bytes,
                file_name=excel_filename,
                mime=excel_mime,
                type="secondary",
                key="bottom_excel_download_btn",
                on_click=log_event,
                args=("excel_download", clean_industry, clean_region, target_solution, len(results) if results else None)
            )
        else:
            if st.button(
                f"📥 {excel_filename} 다운로드 (프로 전용)",
                type="secondary",
                key="bottom_excel_download_btn"
            ):
                log_event(
                    "pro_modal_open",
                    industry=clean_industry,
                    target_region=clean_region,
                    target_solution=target_solution,
                    lead_count=len(results) if results else None
                )
                show_pro_excel_modal(
                    excel_bytes, excel_filename, excel_mime,
                    industry=clean_industry, target_region=clean_region, target_solution=target_solution, lead_count=len(results) if results else None
                )
else:
    # 최초 진입 시 안내 화면
    st.info("💡 위 설정창에서 타깃 조건(업종, 지역, 제공 서비스)을 확인한 뒤 **'🚀 잠재고객 분석 및 피칭 생성'** 버튼을 클릭해보세요. 네이버 플레이스에서 실제 매장 5곳의 지표를 즉각 수집합니다.")
