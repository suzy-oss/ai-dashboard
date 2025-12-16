import streamlit as st
import os
import json
import io
import zipfile
# from github import Github # 로컬 테스트 시 주석
from openai import OpenAI

# --- 버전 확인용 (업데이트 되었는지 확인하세요!) ---
APP_VERSION = "Ver 3.5 (Design Fix + Sharp AI)" 

# --- 1. 설정 ---
# [배포용 설정] 실제 배포 시에는 주석을 풀고 Secrets를 사용하세요.
# try:
#     GITHUB_TOKEN = st.secrets["general"]["github_token"]
#     REPO_NAME = st.secrets["general"]["repo_name"]
#     OPENAI_API_KEY = st.secrets["general"].get("openai_api_key", None)
# except Exception:
#     st.error("🚨 설정 오류: Secrets를 확인하세요.")
#     st.stop()

# [로컬 테스트용] - 배포 전 테스트할 때만 사용
OPENAI_API_KEY = "여기에_키를_입력하세요" 
UPLOAD_DIR = "resources"
ADMIN_PASSWORD = "1234"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴")

# --- 2. CSS 디자인 (메뉴 복구 및 겹침 해결) ---
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* 🚨 [UI 버그 해결] 텍스트 겹침/툴팁 강제 삭제 */
    .st-emotion-cache-1wbqy5l, .st-emotion-cache-1p1m4ay { display: none !important; }
    div[data-testid="stToolbar"] { visibility: hidden; height: 0%; }
    div[data-testid="stDecoration"] { visibility: hidden; height: 0%; }
    div[data-testid="stStatusWidget"] { visibility: hidden; height: 0%; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    
    /* 사이드바 스타일 (메뉴 사라짐 방지) */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* 메뉴 버튼 디자인 (라디오 버튼 커스텀) */
    div.row-widget.stRadio > div { flex-direction: column; }
    div.row-widget.stRadio > div[role="radiogroup"] > label {
        background-color: #21262D;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 8px;
        cursor: pointer;
        border: 1px solid transparent;
        color: #C9D1D9;
        transition: 0.3s;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #30363D;
        color: white;
    }
    /* 선택된 메뉴 */
    div.row-widget.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white;
        font-weight: bold;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.4);
    }
    /* 라디오 버튼 동그라미 숨기기 */
    div.row-widget.stRadio > div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* 리소스 카드 */
    .resource-card {
        background-color: #1F242C; border: 1px solid #30363D;
        border-radius: 12px; padding: 25px; margin-bottom: 20px;
    }
    .resource-card h3 { color: white; margin: 0 0 10px 0; }
    
    /* 파일 터미널 */
    .file-terminal {
        background: #0d1117; padding: 15px; border-radius: 6px;
        color: #7EE787; font-family: monospace; font-size: 0.85em;
        border: 1px solid #30363D; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 로컬 파일 시스템 함수 ---
def get_local_repo_path():
    if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)
    return UPLOAD_DIR

def load_resources_from_local():
    resources = []
    repo_path = get_local_repo_path()
    for item in os.listdir(repo_path):
        item_path = os.path.join(repo_path, item)
        if os.path.isdir(item_path):
            try:
                with open(os.path.join(item_path, "info.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data['id'], data['path'] = item, item_path
                    resources.append(data)
            except: continue
    return sorted(resources, key=lambda x: x.get('title', ''), reverse=True)

def upload_to_local(folder_name, files, meta_data):
    base_path = os.path.join(get_local_repo_path(), folder_name)
    os.makedirs(base_path, exist_ok=True)
    for file in files:
        with open(os.path.join(base_path, file.name), "wb") as f: f.write(file.getvalue())
    with open(os.path.join(base_path, "info.json"), "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=4)

def delete_from_local(folder_path):
    import shutil
    if os.path.exists(folder_path): shutil.rmtree(folder_path)

def download_files_as_zip(selected_resources):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_resources:
            for root, _, files in os.walk(res['path']):
                for file in files:
                    if file != "info.json":
                        zf.write(os.path.join(root, file), arcname=file)
    return zip_buffer.getvalue()

# --- 🔥 핵심: "군기 잡힌" AI 프롬프트 ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY or "입력하세요" in OPENAI_API_KEY:
        return "💡 (API 키가 설정되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # 프롬프트를 아주 구체적이고 직설적으로 변경
    prompt = f"""
    당신은 기업의 '업무 효율화 컨설턴트'입니다. 
    업로드된 도구(파일)를 분석하여, 현업 관리자에게 보고할 '도입 제안서'를 작성하세요.
    
    [분석할 파일 내용]
    {file_contents_summary}
    
    [작성자 힌트]
    {user_hint}
    
    **⚠️ 절대 금지 사항:**
    - "현대의 기업 환경에서는...", "중요합니다." 같은 뻔한 서론 금지.
    - "시간을 절약합니다." 같은 추상적인 표현 금지.
    - 번역투(~했습니다, ~입니다) 금지. 간결한 '보고서체'(~함, ~임) 사용.
    
    **✍️ 작성 포인트:**
    1. **Pain Point**: "어떤 구체적인 업무"가 꼬이고 있는지, 그로 인해 "어떤 사고(누락, 지연)"가 터지는지 지적할 것.
    2. **Solution**: 코드를 근거로 "정확히 무엇을 자동화"해서 문제를 푸는지 설명할 것.
    
    **출력 형식 (Markdown):**
    
    ### 🛑 문제 정의 (Pain Point)
    (예시: 스페이스방의 대화량이 많아 중요 공지가 타임라인에 묻히고, 이로 인해 작업자가 변경된 규정을 놓치는 리스크 발생.)
    
    ### 💡 해결 솔루션 (Solution)
    (예시: Google Chat API를 통해 대화 로그를 실시간 수집하고, '공지' 키워드가 포함된 메시지만 별도 시트로 자동 이관하여 아카이빙함.)
    * **핵심 로직**: (코드 분석 내용)
    
    ### 🚀 도입 효과 (Impact)
    * (정량적: 예 - 공지 확인 시간 90% 단축)
    * (정성적: 예 - 중요 이슈 누락 ZERO화 달성)
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"분석 실패: {str(e)}"

# --- 4. 메인 화면 ---
def main():
    with st.sidebar:
        st.header("🔴 Red Drive")
        st.caption(APP_VERSION) # 버전 확인용
        st.write("")
        menu = st.radio("메뉴 이동", ["리소스 탐색", "관리자 모드"]) # 라벨 표시

    if menu == "리소스 탐색":
        st.title("Red Drive | AI Resource Hub")
        st.divider()

        if 'resources_cache' not in st.session_state:
            st.session_state['resources_cache'] = load_resources_from_local()
        
        resources = st.session_state['resources_cache']
        
        col1, col2 = st.columns([8, 2])
        search = col1.text_input("검색", placeholder="키워드...", label_visibility="collapsed")
        if col2.button("🔄 새로고침"):
            del st.session_state['resources_cache']
            st.rerun()

        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

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

    else: # 관리자 모드
        st.title("🛠️ 관리자 모드")
        if st.text_input("Password", type="password") != ADMIN_PASSWORD:
            st.stop()
            
        tab1, tab2 = st.tabs(["신규 등록", "삭제"])
        with tab1:
            with st.form("reg"):
                title = st.text_input("제목")
                cat = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Tool"])
                files = st.file_uploader("파일", accept_multiple_files=True)
                hint = st.text_area("힌트 (문제점 위주로 적어주세요)")
                if st.form_submit_button("등록"):
                    if title and files:
                        with st.spinner("AI가 깐깐하게 분석 중..."):
                            summary = ""
                            for f in files:
                                try: summary += f"\nFile: {f.name}\n{f.getvalue().decode('utf-8')[:1000]}"
                                except: summary += f"\nFile: {f.name} (Binary)"
                            desc = generate_pro_description(summary, hint)
                            meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                            upload_to_local(folder_name=title, files=files, meta_data=meta)
                        st.success("등록 완료! 탐색 탭에서 확인하세요.")
                        del st.session_state['resources_cache']

        with tab2:
            if st.button("목록 갱신"): st.session_state['resources_cache'] = load_resources_from_local()
            res_list = st.session_state.get('resources_cache', [])
            if res_list:
                target = st.selectbox("삭제 대상", [r['title'] for r in res_list])
                if st.button("삭제"):
                    tgt = next(r for r in res_list if r['title'] == target)
                    delete_from_local(tgt['path'])
                    st.success("삭제됨")
                    del st.session_state['resources_cache']
                    st.rerun()

if __name__ == "__main__":
    main()
