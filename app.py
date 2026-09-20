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

# google-genai 최신 패키지 안전 임포트
try:
    from google import genai
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
    .badge-fact-yes {
        background: #f0fdf4;
        color: #15803d;
        border: 1px solid #bbf7d0;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        text-decoration: none;
    }
    .badge-fact-no {
        background: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
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
        "homepage_url": None,
        "instagram_url": None,
        "has_talktalk": False,
        "talktalk_url": None,
        "menu_count": 0,
        "has_price_info": False,
        "keywords": [],
        "keyword_count": None,
        "keywords_status": "unconfirmed",
        "has_keywords_info": False,
        "visitor_reviews": 86,
        "blog_reviews": 42,
        "has_booking": False,
        "rating": 4.8,
        "review_count": 86,
        "vulnerability": "방문자 리뷰 86개로 상권 내 검색 유입은 발생하고 있으나, 네이버 플레이스 기준 공식 홈페이지 및 인스타그램 링크가 미등록되어 있으며 네이버 간편 예약과 톡톡 상담 접점이 미연동 상태입니다. 온라인상에서 가격 정보 또한 미확인되어 심야/주말 탐색 고객의 방문 전환 경로에서 이탈 가설이 도출됩니다.",
        "priority_score": 94,
        "pitch_fact": "대표님, 네이버 플레이스 방문 트래픽 중 예약과 톡톡 부재로 이탈하는 고객 문의를 실시간 간편 예약 및 상담 파이프라인으로 흡수하는 안을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 기반으로 모바일 예약 전환과 신규 체험 상담을 2배 높일 수 있는 맞춤 진단 리포트를 무상으로 공유해 드리고자 합니다.",
        "pitch_dm": "원장님 안녕하세요! 센터 인테리어와 후기가 너무 좋아서 눈여겨보고 있었습니다 😊 최근 네이버를 통한 신규 상담 전환은 원활하신가요? 동종 업계 반응 좋았던 실무 팁을 가볍게 나누고 싶습니다!",
        "cold_pitch": "대표님, 네이버 플레이스 방문 트래픽 중 예약과 톡톡 부재로 이탈하는 고객 문의를 실시간 간편 예약 및 상담 파이프라인으로 흡수하는 안을 제안드립니다."
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
        "homepage_url": None,
        "instagram_url": "https://instagram.com/moment_seongsu",
        "has_talktalk": True,
        "talktalk_url": "https://talk.naver.com/sample2",
        "menu_count": 8,
        "has_price_info": True,
        "keywords": ["성수카페", "스페셜티커피", "핸드드립"],
        "keyword_count": 3,
        "keywords_status": "confirmed",
        "has_keywords_info": True,
        "visitor_reviews": 210,
        "blog_reviews": 130,
        "has_booking": False,
        "rating": 4.6,
        "review_count": 210,
        "vulnerability": "블로그 리뷰 130개 및 인스타그램 공식 연동으로 탄탄한 인지도를 갖추고 있으나, 네이버 플레이스 기준 공식 홈페이지(자사몰) 링크가 미등록되어 있어 인근 기업 대상의 B2B 원두 정기구독 및 오피스 납품 전용 접점이 분산되는 흐름이 관측됩니다.",
        "priority_score": 88,
        "pitch_fact": "대표님, 성수 로스터리 인지도를 기반으로 인근 120개 오피스를 겨냥한 B2B 원두 정기구독 및 납품 수주 파이프라인 구축을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 프리미엄 원두 브랜딩을 오피스 정기 납품 시장으로 확장하여 평일 고정 매출을 창출하는 B2B 전략 리포트를 무상 전달드리고자 연락드렸습니다.",
        "pitch_dm": "대표님 안녕하세요! 원두 라인업과 피드 감성이 너무 매력적이어서 오래 지켜보고 있었습니다 ☕ 혹시 인근 기업 오피스 구독이나 B2B 납품 문의도 활발하신가요? 유용한 B2B 확장 사례를 공유해드리고 싶어요!",
        "cold_pitch": "대표님, 성수 로스터리 인지도를 기반으로 인근 120개 오피스를 겨냥한 B2B 원두 정기구독 및 납품 수주 파이프라인 구축을 제안드립니다."
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
        "homepage_url": None,
        "instagram_url": None,
        "has_talktalk": False,
        "talktalk_url": None,
        "menu_count": 4,
        "has_price_info": True,
        "keywords": ["강남구청필라테스", "체형교정", "기구필라테스"],
        "keyword_count": 3,
        "keywords_status": "confirmed",
        "has_keywords_info": True,
        "visitor_reviews": 42,
        "blog_reviews": 15,
        "has_booking": False,
        "rating": 4.5,
        "review_count": 42,
        "vulnerability": "방문자 리뷰 42개 및 등록 메뉴 4개의 가격이 정상 노출되어 있으나, 네이버 플레이스 기준 공식 홈페이지 및 인스타그램 링크가 미등록되어 있으며 네이버 간편 예약이 미연동 상태입니다. 탐색 고객을 즉각적인 체험 방문으로 연결하는 모바일 전환 트리거 보강이 권장됩니다.",
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
        "homepage_url": "https://velvetmood.kr",
        "instagram_url": "https://instagram.com/velvetmood_cafe",
        "has_talktalk": True,
        "talktalk_url": "https://talk.naver.com/sample4",
        "menu_count": 12,
        "has_price_info": True,
        "keywords": ["성수디저트", "성수베이커리", "성수데이트"],
        "keyword_count": 3,
        "keywords_status": "confirmed",
        "has_keywords_info": True,
        "visitor_reviews": 14,
        "blog_reviews": 28,
        "has_booking": True,
        "rating": 4.3,
        "review_count": 14,
        "vulnerability": "공식 홈페이지, 인스타그램, 네이버 예약 및 톡톡까지 풀 패키지 채널을 확보하고 있으나, 영수증 리뷰가 14건으로 초기 단계여서 검색 상위 점유를 위한 방문자 후기 활성화 및 단골 고객 락인(Lock-in) 이벤트 장치가 보강될 필요가 있습니다.",
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
        "homepage_url": None,
        "instagram_url": None,
        "has_talktalk": False,
        "talktalk_url": None,
        "menu_count": 0,
        "has_price_info": False,
        "keywords": ["대치동필라테스", "자이로토닉", "체형교정"],
        "keyword_count": 3,
        "keywords_status": "confirmed",
        "has_keywords_info": True,
        "visitor_reviews": 130,
        "blog_reviews": 85,
        "has_booking": False,
        "rating": 4.9,
        "review_count": 130,
        "vulnerability": "방문자 리뷰 130건으로 높은 신뢰도를 갖추었으나, 네이버 플레이스 기준 공식 홈페이지 및 인스타그램 링크가 미등록 상태이며 가격 정보 또한 온라인상에서 미확인됩니다. 대치 상권의 프라이빗 수요를 고려할 때 온라인 비대면 가격 및 상세 안내 파이프라인 정비가 유효합니다.",
        "priority_score": 95,
        "pitch_fact": "대표님, 대치동 학부모 타깃의 '청소년 체형교정 & 자이로토닉' 고단가 프라이빗 세션 전용 랜딩페이지 및 자동 상담 시스템을 제안드립니다.",
        "pitch_partner": "대표님 안녕하십니까. 귀사의 차별화된 자이로토닉 프로그램을 기반으로 고단가 VIP 고객 유치를 자동화하는 프라이빗 마케팅 진단 리포트를 무상 제공해 드리고자 합니다.",
        "pitch_dm": "원장님 안녕하세요! 자이로토닉 전문 강사진 후기가 정말 좋네요 👍 대치 상권에서 고단가 정기 세션 문의를 비약적으로 늘린 사례가 있어 가볍게 인사드립니다!",
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
    (영업 우선순위, 상호명, 업종, 전화번호, 주소, 네이버 플레이스 팩트 5종, AI 진단 요약, 3종 피칭 문구 등)"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="B2B_영업CRM_리드목록")
        worksheet = writer.sheets["B2B_영업CRM_리드목록"]
        
        # 1. 컬럼별 맞춤 너비(Width) 정의
        col_width_defaults = {
            "연락 우선순위": 16,
            "솔루션 적합도 점수": 18,
            "우선순위점수": 14,
            "상호명": 25,
            "업종": 16,
            "전화번호": 26,
            "주소": 36,
            "홈페이지 링크": 32,
            "인스타그램 링크": 32,
            "네이버 톡톡": 14,
            "메뉴 등록 수": 14,
            "가격 정보 여부": 22,
            "대표 키워드 수": 14,
            "대표 키워드": 32,
            "네이버 예약": 14,
            "방문자 리뷰": 14,
            "블로그 리뷰": 14,
            "AI 진단 요약": 52,
            "팩트 제안 문구": 46,
            "정중한 제안 문구": 46,
            "DM 제안 문구": 46,
            "연락 일자": 15,
            "영업 결과(부재/거절/상담예정/미팅성사)": 26,
            "비고 및 메모": 32,
        }
        for col_idx, col_name in enumerate(df.columns, start=1):
            letter = get_column_letter(col_idx)
            w = col_width_defaults.get(col_name, 20)
            worksheet.column_dimensions[letter].width = w

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
        center_col_names = {"우선순위점수", "업종", "전화번호", "네이버 톡톡", "메뉴 등록 수", "가격 정보 여부", "네이버 예약", "방문자 리뷰", "블로그 리뷰", "연락 일자", "영업 결과(부재/거절/상담예정/미팅성사)"}
        wrap_col_names = {"상호명", "주소", "홈페이지 링크", "인스타그램 링크", "AI 진단 요약", "팩트 제안 문구", "정중한 제안 문구", "DM 제안 문구", "비고 및 메모"}

        max_row = worksheet.max_row
        for row_idx in range(2, max_row + 1):
            worksheet.row_dimensions[row_idx].height = 92  # 3가지 피칭 및 심층 진단 여백 확보
            for col_idx, col_name in enumerate(df.columns, start=1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                cell.font = body_font
                cell.border = thin_border
                
                is_center = col_name in center_col_names
                is_wrap = col_name in wrap_col_names
                
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
    """genai.Client(api_key=api_key).models.list()를 조회하여 'generateContent'를 지원하는 표준 유효 모델 목록 추출
    (쿼터 제한이 극심한 omni, preview, experimental 등은 완전 제외)"""
    if not HAS_GENAI or not api_key:
        return []
    try:
        client = genai.Client(api_key=api_key)
        # 쿼터 초과 및 불안정을 유발하는 프리뷰/실험 모델 키워드 필터링
        EXCLUDE_KEYWORDS = ["omni", "preview", "experimental", "exp", "thinking"]
        
        valid_models = []
        for m in client.models.list():
            actions = getattr(m, 'supported_actions', getattr(m, 'supported_generation_methods', [])) or []
            if 'generateContent' in actions:
                m_name = m.name or ""
                clean_name = m_name.replace("models/", "")
                name_lower = clean_name.lower()
                if any(k in name_lower for k in EXCLUDE_KEYWORDS):
                    continue
                valid_models.append(clean_name)
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
        client = genai.Client(api_key=api_key)
        # 자동 감지된 최적 모델 선택 (404 Not Found 방지)
        target_model = model_name or resolve_best_model(api_key)

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
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
        except Exception:
            # 2차 시도: 일반 텍스트 포맷 호출 후 정규식 파싱
            response = client.models.generate_content(
                model=target_model,
                contents=prompt
            )

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


def sanitize_lead(lead: dict, target_region: str, industry: str) -> dict:
    """
    Candidate Sanitizer v0 (Observe Only):
    수집된 매장 팩트(주소, 카테고리)와 사용자의 검색 타깃(target_region, industry)의
    적합성을 confirmed / uncertain / mismatch 3단계로 보수적으로 판정 (관찰 모드)
    - mismatch: 명백한 타 행정구역 이탈 또는 검증된 비적합 업종
    - uncertain: 동/상권/역세권 등 자유 주소이거나 복합시설 가능성
    - confirmed: 명확히 일치
    """
    reg = (target_region or "").strip()
    ind = (industry or "").strip()
    addr = str(lead.get("roadAddress") or lead.get("address") or "").strip()
    cat = str(lead.get("category") or "").strip()
    title = str(lead.get("title") or lead.get("name") or "").strip()

    # 1. 지역 판정 (Region Match)
    region_match = "uncertain"
    region_reason = ""

    if not reg:
        region_match = "uncertain"
        region_reason = "타깃 지역 미입력"
    else:
        tokens = reg.split()
        last_token = tokens[-1] if tokens else ""
        is_admin_district = any(last_token.endswith(sfx) for sfx in ["구", "시", "군"])

        if is_admin_district:
            target_district = last_token
            if target_district in addr:
                region_match = "confirmed"
                region_reason = f"행정구역 일치 ({target_district})"
            else:
                region_match = "mismatch"
                region_reason = f"행정구역 불일치 (타깃: {target_district}, 주소: {addr})"
        else:
            core_reg = reg[:-1] if reg.endswith("역") and len(reg) > 2 else reg
            core_reg_dong = reg[:-1] if reg.endswith("동") and len(reg) > 2 else reg

            if reg in addr or core_reg in addr or core_reg_dong in addr or reg in title or core_reg in title:
                region_match = "confirmed"
                region_reason = f"지역 키워드 확인 ({reg})"
            else:
                region_match = "uncertain"
                region_reason = f"자유 상권/역세권 주소 직접 대조 불가 ({reg})"

    # 2. 업종 판정 (Category Match)
    category_match = "uncertain"
    category_reason = ""

    cat_lower = cat.lower()
    ind_lower = ind.lower()
    cafe_allowlist = ["카페", "디저트", "베이커리", "커피", "브런치", "제과", "북카페", "아이스크림"]

    is_mismatch = False
    if "피부과" in ind_lower:
        if any(bad in cat_lower for bad in ["발관리", "마사지", "스파"]) and not any(ok in cat_lower for ok in ["피부과", "의원", "병원"]):
            is_mismatch = True
            category_reason = f"비의료 미용/마사지 시설 ({cat})"
    elif "필라테스" in ind_lower:
        if any(bad in cat_lower for bad in ["수영장", "골프"]) and not any(ok in cat_lower for ok in ["필라테스", "요가"]):
            is_mismatch = True
            category_reason = f"수영/골프 등 이종 체육시설 ({cat})"
    elif "카페" in ind_lower:
        if any(bad in cat_lower for bad in ["술집", "주점", "호프", "포차", "요리주점"]) and not any(ok in cat_lower for ok in cafe_allowlist):
            is_mismatch = True
            category_reason = f"야간 주점/유흥 시설 ({cat})"

    if is_mismatch:
        category_match = "mismatch"
    else:
        if ind_lower in cat_lower:
            category_match = "confirmed"
            category_reason = f"업종명 직접 일치 ({cat})"
        elif "카페" in ind_lower and any(ok in cat_lower for ok in cafe_allowlist):
            category_match = "confirmed"
            category_reason = f"카페 연관 표준 카테고리 ({cat})"
        elif "필라테스" in ind_lower and any(sub in cat_lower for sub in ["헬스장", "피트니스", "스포츠시설", "체육시설", "요가"]):
            category_match = "uncertain"
            category_reason = f"헬스/피트니스 복합시설 가능성 ({cat})"
        elif "피부과" in ind_lower and any(sub in cat_lower for sub in ["피부", "체형", "에스테틱", "관리"]):
            category_match = "uncertain"
            category_reason = f"에스테틱/피부관리 복합 가능성 ({cat})"
        else:
            category_match = "uncertain"
            category_reason = f"카테고리 직관 대조 보류 ({cat})"

    # 3. 종합 Sanitizer 상태 판정
    if region_match == "mismatch" or category_match == "mismatch":
        sanitizer_status = "mismatch"
        reasons = []
        if region_match == "mismatch":
            reasons.append(region_reason)
        if category_match == "mismatch":
            reasons.append(category_reason)
        sanitizer_reason = " / ".join(reasons)
    elif region_match == "uncertain" or category_match == "uncertain":
        sanitizer_status = "uncertain"
        reasons = []
        if region_match == "uncertain":
            reasons.append(region_reason)
        if category_match == "uncertain":
            reasons.append(category_reason)
        sanitizer_reason = " / ".join(reasons)
    else:
        sanitizer_status = "confirmed"
        sanitizer_reason = "지역 및 업종 적합도 정상 확인"

    return {
        "region_match": region_match,
        "category_match": category_match,
        "sanitizer_status": sanitizer_status,
        "sanitizer_reason": sanitizer_reason
    }

def crawl_naver_place_leads(region: str, industry: str, limit: int = 10) -> list:
    """모바일 네이버 지도/검색(m.search.naver.com)에서 실시간으로 상위 매장(최대 10곳)의 팩트 지표를 고속 스크래핑
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
    # 2. 각 플레이스 모바일 홈 페이지에서 __APOLLO_STATE__ 및 예약/링크/메뉴 태그 고속 추출
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
                    # 1) 네이버 간편 예약 활성화 여부 판별
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

                    # ROOT_QUERY 내 placeDetail 객체 우선 참조 (풀 상세 데이터 확보)
                    place_detail = {}
                    root_query = data.get('ROOT_QUERY') or {}
                    if isinstance(root_query, dict):
                        for rk, rv in root_query.items():
                            if rk.startswith('placeDetail(') and isinstance(rv, dict):
                                place_detail = rv
                                break

                    # 2) 팩트 1 & 2: 공식 홈페이지 및 인스타그램 링크 방어적 파싱
                    homepage_url = None
                    instagram_url = None
                    homepages_obj = place_detail.get('homepages') or b.get('homepages') or {}
                    all_hp_items = []
                    if isinstance(homepages_obj, dict):
                        repr_hp = homepages_obj.get('repr')
                        if isinstance(repr_hp, dict):
                            all_hp_items.append(repr_hp)
                        etc_hp = homepages_obj.get('etc')
                        if isinstance(etc_hp, list):
                            all_hp_items.extend([item for item in etc_hp if isinstance(item, dict)])

                    for hp in all_hp_items:
                        u = (hp.get('url') or hp.get('landingUrl') or '').strip()
                        t = (hp.get('type') or hp.get('typeI18n') or '').strip()
                        if not u or not u.startswith('http'):
                            continue
                        # 인스타그램 판별
                        if not instagram_url and ('인스타그램' in t or 'instagram.com' in u.lower()):
                            instagram_url = u
                        # 홈페이지 판별 (블로그, 인스타, 유튜브, 페이스북 제외한 공식 사이트)
                        elif not homepage_url and ('홈페이지' in t or (t not in ['블로그', '인스타그램', '유튜브', '페이스북'] and not any(x in u.lower() for x in ['instagram.com', 'blog.naver.com', 'youtube.com', 'facebook.com']))):
                            homepage_url = u

                    # 3) 팩트 3: 네이버 톡톡 실시간 상담 연동 여부 및 URL
                    raw_talktalk = str(place_detail.get('talktalkUrl') or b.get('talktalkUrl') or '').strip()
                    talktalk_url = raw_talktalk if raw_talktalk.startswith('http') else None
                    has_talktalk = bool(talktalk_url)

                    # 4) 팩트 4: 메뉴/서비스 등록 개수 및 가격 정보 노출 여부
                    menu_items = [v for k, v in data.items() if k.startswith(f'Menu:{pid}_') or (k.startswith('Menu:') and isinstance(v, dict))]
                    if not menu_items:
                        ref_menus = place_detail.get('menus') or b.get('menus') or []
                        for rm in ref_menus:
                            if isinstance(rm, dict) and '__ref' in rm:
                                ref_k = rm['__ref']
                                if ref_k in data and isinstance(data[ref_k], dict):
                                    menu_items.append(data[ref_k])

                    menu_count = len(menu_items)
                    # 유효 가격 등록 여부 검증 (가격이 등록되어 있고 빈값, 0, '-'이 아닌 경우)
                    has_price_info = any(
                        m.get('price') and str(m.get('price')).strip() not in ['', '0', 'None', '-']
                        for m in menu_items
                    )

                    # 5) 팩트 5: 네이버 플레이스 대표 키워드 (스마트플레이스 관리자 등록 대표 키워드) 방어적 파싱
                    info_tab = place_detail.get('informationTab') or {}
                    raw_keywords = info_tab.get('keywordList')
                    if isinstance(raw_keywords, list):
                        keywords = [str(k).strip() for k in raw_keywords if k and str(k).strip()]
                        keyword_count = len(keywords)
                        keywords_status = "confirmed"
                        has_keywords_info = True
                    else:
                        keywords = []
                        keyword_count = None
                        keywords_status = "unconfirmed"
                        has_keywords_info = False

                    lead_item = {
                        "id": pid,
                        "title": title,
                        "category": category,
                        "address": address,
                        "telephone": phone,
                        "visitor_reviews": int(b.get('visitorReviewsTotal') or 0),
                        "blog_reviews": int(b.get('cafeBlogReviewsTotal') or 0),
                        "has_booking": has_booking,
                        "homepage_url": homepage_url,
                        "has_homepage": bool(homepage_url),
                        "instagram_url": instagram_url,
                        "has_instagram": bool(instagram_url),
                        "talktalk_url": talktalk_url,
                        "has_talktalk": has_talktalk,
                        "menu_count": menu_count,
                        "has_price_info": has_price_info,
                        "keywords": keywords,
                        "keyword_count": keyword_count,
                        "keywords_status": keywords_status,
                        "has_keywords_info": has_keywords_info,
                        "place_url": pr.url or f"https://m.place.naver.com/place/{pid}/home",
                        "link": homepage_url or instagram_url or pr.url or f"https://m.place.naver.com/place/{pid}/home"
                    }
                    san_res = sanitize_lead(lead_item, region, industry)
                    lead_item.update(san_res)
                    leads.append(lead_item)
        except Exception:
            continue

    return leads

def calculate_priority_score(lead: dict, target_solution: str) -> int:
    """
    현재 수집된 팩트와 선택된 target_solution을 기반으로 영업 제안 우선순위 점수(0~100)를 결정론적으로 계산.
    - 점수의 의미: '실제 결핍 확정도'나 '업체 인지도/규모'가 아닌 '수집 데이터 기준 솔루션 제안 우선순위'
    - 동일한 업체 팩트 + 동일한 target_solution이면 100% 동일한 점수 산출
    - 리뷰 수/활동량 지표는 솔루션 제안 필요성의 직접 근거가 아니므로 점수 계산에서 완전 배제 (가산 없음)
    """
    has_b = bool(lead.get("has_booking"))
    has_hp = bool(lead.get("has_homepage"))
    has_insta = bool(lead.get("has_instagram"))
    has_tt = bool(lead.get("has_talktalk"))
    has_price = bool(lead.get("has_price_info"))
    menu_count = int(lead.get("menu_count") or 0)

    sol = (target_solution or "").strip()

    # 1. 솔루션별 결정론적 점수 산정
    # A. 종합 로컬 마케팅 (플레이스 상위노출 & 블로그 체험단) - "플레이스" 단어 포함 매칭 충돌 방지를 위해 최우선 판별
    if "로컬 마케팅" in sol or "상위노출" in sol or "체험단" in sol:
        # 현재 키워드/순위 팩트 미확보 상태이므로 과도한 고득점 금지 (상한 74점 고정)
        base = 62
        if not has_b:
            base += 4
        if not has_tt:
            base += 4
        if not has_price:
            base += 4
        return max(40, min(74, base))

    # B. 네이버 플레이스 최적화 & 간편 예약 연동
    elif "플레이스" in sol or "예약" in sol:
        # 기본 95점에서 수집 데이터상 이미 확인된 접점마다 감점
        base = 95
        if has_b:
            base -= 30  # 핵심 기능인 간편예약 이미 확인 (가장 큰 감점)
        if has_tt:
            base -= 15  # 톡톡 상담 연동 확인
        if has_price:
            base -= 10  # 가격 공개 확인
        if menu_count >= 5:
            base -= 8   # 상세 메뉴 등록 확인
        elif menu_count > 0:
            base -= 4
        if has_hp:
            base -= 6   # 보조 신호: 공식 홈페이지 등록 확인
        
        return max(20, min(98, base))

    # C. 웹사이트/랜딩페이지 제작 & 전환 최적화
    elif "웹사이트" in sol or "랜딩페이지" in sol:
        if not has_hp:
            # 홈페이지 미확인 -> 높은 제안 기회 (90~96점)
            base = 90
            if not has_b:
                base += 3
            if not has_tt:
                base += 3
            return max(88, min(96, base))
        else:
            # 홈페이지 확인 -> 신규 제작 필요성 낮음 (상한 68점으로 엄격 제한)
            base = 55
            if not has_b:
                base += 6
            if not has_tt:
                base += 5
            return max(35, min(68, base))

    # D. SNS 퍼포먼스 광고 & 숏폼/인스타 브랜딩
    elif "SNS" in sol or "인스타" in sol or "숏폼" in sol:
        if not has_insta:
            # 인스타그램 미확인 -> 높은 제안 기회 (90~96점)
            base = 90
            if not has_hp:
                base += 3
            if not has_b:
                base += 3
            return max(88, min(96, base))
        else:
            # 인스타그램 확인 -> 운영 품질 직접 판별 불가 (상한 68점으로 엄격 제한)
            base = 55
            if not has_hp:
                base += 6
            if not has_b:
                base += 5
            return max(35, min(68, base))

    # E. 기타 (직접 입력)
    else:
        # 임의 입력 솔루션 -> 일반 접점 미확인 정도 기준 보조 계산 (상한 74점 고정)
        base = 60
        if not has_b:
            base += 5
        if not has_hp:
            base += 5
        if not has_tt:
            base += 4
        return max(40, min(74, base))

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
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return None, f"Gemini Client 초기화 실패: {e}"

    facts_list = []
    for idx, l in enumerate(leads):
        vr = l.get("visitor_reviews", 0)
        br = l.get("blog_reviews", 0)
        has_b = l.get("has_booking", False)
        hp_url = l.get("homepage_url")
        insta_url = l.get("instagram_url")
        has_tt = l.get("has_talktalk", False)
        m_count = l.get("menu_count", 0)
        has_price = l.get("has_price_info", False)
        kws = l.get("keywords", [])
        has_kw_info = l.get("has_keywords_info", False) or l.get("keywords_status") == "confirmed"
        if has_kw_info:
            if kws:
                kw_status = f"네이버 플레이스 대표 키워드 확인: {', '.join(kws)}"
            else:
                kw_status = "네이버 플레이스 수집 데이터에서 대표 키워드가 0개로 확인됨"
        else:
            kw_status = "네이버 플레이스 수집 데이터에서 대표 키워드 미확인"

        facts_list.append({
            "idx": idx,
            "title": l["title"],
            "category": l["category"],
            "address": l["address"],
            "visitor_reviews": vr,
            "blog_reviews": br,
            "naver_booking": "네이버 간편예약 연동 확인" if has_b else "네이버 플레이스 수집 데이터에서 간편예약 미확인",
            "homepage_status": f"공식 홈페이지 등록 확인 ({hp_url})" if hp_url else "네이버 플레이스 수집 데이터에서 공식 홈페이지 미확인",
            "instagram_status": f"공식 인스타그램 등록 확인 ({insta_url})" if insta_url else "네이버 플레이스 수집 데이터에서 인스타그램 미확인",
            "talktalk_status": "네이버 톡톡 상담 연동 확인" if has_tt else "네이버 플레이스 수집 데이터에서 톡톡 미확인",
            "price_status": f"메뉴/서비스 {m_count}개 등록 확인 (가격 정보 노출)" if has_price else (f"등록 메뉴 {m_count}개 확인 (네이버 플레이스 수집 데이터에서 가격 정보 미확인)" if m_count > 0 else "네이버 플레이스 수집 데이터에서 메뉴 및 가격 정보 미확인"),
            "representative_keywords": kw_status
        })

    facts_json = json.dumps(facts_list, ensure_ascii=False, indent=2)

    prompt = f"""
당신은 대한민국 최상위 B2B 세일즈 전략 및 비즈니스 전환율 최적화 수석 컨설턴트입니다.
아래는 네이버 플레이스에서 실시간 직접 수집한 실제 매장 {len(leads)}곳의 [확인된 팩트 데이터]입니다:

{facts_json}

나의 제안 솔루션: "{target_solution}"

위 {len(leads)}개 매장의 [확인된 팩트]만을 바탕으로, 각 매장별 [객관적 온라인 접점 진단]과 [3가지 맞춤 피칭 문구]를 작성하세요.

[핵심 작성 원칙 - 절대 엄수]
1. [미측정 개념 자동 파생 및 사용 금지]:
   아래 항목들은 실제 데이터로 측정한 것이 아니므로, '가설', '가능성', '검토' 등의 단어를 붙여서도 **절대 사용하지 마세요**:
   - '고객 이탈', '잠재고객 이탈', '문의 이탈'
   - '매출 손실', '전환 손실'
   - '브랜드 인지도', '브랜드 관심도', '고객 유입 풍부'
   - '예약 전환율 저하', '경쟁사로의 이탈'

2. [바람직한 팩트 기술 및 진단 서술 방식]:
   - 리뷰 수: 리뷰가 많더라도 '높은 브랜드 인지도', '관심도 풍부' 등으로 자의적 해석하지 말고, 있는 사실 그대로 '네이버 기준 블로그 리뷰 O건 확인' 수준으로만 기술하세요.
   - 대표 키워드: 확인된 경우 실제 키워드 목록(또는 0개 확인 사실)을 팩트로 활용할 수 있습니다. 대표 키워드 미확인 또는 0개 확인을 실제 미등록이나 SEO 미흡, 관리 소홀을 의미한다고 단정하지 마세요 ('네이버 플레이스 수집 데이터에서 대표 키워드는 확인되지 않았거나 0개로 확인되었으며, 실제 등록 및 검색 관리 여부는 추가 확인이 필요합니다' 수준으로 기술). 키워드 수만으로 검색 상위노출 성과, 검색량, 노출 순위를 임의로 추정하거나 단정하지 마세요.
   - 미확인 채널: '미확인'을 '없음/미흡/부재'로 단정하지 마세요. '네이버 플레이스 수집 데이터에서는 [항목]이 확인되지 않았으며, 다른 채널 운영 여부는 현재 데이터만으로 확인할 수 없습니다'로 표현하세요.
   - 가격 미확인: 가격 미확인을 이탈로 연결 짓지 마세요. '네이버 플레이스 수집 데이터에서는 상세 가격 정보가 확인되지 않았습니다. 업종 특성상 상담 후 가격을 안내하는 구조일 수 있으므로 실제 안내 경로는 추가 확인이 필요합니다' 수준으로 신중히 기술하세요.
   - 외부 사정: 카카오톡 채널, 유선 상담, 오프라인 접객 상태 등 수집되지 않은 영역을 임의로 단정하지 마세요.

3. [피칭 문구 작성 규칙 - 3단계 구조 엄수]:
   문제를 억지로 만들어내거나 가공의 손실/이탈을 언급하지 말고, 반드시 아래 순서로 작성하세요:
   [현재 확인된 상태] → [추가 확인이 필요한 부분] → [제안 가능한 개선]
   - pitch_fact (팩트 제안형 - 문자/전화용):
     확인된 팩트와 추가 확인 사항을 바탕으로 구체적인 온라인 접점 개선안을 제시하는 전문적인 1줄 문장.
   - pitch_partner (정중한 파트너형 - 이메일용):
     무상 맞춤 진단 리포트 제공 및 파트너십을 제안하는 품격 있고 정중한 문장 (대표님께 거부감 없는 어조).
   - pitch_dm (인스타 DM형 - SNS용):
     가벼운 안부와 칭찬으로 시작하여 소통을 여는 친근하고 캐주얼한 소통 톤 (이모지 활용).

4. priority_score (영업 우선순위 점수):
   - 제안 솔루션 [{target_solution}] 도입을 통해 온라인 접점 정비 및 전환 동선 확장의 기여도가 클수록 85~98점 부여 (0~100 정수).

[출력 포맷]
반드시 마크다운 백틱(```) 없이 오직 아래 순수 JSON 리스트 포맷만 반환하세요:
[
  {{
    "idx": 0,
    "priority_score": 90,
    "vulnerability": "네이버 플레이스 수집 데이터 기준 방문자 리뷰 130건과 블로그 리뷰 25건이 확인됩니다. 공식 홈페이지 링크와 톡톡 상담 연동은 플레이스 데이터상에서 확인되지 않았으며, 다른 상담 채널의 운영 여부는 현재 데이터로 확인할 수 없습니다. 상세 가격 정보 또한 미확인 상태이므로 업종 특성을 고려하여 고객이 방문 전에 정보를 확인할 수 있는 경로가 갖추어져 있는지 추가 확인 후 온라인 접점 보강 방안을 검토해 볼 수 있습니다.",
    "pitch_fact": "대표님, 현재 플레이스상 확인된 예약 채널에 더해 방문 전 상세 정보 안내 동선을 추가 확인한 뒤, 온라인 접점을 더욱 직관적으로 정비하는 방안을 제안드립니다.",
    "pitch_partner": "대표님 안녕하십니까. 현재 네이버 플레이스에 등록된 정보 현황을 바탕으로, 온라인 고객 상담 접점을 보다 효율적으로 정비할 수 있는 실무 진단 리포트를 무상으로 공유해 드리고자 합니다.",
    "pitch_dm": "대표님 안녕하세요! 플레이스에 등록된 공간 정보 잘 보았습니다 😊 최근 네이버나 모바일 채널을 통한 신규 고객 문의 동선은 원활하신가요? 실무 전환 팁을 가볍게 나누고 싶습니다!"
  }}
]
"""
    try:
        response = None
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
        except Exception:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt
            )

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
            hp_url = lead.get("homepage_url")
            insta_url = lead.get("instagram_url")
            has_tt = lead.get("has_talktalk", False)
            m_count = lead.get("menu_count", 0)
            has_price = lead.get("has_price_info", False)
            is_large = (vr >= 150 or br >= 50)

            # 우선순위 점수는 Gemini 반환값 대신 팩트 기반 Python 함수에서 결정론적으로 최종 계산
            score = calculate_priority_score(lead, target_solution)

            if match_ai:
                vuln = match_ai.get("vulnerability", "")
                p_fact = match_ai.get("pitch_fact", match_ai.get("cold_pitch", ""))
                p_partner = match_ai.get("pitch_partner", "")
                p_dm = match_ai.get("pitch_dm", "")
            else:
                missing_channels = []
                if not hp_url:
                    missing_channels.append("공식 홈페이지 미확인")
                if not insta_url:
                    missing_channels.append("인스타그램 미확인")
                if not has_tt:
                    missing_channels.append("네이버 톡톡 미확인")
                if not has_price:
                    missing_channels.append("가격 정보 미확인")
                ch_desc = ", ".join(missing_channels[:2]) if missing_channels else "상세 안내 접점 검토 필요"

                if is_large:
                    vuln = f"방문자 리뷰 {vr}개로 상권 내 고객 유입 접점을 확보하고 있으나, 네이버 플레이스 수집 데이터 기준 {ch_desc} 상태로 확인되어 상담 자동화 및 고객 전환 관점에서 추가적인 접점 확장이 권장됩니다."
                    p_fact = f"대표님, {lead['title']}의 방문 트래픽을 단골 고객으로 락인하고 상담을 지원하는 {target_solution} 구축을 제안드립니다."
                    p_partner = f"대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 바탕으로 상담 리소스를 절감하고 전환율을 높이는 맞춤 리포트를 무상 제공해 드리고자 합니다."
                    p_dm = f"대표님 안녕하세요! {lead['title']} 인지도와 리뷰 평판이 너무 좋아 평소 관심 있게 지켜보고 있었습니다 ✨ 최근 온라인 예약 및 신규 고객 유입 동선은 만족스러우신가요?"
                else:
                    vuln = f"방문자 리뷰 {vr}개로 지역 검색 유입이 형성되어 있으나, 네이버 플레이스 수집 데이터 기준 {ch_desc} 및 간편예약 미연동으로 모바일 탐색 고객의 방문 전환 동선 관점에서 보강 여지가 있습니다. 직관적인 상담 및 신청 파이프라인 정비가 권장됩니다."
                    p_fact = f"대표님, {lead['title']}의 방문자 리뷰 {vr}개 유입 중 온라인 전환 접점을 보강하여 잠재 고객을 {target_solution}으로 효과적으로 연결해 드립니다."
                    p_partner = f"대표님 안녕하십니까. {lead['title']}의 지역 플레이스 인지도를 바탕으로 온라인 예약 및 고객 전환율을 높이는 맞춤 진단 리포트를 무상 전달드리고자 합니다."
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
                "homepage_url": hp_url,
                "has_homepage": bool(hp_url),
                "instagram_url": insta_url,
                "has_instagram": bool(insta_url),
                "talktalk_url": lead.get("talktalk_url"),
                "has_talktalk": has_tt,
                "menu_count": m_count,
                "has_price_info": has_price,
                "keywords": lead.get("keywords", []),
                "keyword_count": lead.get("keyword_count"),
                "keywords_status": lead.get("keywords_status", "confirmed" if lead.get("keywords") else "unconfirmed"),
                "has_keywords_info": lead.get("has_keywords_info", bool(lead.get("keywords"))),
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
    """Gemini API가 없거나 오류 시, 수집된 4종 팩트 데이터를 기반으로 사실에 입각한 3종 맞춤 피칭 및 객관적 결핍 진단 합성"""
    results = []
    for idx, l in enumerate(leads):
        has_b = l.get("has_booking", False)
        vr = l.get("visitor_reviews", 0)
        br = l.get("blog_reviews", 0)
        hp_url = l.get("homepage_url")
        insta_url = l.get("instagram_url")
        has_tt = l.get("has_talktalk", False)
        m_count = l.get("menu_count", 0)
        has_price = l.get("has_price_info", False)
        is_large = (vr >= 150 or br >= 50)
        score = calculate_priority_score(l, target_solution)

        missing_channels = []
        if not hp_url:
            missing_channels.append("공식 홈페이지 미확인")
        if not insta_url:
            missing_channels.append("인스타그램 미확인")
        if not has_tt:
            missing_channels.append("네이버 톡톡 미확인")
        if not has_price:
            missing_channels.append("가격 정보 미확인")
        ch_desc = ", ".join(missing_channels[:2]) if missing_channels else "상세 안내 접점 검토 필요"
        
        if is_large:
            vuln = f"방문자 리뷰 {vr}개로 상권 내 고객 유입 접점을 확보하고 있으나, 네이버 플레이스 수집 데이터 기준 {ch_desc} 상태로 확인되어 상담 자동화 및 고객 전환 관점에서 추가적인 접점 확장이 권장됩니다."
            p_fact = f"대표님, {l['title']}의 방문 트래픽을 단골 고객으로 락인하고 상담을 지원하는 {target_solution} 구축을 제안드립니다."
            p_partner = f"대표님 안녕하십니까. 귀사의 우수한 플레이스 인지도를 바탕으로 상담 리소스를 절감하고 전환율을 높이는 맞춤 리포트를 무상 제공해 드리고자 합니다."
            p_dm = f"대표님 안녕하세요! {l['title']} 인지도와 리뷰 평판이 너무 좋아 평소 관심 있게 지켜보고 있었습니다 ✨ 최근 온라인 예약 및 신규 고객 유입 동선은 만족스러우신가요?"
        else:
            if not has_b:
                vuln = f"방문자 리뷰 {vr}개로 지역 검색 유입이 형성되어 있으나, 네이버 플레이스 수집 데이터 기준 {ch_desc} 및 간편예약 미연동으로 모바일 탐색 고객의 방문 전환 동선 관점에서 보강 여지가 있습니다. 직관적인 상담 및 신청 파이프라인 정비가 권장됩니다."
                p_fact = f"대표님, {l['title']}의 방문자 리뷰 {vr}개 유입 중 온라인 전환 접점을 보강하여 잠재 고객을 {target_solution}으로 효과적으로 연결해 드립니다."
                p_partner = f"대표님 안녕하십니까. {l['title']}의 지역 플레이스 인지도를 바탕으로 온라인 예약 및 고객 전환율을 높이는 맞춤 진단 리포트를 무상 전달드리고자 합니다."
                p_dm = f"대표님 안녕하세요! {l['title']} 공간이 정말 매력적이어서 피드 구경하다 인사드려요 😊 최근 온라인 채널을 통한 신규 고객 문의는 원활하신가요?"
            else:
                vuln = f"방문자 리뷰 {vr}개와 네이버 간편예약을 연동하여 기본 유입망은 갖추었으나, 네이버 플레이스 수집 데이터 기준 {ch_desc} 상태로 확인됩니다. 실제 탐색 고객의 방문 결정을 돕기 위한 온라인 접점 보강이 권장됩니다."
                p_fact = f"대표님, 이미 활성화된 네이버 예약 시스템에 더해 {target_solution}로 고객 전환율을 높여 성장을 지원해 드립니다."
                p_partner = f"대표님 안녕하십니까. {l['title']}의 예약 시스템에 고객 전환과 단골 락인을 더하는 실무 분석 리포트를 무상으로 전달드리고 싶습니다."
                p_dm = f"대표님 안녕하세요! {l['title']}의 예약 고객 재방문 및 상담 효율화를 돕는 유용한 인사이트를 공유해 드려도 될까요?"

        results.append({
            "id": idx + 1,
            "title": l["title"],
            "category": l["category"],
            "address": l["address"],
            "telephone": l["telephone"],
            "visitor_reviews": vr,
            "blog_reviews": br,
            "has_booking": has_b,
            "homepage_url": hp_url,
            "has_homepage": bool(hp_url),
            "instagram_url": insta_url,
            "has_instagram": bool(insta_url),
            "talktalk_url": l.get("talktalk_url"),
            "has_talktalk": has_tt,
            "menu_count": m_count,
            "has_price_info": has_price,
            "keywords": l.get("keywords", []),
            "keyword_count": l.get("keyword_count"),
            "keywords_status": l.get("keywords_status", "confirmed" if l.get("keywords") else "unconfirmed"),
            "has_keywords_info": l.get("has_keywords_info", bool(l.get("keywords"))),
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
        # 1단계: 네이버 플레이스 모바일 타깃 고속 수집 (단일 검색 결과에서 최대 10곳 보존)
        with st.spinner(f"🔍 네이버 검색에서 확인된 '{target_region} {industry}' 후보 업체의 팩트 지표를 실시간 수집 중..."):
            crawled_leads = crawl_naver_place_leads(target_region, industry, limit=10)

        if not crawled_leads:
            st.warning(f"⚠️ 네이버 플레이스에서 '{target_region} {industry}' 실시간 검색 결과를 찾지 못했습니다. 지역명이나 업종명을 확인해주세요.")
            lead_results = None
        else:
            # Candidate Sanitizer v1: 명백한 부적합(mismatch) 후보만 제외 (confirmed, uncertain은 그대로 유지)
            valid_leads = [l for l in crawled_leads if l.get("sanitizer_status") != "mismatch"]
            
            if not valid_leads:
                st.warning(f"⚠️ 검색된 후보 중 타깃 조건('{target_region} {industry}')에 부합하는 유효 업체가 없습니다. 지역명(구/시 단위)이나 업종명을 보다 구체적으로 입력해주세요.")
                lead_results = None
            else:
                # Lead Selection Engine Core v1:
                # 1) 전체 유효 후보를 대상으로 결정론적 영업 제안 우선순위 점수 계산
                for l in valid_leads:
                    l["priority_score"] = calculate_priority_score(l, target_solution)

                # 2) 점수 내림차순 정렬 (동점 시 네이버 원본 순위 유지 - Stable Sort)
                sorted_valid_leads = sorted(valid_leads, key=lambda x: x.get("priority_score", 0), reverse=True)

                # 3) 상위 최대 5개 선별 (5개 이하인 경우 전체 유지)
                selected_leads = sorted_valid_leads[:5]

                # 2단계: Gemini 경량 파이프라인 (선별된 상위 최대 5개 매장만 Single-shot 1회 분석)
                if gemini_api_key:
                    active_model = gemini_model_choice or resolve_best_model(gemini_api_key)
                    with st.spinner(f"⚡ 선별된 상위 {len(selected_leads)}개 업체 AI 분석 및 맞춤 피칭 생성 중... (약 5~15초 소요)"):
                        analyzed_leads, err_msg = analyze_crawled_leads_with_gemini(
                            gemini_api_key, selected_leads, target_solution, model_name=active_model
                        )
                        if analyzed_leads:
                            lead_results = analyzed_leads
                            st.toast(f"✅ 네이버 플레이스 실시간 팩트 지표 기반 AI 분석이 초고속 완료되었습니다!", icon="🎯")
                        else:
                            st.error(f"AI 분석 중 오류 발생: {err_msg}. 수집된 팩트 지표 기반으로 즉시 보강합니다.")
                            lead_results = enrich_leads_rule_based(selected_leads, target_solution)
                else:
                    st.info("ℹ️ Gemini API Key가 입력되지 않아 수집된 팩트 지표(방문자/블로그 리뷰 수, 예약 여부)를 바탕으로 기본 진단 및 피칭을 자동 합성했습니다.")
                    lead_results = enrich_leads_rule_based(selected_leads, target_solution)
            
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

# -------------------------------------------------------------
# 7. 결과 화면 탭 뷰 (카드 뷰 vs 테이블 뷰)
# -------------------------------------------------------------
results = st.session_state.get("lead_results", None)

if results:
    # 0) priority_score 기준 내림차순 정렬 및 동점 처리(공동 순위) 부여
    sorted_results = sorted(results, key=lambda x: x.get("priority_score", 0), reverse=True)
    
    # 점수별 빈도수 집계 (동점 판별용)
    from collections import Counter
    score_counts = Counter(l.get("priority_score", 0) for l in sorted_results)
    
    current_rank = 1
    for i, lead in enumerate(sorted_results):
        score = lead.get("priority_score", 0)
        if i > 0 and score < sorted_results[i - 1].get("priority_score", 0):
            current_rank = i + 1  # Standard competition ranking (예: 1, 2, 3, 3, 5)
        
        is_tie = score_counts[score] > 1
        lead["contact_rank"] = current_rank
        lead["rank_label"] = f"공동 {current_rank}순위" if is_tie else f"{current_rank}순위"
        lead["rank_badge"] = f"공동 {current_rank}위" if is_tie else f"{current_rank}위"

    results = sorted_results

    # 1) 실무 영업 CRM 시트 규격 데이터 가공 (팩트 지표 5종 포함 18개 컬럼)
    today_str = datetime.now().strftime("%Y%m%d")
    clean_region = target_region.strip().replace(" ", "_") if target_region else "전국"
    clean_industry = industry.strip().replace(" ", "_") if industry else "업종"
    excel_filename = f"영업CRM_{clean_region}_{clean_industry}_{today_str}.xlsx"

    df_export = pd.DataFrame([
        {
            "연락 우선순위": l.get("rank_label", f"{i+1}순위"),
            "솔루션 적합도 점수": l["priority_score"],
            "상호명": l["title"],
            "업종": l["category"],
            "전화번호": l.get("telephone", "").strip() if l.get("telephone") and l.get("telephone").strip() not in ["", "정보 없음", "전화번호 미등록", "미등록", "-"] else "미등록 (네이버톡톡/DM 권장)",
            "주소": l["address"],
            "홈페이지 링크": l.get("homepage_url") or "네이버 플레이스 기준 미등록",
            "인스타그램 링크": l.get("instagram_url") or "네이버 플레이스 기준 미등록",
            "네이버 톡톡": "연동" if l.get("has_talktalk") else "미연동",
            "메뉴 등록 수": f"{l.get('menu_count', 0)}개",
            "가격 정보 여부": "공개" if l.get("has_price_info") else "플레이스 기준 미확인",
            "대표 키워드 수": (l.get("keyword_count", len(l.get("keywords", []))) if (l.get("has_keywords_info") or l.get("keywords_status") == "confirmed") and l.get("keyword_count") is not None else "미확인"),
            "대표 키워드": ((", ".join(l.get("keywords", [])) if l.get("keywords") else "0개 확인") if (l.get("has_keywords_info") or l.get("keywords_status") == "confirmed") else "미확인"),
            "네이버 예약": "연동" if l.get("has_booking") else "미연동",
            "방문자 리뷰": l.get("visitor_reviews", 0),
            "블로그 리뷰": l.get("blog_reviews", 0),
            "AI 진단 요약": l["vulnerability"],
            "팩트 제안 문구": l.get("pitch_fact", l.get("cold_pitch", "")),
            "정중한 제안 문구": l.get("pitch_partner", ""),
            "DM 제안 문구": l.get("pitch_dm", ""),
            "연락 일자": "",
            "영업 결과(부재/거절/상담예정/미팅성사)": "",
            "비고 및 메모": f"홈페이지 {'등록' if l.get('homepage_url') else '미등록'}, 인스타 {'연동' if l.get('instagram_url') else '미등록'}, 톡톡 {'연동' if l.get('has_talktalk') else '미연동'}"
        }
        for i, l in enumerate(results)
    ])
    # 솔루션 적합도 점수 기준 내림차순 정렬
    df_export = df_export.sort_values(by="솔루션 적합도 점수", ascending=False).reset_index(drop=True)
    excel_bytes = generate_excel_bytes(df_export)
    excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 2) 결과 목록 상단 헤더 & 프로 결제 안내 모달 연동 엑셀 다운로드 버튼
    top_col1, top_col2 = st.columns([2.6, 1.8])
    with top_col1:
        st.markdown(f"### 📋 네이버 플레이스 영업 후보 ({len(results)}개)")
        st.caption("💡 현재 수집된 네이버 플레이스 팩트와 선택한 솔루션의 적합도를 기준으로 연락 우선순위를 정렬했습니다.")
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
            # 연락 우선순위 뱃지 분기 (절대 점수 노출 배제)
            rank_num = lead.get("contact_rank", 1)
            rank_badge_text = lead.get("rank_badge", f"{rank_num}위")
            if rank_num == 1:
                score_badge = f'<span class="badge-score-high">🔥 연락 우선순위 {rank_badge_text}</span>'
            elif rank_num == 2:
                score_badge = f'<span class="badge-score-mid">⚡ 연락 우선순위 {rank_badge_text}</span>'
            else:
                score_badge = f'<span class="badge-score-low">연락 우선순위 {rank_badge_text}</span>'
                
            # 예약 뱃지 분기
            if lead.get("has_booking"):
                booking_badge = '<span class="badge-booking-yes">🟢 네이버 간편예약 연동</span>'
            else:
                booking_badge = '<span class="badge-booking-no">🔴 간편예약 미연동</span>'
                
            vr_count = lead.get("visitor_reviews", 0)
            br_count = lead.get("blog_reviews", 0)
            review_badge = f'<span class="badge-review">💬 방문자 리뷰 <b>{vr_count:,}</b>개 &nbsp;|&nbsp; 📝 블로그 리뷰 <b>{br_count:,}</b>개</span>'
            
            # 팩트 뱃지 4종 생성
            hp_url = lead.get("homepage_url")
            if hp_url:
                hp_badge = f'<a href="{hp_url}" target="_blank" class="badge-fact-yes">🌐 공식 홈페이지 ↗</a>'
            else:
                hp_badge = '<span class="badge-fact-no">🌐 홈페이지 링크 미등록</span>'

            insta_url = lead.get("instagram_url")
            if insta_url:
                insta_badge = f'<a href="{insta_url}" target="_blank" class="badge-fact-yes">📸 인스타그램 ↗</a>'
            else:
                insta_badge = '<span class="badge-fact-no">📸 인스타그램 미등록</span>'

            if lead.get("has_talktalk"):
                tt_url = lead.get("talktalk_url")
                if tt_url:
                    talktalk_badge = f'<a href="{tt_url}" target="_blank" class="badge-fact-yes">💬 네이버 톡톡 연동 ↗</a>'
                else:
                    talktalk_badge = '<span class="badge-fact-yes">💬 네이버 톡톡 연동</span>'
            else:
                talktalk_badge = '<span class="badge-fact-no">💬 톡톡 미연동</span>'

            m_count = lead.get("menu_count", 0)
            if lead.get("has_price_info"):
                price_badge = f'<span class="badge-fact-yes">🏷️ 메뉴 {m_count}개 (가격 공개)</span>'
            elif m_count > 0:
                price_badge = f'<span class="badge-fact-no">🏷️ 가격 미확인 ({m_count}개)</span>'
            else:
                price_badge = '<span class="badge-fact-no">🏷️ 메뉴/가격 미확인</span>'

            # 대표 키워드 뱃지 및 보조 텍스트
            has_kw = lead.get("has_keywords_info", False) or lead.get("keywords_status") == "confirmed"
            kw_list = lead.get("keywords", [])
            if has_kw:
                if kw_list:
                    kw_badge = f'<span class="badge-fact-yes">🔑 대표 키워드 {len(kw_list)}개</span>'
                    kw_text_html = f'<div style="font-size: 12.5px; color: #475569; margin: 4px 0 8px 0;">🔑 <b>대표 키워드:</b> {" · ".join(kw_list)}</div>'
                else:
                    kw_badge = '<span class="badge-fact-no">🔑 대표 키워드 0개 확인</span>'
                    kw_text_html = ''
            else:
                kw_badge = '<span class="badge-fact-no">🔑 대표 키워드 미확인</span>'
                kw_text_html = ''

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
                <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px;">
                    {booking_badge}
                    {hp_badge}
                    {insta_badge}
                    {talktalk_badge}
                    {price_badge}
                    {kw_badge}
                </div>
                {kw_text_html}
                <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px;">
                    {review_badge}
                </div>
                <div style="font-size: 13px; color: #475569; margin-bottom: 10px;">
                    📍 {lead['address']} &nbsp;|&nbsp; 📞 {lead['telephone']}
                </div>
                <div class="vuln-box">
                    <strong>🔍 AI 온라인 전환 경로 진단 (확인된 팩트 기반 분석):</strong><br>
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
    st.info("💡 위 설정창에서 타깃 조건(업종, 지역, 제공 서비스)을 확인한 뒤 **'🚀 잠재고객 분석 및 피칭 생성'** 버튼을 클릭해보세요. 네이버 플레이스에서 실제 매장의 지표를 실시간 수집합니다.")
