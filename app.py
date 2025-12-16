import streamlit as st
import os
import json
import io
import zipfile
# from github import Github # GitHub 연동 잠시 해제 (로컬 테스트용)
from openai import OpenAI

# --- 1. 설정 및 비밀키 로드 ---
# 로컬 테스트를 위해 GitHub/OpenAI 관련 시크릿 로드 부분을 주석 처리하거나
# 실제 배포 시에는 이 부분을 다시 활성화해야 합니다.
# try:
#     GITHUB_TOKEN = st.secrets["general"]["github_token"]
#     REPO_NAME = st.secrets["general"]["repo_name"]
#     OPENAI_API_KEY = st.secrets["general"].get("openai_api_key", None)
# except Exception:
#     st.error("🚨 설정 오류: Streamlit Secrets에 github_token과 repo_name이 설정되지 않았습니다.")
#     st.stop()

# 로컬 테스트를 위한 임시 API 키 (배포 시 제거)
OPENAI_API_KEY = "여기에_당신의_OPENAI_API_KEY를_입력하세요" 

ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources" # 로컬 저장소 폴더 이름

# 페이지 설정
st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴")

# --- 2. 디자인(CSS) 수정 (버그 픽스 & 가독성 강화) ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 🔴 전체 페이지 스타일 (다크 모드) */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }

    /* 🚫 UI 버그 수정: 툴팁 및 단축키 도움말 완벽 제거 (강력한 선택자 사용) */
    
    /* 1. 툴팁 호버 타겟 제거 */
    div[data-testid="stTooltipHoverTarget"] {
        display: none !important;
    }
    /* 2. Expander 헤더 내의 단축키 아이콘 컨테이너 제거 */
    .streamlit-expanderHeader > div:last-child {
        display: none !important;
    }
    /* 3. 툴바 및 배포 버튼 제거 */
    div[data-testid="stToolbar"], .stDeployButton {
        display: none !important;
    }
    
    /* 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }

    /* 사이드바 메뉴 버튼 스타일 */
    div[role="radiogroup"] label {
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 12px 15px;
        margin-bottom: 8px;
        transition: 0.2s;
        cursor: pointer;
        font-weight: 500;
        display: flex; /* 버튼 내용을 가로로 정렬 */
        align-items: center;
    }
    div[role="radiogroup"] label:hover {
        background-color: #30363D;
        color: white;
        transform: translateX(3px);
    }
    /* 선택된 메뉴 스타일 */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        border: 1px solid #ff8a8a;
        box-shadow: 0 2px 8px rgba(230, 57, 70, 0.4);
    }
    /* 기본 라디오 버튼 원형 숨김 */
    div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* 📦 리소스 카드 스타일 */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    }
    .resource-card:hover {
        transform: translateY(-5px);
        border-color: #E63946;
        box-shadow: 0 10px 20px rgba(230, 57, 70, 0.15);
    }
    .resource-card h3 {
        color: #FFFFFF !important;
        font-weight: 700;
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 1.5rem;
    }
    
    /* 카테고리 뱃지 스타일 */
    .category-badge {
        background: #E63946;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: bold;
        display: inline-block; /* 텍스트와 잘 어울리도록 */
    }

    /* 파일 리스트 (터미널 스타일) */
    .file-terminal {
        background-color: #0d1117;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 15px;
        font-family: 'Consolas', 'Courier New', monospace;
        color: #7EE787;
        font-size: 0.85rem;
        margin-top: 10px;
        white-space: pre-wrap;
    }
    .file-item {
        margin-bottom: 4px;
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363D !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #E63946 !important;
        box-shadow: 0 0 0 1px #E63946 !important;
    }
    
    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background-color: #21262D;
        color: #E6E6E6;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #30363D;
    }
    .streamlit-expanderContent {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-top: none;
        border-radius: 0 0 6px 6px;
        padding: 20px;
    }
    
    /* 버튼 스타일 */
    .stButton button {
        background-color: #21262D;
        color: white;
        border: 1px solid #30363D;
        font-weight: 600;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        transition: all 0.2s;
    }
    .stButton button:hover {
        background-color: #30363D;
        border-color: #8b949e;
    }
    /* 주요 버튼(Primary) 스타일 */
    .stButton button[kind="primary"] {
        background-color: #E63946;
        border-color: #E63946;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #C1121F;
        border-color: #C1121F;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.3);
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #21262D;
        color: #8b949e;
        border-radius: 6px;
        border: 1px solid transparent;
        padding: 8px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E63946 !important;
        color: white !important;
    }

    /* 체크박스 스타일 */
    .stCheckbox label {
        color: #FAFAFA !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 기능 함수들 (로컬 파일 시스템 기반) ---

# GitHub 연동 대신 로컬 폴더 사용
def get_local_repo_path():
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    return UPLOAD_DIR

def load_resources_from_local():
    resources = []
    repo_path = get_local_repo_path()
    try:
        # UPLOAD_DIR 내의 모든 폴더를 순회
        for item in os.listdir(repo_path):
            item_path = os.path.join(repo_path, item)
            if os.path.isdir(item_path):
                try:
                    # 각 폴더 안의 info.json 파일 읽기
                    info_file_path = os.path.join(item_path, "info.json")
                    if os.path.exists(info_file_path):
                        with open(info_file_path, "r", encoding="utf-8") as f:
                            info_data = json.load(f)
                            info_data['id'] = item
                            info_data['path'] = item_path
                            resources.append(info_data)
                except Exception as e:
                    print(f"Error loading resource {item}: {e}")
                    continue 
    except Exception as e:
        print(f"Error accessing upload directory: {e}")
        return []
    return sorted(resources, key=lambda x: x.get('title', ''), reverse=True)

def upload_to_local(folder_name, files, meta_data):
    repo_path = get_local_repo_path()
    base_path = os.path.join(repo_path, folder_name)
    
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    
    # 1. 파일 저장
    for file in files:
        file_path = os.path.join(base_path, file.name)
        with open(file_path, "wb") as f:
            f.write(file.getvalue())
            
    # 2. info.json 파일 생성
    json_path = os.path.join(base_path, "info.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=4)

def delete_from_local(folder_path):
    # 폴더와 그 안의 모든 내용을 삭제
    import shutil
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)

def download_files_as_zip(selected_resources):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_resources:
            folder_path = res['path']
            # 폴더 내의 모든 파일 순회
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file == "info.json": continue
                    file_path = os.path.join(root, file)
                    # ZIP 파일 내에 폴더 구조 없이 파일만 추가
                    zf.write(file_path, arcname=file)
    return zip_buffer.getvalue()

# --- 🔥 핵심 개선: 프롬프트 고도화 (비즈니스 리포트 톤) ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY or OPENAI_API_KEY == "여기에_당신의_OPENAI_API_KEY를_입력하세요":
        return "💡 (API 키가 설정되지 않아 자동 설명이 생성되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 IT 서비스 기획자(Service Planner)이자 시니어 개발자입니다.
    사용자가 업로드한 코드와 힌트를 바탕으로 '비즈니스 임팩트' 중심의 분석 보고서를 작성하세요.
    
    [분석할 파일 내용 요약]
    {file_contents_summary}
    
    [사용자 힌트]
    {user_hint}
    
    **작성 가이드라인:**
    1. **말투**: '해요체'나 번역투를 지양하고, 전문적인 보고서체(개조식 또는 ~함/됨)를 사용하세요.
    2. **내용**: 뻔한 일반론(예: "시간을 절약합니다") 대신 구체적인 상황을 묘사하세요(예: "수작업 데이터 이관 시 발생하는 휴먼 에러를 0%로 줄임").
    3. **코드 분석**: 코드가 '어떻게' 작동하는지 기술적인 근거를 포함하세요.

    **출력 포맷 (Markdown):**
    
    ### 🛑 Pain Point (문제 정의)
    (이 도구가 없을 때 현업에서 발생하는 구체적인 비효율이나 리스크를 1~2문장으로 날카롭게 지적)
    
    ### 💡 Solution (해결 로직)
    (파일 내용을 근거로 이 도구의 핵심 작동 원리를 설명)
    - **Logic**: (주요 함수나 로직이 데이터를 어떻게 처리하는지 요약)
    - **Flow**: (사용자 입력 -> 처리 -> 결과물의 흐름 설명)
    
    ### 🚀 Business Impact (기대 효과)
    - (정량적/정성적 효과 1)
    - (정량적/정성적 효과 2)
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 분석 실패: {str(e)}"

# --- 4. 메인 로직 ---

def main():
    # 사이드바 컨테이너
    with st.sidebar:
        st.markdown("## 🔴 Red Drive")
        # 메뉴 라디오 버튼
        menu = st.radio("MENU", ["리소스 탐색", "관리자 모드"], label_visibility="collapsed")
        st.divider()
        st.info("💡 **Red Drive**는 레드사업실의 자산을 영구적으로 보관하는 아카이브입니다.")

    # [탐색 탭]
    if menu == "리소스 탐색":
        st.markdown("<h1 style='color:#E63946; margin-bottom:0;'>Red Drive <span style='color:#888; font-size:0.5em; font-weight:400;'>| AI Resource Hub</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#CCC; margin-top:5px;'>레드사업실의 AI 도구와 데이터를 가장 직관적으로 탐색하고 활용하세요.</p>", unsafe_allow_html=True)
        st.divider()

        # 리소스 로드 (로컬)
        if 'resources_cache' not in st.session_state:
            with st.spinner("🚀 리소스를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_local()
        
        resources = st.session_state['resources_cache']
        
        # 검색바와 새로고침 버튼
        col_search, col_refresh = st.columns([9, 1])
        with col_search:
            search_query = st.text_input("검색", placeholder="키워드 입력 (예: 회의록, 프롬프트...)", label_visibility="collapsed")
        with col_refresh:
            if st.button("🔄", help="리소스 목록 새로고침"):
                del st.session_state['resources_cache']
                st.rerun()

        if search_query:
            resources = [r for r in resources if search_query.lower() in str(r).lower()]

        # 전체 선택/해제 버튼
        if 'selected_ids' not in st.session_state: st.session_state['selected_ids'] = []
        c1, c2, _ = st.columns([1.5, 1.5, 7])
        if c1.button("✅ 전체 선택"):
            st.session_state['selected_ids'] = [r['id'] for r in resources]
            st.rerun()
        if c2.button("❌ 선택 해제"):
            st.session_state['selected_ids'] = []
            st.rerun()

        # 리소스가 없을 때 표시
        if not resources:
            st.warning("등록된 리소스가 없습니다. 관리자 모드에서 첫 번째 리소스를 등록해보세요!")
        
        # 리소스 카드 렌더링
        for res in resources:
            # 카테고리 뱃지 HTML
            category_badge = f'<span class="category-badge">{res.get("category", "General")}</span>'
            file_count = f'<span style="color:#888; font-size:0.9em;">파일 {len(res.get("files", []))}개</span>'
            
            st.markdown(f"""
            <div class="resource-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px; align-items:center;">
                    {category_badge}
                    {file_count}
                </div>
                <h3>{res.get('title')}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 상세 내용 Expander
            with st.expander(f"📖 '{res.get('title')}' 분석 보고서 & 파일 확인"):
                st.markdown(res.get('description', '설명 없음'))
                
                # 파일 리스트 HTML 생성
                file_list_html = "".join([f'<div class="file-item">📄 {f}</div>' for f in res.get('files', [])])
                st.markdown(f'<div class="file-terminal"><b>[Included Files]</b><br>{file_list_html}</div>', unsafe_allow_html=True)

            # 선택 체크박스
            is_checked = res['id'] in st.session_state['selected_ids']
            if st.checkbox(f"📥 다운로드 담기", value=is_checked, key=f"chk_{res['id']}"):
                if res['id'] not in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].append(res['id'])
                    st.rerun()
            else:
                if res['id'] in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].remove(res['id'])
                    st.rerun()
            st.write("") # 카드 간 간격

        # 하단 일괄 다운로드 버튼
        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"현재 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("압축 파일을 생성 중입니다..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button("⬇️ ZIP 파일 저장", zip_data, "RedDrive_Archive.zip", "application/zip", use_container_width=True)

    # [관리자 탭]
    else:
        st.title("🛠️ 관리자 모드")
        
        # 관리자 로그인
        if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False
        if not st.session_state['is_admin']:
            pwd = st.text_input("Admin Password", type="password")
            if st.button("Login"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state['is_admin'] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")
            return

        st.success(f"로컬 저장소({UPLOAD_DIR})에 연결되었습니다.")
        
        # 탭 구성
        tab1, tab2 = st.tabs(["📤 신규 등록", "🗑️ 리소스 삭제"])

        # 신규 등록 탭
        with tab1:
            with st.form("upload", clear_on_submit=True):
                st.subheader("새로운 리소스 등록")
                title = st.text_input("Title (제목)")
                category = st.selectbox("Category (카테고리)", ["Workflow", "Prompt", "Data", "Tool"])
                files = st.file_uploader("Files (코드를 읽어서 분석합니다)", accept_multiple_files=True)
                hint = st.text_area("Hint (핵심 기능 요약)")
                
                if st.form_submit_button("🚀 등록 및 AI 분석 시작"):
                    if title and files:
                        with st.spinner("🤖 AI가 코드를 읽고 분석 보고서를 작성 중입니다..."):
                            # 파일 내용 읽기
                            file_contents_summary = ""
                            f_names = []
                            for f in files:
                                f_names.append(f.name)
                                # 텍스트 파일만 읽기 시도
                                if any(f.name.endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.json', '.txt', '.md', '.gs', '.sh', '.csv']):
                                    try:
                                        # 앞부분 2000자만 읽어서 요약
                                        content = f.getvalue().decode("utf-8")[:2000]
                                        file_contents_summary += f"\n--- File: {f.name} ---\n{content}\n"
                                    except:
                                        file_contents_summary += f"\n--- File: {f.name} (Binary/Unreadable) ---\n"
                                else:
                                    file_contents_summary += f"\n--- File: {f.name} (Binary) ---\n"

                            # AI 분석 요청
                            desc = generate_pro_description(file_contents_summary, hint)
                        
                        with st.spinner("💾 로컬 저장소에 저장 중..."):
                            # 폴더명 생성 (안전한 이름으로 변환)
                            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                            meta = {"title": title, "category": category, "description": desc, "files": f_names}
                            upload_to_local(folder_name, files, meta)
                            
                        st.balloons()
                        st.success("등록이 완료되었습니다!")
                        # 캐시 초기화하여 목록 갱신
                        if 'resources_cache' in st.session_state: del st.session_state['resources_cache']
                    else:
                        st.warning("제목과 파일을 모두 입력해주세요.")

        # 삭제 탭
        with tab2:
            if st.button("목록 새로고침"):
                st.session_state['resources_cache'] = load_resources_from_local()
            
            resources = st.session_state.get('resources_cache', [])
            if resources:
                target_title = st.selectbox("삭제할 리소스 선택", [r['title'] for r in resources])
                
                # 선택된 리소스 객체 찾기
                target_obj = next((r for r in resources if r['title'] == target_title), None)
                
                if target_obj and st.button("🔥 영구 삭제", type="primary"):
                    with st.spinner("삭제 중..."):
                        delete_from_local(target_obj['path'])
                    st.success("삭제되었습니다.")
                    del st.session_state['resources_cache']
                    st.rerun()
            else:
                st.info("삭제할 리소스가 없습니다.")

if __name__ == "__main__":
    main()
