import streamlit as st
import os
import json
import shutil
import zipfile
import io
from openai import OpenAI

# --- 설정 ---
UPLOAD_DIR = "resources"
ADMIN_PASSWORD = "1234"

# 페이지 설정
st.set_page_config(
    page_title="Red Drive - AI 리소스 센터",
    layout="wide",
    page_icon="🔴",
    initial_sidebar_state="expanded"
)

# --- 디자인(CSS) 수정: 글씨 색상 강제 지정 ---
st.markdown("""
<style>
    /* 폰트 설정 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: Pretendard, sans-serif;
    }
    
    /* 메인 타이틀 레드 컬러 */
    .main-title {
        color: #E63946; 
        font-weight: 800;
    }
    
    /* 1. 사이드바 강제 스타일링 (흰 배경 + 검은 글씨) */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    section[data-testid="stSidebar"] * {
        color: #333333 !important; /* 사이드바의 모든 글씨를 검게 */
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 {
        color: #E63946 !important; /* 제목은 레드로 유지 */
    }

    /* 2. 리소스 카드 강제 스타일링 (흰 배경 + 검은 글씨) */
    .resource-card-container {
        background-color: #ffffff;
        color: #333333; /* 기본 글씨 검게 */
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    /* 카드 안의 제목, 설명, 리스트 등 모든 요소 검은색 강제 */
    .resource-card-container h1, .resource-card-container h2, .resource-card-container h3,
    .resource-card-container p, .resource-card-container span, .resource-card-container li {
        color: #333333 !important;
    }
    
    /* 버튼 스타일 (레드) */
    div[data-testid="stForm"] button, div[data-testid="column"] button {
        background-color: #E63946;
        color: white !important; /* 버튼 글씨는 흰색 유지 */
        border: none;
    }
    div[data-testid="stForm"] button:hover, div[data-testid="column"] button:hover {
        background-color: #C1121F;
    }
</style>
""", unsafe_allow_html=True)

# --- 함수 정의 (기존과 동일) ---
def load_resources():
    resources = []
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    for item in os.listdir(UPLOAD_DIR):
        item_path = os.path.join(UPLOAD_DIR, item)
        if os.path.isdir(item_path):
            info_path = os.path.join(item_path, "info.json")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        data['id'] = item
                        resources.append(data)
                    except json.JSONDecodeError:
                        continue
    return resources

def create_zip(selected_ids):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res_id in selected_ids:
            folder_path = os.path.join(UPLOAD_DIR, res_id)
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join(res_id, file)
                    zf.write(file_path, arcname)
    return zip_buffer.getvalue()

def generate_description(file_names, user_input_hint):
    if not st.session_state.get('openai_api_key'):
        return "💡 API 키가 입력되지 않아 자동 설명이 생성되지 않았습니다."
    
    client = OpenAI(api_key=st.session_state['openai_api_key'])
    prompt = f"""
    'Red Drive' 플랫폼 자료 설명.
    파일 목록: {', '.join(file_names)}
    힌트: {user_input_hint}
    이해하기 쉽고 전문적인 한국어로 2~3문장 설명 작성.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"설명 생성 실패: {str(e)}"

# --- 메인 페이지 ---
def main_page():
    st.markdown('<h1 class="main-title">🔴 Red Drive <span style="font-size:0.6em; color:#bbb;">| AI 리소스 센터</span></h1>', unsafe_allow_html=True)
    st.markdown("우리 레드사업실의 업무 효율을 높여줄 AI 도구와 데이터를 이곳에서 공유하고 활용하세요!")
    st.divider()

    with st.sidebar:
        st.header("🔍 검색 및 필터")
        search_query = st.text_input("검색어 입력", placeholder="예: 이메일...")
        st.caption("💡 팁: 체크박스 선택 후 하단 '일괄 다운로드' 클릭")

    resources = load_resources()
    if search_query:
        resources = [r for r in resources if search_query.lower() in r.get('title','').lower() or search_query.lower() in r.get('description','').lower()]

    if not resources:
        st.info("👋 등록된 리소스가 없습니다. 관리자 페이지에서 자료를 업로드해주세요.")
        return

    if 'selected_resources' not in st.session_state:
        st.session_state['selected_resources'] = []

    # 전체 선택 버튼
    if st.button("전체 선택/해제"):
        if len(st.session_state['selected_resources']) == len(resources):
            st.session_state['selected_resources'] = []
        else:
            st.session_state['selected_resources'] = [r['id'] for r in resources]
            
    # 리소스 카드 출력
    cols = st.columns(2)
    for idx, res in enumerate(resources):
        with cols[idx % 2]:
            with st.container():
                # HTML div로 감싸서 CSS 강제 적용
                st.markdown(f"""
                <div class="resource-card-container">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:blue; font-weight:bold;">[{res.get('category', 'General')}]</span>
                        <span style="color:#666;">📄 파일 {len(res.get('files', []))}개</span>
                    </div>
                    <h3 style="margin-top:10px; color:#333 !important;">{res.get('title', '제목 없음')}</h3>
                    <p style="color:#333 !important;">{res.get('description', '설명 없음')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 기능 버튼들 (Streamlit 네이티브 기능 사용을 위해 분리)
                c1, c2 = st.columns([0.1, 0.9])
                is_selected = res['id'] in st.session_state['selected_resources']
                if st.checkbox(f"{res['title']} 선택", key=f"chk_{res['id']}", value=is_selected):
                    if res['id'] not in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].append(res['id'])
                else:
                    if res['id'] in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].remove(res['id'])
                
                with st.expander("👉 포함된 파일 목록 보기"):
                    for f in res.get('files', []):
                        st.text(f"- {f}")

    st.divider()
    if st.session_state['selected_resources']:
        st.success(f"✅ {len(st.session_state['selected_resources'])}개 리소스 선택됨")
        zip_data = create_zip(st.session_state['selected_resources'])
        st.download_button("📦 선택한 리소스 일괄 다운로드 (ZIP)", zip_data, "RedDrive.zip", "application/zip", use_container_width=True)

# --- 관리자 페이지 ---
def admin_page():
    st.title("🛠️ 리소스 업로드")
    pwd = st.text_input("비밀번호", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("🔒 비밀번호를 입력하세요.")
        return

    st.success("인증됨")
    api_key = st.text_input("OpenAI API Key", type="password")
    if api_key: st.session_state['openai_api_key'] = api_key

    with st.form("upload", clear_on_submit=True):
        title = st.text_input("제목")
        category = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Etc"])
        files = st.file_uploader("파일", accept_multiple_files=True)
        hint = st.text_area("힌트")
        if st.form_submit_button("업로드"):
            if title and files:
                folder = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                path = os.path.join(UPLOAD_DIR, folder)
                os.makedirs(path, exist_ok=True)
                f_names = []
                for f in files:
                    with open(os.path.join(path, f.name), "wb") as wb: wb.write(f.getbuffer())
                    f_names.append(f.name)
                
                desc = generate_description(f_names, hint)
                with open(os.path.join(path, "info.json"), "w", encoding="utf-8") as jf:
                    json.dump({"title":title, "category":category, "description":desc, "files":f_names}, jf, ensure_ascii=False)
                st.success("등록 완료!")

# --- 실행 ---
st.sidebar.title("🔴 Red Drive")
page = st.sidebar.radio("메뉴", ["리소스 탐색", "관리자 업로드"])
if page == "리소스 탐색": main_page()
else: admin_page()
