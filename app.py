import streamlit as st
import os
import json
import io
import zipfile
from openai import OpenAI

# --- 버전 확인용 (업데이트 확인을 위해 필수) ---
CURRENT_VERSION = "✅ v4.1 (폰트 버그 수정 완료)"

# --- 1. 설정 ---
# [로컬 테스트용] - 배포 시에는 st.secrets 사용 권장
OPENAI_API_KEY = "여기에_키를_입력하세요" 
ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources"

st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴", initial_sidebar_state="expanded")

# --- 2. CSS 디자인 수정 (폰트 버그 해결) ---
st.markdown("""
<style>
    /* 1. 폰트 적용 (아이콘이 깨지지 않도록 !important 제거 및 범위 한정) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, [class*="css"] {
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
    }
    
    /* 🔴 전체 테마: 다크 모드 */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* 2. UI 정리 (배포 버튼 등 불필요한 요소 숨김) */
    .stDeployButton { display: none !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }
    header { visibility: hidden; }
    
    /* 3. 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    section[data-testid="stSidebar"] * {
        color: #E6E6E6 !important;
    }

    /* 4. 메뉴(라디오 버튼) 커스텀 */
    div.row-widget.stRadio > div[role="radiogroup"] > label {
        background-color: #21262D;
        padding: 12px;
        margin-bottom: 8px;
        border-radius: 8px;
        border: 1px solid #30363D;
        cursor: pointer;
        transition: 0.2s;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #E63946;
        border-color: #E63946;
        color: white !important;
    }
    /* 선택된 항목 */
    div.row-widget.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #E63946 !important;
        color: white !important;
        font-weight: bold;
    }
    div.row-widget.stRadio > div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* 5. 리소스 카드 스타일 */
    .resource-card {
        background-color: #1F242C;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .resource-card h3 { color: white !important; margin: 0 0 10px 0; }
    
    /* 6. 입력창 스타일 */
    .stTextInput input, .stTextArea textarea {
        background-color: #0d1117 !important; 
        color: white !important;
        border: 1px solid #30363D !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 파일 시스템 함수 (로컬/Github 공용 구조) ---
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

# --- 4. AI 프롬프트 (보고서 스타일) ---
def generate_pro_description(file_contents_summary, user_hint):
    if not OPENAI_API_KEY or "입력하세요" in OPENAI_API_KEY:
        return "💡 (API 키가 없어 자동 설명이 생성되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    당신은 기업의 '업무 효율화 컨설턴트'입니다. 
    업로드된 도구(파일)를 분석하여, 현업 관리자에게 보고할 '도입 제안서'를 작성하세요.
    
    [분석할 파일 내용]
    {file_contents_summary}
    
    [작성자 힌트]
    {user_hint}
    
    **작성 전략 (보고서 톤앤매너):**
    1. **Pain Point (문제 정의)**: 현업의 구체적인 비효율, 리스크, 휴먼 에러를 날카롭게 지적할 것. (서론/인사말 생략)
    2. **Solution (해결책)**: 코드를 근거로 어떤 기술이 문제를 해결하는지 명시.
    3. **Impact (효과)**: 정량적/정성적 기대 효과.
    
    **출력 형식 (Markdown):**
    
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
    with st.sidebar:
        st.header("🔴 Red Drive")
        st.caption(CURRENT_VERSION) # 버전 확인용 텍스트
        st.write("---")
        
        # 메뉴
        menu = st.radio("이동할 페이지", ["리소스 탐색", "관리자 모드"]) 

    # [페이지 1] 리소스 탐색
    if menu == "리소스 탐색":
        st.title("Red Drive | AI Resource Hub")
        st.write("레드사업실의 AI 도구와 데이터를 탐색하고 다운로드하세요.")
        st.divider()

        if 'resources_cache' not in st.session_state:
            st.session_state['resources_cache'] = load_resources_from_local()
        
        resources = st.session_state['resources_cache']
        
        # 검색
        col1, col2 = st.columns([8, 2])
        search = col1.text_input("검색", placeholder="키워드...", label_visibility="collapsed")
        if col2.button("🔄 새로고침"):
            del st.session_state['resources_cache']
            st.rerun()

        if search: resources = [r for r in resources if search.lower() in str(r).lower()]

        if not resources:
            st.info("등록된 리소스가 없습니다. 관리자 모드에서 파일을 등록해주세요.")

        for res in resources:
            # 카드 렌더링
            st.markdown(f"""
            <div class="resource-card">
                <span style="background:#E63946; color:white; padding:4px 10px; border-radius:10px; font-size:0.8em;">{res.get('category')}</span>
                <span style="color:#888; margin-left:10px; font-size:0.9em;">파일 {len(res.get('files', []))}개</span>
                <h3 style="margin-top:10px;">{res.get('title')}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 상세 내용
            with st.expander("📄 상세 보고서 및 파일 보기"):
                st.markdown(res.get('description'))
                # 파일 목록 출력
                if res.get('files'):
                    st.caption("포함된 파일:")
                    for f in res.get('files'):
                        st.code(f, language="bash")
                        
            # 다운로드 체크박스 대신 버튼 사용 고려 (단순화를 위해)
            # 여기서는 기존 체크박스 로직 유지하되 스타일 간소화

    # [페이지 2] 관리자 모드
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
                            with st.spinner("AI가 분석 중..."):
                                summary = ""
                                for f in files:
                                    try: summary += f"\nFile: {f.name}\n{f.getvalue().decode('utf-8')[:1000]}"
                                    except: summary += f"\nFile: {f.name} (Binary)"
                                desc = generate_pro_description(summary, hint)
                                meta = {"title":title, "category":cat, "description":desc, "files":[f.name for f in files]}
                                upload_to_local(folder_name=title, files=files, meta_data=meta)
                            st.success("등록 완료! 탐색 탭에서 확인하세요.")
                            del st.session_state['resources_cache']
                        else:
                            st.error("제목과 파일을 모두 입력해주세요.")

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

if __name__ == "__main__":
    main()
