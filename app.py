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

# 페이지 설정
st.set_page_config(
    page_title="Red Drive - AI 리소스 센터",
    layout="wide",
    page_icon="🔴",
    initial_sidebar_state="expanded"
)

# --- 디자인(CSS) 업그레이드 ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: Pretendard, sans-serif;
    }
    
    /* 타이틀 스타일 */
    .main-title { color: #E63946; font-weight: 800; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    
    /* 탭(Tab) 스타일 개선 - 가독성 확보 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #f1f3f5;
        border-radius: 5px;
        color: #495057;
        font-weight: 600;
        border: 1px solid #ddd;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E63946 !important;
        color: white !important;
        border: none;
    }
    
    /* 사이드바 & 카드 글씨색 강제 (다크모드 방지) */
    section[data-testid="stSidebar"] { background-color: #f8f9fa; }
    section[data-testid="stSidebar"] * { color: #333333 !important; }
    
    .resource-card-container {
        background-color: #ffffff;
        color: #333333;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .resource-card-container * { color: #333333 !important; }
    
    /* 버튼 스타일 */
    .stButton > button { border-radius: 8px; font-weight: bold; border:none; }
    /* 주요 버튼 (빨강) */
    div[data-testid="stForm"] button, .primary-btn button {
        background-color: #E63946; color: white !important;
    }
    div[data-testid="stForm"] button:hover, .primary-btn button:hover {
        background-color: #C1121F;
    }
</style>
""", unsafe_allow_html=True)

# --- 함수 정의 ---
def load_resources():
    resources = []
    if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)
    for item in os.listdir(UPLOAD_DIR):
        item_path = os.path.join(UPLOAD_DIR, item)
        if os.path.isdir(item_path):
            info_path = os.path.join(item_path, "info.json")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        data['id'] = item
                        resources.append(data)
                    except: continue
    return sorted(resources, key=lambda x: x.get('title', ''))

def create_zip(selected_ids):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res_id in selected_ids:
            folder_path = os.path.join(UPLOAD_DIR, res_id)
            for root, _, files in os.walk(folder_path):
                for file in files:
                    # info.json은 다운로드에서 제외!
                    if file == "info.json":
                        continue
                    file_path = os.path.join(root, file)
                    arcname = file  # 폴더 없이 파일만 깔끔하게 압축
                    zf.write(file_path, arcname)
    return zip_buffer.getvalue()

def generate_description(file_names, user_input_hint):
    if not st.session_state.get('openai_api_key'):
        return "💡 (API 키가 없어 자동 설명이 생략되었습니다. 관리자가 직접 수정해주세요.)"
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
        return f"오류: {str(e)}"

# --- 메인 페이지 (탐색) ---
def main_page():
    st.markdown('<h1 class="main-title">🔴 Red Drive <span style="font-size:0.6em; color:#bbb;">| AI 리소스 센터</span></h1>', unsafe_allow_html=True)
    st.markdown("우리 레드사업실의 업무 효율을 높여줄 AI 도구와 데이터를 공유합니다.")
    st.divider()

    with st.sidebar:
        st.header("🔍 검색 및 필터")
        search_query = st.text_input("검색어 입력", placeholder="예: 회의록, 이메일...")
        
    resources = load_resources()
    if search_query:
        resources = [r for r in resources if search_query.lower() in r.get('title','').lower() or search_query.lower() in r.get('description','').lower()]

    if not resources:
        st.info("👋 등록된 리소스가 없습니다. 관리자 페이지에서 자료를 업로드해주세요.")
        return

    # 세션 상태 초기화
    if 'selected_resources' not in st.session_state:
        st.session_state['selected_resources'] = []

    # 전체 선택 / 해제 버튼 (버그 수정됨)
    c_btn1, c_btn2, _ = st.columns([1, 1, 6])
    if c_btn1.button("✅ 전체 선택"):
        st.session_state['selected_resources'] = [r['id'] for r in resources]
        st.rerun()
    if c_btn2.button("❌ 선택 해제"):
        st.session_state['selected_resources'] = []
        st.rerun()
            
    # 카드 리스트 출력
    cols = st.columns(2)
    for idx, res in enumerate(resources):
        with cols[idx % 2]:
            with st.container():
                st.markdown(f"""
                <div class="resource-card-container">
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                        <span style="color:#E63946; font-weight:bold; background:#fff5f5; padding:2px 8px; border-radius:4px;">{res.get('category', 'General')}</span>
                        <span style="color:#868e96; font-size:0.9em;">파일 {len(res.get('files', []))}개</span>
                    </div>
                    <h3 style="margin:0 0 10px 0; color:#333 !important;">{res.get('title', '제목 없음')}</h3>
                    <p style="color:#555 !important; line-height:1.5;">{res.get('description', '설명 없음')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([0.1, 0.9])
                is_selected = res['id'] in st.session_state['selected_resources']
                
                # 체크박스 로직
                if st.checkbox(f" '{res['title']}' 선택", key=f"chk_{res['id']}", value=is_selected):
                    if res['id'] not in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].append(res['id'])
                else:
                    if res['id'] in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].remove(res['id'])
                
                with st.expander("📄 포함된 파일 목록"):
                    for f in res.get('files', []):
                        st.text(f"- {f}")

    st.divider()
    # 다운로드 구역
    if st.session_state['selected_resources']:
        st.success(f"✅ 총 {len(st.session_state['selected_resources'])}개의 리소스가 선택되었습니다.")
        zip_data = create_zip(st.session_state['selected_resources'])
        # 버튼에 CSS 클래스 부여를 위한 빈 컨테이너 사용
        st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
        st.download_button(
            label="📦 선택한 리소스 일괄 다운로드 (ZIP)",
            data=zip_data,
            file_name="RedDrive_Resources.zip",
            mime="application/zip",
            use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

# --- 관리자 페이지 (가이드 추가됨) ---
def admin_page():
    st.title("🛠️ 리소스 관리자")
    
    # 1. 로그인
    if 'is_admin' not in st.session_state:
        st.session_state['is_admin'] = False
        
    if not st.session_state['is_admin']:
        pwd = st.text_input("관리자 비밀번호를 입력하세요", type="password")
        if st.button("로그인"):
            if pwd == ADMIN_PASSWORD:
                st.session_state['is_admin'] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        return

    # 2. 로그인 성공 후 화면
    st.info("🔓 관리자 모드입니다.")
    api_key = st.text_input("OpenAI API Key (자동 설명용)", type="password", placeholder="sk-...")
    if api_key: st.session_state['openai_api_key'] = api_key

    # 친절한 사용 가이드 (접었다 폈다 가능)
    with st.expander("ℹ️ 사용 가이드 (처음 오셨나요?)", expanded=False):
        st.markdown("""
        ### 1️⃣ 신규 등록 방법
        1. **'📤 신규 등록'** 탭을 클릭하세요.
        2. **제목**과 **카테고리**를 입력하세요.
        3. 파일을 드래그해서 넣으세요. (여러 개 가능)
        4. (선택) AI에게 힌트를 주면 설명을 더 잘 써줍니다.
        5. **'업로드'** 버튼을 누르면 끝!
        
        ### 2️⃣ 수정 및 삭제 방법
        1. **'✏️ 수정 및 삭제'** 탭을 클릭하세요.
        2. 목록에서 고치고 싶은 리소스를 선택하세요.
        3. 오타를 수정하거나 파일을 추가/삭제하고 **'저장'**을 누르세요.
        4. 지우고 싶으면 맨 아래 빨간색 **'삭제'** 버튼을 누르세요.
        """)
    
    st.write("") # 여백

    # 탭 디자인
    tab1, tab2 = st.tabs(["📤 신규 등록", "✏️ 수정 및 삭제"])

    # [탭 1] 신규 등록
    with tab1:
        with st.form("upload_form", clear_on_submit=True):
            st.subheader("새 리소스 등록")
            title = st.text_input("리소스 제목", placeholder="예: 주간 업무 요약 봇")
            col_cat, col_empty = st.columns(2)
            category = col_cat.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Etc"])
            
            files = st.file_uploader("파일 업로드 (여기에 드래그)", accept_multiple_files=True)
            hint = st.text_area("AI 힌트 (선택사항)", placeholder="이 파일은 ~하는 역할을 합니다.")
            
            if st.form_submit_button("🚀 업로드 및 등록"):
                if title and files:
                    folder = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                    path = os.path.join(UPLOAD_DIR, folder)
                    os.makedirs(path, exist_ok=True)
                    f_names = []
                    for f in files:
                        with open(os.path.join(path, f.name), "wb") as wb: wb.write(f.getbuffer())
                        f_names.append(f.name)
                    
                    with st.spinner("🤖 AI가 설명을 작성 중입니다..."):
                        desc = generate_description(f_names, hint)
                    
                    with open(os.path.join(path, "info.json"), "w", encoding="utf-8") as jf:
                        json.dump({"title":title, "category":category, "description":desc, "files":f_names}, jf, ensure_ascii=False)
                    st.success("✅ 등록 완료!")
                else:
                    st.warning("제목과 파일을 모두 입력해주세요.")

    # [탭 2] 수정 및 삭제
    with tab2:
        resources = load_resources()
        if not resources:
            st.info("수정할 리소스가 없습니다.")
        else:
            st.subheader("기존 리소스 관리")
            # 선택 박스
            resource_titles = {f"{r['title']}": r for r in resources}
            selected_option = st.selectbox("관리할 리소스 선택", list(resource_titles.keys()))
            
            if selected_option:
                target_res = resource_titles[selected_option]
                target_path = os.path.join(UPLOAD_DIR, target_res['id'])
                
                # 수정 폼
                with st.form("edit_form"):
                    st.markdown(f"**Editing: {target_res['title']}**")
                    new_title = st.text_input("제목 수정", value=target_res['title'])
                    
                    # 카테고리 인덱스 찾기
                    cats = ["Workflow", "Prompt", "Data", "Etc"]
                    try: 
                        c_idx = cats.index(target_res.get('category'))
                    except: 
                        c_idx = 3
                    new_category = st.selectbox("카테고리 수정", cats, index=c_idx)
                    
                    new_desc = st.text_area("설명 수정", value=target_res['description'], height=150)
                    
                    st.markdown("---")
                    st.markdown("**📂 파일 관리**")
                    
                    # 기존 파일 삭제 체크박스
                    existing_files = target_res.get('files', [])
                    files_to_remove = []
                    if existing_files:
                        st.caption("삭제할 파일 선택:")
                        cols_del = st.columns(3)
                        for idx, f_name in enumerate(existing_files):
                            if cols_del[idx%3].checkbox(f"🗑️ {f_name}", key=f"del_{target_res['id']}_{f_name}"):
                                files_to_remove.append(f_name)
                    
                    new_files = st.file_uploader("추가 파일 업로드", accept_multiple_files=True)
                    
                    if st.form_submit_button("💾 수정사항 저장"):
                        # 파일 삭제
                        for rm_f in files_to_remove:
                            p = os.path.join(target_path, rm_f)
                            if os.path.exists(p): os.remove(p)
                        
                        # 파일 추가
                        current_files = [f for f in existing_files if f not in files_to_remove]
                        if new_files:
                            for nf in new_files:
                                with open(os.path.join(target_path, nf.name), "wb") as wb:
                                    wb.write(nf.getbuffer())
                                current_files.append(nf.name)
                        
                        # JSON 업데이트
                        updated_meta = {
                            "title": new_title, "category": new_category,
                            "description": new_desc, "files": current_files
                        }
                        with open(os.path.join(target_path, "info.json"), "w", encoding="utf-8") as jf:
                            json.dump(updated_meta, jf, ensure_ascii=False, indent=4)
                        
                        st.success("수정 완료!")
                        st.rerun()

                # 삭제 구역 (위험)
                st.write("")
                st.markdown("##### 🚨 위험 구역")
                col_del_1, col_del_2 = st.columns([1, 4])
                if col_del_1.button("🔥 리소스 삭제", type="primary"):
                    shutil.rmtree(target_path)
                    st.warning("삭제되었습니다.")
                    st.rerun()

# --- 실행 ---
st.sidebar.title("🔴 Red Drive")
page = st.sidebar.radio("메뉴", ["리소스 탐색", "관리자 모드"], label_visibility="collapsed")

if page == "리소스 탐색": main_page()
else: admin_page()
