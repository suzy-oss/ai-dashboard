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

# --- 2. 디자인(CSS) 수정 (버그 수정 및 가독성 강화) ---
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

    /* 🚫 UI 버그 수정: Streamlit 툴팁/단축키 도움말 강제 숨김 (key arrow_down 문제 해결) */
    div[data-testid="stTooltipHoverTarget"] > div { display: none !important; }
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
        padding: 10px 15px;
        margin-bottom: 5px;
        transition: 0.2s;
        cursor: pointer;
    }
    div[role="radiogroup"] label:hover {
        background-color: #30363D;
        color: white;
    }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        border: 1px solid #ff8a8a;
    }
    div[role="radiogroup"] > label > div:first-child { display: none; }

    /* 📦 리소스 카드 (가독성 & 디자인 개선) */
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
        margin-bottom: 10px;
        font-size: 1.5rem;
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
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363D !important;
    }
    
    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background-color: #21262D;
        color: white;
        border-radius: 6px;
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

# --- 🔥 핵심 개선: 파일 내용 읽어서 AI에게 전달하기 ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY:
        return "💡 (API 키가 없어 자동 설명이 생성되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 IT 비즈니스 분석가이자 테크니컬 라이터입니다.
    사용자가 업로드한 'Red Drive' 리소스 파일들의 **실제 내용**과 힌트를 바탕으로 분석 보고서를 작성하세요.
    
    [분석할 파일 내용 요약]
    {file_contents_summary}
    
    [사용자 힌트]
    {user_hint}
    
    위 내용을 바탕으로 아래 마크다운 포맷에 맞춰 전문적이고 구체적으로 작성하세요.
    (파일명만 나열하지 말고, 코드가 실제로 무슨 일을 하는지 분석해서 적으세요.)
    
    ### 🛑 문제 정의 (Pain Point)
    (이 도구가 해결하려는 비효율성을 구체적으로 2문장)
    
    ### 💡 솔루션 (Solution Logic)
    (파일 내용을 분석하여 이 도구의 작동 원리를 설명)
    - **핵심 로직**: (코드나 데이터가 어떻게 작동하는지 분석)
    - **구성 요소**: (각 파일이 어떤 역할을 하는지 구체적으로)
    
    ### 🚀 비즈니스 임팩트 (Impact)
    (도입 시 예상되는 정량적/정성적 효과)
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

    if menu == "리소스 탐색":
        st.markdown("<h1 style='color:#E63946;'>Red Drive <span style='color:#666; font-size:0.5em;'>| AI Resource Hub</span></h1>", unsafe_allow_html=True)
        st.write("레드사업실의 AI 도구와 데이터를 가장 직관적으로 탐색하고 활용하세요.")
        st.divider()

        if 'resources_cache' not in st.session_state:
            with st.spinner("🚀 GitHub에서 데이터를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_github()
        
        resources = st.session_state['resources_cache']
        
        # 검색 및 필터
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
            # 카드 디자인
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
            
            # 설명 펼치기
            with st.expander(f"📖 '{res.get('title')}' 상세 분석 보고서 보기"):
                st.markdown(res.get('description', '설명 없음'))
                file_html = "".join([f'<div class="file-item">📄 {f}</div>' for f in res.get('files', [])])
                st.markdown(f'<div class="file-terminal"><b>Files included:</b><br>{file_html}</div>', unsafe_allow_html=True)

            # 체크박스 (UI 충돌 방지를 위해 별도 배치)
            is_checked = res['id'] in st.session_state['selected_ids']
            if st.checkbox(f"📥 다운로드 목록에 추가", value=is_checked, key=f"chk_{res['id']}"):
                if res['id'] not in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].append(res['id'])
                    st.rerun()
            else:
                if res['id'] in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].remove(res['id'])
                    st.rerun()
            
            st.write("") # 간격

        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"현재 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("압축 중..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button("⬇️ ZIP 저장", zip_data, "RedDrive_Archive.zip", "application/zip", use_container_width=True)

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
                hint = st.text_area("Hint (AI에게 줄 추가 정보)")
                
                if st.form_submit_button("🚀 Upload & Analyze"):
                    if title and files:
                        with st.spinner("🤖 AI가 파일 내용을 읽고 분석 중입니다..."):
                            # 1. 파일 내용 읽기 (텍스트 파일만)
                            file_contents_summary = ""
                            f_names = []
                            for f in files:
                                f_names.append(f.name)
                                # 텍스트로 읽을 수 있는 확장자만 읽음
                                if any(f.name.endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.json', '.txt', '.md', '.gs', '.sh', '.csv']):
                                    try:
                                        # 앞부분 2000자만 읽어서 요약 (토큰 절약)
                                        content = f.getvalue().decode("utf-8")[:2000]
                                        file_contents_summary += f"\n--- File: {f.name} ---\n{content}\n"
                                    except:
                                        file_contents_summary += f"\n--- File: {f.name} (Binary/Unreadable) ---\n"
                                else:
                                    file_contents_summary += f"\n--- File: {f.name} (Binary/Image) ---\n"

                            # 2. 분석 요청
                            desc = generate_pro_description(file_contents_summary, hint)
                        
                        with st.spinner("☁️ GitHub에 저장 중..."):
                            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                            meta = {"title": title, "category": category, "description": desc, "files": f_names}
                            upload_to_github(folder_name, files, meta)
                            
                        st.balloons()
                        st.success("업로드 완료! AI 분석 보고서가 생성되었습니다.")
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
