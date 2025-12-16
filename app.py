import streamlit as st
import os
import json
import io
import zipfile
from github import Github
from openai import OpenAI
from datetime import datetime

# --- 버전 정보 ---
CURRENT_VERSION = "🇰🇷 v7.0 (한글화 + 드롭박스 수리)"

# --- 1. 설정 및 시크릿 로드 ---
try:
    GITHUB_TOKEN = st.secrets["general"]["github_token"]
    REPO_NAME = st.secrets["general"]["repo_name"]
    OPENAI_API_KEY = st.secrets["general"]["openai_api_key"]
except Exception as e:
    st.error(f"🚨 설정 오류: Secrets를 확인해주세요. ({str(e)})")
    st.stop()

ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴", initial_sidebar_state="expanded")

# --- 2. CSS 디자인 (드롭박스 수리 + 한글 폰트 + UI 개선) ---
st.markdown("""
<style>
    /* 폰트: 프리텐다드 강제 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 전체 배경: 다크 모드 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* 불필요한 UI 숨김 */
    .stDeployButton, header, div[data-testid="stStatusWidget"], div[data-testid="stTooltipHoverTarget"] { display: none !important; }

    /* 📂 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* 🚨 메뉴 버튼 스타일 (반응형) */
    div[role="radiogroup"] { display: flex; flex-direction: column; gap: 8px; }
    div[role="radiogroup"] label {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 12px 16px;
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

    /* 📦 리소스 카드 (그리드형) */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 24px;
        height: 100%;
        display: flex; flex-direction: column; justify-content: space-between;
        transition: transform 0.2s;
    }
    .resource-card:hover {
        border-color: #E63946;
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .resource-title {
        color: white; font-size: 1.2rem; font-weight: 700; margin: 10px 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    
    /* 🛠️ [긴급 수리] 드롭박스(Selectbox) 글씨 보이게 수정 */
    /* 드롭박스 선택된 값 배경 */
    div[data-baseweb="select"] > div {
        background-color: #0d1117 !important;
        color: white !important;
        border-color: #30363D !important;
    }
    /* 드롭박스 펼쳤을 때 메뉴 배경 및 글씨 */
    div[data-baseweb="popover"] div, div[data-baseweb="menu"], ul {
        background-color: #1F242C !important;
        color: white !important;
    }
    /* 옵션 항목들 */
    div[data-baseweb="option"] {
        color: white !important;
    }
    /* 마우스 올렸을 때 하이라이트 */
    div[data-baseweb="option"]:hover, li[aria-selected="true"] {
        background-color: #E63946 !important;
        color: white !important;
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important; 
        color: white !important; 
        border: 1px solid #30363D !important;
    }
    
    /* 현황판 스타일 */
    div[data-testid="stMetric"] {
        background-color: #161B22; padding: 15px; border-radius: 10px; border: 1px solid #30363D;
    }
    div[data-testid="stMetricLabel"] { color: #8b949e; }
    div[data-testid="stMetricValue"] { color: #E63946; }
</style>
""", unsafe_allow_html=True)

# --- 3. GitHub 함수 ---
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

# --- 4. AI 설명 생성 (한국어/전문적 톤) ---
def generate_desc(summary, hint):
    if not OPENAI_API_KEY: return "API 키가 설정되지 않았습니다."
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # 🚨 한국어 강제 출력 프롬프트
    prompt = f"""
    당신은 기업의 IT 컨설턴트입니다. 아래 코드를 분석하여 임원 및 실무자 보고용 문서를 작성하세요.
    반드시 **한국어(Korean)**로 작성해야 합니다.
    
    [파일 내용 요약]: {summary}
    [작성자 힌트]: {hint}
    
    **작성 가이드:**
    1. 서론 생략, 바로 본론 진입.
    2. 전문적인 비즈니스 용어 사용.
    3. Markdown 포맷 사용.
    
    **출력 양식:**
    ### 🛑 문제 정의 (Pain Point)
    (이 도구가 없을 때 발생하는 비효율, 리스크, 휴먼 에러 등을 구체적으로 서술)

    ### 💡 해결 방안 (Solution)
    (코드가 작동하는 원리와 이를 통해 자동화되는 프로세스 설명)

    ### 🚀 기대 효과 (Impact)
    (도입 시 얻을 수 있는 정량적, 정성적 이점)
    """
    try:
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except str as e: return f"오류 발생: {e}"

# --- 5. 메인 화면 ---
def main():
    # 사이드바 메뉴
    with st.sidebar:
        st.title("🔴 Red Drive")
        st.caption(CURRENT_VERSION)
        st.write("---")
        menu = st.radio("메뉴 이동", ["🗂️ 리소스 탐색", "⚙️ 관리자 모드"], label_visibility="collapsed")

    # [탐색 페이지]
    if "탐색" in menu:
        st.title("Red Drive | AI 리소스 센터")
        st.markdown("레드사업실의 AI 도구와 데이터를 한곳에서 탐색하고 활용하세요.")
        
        # 데이터 로드
        if 'resources' not in st.session_state:
            with st.spinner("최신 데이터를 불러오는 중..."):
                st.session_state['resources'] = load_resources_from_github()
        
        resources = st.session_state['resources']
        
        # 현황판
        m1, m2, m3 = st.columns(3)
        m1.metric("총 리소스", f"{len(resources)}개")
        total_files = sum([len(r.get('files', [])) for r in resources])
        m2.metric("전체 파일", f"{total_files}개")
        m3.metric("시스템 상태", "정상 가동 🟢")
        
        st.divider()

        # 검색 및 필터
        c1, c2 = st.columns([5, 1])
        search = c1.text_input("검색", placeholder="키워드 입력 (예: 회의록, 요약...)", label_visibility="collapsed")
        if c2.button("🔄 새로고침"):
            del st.session_state['resources']
            st.rerun()
            
        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

        # 선택 기능
        if 'selected' not in st.session_state: st.session_state['selected'] = []
        
        if not resources:
            st.info("등록된 리소스가 없습니다. 관리자 모드에서 첫 자료를 등록해보세요.")
        else:
            cols = st.columns(2)
            for idx, res in enumerate(resources):
                with cols[idx % 2]:
                    with st.container():
                        # 카드 렌더링
                        st.markdown(f"""
                        <div class="resource-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="background:#E63946; color:white; padding:4px 10px; border-radius:8px; font-size:0.8em; font-weight:bold;">{res.get('category')}</span>
                                <span style="color:#666; font-size:0.8em;">파일: {len(res.get('files', []))}개</span>
                            </div>
                            <div class="resource-title" title="{res.get('title')}">{res.get('title')}</div>
                            <div style="color:#aaa; font-size:0.9em; height:45px; overflow:hidden; margin-bottom:15px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">
                                {res.get('description', '').replace('#', '').replace('*', '')[:100]}...
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 버튼 영역
                        c_check, c_view = st.columns([1, 2])
                        is_sel = res['id'] in st.session_state['selected']
                        if c_check.checkbox("선택", key=res['id'], value=is_sel):
                            if res['id'] not in st.session_state['selected']:
                                st.session_state['selected'].append(res['id'])
                        else:
                            if res['id'] in st.session_state['selected']:
                                st.session_state['selected'].remove(res['id'])
                                
                        with c_view.expander("상세 내용 보기"):
                            st.markdown(res.get('description'))
                            st.caption("포함된 파일:")
                            for f in res.get('files', []): st.code(f, language="bash")

        # 하단 플로팅 바
        if st.session_state['selected']:
            st.markdown("---")
            c_info, c_btn = st.columns([8, 2])
            c_info.success(f"{len(st.session_state['selected'])}개의 리소스가 선택되었습니다.")
            if c_btn.button("📦 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                target_objs = [r for r in resources if r['id'] in st.session_state['selected']]
                with st.spinner("파일을 압축하는 중입니다..."):
                    zip_data = download_zip(target_objs)
                    st.download_button("내 컴퓨터에 저장", zip_data, "RedDrive_Resources.zip", "application/zip", use_container_width=True)

    # [관리자 페이지]
    elif "관리자" in menu:
        st.title("⚙️ 관리자 모드")
        
        pwd = st.text_input("비밀번호 입력", type="password")
        if pwd == ADMIN_PASSWORD:
            t1, t2 = st.tabs(["업로드(등록)", "파일 삭제"])
            
            with t1:
                with st.form("upl"):
                    title = st.text_input("제목 (한글)")
                    cat = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Tool"])
                    files = st.file_uploader("관련 파일 업로드", accept_multiple_files=True)
                    hint = st.text_area("AI 힌트 (어떤 문제를 해결하는지 간단히 적어주세요)")
                    
                    if st.form_submit_button("등록 및 AI 분석 시작"):
                        if title and files:
                            with st.spinner("AI가 문서를 분석하고 보고서를 작성 중입니다..."):
                                # 파일명 목록만 AI에게 전달 (내용까지 읽으면 느릴 수 있음)
                                summ = ", ".join([f.name for f in files])
                                desc = generate_desc(summ, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                # 안전한 폴더명 생성
                                folder_name = "".join(x for x in title if x.isalnum()) + "_" + os.urandom(4).hex()
                                upload_to_github(folder_name, files, meta)
                            
                            st.balloons()
                            st.success("등록이 완료되었습니다!")
                            del st.session_state['resources']
            
            with t2:
                if st.button("목록 새로고침"): 
                    st.session_state['resources'] = load_resources_from_github()
                
                res_list = st.session_state.get('resources', [])
                if res_list:
                    # 드롭박스: 이제 글씨가 잘 보일 것입니다.
                    target = st.selectbox("삭제할 리소스 선택", [r['title'] for r in res_list])
                    if st.button("영구 삭제", type="primary"):
                        tgt = next(r for r in res_list if r['title'] == target)
                        with st.spinner("삭제 중입니다..."):
                            delete_from_github(tgt['path'])
                        st.success("삭제되었습니다.")
                        del st.session_state['resources']
                        st.rerun()

if __name__ == "__main__":
    main()
