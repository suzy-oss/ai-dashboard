import streamlit as st
import os
import json
import shutil
import zipfile
import io
from openai import OpenAI

# --- 설정 ---
UPLOAD_DIR = "resources"
ADMIN_PASSWORD = "1234"

# 페이지 기본 설정
st.set_page_config(
    page_title="Red Drive - AI 리소스 센터",
    layout="wide",
    page_icon="🔴",
    initial_sidebar_state="expanded"
)

# --- 디자인(CSS) 수정: 글씨 가독성 및 탭 스타일 ---
st.markdown("""
<style>
    /* 폰트 설정 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: Pretendard, sans-serif;
    }
    
    /* 메인 타이틀 레드 컬러 */
    .main-title {
        color: #E63946; 
        font-weight: 800;
    }
    
    /* 사이드바 및 카드 글씨색 강제 지정 (다크모드 대응) */
    section[data-testid="stSidebar"] * {
        color: #333333 !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    .resource-card-container {
        background-color: #ffffff;
        color: #333333;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .resource-card-container * {
        color: #333333 !important;
    }
    
    /* 버튼 스타일 */
    div[data-testid="stForm"] button, div[data-testid="column"] button {
        background-color: #E63946;
        color: white !important;
        border: none;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #C1121F;
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        border-bottom: 2px solid #E63946;
        color: #E63946;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 함수 정의 ---
def load_resources():
    resources = []
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    for item in os.listdir(UPLOAD_DIR):
        item_path = os.path.join(UPLOAD_DIR, item)
        if os.path.isdir(item_path):
            info_path = os.path.join(item_path, "info.json")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        data['id'] = item # 폴더명을 ID로 사용
                        resources.append(data)
                    except json.JSONDecodeError:
                        continue
    # 최신순 정렬 (폴더 생성 시간 기준 등, 여기선 단순 로드 순서)
    return sorted(resources, key=lambda x: x.get('title', ''))

def create_zip(selected_ids):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res_id in selected_ids:
            folder_path = os.path.join(UPLOAD_DIR, res_id)
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join(res_id, file)
                    zf.write(file_path, arcname)
    return zip_buffer.getvalue()

def generate_description(file_names, user_input_hint):
    if not st.session_state.get('openai_api_key'):
        return "💡 API 키가 입력되지 않아 자동 설명이 생성되지 않았습니다."
    
    client = OpenAI(api_key=st.session_state['openai_api_key'])
    prompt = f"""
    'Red Drive' 플랫폼 자료 설명.
    파일 목록: {', '.join(file_names)}
    힌트: {user_input_hint}
    이해하기 쉽고 전문적인 한국어로 2~3문장 설명 작성.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"설명 생성 실패: {str(e)}"

# --- 메인 페이지 ---
def main_page():
    st.markdown('<h1 class="main-title">🔴 Red Drive <span style="font-size:0.6em; color:#bbb;">| AI 리소스 센터</span></h1>', unsafe_allow_html=True)
    st.markdown("우리 레드사업실의 업무 효율을 높여줄 AI 도구와 데이터를 이곳에서 공유하고 활용하세요!")
    st.divider()

    with st.sidebar:
        st.header("🔍 검색 및 필터")
        search_query = st.text_input("검색어 입력", placeholder="예: 이메일...")
        
    resources = load_resources()
    if search_query:
        resources = [r for r in resources if search_query.lower() in r.get('title','').lower() or search_query.lower() in r.get('description','').lower()]

    if not resources:
        st.info("👋 등록된 리소스가 없습니다. 관리자 페이지에서 자료를 업로드해주세요.")
        return

    if 'selected_resources' not in st.session_state:
        st.session_state['selected_resources'] = []

    if st.button("전체 선택/해제"):
        if len(st.session_state['selected_resources']) == len(resources):
            st.session_state['selected_resources'] = []
        else:
            st.session_state['selected_resources'] = [r['id'] for r in resources]
            
    cols = st.columns(2)
    for idx, res in enumerate(resources):
        with cols[idx % 2]:
            with st.container():
                st.markdown(f"""
                <div class="resource-card-container">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:blue; font-weight:bold;">[{res.get('category', 'General')}]</span>
                        <span style="color:#666;">📄 파일 {len(res.get('files', []))}개</span>
                    </div>
                    <h3 style="margin-top:10px; color:#333 !important;">{res.get('title', '제목 없음')}</h3>
                    <p style="color:#333 !important;">{res.get('description', '설명 없음')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([0.1, 0.9])
                is_selected = res['id'] in st.session_state['selected_resources']
                if st.checkbox(f"선택: {res['title']}", key=f"chk_{res['id']}", value=is_selected):
                    if res['id'] not in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].append(res['id'])
                else:
                    if res['id'] in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].remove(res['id'])
                
                with st.expander("👉 파일 목록 보기"):
                    for f in res.get('files', []):
                        st.text(f"- {f}")

    st.divider()
    if st.session_state['selected_resources']:
        st.success(f"✅ {len(st.session_state['selected_resources'])}개 리소스 선택됨")
        zip_data = create_zip(st.session_state['selected_resources'])
        st.download_button("📦 선택한 리소스 일괄 다운로드 (ZIP)", zip_data, "RedDrive.zip", "application/zip", use_container_width=True)

# --- 관리자 페이지 (수정/삭제 추가됨) ---
def admin_page():
    st.title("🛠️ 리소스 관리자")
    pwd = st.text_input("비밀번호", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("🔒 비밀번호를 입력하세요.")
        return

    st.success("인증 완료")
    api_key = st.text_input("OpenAI API Key (자동 설명용)", type="password")
    if api_key: st.session_state['openai_api_key'] = api_key

    # 탭으로 기능 분리
    tab1, tab2 = st.tabs(["📤 신규 등록", "✏️ 수정 및 삭제"])

    # 1. 신규 등록 탭
    with tab1:
        with st.form("upload_form", clear_on_submit=True):
            st.subheader("새 리소스 등록")
            title = st.text_input("제목")
            category = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Etc"])
            files = st.file_uploader("파일 업로드", accept_multiple_files=True)
            hint = st.text_area("AI 힌트")
            
            if st.form_submit_button("🚀 업로드"):
                if title and files:
                    folder = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                    path = os.path.join(UPLOAD_DIR, folder)
                    os.makedirs(path, exist_ok=True)
                    f_names = []
                    for f in files:
                        with open(os.path.join(path, f.name), "wb") as wb: wb.write(f.getbuffer())
                        f_names.append(f.name)
                    
                    with st.spinner("설명 생성 중..."):
                        desc = generate_description(f_names, hint)
                    
                    with open(os.path.join(path, "info.json"), "w", encoding="utf-8") as jf:
                        json.dump({"title":title, "category":category, "description":desc, "files":f_names}, jf, ensure_ascii=False)
                    st.success("등록 완료!")

    # 2. 수정 및 삭제 탭
    with tab2:
        resources = load_resources()
        if not resources:
            st.info("수정할 리소스가 없습니다.")
        else:
            st.subheader("기존 리소스 관리")
            # 선택 박스
            resource_titles = {f"{r['title']} ({r['id'][:8]}...)": r for r in resources}
            selected_option = st.selectbox("관리할 리소스 선택", list(resource_titles.keys()))
            
            if selected_option:
                target_res = resource_titles[selected_option]
                target_path = os.path.join(UPLOAD_DIR, target_res['id'])
                
                # 수정 폼
                with st.form("edit_form"):
                    st.markdown(f"**'{target_res['title']}' 수정하기**")
                    new_title = st.text_input("제목 수정", value=target_res['title'])
                    
                    cat_idx = ["Workflow", "Prompt", "Data", "Etc"].index(target_res.get('category', 'Etc')) if target_res.get('category', 'Etc') in ["Workflow", "Prompt", "Data", "Etc"] else 3
                    new_category = st.selectbox("카테고리 수정", ["Workflow", "Prompt", "Data", "Etc"], index=cat_idx)
                    
                    new_desc = st.text_area("설명 수정", value=target_res['description'])
                    
                    # 파일 관리
                    st.markdown("---")
                    st.markdown("**📂 파일 관리**")
                    
                    # 기존 파일 삭제 선택
                    existing_files = target_res.get('files', [])
                    files_to_remove = []
                    if existing_files:
                        st.caption("삭제할 파일을 체크하세요:")
                        cols_del = st.columns(2)
                        for idx, f_name in enumerate(existing_files):
                            if cols_del[idx%2].checkbox(f"🗑️ {f_name} 삭제", key=f"del_{target_res['id']}_{f_name}"):
                                files_to_remove.append(f_name)
                    
                    # 새 파일 추가
                    new_files = st.file_uploader("추가할 파일이 있다면 선택", accept_multiple_files=True)
                    
                    if st.form_submit_button("💾 수정사항 저장"):
                        # 1. 파일 삭제 처리
                        for rm_f in files_to_remove:
                            full_rm_path = os.path.join(target_path, rm_f)
                            if os.path.exists(full_rm_path):
                                os.remove(full_rm_path)
                        
                        # 2. 새 파일 저장 처리
                        current_files = [f for f in existing_files if f not in files_to_remove]
                        if new_files:
                            for nf in new_files:
                                with open(os.path.join(target_path, nf.name), "wb") as wb:
                                    wb.write(nf.getbuffer())
                                current_files.append(nf.name)
                        
                        # 3. JSON 업데이트
                        updated_meta = {
                            "title": new_title,
                            "category": new_category,
                            "description": new_desc,
                            "files": current_files
                        }
                        with open(os.path.join(target_path, "info.json"), "w", encoding="utf-8") as jf:
                            json.dump(updated_meta, jf, ensure_ascii=False, indent=4)
                            
                        st.success("수정이 완료되었습니다! (새로고침하면 반영됩니다)")
                        st.rerun()

                # 삭제 버튼 (위험하므로 폼 밖으로 분리)
                st.markdown("---")
                st.markdown("**🚨 위험 구역**")
                col_del_btn, _ = st.columns([1, 4])
                if col_del_btn.button("🔥 이 리소스 영구 삭제", type="primary", use_container_width=True):
                    shutil.rmtree(target_path)
                    st.warning(f"'{target_res['title']}' 리소스가 삭제되었습니다.")
                    st.rerun()

# --- 실행 ---
st.sidebar.title("🔴 Red Drive")
page = st.sidebar.radio("메뉴", ["리소스 탐색", "관리자 업로드"])
if page == "리소스 탐색": main_page()
else: admin_page()
