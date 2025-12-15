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

# 페이지 기본 설정 (제목 변경 및 디자인 테마 적용)
st.set_page_config(
    page_title="Red Drive - AI 리소스 센터",
    layout="wide",
    page_icon="🔴",
    initial_sidebar_state="expanded"
)

# CSS로 디자인 다듬기 (레드 포인트 강조)
st.markdown("""
<style>
    /* 전체 테마 및 폰트 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
    }
    
    /* 메인 타이틀 강조 */
    .main-title {
        color: #E63946; /* 레드 컬러 */
        font-weight: 800;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    /* 버튼 스타일링 (레드 포인트) */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    /* 주요 버튼 (다운로드, 업로드) */
    div[data-testid="stForm"] button, div[data-testid="column"] button {
        background-color: #E63946;
        color: white;
    }
    div[data-testid="stForm"] button:hover, div[data-testid="column"] button:hover {
        background-color: #C1121F; /* 더 진한 레드 */
    }

    /* 리소스 카드 스타일링 */
    .resource-card-container {
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        background-color: #fff;
        transition: transform 0.2s;
    }
    .resource-card-container:hover {
         transform: translateY(-3px);
         box-shadow: 0 6px 16px rgba(230, 57, 70, 0.15); /* 레드 그림자 */
         border-color: #ffcdd2;
    }
    
    /* 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 {
        color: #E63946;
    }
    
    /* 경고/정보 박스 커스텀 */
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 함수 정의 (이전과 동일) ---
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
        return "💡 API 키가 입력되지 않아 자동 설명이 생성되지 않았습니다. (관리자 페이지에서 키를 입력해주세요)"
    
    client = OpenAI(api_key=st.session_state['openai_api_key'])
    prompt = f"""
    'Red Drive'라는 AI 리소스 공유 플랫폼에 올라온 자료야.
    포함된 파일들을 보고 팀원들이 이해하기 쉽게 2~3문장의 한국어 설명을 작성해줘.
    
    - 파일 목록: {', '.join(file_names)}
    - 작성자 힌트: {user_input_hint}
    
    전문적이고 명확한 어조로, '~~하는 워크플로우입니다.', '~~ 데이터셋입니다.' 등으로 끝맺어줘.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI 설명 생성 중 오류 발생: {str(e)}"

# --- 메인 앱 로직 ---
def main_page():
    # 타이틀 변경 및 디자인 적용
    st.markdown('<h1 class="main-title">🔴 Red Drive <span style="font-size:0.6em; color:#666;">| AI 리소스 센터</span></h1>', unsafe_allow_html=True)
    st.markdown("우리 레드사업실의 업무 효율을 높여줄 AI 도구와 데이터를 이곳에서 공유하고 활용하세요!")
    st.divider()

    with st.sidebar:
        st.header("🔍 검색 및 필터")
        search_query = st.text_input("검색어 입력", placeholder="예: 이메일, 프롬프트...")
        st.caption("💡 팁: 여러 자료를 선택 후 하단의 '일괄 다운로드'를 클릭하세요.")

    resources = load_resources()
    if search_query:
        resources = [r for r in resources if search_query.lower() in r.get('title','').lower() or search_query.lower() in r.get('description','').lower()]

    if not resources:
        st.info("👋 아직 등록된 리소스가 없습니다. 관리자 페이지에서 첫 번째 자료를 업로드해주세요!")
        return

    if 'selected_resources' not in st.session_state:
        st.session_state['selected_resources'] = []

    col_all_1, col_all_2 = st.columns([1.2, 8])
    if col_all_1.button("전체 선택/해제"):
        if len(st.session_state['selected_resources']) == len(resources):
            st.session_state['selected_resources'] = []
        else:
            st.session_state['selected_resources'] = [r['id'] for r in resources]
            
    cols = st.columns(2)
    for idx, res in enumerate(resources):
        with cols[idx % 2]:
            # 카드 디자인 컨테이너 적용
            with st.container():
                st.markdown('<div class="resource-card-container">', unsafe_allow_html=True)
                c1, c2 = st.columns([8, 1])
                # 카테고리 배지 스타일
                badge_color = {"Workflow": "blue", "Prompt": "green", "Data": "orange"}.get(res.get('category'), "grey")
                c1.markdown(f":{badge_color}[**{res.get('category', 'General')}**] | 📄 파일 {len(res.get('files', []))}개")
                
                is_selected = res['id'] in st.session_state['selected_resources']
                if c2.checkbox("선택", key=f"chk_{res['id']}", value=is_selected, label_visibility="collapsed"):
                    if res['id'] not in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].append(res['id'])
                else:
                    if res['id'] in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].remove(res['id'])

                st.subheader(res.get('title', '제목 없음'))
                st.write(res.get('description', '설명 없음'))
                with st.expander("포함된 파일 보기"):
                    for f in res.get('files', []):
                        st.markdown(f"- 📄 `{f}`")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    if st.session_state['selected_resources']:
        st.success(f"✅ {len(st.session_state['selected_resources'])}개 리소스가 선택되었습니다.")
        zip_data = create_zip(st.session_state['selected_resources'])
        st.download_button(
            label="📦 선택한 리소스 일괄 다운로드 (ZIP)",
            data=zip_data,
            file_name="RedDrive_Resources.zip",
            mime="application/zip",
            use_container_width=True
        )

# --- 관리자 페이지 ---
def admin_page():
    st.title("🛠️ 리소스 업로드 (관리자)")
    pwd = st.text_input("관리자 비밀번호", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("🔒 비밀번호를 입력하세요.")
        return

    st.success("🔓 인증되었습니다.")
    api_key = st.text_input("OpenAI API Key (자동 설명 생성용)", type="password", help="키가 없으면 AI 설명 기능이 작동하지 않습니다.")
    if api_key:
        st.session_state['openai_api_key'] = api_key

    with st.form("upload_form", clear_on_submit=True):
        st.subheader("새 리소스 등록")
        col1, col2 = st.columns([2, 1])
        title = col1.text_input("리소스 제목", placeholder="예: 주간 업무 자동화 봇")
        category = col2.selectbox("카테고리", ["Workflow", "Prompt", "Data", "기타"])
        
        uploaded_files = st.file_uploader("관련 파일 모두 업로드 (드래그 앤 드롭)", accept_multiple_files=True)
        user_hint = st.text_area("AI에게 줄 힌트 (선택사항)", placeholder="예: 이 워크플로우는 노션이랑 슬랙을 연결해줍니다.")
        
        generate_btn = st.form_submit_button("🚀 업로드 및 등록 시작")
        
        if generate_btn and title and uploaded_files:
            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
            target_dir = os.path.join(UPLOAD_DIR, folder_name)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            file_names = []
            for up_file in uploaded_files:
                file_path = os.path.join(target_dir, up_file.name)
                with open(file_path, "wb") as f:
                    f.write(up_file.getbuffer())
                file_names.append(up_file.name)
            
            with st.spinner("🤖 AI가 열심히 설명을 작성하고 있습니다..."):
                description = generate_description(file_names, user_hint)

            meta_data = {"title": title, "category": category, "description": description, "files": file_names}
            with open(os.path.join(target_dir, "info.json"), "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=4)
                
            st.balloons()
            st.success(f"✅ '{title}' 등록 완료! (파일명: {', '.join(file_names)})")
        elif generate_btn:
            st.error("제목과 파일을 모두 입력해주세요.")

# --- 앱 실행 라우터 ---
st.sidebar.title("🔴 Red Drive")
page = st.sidebar.radio("메뉴 선택", ["리소스 탐색", "관리자 업로드"], label_visibility="collapsed")

if page == "리소스 탐색":
    main_page()
else:
    admin_page()
