import streamlit as st
import os
import json
import io
import zipfile
import re
import time
# 📌 Github 관련 모듈
from github import Github, GithubException, UnknownObjectException
from openai import OpenAI

# --- 버전 정보 ---
CURRENT_VERSION = "🚀 v14.0 (Final Fix: 프롬프트 복구 & 특수효과 적용)"

# --- 1. 시크릿 로드 ---
try:
    GITHUB_TOKEN = st.secrets["general"]["github_token"]
    REPO_NAME = st.secrets["general"]["repo_name"]
    OPENAI_API_KEY = st.secrets["general"]["openai_api_key"]
except Exception as e:
    st.error(f"🚨 설정 오류: Secrets를 확인하세요. ({str(e)})")
    st.stop()

ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴", initial_sidebar_state="expanded")

# --- 2. CSS 디자인 ---
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, p, h1, h2, h3, h4, h5, h6, span, div, label, input, textarea, button {
        font-family: Pretendard, sans-serif;
    }
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stDeployButton, header, div[data-testid="stStatusWidget"] { display: none !important; }
    div[data-testid="stTooltipHoverTarget"] { display: none !important; }

    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    div[role="radiogroup"] label {
        background-color: transparent; border: 1px solid transparent; border-radius: 6px;
        padding: 12px 16px; margin: 0 !important; transition: all 0.2s ease;
        color: #8b949e !important; font-weight: 600;
    }
    div[role="radiogroup"] label:hover { background-color: #21262D; color: white !important; }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important; color: white !important;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.3); border: none;
    }
    .resource-card {
        background-color: #1F242C; border: 1px solid #30363D; border-radius: 12px;
        padding: 20px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;
        margin-bottom: 15px;
    }
    .resource-title { color: white; font-size: 1.2rem; font-weight: 700; margin: 10px 0 5px 0; }
    .resource-preview { color: #B0B0B0; font-size: 0.9rem; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 3. 헬퍼 함수 ---
def clean_text_for_preview(text):
    if not text: return "내용 없음"
    clean = re.sub(r'[#*`\->]', '', text)
    clean = " ".join(clean.split())
    return clean[:120]

def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

@st.cache_data(ttl=60)
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
                except: continue
    except: return []
    return sorted(resources, key=lambda x: x.get('title', ''), reverse=True)

def safe_create_or_update(repo, file_path, message, content):
    try:
        existing_file = repo.get_contents(file_path)
        repo.update_file(file_path, message, content, existing_file.sha)
    except UnknownObjectException:
        try:
            repo.create_file(file_path, message, content)
        except GithubException as e:
            if e.status == 409:
                st.error("🚨 보안 경고: 파일 안에 OpenAI Key 같은 비밀 정보가 포함되어 있어 GitHub가 업로드를 차단했습니다. 키를 지우고 다시 시도하세요.")
            else:
                st.error(f"❌ GitHub 오류 ({e.status}): {e.data}")
            st.stop()
    except GithubException as e:
        st.error(f"❌ 알 수 없는 GitHub 오류: {str(e)}")
        st.stop()

def upload_to_github(folder_name, files, meta_data):
    repo = get_repo()
    base_path = f"{UPLOAD_DIR}/{folder_name}"
    
    progress_text = "파일 업로드 시작..."
    my_bar = st.progress(0, text=progress_text)
    
    total_steps = len(files) + 1
    
    for idx, file in enumerate(files):
        safe_filename = file.name 
        file_path = f"{base_path}/{safe_filename}"
        content_bytes = file.getvalue()
        
        safe_create_or_update(repo, file_path, f"Add {safe_filename}", content_bytes)
        
        percent = int(((idx + 1) / total_steps) * 100)
        my_bar.progress(percent, text=f"Uploading: {safe_filename}")
            
    json_path = f"{base_path}/info.json"
    json_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
    safe_create_or_update(repo, json_path, "Add info", json_content)
    
    my_bar.progress(100, text="업로드 완료!")
    time.sleep(0.5)
    my_bar.empty()

def delete_from_github(folder_path):
    repo = get_repo()
    contents = repo.get_contents(folder_path)
    for c in contents: repo.delete_file(c.path, "Del", c.sha)

def download_zip(selected_objs):
    repo = get_repo()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_objs:
            safe_folder_name = re.sub(r'[\\/:*?"<>|]', '_', res.get('title', 'Untitled'))
            contents = repo.get_contents(res['path'])
            for c in contents:
                if c.name != "info.json":
                    zip_path = f"{safe_folder_name}/{c.name}"
                    zf.writestr(zip_path, c.decoded_content)
    return zip_buffer.getvalue()

# 📌 [복구 완료] 선생님이 주신 완벽한 프롬프트 적용
def generate_desc(file_contents_str, hint):
    if not OPENAI_API_KEY: return "API 키가 설정되지 않았습니다."
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 기업의 수석 IT 컨설턴트입니다. 
    사용자가 업로드한 '파일의 실제 내용'을 분석하여 임원 및 실무자 보고용 문서를 작성하세요.
    
    [분석할 파일 내용]:
    {file_contents_str}
    
    [작성자 힌트]: 
    {hint}
    
    **작성 가이드:**
    1. 서론(안녕하세요 등) 절대 금지. 바로 본론 진입.
    2. 전문적인 비즈니스 용어 사용.
    3. 화살표(->)를 사용하여 데이터 흐름을 명확히 표현.
    4. 언어: 한국어 (Korean)
    
    **출력 포맷 (Markdown):**
    
    ### 📋 시스템 요약 (Executive Summary)
    (이 도구가 무엇인지, 어떤 비즈니스 가치를 주는지 2줄 요약)

    ### ⚙️ 아키텍처 및 데이터 흐름
    * **Flow**: `[입력] -> [처리] -> [출력]` (실제 로직 반영)
    * **핵심 구성 요소**:
        * **파일명**: (해당 파일의 구체적 역할과 로직 설명)

    ### 🛠️ 기술적 메커니즘 (Deep Dive)
    * **트리거**: (언제 실행되는지)
    * **로직**: (데이터가 어떻게 가공되는지 코드 레벨 분석)

    ### ✨ 비즈니스 임팩트
    (도입 시 정량적/정성적 기대 효과)
    """
    try:
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except str as e: return f"오류 발생: {e}"

# --- 5. 메인 화면 ---
def main():
    with st.sidebar:
        st.title("🔴 Red Drive")
        st.caption(CURRENT_VERSION)
        st.write("---")
        menu = st.radio("메뉴 이동", ["🗂️ 리소스 탐색", "⚙️ 관리자 모드"], label_visibility="collapsed")

    if "탐색" in menu:
        st.title("Red Drive | AI 리소스 센터")
        
        if 'resources' not in st.session_state:
            with st.spinner("데이터 로딩 중..."):
                st.session_state['resources'] = load_resources_from_github()
        
        resources = st.session_state['resources']
        st.metric("총 리소스", f"{len(resources)}개")
        st.divider()

        c1, c2 = st.columns([5, 1])
        search = c1.text_input("검색", placeholder="키워드...", label_visibility="collapsed")
        if c2.button("🔄 새로고침"):
            if 'resources' in st.session_state: del st.session_state['resources']
            st.rerun()
        if search: resources = [r for r in resources if search.lower() in str(r).lower()]
        
        if 'selected' not in st.session_state: st.session_state['selected'] = []

        if not resources:
            st.info("등록된 리소스가 없습니다.")
        else:
            cols = st.columns(2)
            for idx, res in enumerate(resources):
                with cols[idx % 2]:
                    with st.container():
                        st.markdown(f"""
                        <div class="resource-card">
                            <div style="font-weight:bold; color:#E63946;">{res.get('category')}</div>
                            <div class="resource-title">{res.get('title')}</div>
                            <div class="resource-preview">{clean_text_for_preview(res.get('description', ''))}...</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        c_chk, c_exp = st.columns([1, 2])
                        is_sel = res['id'] in st.session_state['selected']
                        if c_chk.checkbox("선택", key=res['id'], value=is_sel):
                            if res['id'] not in st.session_state['selected']: st.session_state['selected'].append(res['id'])
                        else:
                            if res['id'] in st.session_state['selected']: st.session_state['selected'].remove(res['id'])
                        with c_exp.expander("상세 보기"):
                            st.markdown(res.get('description', ''))

        if st.session_state['selected']:
            st.markdown("---")
            # 📌 다운로드 버튼 클릭 시 눈송이 효과
            if st.button("📦 다운로드 (ZIP)", type="primary", use_container_width=True):
                st.snow()  # ❄️ 눈송이 효과
                
                target = [r for r in resources if r['id'] in st.session_state['selected']]
                with st.spinner("압축 중... 잠시만 기다려주세요 ❄️"):
                    zip_data = download_zip(target)
                    time.sleep(1) 
                    st.download_button("💾 파일 저장하기 (Click)", zip_data, "RedDrive.zip", "application/zip", use_container_width=True)

    elif "관리자" in menu:
        st.title("⚙️ 관리자 모드")
        pwd = st.text_input("비밀번호", type="password")
        if pwd == ADMIN_PASSWORD:
            t1, t2 = st.tabs(["신규 등록", "삭제"])
            with t1:
                with st.form("upl"):
                    title = st.text_input("제목 (한글)")
                    cat = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Tool"])
                    files = st.file_uploader("파일 업로드", accept_multiple_files=True)
                    hint = st.text_area("AI 힌트")
                    
                    if st.form_submit_button("등록"):
                        if title and files:
                            with st.spinner("AI 분석 및 업로드 중..."):
                                content_summary = ""
                                for f in files:
                                    try: content_summary += f.getvalue().decode("utf-8")[:1000]
                                    except: content_summary += "Binary File"
                                desc = generate_desc(content_summary, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                
                                safe_title = "".join(x for x in title if x.isalnum()) 
                                folder_name = f"{safe_title}_{os.urandom(4).hex()}"
                                
                                upload_to_github(folder_name, files, meta)
                            
                            # 📌 업로드 성공 시 풍선 효과
                            st.balloons() 
                            st.success("등록이 완료되었습니다! 잠시 후 목록이 갱신됩니다.")
                            time.sleep(3) 
                            
                            del st.session_state['resources']
                            st.rerun()

            with t2:
                if st.button("목록 새로고침"): 
                    st.session_state['resources'] = load_resources_from_github()
                res_list = st.session_state.get('resources', [])
                if res_list:
                    target = st.selectbox("삭제 대상", [r['title'] for r in res_list])
                    if st.button("영구 삭제", type="primary"):
                        tgt = next(r for r in res_list if r['title'] == target)
                        with st.spinner("삭제 중..."): delete_from_github(tgt['path'])
                        st.success("삭제됨")
                        del st.session_state['resources']
                        st.rerun()

if __name__ == "__main__":
    main()
