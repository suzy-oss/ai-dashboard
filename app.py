import streamlit as st
import os
import json
import io
import zipfile
from github import Github
from openai import OpenAI

# --- 버전 정보 (업데이트 확인용) ---
CURRENT_VERSION = "✨ v5.0 (디자인/기능 완전 복구)"

# --- 1. 시크릿(Secrets) 로드 (가장 중요!) ---
# Streamlit Cloud의 Secrets에서 키를 가져옵니다.
try:
    GITHUB_TOKEN = st.secrets["general"]["github_token"]
    REPO_NAME = st.secrets["general"]["repo_name"]
    OPENAI_API_KEY = st.secrets["general"]["openai_api_key"]
except Exception as e:
    st.error(f"🚨 설정 오류: Streamlit Secrets를 찾을 수 없습니다. ({str(e)})")
    st.stop()

ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴", initial_sidebar_state="expanded")

# --- 2. 디자인(CSS) : 반응형 메뉴 + 다크 테마 + 겹침 해결 ---
st.markdown("""
<style>
    /* 폰트 적용 (아이콘 깨짐 방지를 위해 !important 제외) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, [class*="css"] {
        font-family: Pretendard, sans-serif;
    }
    
    /* 🔴 전체 테마: 다크 모드 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* UI 정리 (불필요한 요소 숨김) */
    .stDeployButton, header, div[data-testid="stStatusWidget"] { display: none !important; }
    
    /* 🚨 텍스트 겹침 문제 해결 (아이콘은 살리고 툴팁만 제거) */
    div[data-testid="stTooltipHoverTarget"] { display: none !important; }
    
    /* 📂 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    section[data-testid="stSidebar"] * { color: #E6E6E6 !important; }

    /* 🔘 메뉴(라디오 버튼) -> 반응형 버튼 스타일로 변신 */
    div.row-widget.stRadio > div[role="radiogroup"] > label {
        background-color: #21262D;
        padding: 14px 20px;
        margin-bottom: 10px;
        border-radius: 10px;
        border: 1px solid #30363D;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #30363D;
        border-color: #E63946;
        transform: translateY(-2px); /* 살짝 떠오르는 효과 */
        color: white !important;
    }
    /* 선택된 메뉴 강조 */
    div.row-widget.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        font-weight: bold;
        box-shadow: 0 0 15px rgba(230, 57, 70, 0.5); /* 붉은 네온 효과 */
        border: none;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label > div:first-child { display: none; }

    /* 📦 리소스 카드 (반응형 Hover 효과 복구) */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 15px;
        padding: 25px;
        margin-bottom: 20px;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    .resource-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        border-color: #E63946;
    }
    .resource-card h3 { color: white !important; margin: 0 0 10px 0; font-size: 1.4rem; }
    
    /* 터미널 스타일 파일 목록 */
    .file-terminal {
        background: #0d1117; padding: 15px; border-radius: 8px;
        color: #7EE787; font-family: monospace; font-size: 0.85em;
        border: 1px solid #30363D; margin-top: 10px;
    }

    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important; 
        color: white !important;
        border: 1px solid #30363D !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. GitHub 연동 함수 (영구 저장용) ---
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
                except: continue
    except: return []
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

# --- 4. AI 프롬프트 (군기 잡힌 버전) ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY:
        return "💡 (API 키가 로드되지 않았습니다. Secrets를 확인하세요.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
    당신은 기업의 '업무 효율화 컨설턴트'입니다. 
    업로드된 도구를 분석하여 '도입 제안서'를 작성하세요.
    
    [파일 내용 요약]
    {file_contents_summary}
    [작성자 힌트]
    {user_hint}
    
    **작성 가이드:**
    - 서론(현대 사회는.. 등) 금지. 바로 본론으로 진입.
    - 구체적인 Pain Point(문제)와 Solution(해결책) 위주로 작성.
    - Markdown 형식 준수.
    
    ### 🛑 문제 정의 (Pain Point)
    (내용)
    
    ### 💡 해결 솔루션 (Solution)
    (내용)
    * **핵심 로직**: ...
    
    ### 🚀 도입 효과 (Impact)
    (내용)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"분석 실패: {str(e)}"

# --- 5. 메인 화면 ---
def main():
    # 사이드바
    with st.sidebar:
        st.header("🔴 Red Drive")
        st.caption(CURRENT_VERSION)
        st.write("---")
        menu = st.radio("MENU", ["리소스 탐색", "관리자 모드"]) 

    # [리소스 탐색 탭]
    if menu == "리소스 탐색":
        st.title("Red Drive | AI Resource Hub")
        st.write("레드사업실의 AI 도구와 데이터를 탐색하고 다운로드하세요.")
        st.divider()

        # 데이터 로드 (GitHub)
        if 'resources_cache' not in st.session_state:
            with st.spinner("🚀 GitHub에서 데이터를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_github()
        
        resources = st.session_state['resources_cache']
        
        # 검색 및 필터
        col1, col2 = st.columns([8, 2])
        search = col1.text_input("검색", placeholder="키워드...", label_visibility="collapsed")
        if col2.button("🔄 새로고침"):
            del st.session_state['resources_cache']
            st.rerun()

        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

        # ✅ 전체 선택 / 해제 버튼 (복구됨)
        if 'selected_ids' not in st.session_state: st.session_state['selected_ids'] = []
        c_btn1, c_btn2, _ = st.columns([1.5, 1.5, 7])
        if c_btn1.button("✅ 전체 선택"):
            st.session_state['selected_ids'] = [r['id'] for r in resources]
            st.rerun()
        if c_btn2.button("❌ 선택 해제"):
            st.session_state['selected_ids'] = []
            st.rerun()

        if not resources:
            st.info("등록된 리소스가 없습니다. 관리자 모드에서 파일을 등록해주세요.")

        # 리소스 카드 출력
        for res in resources:
            st.markdown(f"""
            <div class="resource-card">
                <span style="background:#E63946; color:white; padding:4px 10px; border-radius:10px; font-size:0.8em;">{res.get('category')}</span>
                <span style="color:#888; margin-left:10px; font-size:0.9em;">파일 {len(res.get('files', []))}개</span>
                <h3 style="margin-top:10px;">{res.get('title')}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("📄 상세 보고서 및 파일 보기"):
                st.markdown(res.get('description'))
                file_html = "".join([f"<div>📄 {f}</div>" for f in res.get('files', [])])
                st.markdown(f'<div class="file-terminal">{file_html}</div>', unsafe_allow_html=True)
            
            # 체크박스 (UI 분리)
            is_checked = res['id'] in st.session_state['selected_ids']
            if st.checkbox(f"📥 다운로드 담기 ({res['title']})", value=is_checked, key=res['id']):
                if res['id'] not in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].append(res['id'])
                    st.rerun()
            else:
                if res['id'] in st.session_state['selected_ids']:
                    st.session_state['selected_ids'].remove(res['id'])
                    st.rerun()
            st.write("") 

        # ✅ 하단 플로팅 다운로드 버튼 (복구됨)
        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"현재 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 선택한 리소스 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("GitHub에서 파일을 다운로드하여 압축 중입니다..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button("⬇️ ZIP 파일 저장", zip_data, "RedDrive_Resources.zip", "application/zip", use_container_width=True)

    # [관리자 모드 탭]
    elif menu == "관리자 모드":
        st.title("🛠️ 관리자 모드")
        
        pwd = st.text_input("관리자 비밀번호", type="password")
        if pwd == ADMIN_PASSWORD:
            st.success("인증되었습니다.")
            
            tab1, tab2 = st.tabs(["📤 신규 등록", "🗑️ 삭제"])
            
            with tab1:
                with st.form("reg"):
                    st.subheader("파일 등록 및 AI 분석")
                    title = st.text_input("제목")
                    cat = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Tool"])
                    files = st.file_uploader("파일 업로드", accept_multiple_files=True)
                    hint = st.text_area("힌트 (문제점 위주로)")
                    
                    if st.form_submit_button("등록 시작"):
                        if title and files:
                            # 1. AI 분석
                            with st.spinner("AI가 코드를 읽고 분석 중..."):
                                summary = ""
                                for f in files:
                                    try: summary += f"\nFile: {f.name}\n{f.getvalue().decode('utf-8')[:1000]}"
                                    except: summary += f"\nFile: {f.name} (Binary)"
                                desc = generate_pro_description(summary, hint)
                            
                            # 2. GitHub 업로드
                            with st.spinner("GitHub에 저장 중..."):
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                                upload_to_github(folder_name, files, meta)
                            
                            # ✅ 풍선 효과 복구!
                            st.balloons() 
                            st.success("등록 완료! 리소스 탐색 탭에서 확인하세요.")
                            del st.session_state['resources_cache']
                        else:
                            st.error("제목과 파일을 모두 입력해주세요.")

            with tab2:
                if st.button("목록 갱신"): st.session_state['resources_cache'] = load_resources_from_github()
                res_list = st.session_state.get('resources_cache', [])
                if res_list:
                    target = st.selectbox("삭제 대상", [r['title'] for r in res_list])
                    if st.button("영구 삭제"):
                        tgt = next(r for r in res_list if r['title'] == target)
                        with st.spinner("GitHub에서 삭제 중..."):
                            delete_from_github(tgt['path'])
                        st.success("삭제되었습니다.")
                        del st.session_state['resources_cache']
                        st.rerun()

if __name__ == "__main__":
    main()
