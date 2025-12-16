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

# --- 2. 디자인(CSS) 대폭 개선 (다크 모드 & 반응형) ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 🔴 전체 페이지 배경 및 텍스트 (다크 모드 강제) */
    .stApp {
        background-color: #0E1117; /* 아주 짙은 남색/검정 */
        color: #FAFAFA;
    }

    /* 사이드바 스타일링 */
    section[data-testid="stSidebar"] {
        background-color: #161B22; /* 사이드바 배경 */
        border-right: 1px solid #30363D;
    }
    
    /* 🔴 사이드바 메뉴 (라디오 버튼) 커스텀 */
    div[role="radiogroup"] > label > div:first-child {
        display: none; /* 기본 동그라미 숨김 */
    }
    div[role="radiogroup"] label {
        padding: 15px 20px;
        margin-bottom: 8px;
        border-radius: 8px;
        border: 1px solid transparent;
        transition: all 0.3s ease;
        background-color: #21262D; /* 기본 버튼 색 */
        color: #C9D1D9;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
    }
    div[role="radiogroup"] label:hover {
        background-color: #30363D;
        transform: translateX(5px); /* 마우스 올리면 살짝 오른쪽으로 이동 */
    }
    /* 선택된 메뉴 스타일 */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important; /* 레드 포인트 */
        color: white !important;
        box-shadow: 0 0 15px rgba(230, 57, 70, 0.6); /* 붉은 빛 효과 */
        border: 1px solid #ff6b6b;
    }

    /* 📦 리소스 카드 (반응형 효과) */
    .resource-card {
        background-color: #1F242C; /* 카드 배경 (진회색) */
        border: 1px solid #30363D;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 25px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* 부드러운 텐션 */
        position: relative;
        overflow: hidden;
    }
    .resource-card:hover {
        transform: translateY(-7px) scale(1.01); /* 위로 떠오르는 효과 */
        border-color: #E63946; /* 테두리 붉게 변함 */
        box-shadow: 0 10px 30px -10px rgba(230, 57, 70, 0.3); /* 붉은 그림자 */
    }
    .resource-card h3 {
        color: #ffffff !important;
        font-weight: 700;
        margin-top: 0;
        font-size: 1.4rem;
    }
    .resource-card p {
        color: #a0a0a0 !important; /* 본문은 연한 회색 */
        line-height: 1.6;
    }

    /* 📂 파일 리스트 박스 (가독성 해결) */
    .file-terminal {
        background-color: #0d1117; /* 완전 검정 */
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
        font-family: 'Courier New', monospace;
        color: #7EE787; /* 터미널 녹색 */
        font-size: 0.9em;
    }
    .file-item {
        display: block;
        padding: 4px 0;
        border-bottom: 1px dashed #30363D;
    }
    .file-item:last-child { border-bottom: none; }

    /* 입력창 스타일 (글씨 잘 보이게) */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363D !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #E63946 !important;
        box-shadow: 0 0 0 1px #E63946 !important;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #21262D;
        color: #8b949e;
        border-radius: 6px;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E63946 !important;
        color: white !important;
    }
    
    /* 버튼 스타일 */
    .stButton button {
        background-color: #21262D;
        color: white;
        border: 1px solid #30363D;
        font-weight: bold;
        transition: 0.2s;
    }
    .stButton button:hover {
        background-color: #E63946;
        border-color: #E63946;
        color: white;
    }
    /* 빨간색 강조 버튼 (일괄 다운로드 등) */
    .primary-btn button {
        background-color: #E63946 !important;
        box-shadow: 0 4px 14px 0 rgba(230, 57, 70, 0.39);
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
    
    # 1. 파일 업로드
    for file in files:
        file_content = file.getvalue()
        file_path = f"{base_path}/{file.name}"
        try:
            repo.create_file(file_path, f"Add {file.name}", file_content)
        except:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, f"Update {file.name}", file_content, contents.sha)
            
    # 2. info.json
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

def generate_pro_description(file_names, user_hint):
    if not OPENAI_API_KEY:
        return "💡 (API 키가 없어 자동 설명이 생성되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # --- 프롬프트 변경: 구조적 차별화 ---
    prompt = f"""
    당신은 IT 비즈니스 컨설턴트입니다. 'Red Drive'에 업로드된 AI 리소스에 대해 보고서 형식의 설명을 작성해야 합니다.
    기존의 단순한 설명을 넘어, '문제 해결'과 '비즈니스 가치' 중심으로 작성해주세요.
    
    - 파일 목록: {', '.join(file_names)}
    - 작성자 힌트: {user_hint}
    
    다음 마크다운 구조를 엄격히 따라주세요:
    
    ### 🛑 문제 정의 (Pain Point)
    (이 도구가 없다면 발생하던 비효율이나 문제점을 2문장으로 서술)
    
    ### 💡 솔루션 (Solution Logic)
    (이 리소스가 어떻게 문제를 해결하는지 핵심 로직 설명)
    - **자동화 포인트**: (어떤 부분이 자동화되는지)
    - **핵심 프로세스**: (주요 흐름 요약)
    
    ### 🚀 비즈니스 임팩트 (Impact)
    (이것을 도입했을 때 얻을 수 있는 정량적/정성적 효과)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"설명 생성 실패: {str(e)}"

# --- 4. 메인 로직 ---

def main():
    # 사이드바 메뉴 (커스텀 CSS로 버튼처럼 보임)
    with st.sidebar:
        st.markdown("## 🔴 Red Drive")
        st.write("") # 여백
        menu = st.radio("MENU", ["리소스 탐색", "관리자 모드"], label_visibility="collapsed")
        
        st.divider()
        st.info("💡 **Red Drive**는 레드사업실의 자산을 영구적으로 보관하는 아카이브입니다.")

    # [메인] 리소스 탐색
    if menu == "리소스 탐색":
        st.markdown("<h1 style='color:#E63946;'>Red Drive <span style='color:#666; font-size:0.5em;'>| AI Resource Hub</span></h1>", unsafe_allow_html=True)
        st.markdown("레드사업실의 AI 도구와 데이터를 가장 직관적으로 탐색하고 활용하세요.")
        st.divider()

        if 'resources_cache' not in st.session_state:
            with st.spinner("🚀 GitHub에서 데이터를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_github()
        
        resources = st.session_state['resources_cache']
        
        # 검색창
        col_search, col_refresh = st.columns([9, 1])
        search_query = col_search.text_input("검색", placeholder="키워드 입력 (예: 회의록, 프롬프트...)", label_visibility="collapsed")
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

        # 리소스 카드 렌더링
        if not resources:
            st.warning("등록된 리소스가 없습니다.")
        
        for res in resources:
            # HTML 컨테이너 시작
            st.markdown(f"""
            <div class="resource-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px; align-items:center;">
                    <span style="background:#E63946; color:white; padding:5px 12px; border-radius:20px; font-size:0.8em; font-weight:bold;">
                        {res.get('category', 'General')}
                    </span>
                    <span style="color:#666; font-size:0.9em;">Files: {len(res.get('files', []))}</span>
                </div>
                <h3>{res.get('title')}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 설명 및 파일 (Expander)
            with st.expander(f"📖 '{res.get('title')}' 상세 정보 및 파일 보기"):
                st.markdown(res.get('description', '설명 없음'))
                
                # 파일 리스트 (터미널 스타일 적용)
                file_html = "".join([f'<div class="file-item">📄 {f}</div>' for f in res.get('files', [])])
                st.markdown(f'<div class="file-terminal"><b>root@red-drive:~/files# ls -l</b><br>{file_html}</div>', unsafe_allow_html=True)

            # 체크박스
            is_checked = res['id'] in st.session_state['selected_ids']
            if st.checkbox(f"📥 다운로드 담기", value=is_checked, key=res['id']):
                if res['id'] not in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].append(res['id'])
                    st.rerun()
            else:
                if res['id'] in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].remove(res['id'])
                    st.rerun()
            st.write("") # 카드 간 간격

        # 하단 플로팅바 (다운로드)
        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"현재 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 선택 항목 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("압축 중..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button(
                        label="⬇️ ZIP 파일 저장",
                        data=zip_data,
                        file_name="RedDrive_Archive.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

    # [관리자 모드]
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
                    st.error("비밀번호가 틀렸습니다.")
            return

        st.success(f"Connected to: {REPO_NAME}")
        
        tab1, tab2 = st.tabs(["📤 신규 등록", "🗑️ 리소스 삭제"])

        with tab1:
            with st.form("upload", clear_on_submit=True):
                st.subheader("New Resource")
                title = st.text_input("Title")
                category = st.selectbox("Category", ["Workflow", "Prompt", "Data", "Tool"])
                files = st.file_uploader("Files", accept_multiple_files=True)
                hint = st.text_area("AI Hint (핵심 기능 요약)")
                
                if st.form_submit_button("🚀 Upload to GitHub"):
                    if title and files:
                        with st.spinner("🤖 AI 보고서 작성 중..."):
                            f_names = [f.name for f in files]
                            desc = generate_pro_description(f_names, hint)
                        
                        with st.spinner("☁️ GitHub 전송 중..."):
                            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                            meta = {"title": title, "category": category, "description": desc, "files": f_names}
                            upload_to_github(folder_name, files, meta)
                            
                        st.balloons()
                        st.success("업로드 완료!")
                        if 'resources_cache' in st.session_state: del st.session_state['resources_cache']
                    else:
                        st.warning("제목과 파일을 입력하세요.")

        with tab2:
            if st.button("목록 새로고침"):
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
