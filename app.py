import streamlit as st
import os
import json
import io
import zipfile
from github import Github
from openai import OpenAI

# --- 1. 설정 및 비밀키 로드 ---
try:
    GITHUB_TOKEN = st.secrets["general"]["github_token"]
    REPO_NAME = st.secrets["general"]["repo_name"]
    OPENAI_API_KEY = st.secrets["general"].get("openai_api_key", None)
except Exception:
    st.error("🚨 설정 오류: Streamlit Secrets에 github_token과 repo_name이 설정되지 않았습니다.")
    st.stop()

ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

# 페이지 설정
st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴")

# --- 2. 디자인(CSS) 수정 (버그 픽스 & 가독성 강화) ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 🔴 전체 페이지 스타일 */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }

    /* 🚫 UI 버그 수정: 툴팁 및 단축키 도움말 완벽 제거 (3중 차단) */
    div[data-testid="stTooltipHoverTarget"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    /* Expander 옆에 뜨는 작은 도움말 텍스트 제거 */
    .streamlit-expanderHeader small {
        display: none !important;
    }
    /* 툴바 제거 */
    div[data-testid="stToolbar"] { display: none !important; }
    .stDeployButton { display: none !important; }
    
    /* 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }

    /* 사이드바 메뉴 버튼 */
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
    }
    div[role="radiogroup"] label:hover {
        background-color: #30363D;
        color: white;
        transform: translateX(3px);
    }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        border: 1px solid #ff8a8a;
        box-shadow: 0 2px 8px rgba(230, 57, 70, 0.4);
    }
    div[role="radiogroup"] > label > div:first-child { display: none; }

    /* 📦 리소스 카드 */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .resource-card:hover {
        transform: translateY(-5px);
        border-color: #E63946;
        box-shadow: 0 10px 20px rgba(230, 57, 70, 0.15);
    }
    .resource-card h3 {
        color: #FFFFFF !important;
        font-weight: 700;
        margin-bottom: 8px;
        font-size: 1.4rem;
    }
    .resource-card p { color: #CCCCCC !important; line-height: 1.6; }

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
        white-space: pre-wrap; /* 긴 줄 바꿈 */
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363D !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #E63946 !important;
    }
    
    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background-color: #21262D;
        color: #E6E6E6;
        border-radius: 6px;
        font-weight: 600;
    }
    .streamlit-expanderContent {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-top: none;
        border-radius: 0 0 6px 6px;
        padding: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 기능 함수들 ---

def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def load_resources_from_github():
    resources = []
    repo = get_repo()
    try:
        contents = repo.get_contents(UPLOAD_DIR)
        for content in contents:
            if content.type == "dir":
                try:
                    info_file = repo.get_contents(f"{content.path}/info.json")
                    info_data = json.loads(info_file.decoded_content.decode("utf-8"))
                    info_data['id'] = content.name
                    info_data['path'] = content.path
                    resources.append(info_data)
                except:
                    continue 
    except:
        return []
    return sorted(resources, key=lambda x: x.get('title', ''), reverse=True)

def upload_to_github(folder_name, files, meta_data):
    repo = get_repo()
    base_path = f"{UPLOAD_DIR}/{folder_name}"
    
    for file in files:
        file_content = file.getvalue()
        file_path = f"{base_path}/{file.name}"
        try:
            repo.create_file(file_path, f"Add {file.name}", file_content)
        except:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, f"Update {file.name}", file_content, contents.sha)
            
    json_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
    json_path = f"{base_path}/info.json"
    try:
        repo.create_file(json_path, "Add info.json", json_content)
    except:
        contents = repo.get_contents(json_path)
        repo.update_file(contents.path, "Update info.json", json_content, contents.sha)

def delete_from_github(folder_path):
    repo = get_repo()
    contents = repo.get_contents(folder_path)
    for content in contents:
        repo.delete_file(content.path, "Delete resource", content.sha)

def download_files_as_zip(selected_resources):
    repo = get_repo()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_resources:
            folder_path = res['path']
            contents = repo.get_contents(folder_path)
            for content in contents:
                if content.name == "info.json": continue
                zf.writestr(content.name, content.decoded_content)
    return zip_buffer.getvalue()

# --- 🔥 핵심 개선: 프롬프트 고도화 (비즈니스 리포트 톤) ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY:
        return "💡 (API 키가 없어 자동 설명이 생성되지 않았습니다.)"
    
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
    with st.sidebar:
        st.markdown("## 🔴 Red Drive")
        menu = st.radio("MENU", ["리소스 탐색", "관리자 모드"], label_visibility="collapsed")
        st.divider()
        st.info("💡 **Red Drive**는 레드사업실의 자산을 영구적으로 보관하는 아카이브입니다.")

    # [탐색 탭]
    if menu == "리소스 탐색":
        st.markdown("<h1 style='color:#E63946;'>Red Drive <span style='color:#666; font-size:0.5em;'>| AI Resource Hub</span></h1>", unsafe_allow_html=True)
        st.write("레드사업실의 AI 도구와 데이터를 가장 직관적으로 탐색하고 활용하세요.")
        st.divider()

        if 'resources_cache' not in st.session_state:
            with st.spinner("🚀 GitHub에서 데이터를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_github()
        
        resources = st.session_state['resources_cache']
        
        col_search, col_refresh = st.columns([9, 1])
        search_query = col_search.text_input("검색", placeholder="키워드 입력...", label_visibility="collapsed")
        if col_refresh.button("🔄"):
            del st.session_state['resources_cache']
            st.rerun()

        if search_query:
            resources = [r for r in resources if search_query.lower() in str(r).lower()]

        # 전체 선택
        if 'selected_ids' not in st.session_state: st.session_state['selected_ids'] = []
        c1, c2, _ = st.columns([1.5, 1.5, 7])
        if c1.button("✅ 전체 선택"):
            st.session_state['selected_ids'] = [r['id'] for r in resources]
            st.rerun()
        if c2.button("❌ 선택 해제"):
            st.session_state['selected_ids'] = []
            st.rerun()

        if not resources:
            st.warning("등록된 리소스가 없습니다.")
        
        for res in resources:
            st.markdown(f"""
            <div class="resource-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px; align-items:center;">
                    <span style="background:#E63946; color:white; padding:4px 12px; border-radius:12px; font-size:0.8em; font-weight:bold;">
                        {res.get('category', 'General')}
                    </span>
                    <span style="color:#888; font-size:0.9em;">파일 {len(res.get('files', []))}개</span>
                </div>
                <h3>{res.get('title')}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"📖 '{res.get('title')}' 분석 보고서 & 파일 확인"):
                st.markdown(res.get('description', '설명 없음'))
                file_html = "".join([f'<div class="file-item">📄 {f}</div>' for f in res.get('files', [])])
                st.markdown(f'<div class="file-terminal"><b>[Included Files]</b><br>{file_html}</div>', unsafe_allow_html=True)

            is_checked = res['id'] in st.session_state['selected_ids']
            if st.checkbox(f"📥 다운로드 담기", value=is_checked, key=f"chk_{res['id']}"):
                if res['id'] not in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].append(res['id'])
                    st.rerun()
            else:
                if res['id'] in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].remove(res['id'])
                    st.rerun()
            st.write("")

        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"현재 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("압축 중..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button("⬇️ ZIP 저장", zip_data, "RedDrive_Archive.zip", "application/zip", use_container_width=True)

    # [관리자 탭]
    else:
        st.title("🛠️ 관리자 모드")
        
        if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False
        if not st.session_state['is_admin']:
            pwd = st.text_input("Admin Password", type="password")
            if st.button("Login"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state['is_admin'] = True
                    st.rerun()
                else:
                    st.error("비밀번호 불일치")
            return

        st.success(f"Repository: {REPO_NAME}")
        
        tab1, tab2 = st.tabs(["📤 신규 등록", "🗑️ 리소스 삭제"])

        with tab1:
            with st.form("upload", clear_on_submit=True):
                st.subheader("New Resource")
                title = st.text_input("Title")
                category = st.selectbox("Category", ["Workflow", "Prompt", "Data", "Tool"])
                files = st.file_uploader("Files (코드를 읽어서 분석합니다)", accept_multiple_files=True)
                hint = st.text_area("Hint (핵심 기능 요약)")
                
                if st.form_submit_button("🚀 Upload & Analyze"):
                    if title and files:
                        with st.spinner("🤖 AI가 코드를 읽고 분석 보고서를 작성 중입니다..."):
                            # 파일 읽기 로직
                            file_contents_summary = ""
                            f_names = []
                            for f in files:
                                f_names.append(f.name)
                                if any(f.name.endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.json', '.txt', '.md', '.gs', '.sh', '.csv']):
                                    try:
                                        content = f.getvalue().decode("utf-8")[:2000]
                                        file_contents_summary += f"\n--- File: {f.name} ---\n{content}\n"
                                    except:
                                        file_contents_summary += f"\n--- File: {f.name} (Binary) ---\n"
                                else:
                                    file_contents_summary += f"\n--- File: {f.name} (Binary) ---\n"

                            desc = generate_pro_description(file_contents_summary, hint)
                        
                        with st.spinner("☁️ GitHub에 저장 중..."):
                            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                            meta = {"title": title, "category": category, "description": desc, "files": f_names}
                            upload_to_github(folder_name, files, meta)
                            
                        st.balloons()
                        st.success("업로드 완료!")
                        if 'resources_cache' in st.session_state: del st.session_state['resources_cache']
                    else:
                        st.warning("제목과 파일을 입력하세요.")

        with tab2:
            if st.button("새로고침"):
                st.session_state['resources_cache'] = load_resources_from_github()
            
            resources = st.session_state.get('resources_cache', [])
            if resources:
                target = st.selectbox("삭제할 리소스", [r['title'] for r in resources])
                if st.button("🔥 영구 삭제"):
                    target_obj = next((r for r in resources if r['title'] == target), None)
                    if target_obj:
                        with st.spinner("Deleting..."):
                            delete_from_github(target_obj['path'])
                        st.success("삭제됨")
                        del st.session_state['resources_cache']
                        st.rerun()

if __name__ == "__main__":
    main()
