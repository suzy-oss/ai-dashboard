import streamlit as st
import os
import json
import io
import zipfile
import re
from github import Github, GithubException # 예외 처리를 위해 추가
from openai import OpenAI

# --- 버전 정보 ---
CURRENT_VERSION = "🛡️ v12.0 (오류 방지 + 즉시 갱신 + 드롭박스 수리)"

# --- 1. 설정 및 시크릿 로드 ---
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

# --- 2. CSS 디자인 (드롭박스 가시성 + 아이콘 보호) ---
st.markdown("""
<style>
    /* 폰트 적용: 아이콘 깨짐 방지 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, p, h1, h2, h3, h4, h5, h6, span, div, label, input, textarea, button {
        font-family: Pretendard, sans-serif !important;
    }
    
    .material-icons, .material-symbols-rounded, svg, i {
        font-family: 'Material Icons', sans-serif !important; 
        font-style: normal !important;
    }

    /* 🔴 전체 배경 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* 불필요 UI 숨김 */
    .stDeployButton, header, div[data-testid="stStatusWidget"], div[data-testid="stTooltipHoverTarget"] { display: none !important; }

    /* 📂 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* 🚨 메뉴 버튼 스타일 */
    div[role="radiogroup"] { gap: 8px; display: flex; flex-direction: column; }
    div[role="radiogroup"] label {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 10px 15px;
        margin: 0 !important;
        transition: all 0.2s ease;
        color: #8b949e !important;
        font-weight: 600;
        display: flex; align-items: center;
    }
    div[role="radiogroup"] label:hover {
        background-color: #21262D;
        color: white !important;
    }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.3);
        border: none;
    }
    div[role="radiogroup"] label > div:first-child { display: none; }

    /* 🛠️ [드롭박스 최종 수리] 색상 강제 지정 */
    /* 선택 박스 자체 */
    div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        color: white !important;
        border-color: #4A4A4A !important;
    }
    /* 텍스트 강제 흰색 */
    div[data-baseweb="select"] span {
        color: white !important;
    }
    /* 팝업 메뉴 컨테이너 */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {
        background-color: #1F242C !important;
    }
    /* 리스트 아이템 (옵션) */
    li[role="option"] {
        color: white !important;
        background-color: #1F242C !important; 
    }
    /* 마우스 호버 시 */
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {
        background-color: #E63946 !important;
        color: white !important;
    }
    /* 선택된 값 (Single Value) */
    div[data-testid="stSelectbox"] div[class*="singleValue"] {
        color: white !important;
    }

    /* 📦 리소스 카드 */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        height: 100%;
        display: flex; flex-direction: column; justify-content: space-between;
        transition: transform 0.2s;
        margin-bottom: 15px;
    }
    .resource-card:hover {
        border-color: #E63946;
        transform: translateY(-3px);
    }
    .resource-title {
        color: white; font-size: 1.2rem; font-weight: 700; margin: 10px 0 5px 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .resource-preview {
        color: #B0B0B0; font-size: 0.9rem; line-height: 1.5;
        height: 4.5em; overflow: hidden;
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
        margin-bottom: 15px;
        background-color: #161B22;
        padding: 8px; border-radius: 6px;
    }

    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
    }
    .streamlit-expanderContent {
        background-color: #161B22;
        border: 1px solid #4A4A4A;
        border-top: none;
        padding: 20px;
        color: #E0E0E0;
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0E1117 !important; 
        color: white !important; 
        border: 1px solid #30363D !important;
    }
    
    /* 현황판 */
    div[data-testid="stMetric"] {
        background-color: #161B22; padding: 15px; border-radius: 10px; border: 1px solid #30363D;
    }
    div[data-testid="stMetricLabel"] { color: #8b949e; }
    div[data-testid="stMetricValue"] { color: #E63946; }
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

# 🔄 캐시 최적화: 변경이 있을 때만 clear하기 위해 사용
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

def upload_to_github(folder_name, files, meta_data):
    repo = get_repo()
    base_path = f"{UPLOAD_DIR}/{folder_name}"
    for file in files:
        try:
            repo.create_file(f"{base_path}/{file.name}", f"Add {file.name}", file.getvalue())
        except:
            contents = repo.get_contents(f"{base_path}/{file.name}")
            repo.update_file(contents.path, f"Update {file.name}", file.getvalue(), contents.sha)
            
    json_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
    try:
        repo.create_file(f"{base_path}/info.json", "Add info", json_content)
    except:
        c = repo.get_contents(f"{base_path}/info.json")
        repo.update_file(c.path, "Update info", json_content, c.sha)

# 🚨 [안정성 강화] 삭제 로직에 예외 처리 추가
def delete_from_github(folder_path):
    repo = get_repo()
    try:
        contents = repo.get_contents(folder_path)
        for c in contents:
            repo.delete_file(c.path, "Del", c.sha)
    except GithubException as e:
        # 이미 삭제된 파일(404)이면 그냥 넘어감 (사용자 입장에서는 삭제된 거니까 OK)
        if e.status == 404:
            pass 
        else:
            raise e # 다른 에러면 멈춤

def download_zip(selected_objs):
    repo = get_repo()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_objs:
            try:
                contents = repo.get_contents(res['path'])
                for c in contents:
                    if c.name != "info.json": zf.writestr(c.name, c.decoded_content)
            except: continue
    return zip_buffer.getvalue()

# --- 4. AI 설명 생성 ---
def generate_desc(file_contents_str, hint):
    if not OPENAI_API_KEY: return "API 키가 설정되지 않았습니다."
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 기업의 수석 IT 컨설턴트입니다. 
    업로드된 '파일 내용'을 분석하여 임원 보고용 문서를 작성하세요.
    
    [분석할 파일 내용]:
    {file_contents_str}
    
    [작성자 힌트]: 
    {hint}
    
    **작성 가이드:**
    1. 서론(안녕하세요 등) 절대 금지.
    2. 전문적인 비즈니스 용어 사용.
    3. 화살표(->)를 사용하여 데이터 흐름을 명확히 표현.
    4. 언어: 한국어 (Korean)
    
    **출력 포맷 (Markdown):**
    
    ### 📋 시스템 요약 (Executive Summary)
    (이 도구가 무엇인지, 비즈니스 가치 2줄 요약)

    ### ⚙️ 아키텍처 및 데이터 흐름
    * **Flow**: `[입력] -> [처리] -> [출력]` (실제 로직 반영)
    * **핵심 구성 요소**:
        * **파일명**: (역할)

    ### 🛠️ 기술적 메커니즘 (Deep Dive)
    * **트리거**: (언제 실행되는지)
    * **로직**: (데이터 처리 방식)

    ### ✨ 비즈니스 임팩트
    (도입 효과)
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
        
        # 데이터 로드
        if 'resources' not in st.session_state:
            with st.spinner("데이터 로딩 중..."):
                st.session_state['resources'] = load_resources_from_github()
        
        resources = st.session_state['resources']
        
        # 현황판
        m1, m2, m3 = st.columns(3)
        m1.metric("총 리소스", f"{len(resources)}개")
        total_files = sum([len(r.get('files', [])) for r in resources])
        m2.metric("전체 파일", f"{total_files}개")
        m3.metric("상태", "Active 🟢")
        
        st.divider()

        # 검색/새로고침
        c1, c2 = st.columns([5, 1])
        search = c1.text_input("검색", placeholder="키워드 입력...", label_visibility="collapsed")
        if c2.button("🔄 새로고침"):
            # 🚨 강제 갱신 로직
            st.cache_data.clear()
            if 'resources' in st.session_state: del st.session_state['resources']
            st.rerun()
            
        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

        # 리소스 목록
        if 'selected' not in st.session_state: st.session_state['selected'] = []
        
        if not resources:
            st.info("등록된 리소스가 없습니다.")
        else:
            cols = st.columns(2)
            for idx, res in enumerate(resources):
                with cols[idx % 2]:
                    with st.container():
                        # 요약 텍스트 정제
                        desc_raw = res.get('description', '')
                        desc_clean = clean_text_for_preview(desc_raw)

                        st.markdown(f"""
                        <div class="resource-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="background:#E63946; color:white; padding:4px 10px; border-radius:8px; font-size:0.8em; font-weight:bold;">{res.get('category')}</span>
                                <span style="color:#888; font-size:0.8em;">파일 {len(res.get('files', []))}개</span>
                            </div>
                            <div class="resource-title" title="{res.get('title')}">{res.get('title')}</div>
                            <div class="resource-preview">{desc_clean}...</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        c_chk, c_exp = st.columns([1, 2])
                        is_sel = res['id'] in st.session_state['selected']
                        if c_chk.checkbox("선택", key=res['id'], value=is_sel):
                            if res['id'] not in st.session_state['selected']:
                                st.session_state['selected'].append(res['id'])
                        else:
                            if res['id'] in st.session_state['selected']:
                                st.session_state['selected'].remove(res['id'])
                        
                        with c_exp.expander("상세 내용 열기"):
                            st.markdown(desc_raw)
                            st.caption("포함된 파일:")
                            for f in res.get('files', []): st.code(f, language="bash")

        if st.session_state['selected']:
            st.markdown("---")
            c_info, c_btn = st.columns([8, 2])
            c_info.success(f"{len(st.session_state['selected'])}개 선택됨")
            if c_btn.button("📦 다운로드 (ZIP)", type="primary", use_container_width=True):
                target_objs = [r for r in resources if r['id'] in st.session_state['selected']]
                with st.spinner("압축 중..."):
                    zip_data = download_zip(target_objs)
                    st.download_button("저장하기", zip_data, "RedDrive.zip", "application/zip", use_container_width=True)

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
                            with st.spinner("AI가 내용을 읽고 보고서를 작성 중... (잠시만 기다려주세요)"):
                                content_summary = ""
                                for f in files:
                                    # 텍스트 파일만 읽기
                                    if f.name.endswith(('.py', '.js', '.json', '.txt', '.md', '.html', '.css', '.gs', '.csv')):
                                        try:
                                            file_text = f.getvalue().decode("utf-8")
                                            content_summary += f"\n--- [파일명: {f.name}] ---\n{file_text[:3000]}\n"
                                        except:
                                            content_summary += f"\n--- [파일명: {f.name}] (바이너리) ---\n"
                                    else:
                                        content_summary += f"\n--- [파일명: {f.name}] (기타) ---\n"

                                desc = generate_desc(content_summary, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                folder_name = "".join(x for x in title if x.isalnum()) + "_" + os.urandom(4).hex()
                                upload_to_github(folder_name, files, meta)
                            
                            st.balloons()
                            st.success("등록 완료! 목록을 갱신합니다.")
                            # 🚨 등록 직후 강제 캐시 삭제 및 리런 (사용자가 바로 확인 가능하도록)
                            st.cache_data.clear()
                            if 'resources' in st.session_state: del st.session_state['resources']
                            st.rerun()
            with t2:
                if st.button("목록 새로고침"): 
                    st.cache_data.clear()
                    st.session_state['resources'] = load_resources_from_github()
                    st.rerun()
                
                # 데이터 로드
                if 'resources' not in st.session_state:
                    st.session_state['resources'] = load_resources_from_github()
                
                res_list = st.session_state.get('resources', [])
                if res_list:
                    target = st.selectbox("삭제할 리소스", [r['title'] for r in res_list])
                    if st.button("영구 삭제", type="primary"):
                        tgt = next((r for r in res_list if r['title'] == target), None)
                        if tgt:
                            with st.spinner("삭제 처리 중..."):
                                delete_from_github(tgt['path'])
                            st.success("삭제되었습니다. 화면을 갱신합니다.")
                            # 🚨 삭제 직후 강제 갱신
                            st.cache_data.clear()
                            del st.session_state['resources']
                            st.rerun()
                        else:
                            st.warning("이미 삭제된 리소스입니다.")

if __name__ == "__main__":
    main()
