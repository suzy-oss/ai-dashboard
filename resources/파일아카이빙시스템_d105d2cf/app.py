import streamlit as st
import os
import json
import io
import zipfile
from github import Github
from openai import OpenAI
from datetime import datetime

# --- 버전 정보 ---
CURRENT_VERSION = "💎 v6.0 (Grid UI + Dashboard)"

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

# --- 2. CSS 디자인 (메뉴 스타일 완전 변경 + 그리드 + 드롭박스 수정) ---
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif; }
    
    /* 전체 배경 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* UI 숨김 */
    .stDeployButton, header, div[data-testid="stStatusWidget"], div[data-testid="stTooltipHoverTarget"] { display: none !important; }

    /* 📂 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* 🚨 메뉴(Radio)를 진짜 '버튼'처럼 바꾸는 강력한 CSS */
    div[role="radiogroup"] {
        gap: 10px;
        display: flex;
        flex-direction: column;
    }
    div[role="radiogroup"] label {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 0 !important;
        transition: all 0.2s ease;
        color: #8b949e !important;
        font-weight: 600;
        display: flex;
        align-items: center;
    }
    div[role="radiogroup"] label:hover {
        background-color: #21262D;
        color: white !important;
    }
    /* 선택된 메뉴 스타일 */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.3);
        border: none;
    }
    /* 라디오 버튼 동그라미 제거 */
    div[role="radiogroup"] label > div:first-child { display: none; }
    div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] { margin-left: 0; }

    /* 📦 리소스 카드 (그리드용 높이 고정 및 디자인) */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 16px;
        padding: 24px;
        height: 100%; /* 높이 맞춤 */
        transition: transform 0.2s;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .resource-card:hover {
        border-color: #E63946;
        transform: translateY(-5px);
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }
    .resource-title {
        color: white; font-size: 1.3rem; font-weight: 700; margin: 10px 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    
    /* 🛠️ 드롭박스(Selectbox) 글씨 안 보이는 문제 해결 */
    div[data-baseweb="select"] > div {
        background-color: #0d1117 !important;
        color: white !important;
        border-color: #30363D !important;
    }
    div[data-baseweb="menu"] {
        background-color: #1F242C !important;
    }
    div[data-baseweb="option"] {
        color: white !important;
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important; 
        color: white !important; 
        border: 1px solid #30363D !important;
    }
    
    /* 현황판(Metric) 스타일 */
    div[data-testid="stMetric"] {
        background-color: #161B22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363D;
        text-align: center;
    }
    div[data-testid="stMetricLabel"] { color: #8b949e; }
    div[data-testid="stMetricValue"] { color: #E63946; font-size: 1.8rem; }
</style>
""", unsafe_allow_html=True)

# --- 3. GitHub 함수 ---
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

@st.cache_data(ttl=60) # 60초 캐싱으로 속도 향상
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

def delete_from_github(folder_path):
    repo = get_repo()
    contents = repo.get_contents(folder_path)
    for c in contents: repo.delete_file(c.path, "Del", c.sha)

def download_zip(selected_objs):
    repo = get_repo()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_objs:
            contents = repo.get_contents(res['path'])
            for c in contents:
                if c.name != "info.json": zf.writestr(c.name, c.decoded_content)
    return zip_buffer.getvalue()

# --- 4. AI 설명 생성 ---
def generate_desc(summary, hint):
    if not OPENAI_API_KEY: return "API 키 오류"
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
    당신은 IT 컨설턴트입니다. 아래 코드를 분석하여 보고서를 작성하세요.
    [파일요약]: {summary}
    [힌트]: {hint}
    
    서론 없이 바로 다음 항목으로 작성(Markdown):
    ### 🛑 Pain Point
    (문제점)
    ### 💡 Solution
    (해결방식 및 로직)
    ### 🚀 Impact
    (기대효과)
    """
    try:
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except str as e: return f"Error: {e}"

# --- 5. 메인 화면 ---
def main():
    # 사이드바
    with st.sidebar:
        st.title("🔴 Red Drive")
        st.caption(CURRENT_VERSION)
        st.write("---")
        # 여기가 메뉴입니다. CSS로 버튼처럼 보이게 만들었습니다.
        menu = st.radio("MENU", ["🗂️ 리소스 탐색", "⚙️ 관리자 모드"], label_visibility="collapsed")

    # [탐색 페이지]
    if "탐색" in menu:
        st.title("Red Drive Dashboard")
        st.markdown("레드사업실 AI 리소스 통합 아카이브")
        
        # 데이터 로드
        if 'resources' not in st.session_state:
            with st.spinner("서버와 통신 중..."):
                st.session_state['resources'] = load_resources_from_github()
        
        resources = st.session_state['resources']
        
        # 📊 상단 현황판 (대시보드 느낌)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Resources", f"{len(resources)}개")
        total_files = sum([len(r.get('files', [])) for r in resources])
        m2.metric("Total Files", f"{total_files}개")
        m3.metric("Status", "Active 🟢")
        
        st.divider()

        # 검색 및 필터
        c1, c2 = st.columns([5, 1])
        search = c1.text_input("Search", placeholder="키워드 검색...", label_visibility="collapsed")
        if c2.button("🔄 Sync"):
            del st.session_state['resources']
            st.rerun()
            
        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

        # 전체 선택 기능
        if 'selected' not in st.session_state: st.session_state['selected'] = []
        
        # 📦 리소스 카드 그리드 레이아웃 (2열 배치)
        if not resources:
            st.info("등록된 리소스가 없습니다.")
        else:
            # 2열로 나누기
            cols = st.columns(2)
            for idx, res in enumerate(resources):
                with cols[idx % 2]: # 짝수/홀수 인덱스로 컬럼 분배
                    # 카드 디자인
                    with st.container():
                        st.markdown(f"""
                        <div class="resource-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="background:#E63946; color:white; padding:4px 10px; border-radius:8px; font-size:0.8em; font-weight:bold;">{res.get('category')}</span>
                                <span style="color:#666; font-size:0.8em;">Files: {len(res.get('files', []))}</span>
                            </div>
                            <div class="resource-title" title="{res.get('title')}">{res.get('title')}</div>
                            <div style="color:#aaa; font-size:0.9em; height:40px; overflow:hidden; margin-bottom:15px;">
                                {res.get('description', '')[:60]}...
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 기능 버튼들 (카드 아래 배치)
                        c_check, c_view = st.columns([1, 2])
                        is_sel = res['id'] in st.session_state['selected']
                        if c_check.checkbox("선택", key=res['id'], value=is_sel):
                            if res['id'] not in st.session_state['selected']:
                                st.session_state['selected'].append(res['id'])
                        else:
                            if res['id'] in st.session_state['selected']:
                                st.session_state['selected'].remove(res['id'])
                                
                        with c_view.expander("상세 보기"):
                            st.markdown(res.get('description'))
                            st.caption("Files:")
                            for f in res.get('files', []): st.code(f, language="bash")

        # 하단 플로팅 액션 바
        if st.session_state['selected']:
            st.markdown("---")
            c_info, c_btn = st.columns([8, 2])
            c_info.success(f"{len(st.session_state['selected'])}개 리소스 선택됨")
            if c_btn.button("📦 다운로드 (ZIP)", type="primary", use_container_width=True):
                target_objs = [r for r in resources if r['id'] in st.session_state['selected']]
                with st.spinner("압축 중..."):
                    zip_data = download_zip(target_objs)
                    st.download_button("저장하기", zip_data, "RedDrive.zip", "application/zip", use_container_width=True)

    # [관리자 페이지]
    elif "관리자" in menu:
        st.title("⚙️ Admin Console")
        
        pwd = st.text_input("Password", type="password")
        if pwd == ADMIN_PASSWORD:
            t1, t2 = st.tabs(["Upload", "Delete"])
            
            with t1:
                with st.form("upl"):
                    title = st.text_input("Title")
                    cat = st.selectbox("Category", ["Workflow", "Prompt", "Data", "Tool"])
                    files = st.file_uploader("Files", accept_multiple_files=True)
                    hint = st.text_area("Hint")
                    if st.form_submit_button("Upload"):
                        if title and files:
                            with st.spinner("AI Analysis..."):
                                summ = "\n".join([f.name for f in files])
                                desc = generate_desc(summ, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                upload_to_github("".join(x for x in title if x.isalnum()), files, meta)
                            st.balloons()
                            st.success("Uploaded!")
                            del st.session_state['resources']
            
            with t2:
                if st.button("Refresh List"): 
                    st.session_state['resources'] = load_resources_from_github()
                
                res_list = st.session_state.get('resources', [])
                if res_list:
                    # 여기가 수정된 드롭박스입니다.
                    target = st.selectbox("Select Resource to Delete", [r['title'] for r in res_list])
                    if st.button("Delete Permanently", type="primary"):
                        tgt = next(r for r in res_list if r['title'] == target)
                        with st.spinner("Deleting..."):
                            delete_from_github(tgt['path'])
                        st.success("Deleted.")
                        del st.session_state['resources']
                        st.rerun()

if __name__ == "__main__":
    main()