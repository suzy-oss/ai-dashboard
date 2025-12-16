import streamlit as st
import os
import json
import io
import zipfile
from openai import OpenAI

# --- 버전 확인용 (업데이트 확인을 위해 필수) ---
CURRENT_VERSION = "🔥 버전 4.0 긴급 복구"

# --- 1. 설정 ---
# [로컬 테스트용 설정] - 배포 시에는 st.secrets를 사용하는 것이 좋습니다.
OPENAI_API_KEY = "여기에_키를_입력하세요" 
ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴", initial_sidebar_state="expanded")

# --- 2. 강력한 CSS 수정 (겹침 삭제 + 메뉴 복구) ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 🔴 전체 테마: 다크 모드 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* 🚨 [UI 긴급 수리] 겹치는 텍스트 및 상단 배포 버튼 강제 삭제 */
    header { visibility: hidden; } /* 상단 헤더 숨김 */
    .stDeployButton { display: none !important; } /* 배포 버튼 삭제 */
    div[data-testid="stStatusWidget"] { display: none !important; } /* 상태 위젯 삭제 */
    div[data-testid="stToolbar"] { display: none !important; } /* 툴바 삭제 */
    div[data-testid="stDecoration"] { display: none !important; } /* 상단 데코레이션 삭제 */
    
    /* 툴팁 겹침 문제 해결 */
    div[data-testid="stTooltipHoverTarget"] { display: none !important; }
    
    /* 📂 사이드바 스타일 (메뉴가 보이도록 수정) */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
        width: 300px !important; /* 너비 고정 */
    }
    
    /* 사이드바 안의 텍스트 색상 강제 지정 */
    section[data-testid="stSidebar"] * {
        color: #E6E6E6 !important;
    }

    /* 라디오 버튼(메뉴) 스타일링 - 버튼처럼 보이게 */
    div.row-widget.stRadio > div[role="radiogroup"] > label {
        background-color: #21262D;
        padding: 15px;
        margin-bottom: 8px;
        border-radius: 8px;
        border: 1px solid #30363D;
        cursor: pointer;
        transition: 0.2s;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #E63946;
        color: white !important;
        border-color: #E63946;
    }
    /* 선택된 메뉴 강조 */
    div.row-widget.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        font-weight: bold;
        box-shadow: 0 4px 10px rgba(230, 57, 70, 0.5);
    }
    /* 라디오 버튼 동그라미 숨기기 */
    div.row-widget.stRadio > div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* 메인 콘텐츠 카드 스타일 */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
    }
    .resource-card h3 { color: white !important; margin: 0 0 10px 0; }
    
    /* 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important; 
        color: white !important;
        border: 1px solid #30363D !important;
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

# --- 4. AI 프롬프트 (군기 잡힌 버전) ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY or "입력하세요" in OPENAI_API_KEY:
        return "💡 (API 키가 설정되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 기업의 '업무 효율화 컨설턴트'입니다. 
    업로드된 도구(파일)를 분석하여, 현업 관리자에게 보고할 '도입 제안서'를 작성하세요.
    
    [분석할 파일 내용]
    {file_contents_summary}
    
    [작성자 힌트]
    {user_hint}
    
    **작성 전략:**
    1. **Pain Point (문제 정의)**:
       - "현대 사회는..." 같은 서론 절대 금지.
       - 업무 현장에서 발생하는 '구체적인 사고', '비효율', '리스크'를 직설적으로 지적할 것.
       - 예: "수작업 복사/붙여넣기로 인해 월평균 3건의 데이터 누락 발생."
    
    2. **Solution (해결책)**:
       - 코드를 근거로 '어떤 기술'이 '어느 과정'을 대체하는지 설명.
    
    **출력 형식 (Markdown):**
    
    ### 🛑 문제 정의 (Pain Point)
    (현업의 구체적인 문제점 지적)
    
    ### 💡 해결 솔루션 (Solution)
    (코드를 기반으로 한 기술적 해결 방식)
    * **핵심 로직**: ...
    
    ### 🚀 도입 효과 (Impact)
    * (정량적/정성적 기대 효과)
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
    # 사이드바 (메뉴가 여기 있어야 함!)
    with st.sidebar:
        st.header("🔴 Red Drive")
        # 🔥 버전 확인용 텍스트 (업데이트 확인 필수)
        st.warning(CURRENT_VERSION)
        
        st.write("---")
        
        # 메뉴 선택창 (라디오 버튼)
        menu = st.radio("이동할 페이지를 선택하세요", ["리소스 탐색", "관리자 모드"]) 

    # [페이지 1: 리소스 탐색]
    if menu == "리소스 탐색":
        st.title("Red Drive | AI Resource Hub")
        st.write("레드사업실의 AI 도구와 데이터를 탐색하고 다운로드하세요.")
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

        if not resources:
            st.info("등록된 리소스가 없습니다. '관리자 모드'에서 파일을 등록해주세요.")

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

    # [페이지 2: 관리자 모드] - 여기가 사라졌던 메뉴입니다.
    elif menu == "관리자 모드":
        st.title("🛠️ 관리자 모드")
        
        pwd = st.text_input("관리자 비밀번호를 입력하세요", type="password")
        
        if pwd == ADMIN_PASSWORD:
            st.success("인증되었습니다.")
            
            tab1, tab2 = st.tabs(["📤 신규 등록", "🗑️ 삭제"])
            
            # 신규 등록 탭
            with tab1:
                with st.form("reg"):
                    st.subheader("파일 등록 및 AI 분석")
                    title = st.text_input("제목")
                    cat = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Tool"])
                    files = st.file_uploader("파일 업로드", accept_multiple_files=True)
                    hint = st.text_area("힌트 (문제점 위주로)")
                    
                    if st.form_submit_button("등록 시작"):
                        if title and files:
                            with st.spinner("AI가 분석 중..."):
                                summary = ""
                                for f in files:
                                    try: summary += f"\nFile: {f.name}\n{f.getvalue().decode('utf-8')[:1000]}"
                                    except: summary += f"\nFile: {f.name} (Binary)"
                                desc = generate_pro_description(summary, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                upload_to_local(folder_name=title, files=files, meta_data=meta)
                            st.success("등록 완료! '리소스 탐색' 메뉴로 이동해 확인하세요.")
                            del st.session_state['resources_cache']
                        else:
                            st.error("제목과 파일을 모두 입력해주세요.")

            # 삭제 탭
            with tab2:
                if st.button("목록 갱신"): st.session_state['resources_cache'] = load_resources_from_local()
                res_list = st.session_state.get('resources_cache', [])
                if res_list:
                    target = st.selectbox("삭제 대상", [r['title'] for r in res_list])
                    if st.button("영구 삭제"):
                        tgt = next(r for r in res_list if r['title'] == target)
                        delete_from_local(tgt['path'])
                        st.success("삭제됨")
                        del st.session_state['resources_cache']
                        st.rerun()
        elif pwd:
            st.error("비밀번호가 틀렸습니다.")

if __name__ == "__main__":
    main()
