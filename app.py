import streamlit as st
import os
import json
import shutil
import zipfile
import io
from openai import OpenAI

# --- 설정 ---
UPLOAD_DIR = "resources"  # 파일이 저장될 폴더
ADMIN_PASSWORD = "1234"   # 관리자 페이지 비밀번호 (원하는대로 변경)

# 페이지 기본 설정
st.set_page_config(page_title="AI 리소스 센터", layout="wide", page_icon="🚀")

# CSS로 디자인 다듬기 (카드 형태 스타일링)
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; }
    .resource-card {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 함수 정의 ---

# 1. 리소스 불러오기 함수
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
                    data = json.load(f)
                    data['id'] = item # 폴더명을 ID로 사용
                    resources.append(data)
    return resources

# 2. ZIP 생성 함수
def create_zip(selected_ids):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res_id in selected_ids:
            folder_path = os.path.join(UPLOAD_DIR, res_id)
            for root, _, files in os.walk(folder_path):
                for file in files:
                    # info.json 제외하고 압축하고 싶다면 조건 추가 가능
                    file_path = os.path.join(root, file)
                    arcname = os.path.join(res_id, file) # 압축 내 경로
                    zf.write(file_path, arcname)
    return zip_buffer.getvalue()

# 3. OpenAI 설명 생성 함수
def generate_description(file_names, user_input_hint):
    if not st.session_state.get('openai_api_key'):
        return "API 키가 없어 설명을 생성할 수 없습니다."
    
    client = OpenAI(api_key=st.session_state['openai_api_key'])
    
    prompt = f"""
    나는 AI 자동화 리소스를 공유하는 플랫폼을 운영중이야.
    다음 파일들을 포함하는 리소스에 대해 사용자가 쉽게 이해할 수 있는 2~3문장의 설명을 한국어로 작성해줘.
    
    포함된 파일 목록: {', '.join(file_names)}
    사용자 힌트: {user_input_hint}
    
    말투는 '~~하는 워크플로우입니다.', '~~파일입니다.' 처럼 정중하게 끝맺어줘.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- 메인 앱 로직 ---

def main_page():
    st.title("🚀 AI 활용 리소스 센터")
    st.markdown("업무 효율화를 위한 AI 워크플로우, 프롬프트, 데이터셋을 쉽게 찾고 다운로드하세요.")
    st.divider()

    # 사이드바 (검색 및 필터)
    with st.sidebar:
        st.header("🔍 검색 및 필터")
        search_query = st.text_input("검색어 입력", placeholder="예: 이메일, 자동화...")
        st.info("💡 팁: 여러 파일을 선택 후 하단의 '선택 다운로드'를 누르세요.")

    # 데이터 로드
    resources = load_resources()
    
    # 검색 필터링
    if search_query:
        resources = [r for r in resources if search_query.lower() in r['title'].lower() or search_query.lower() in r['description'].lower()]

    if not resources:
        st.warning("등록된 리소스가 없습니다. 관리자 페이지에서 업로드해주세요.")
        return

    # 선택 상태 관리
    if 'selected_resources' not in st.session_state:
        st.session_state['selected_resources'] = []

    # 전체 선택 기능
    col_all_1, col_all_2 = st.columns([1, 8])
    if col_all_1.button("전체 선택/해제"):
        if len(st.session_state['selected_resources']) == len(resources):
            st.session_state['selected_resources'] = []
        else:
            st.session_state['selected_resources'] = [r['id'] for r in resources]
            
    # 리소스 카드 출력 (Grid 레이아웃)
    cols = st.columns(2) # 2열로 배치
    
    for idx, res in enumerate(resources):
        with cols[idx % 2]:
            with st.container(border=True):
                # 상단: 태그 및 체크박스
                c1, c2 = st.columns([8, 1])
                c1.caption(f"📂 {res.get('category', 'General')} | 📄 파일 {len(res.get('files', []))}개")
                
                is_selected = res['id'] in st.session_state['selected_resources']
                if c2.checkbox("", key=f"chk_{res['id']}", value=is_selected):
                    if res['id'] not in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].append(res['id'])
                else:
                    if res['id'] in st.session_state['selected_resources']:
                        st.session_state['selected_resources'].remove(res['id'])

                # 내용
                st.subheader(res['title'])
                st.write(res['description'])
                
                # 포함된 파일 목록 (접기 기능)
                with st.expander("포함된 파일 보기"):
                    for f in res.get('files', []):
                        st.markdown(f"- `{f}`")
    
    # 하단 플로팅 다운로드 버튼 구역
    st.divider()
    if st.session_state['selected_resources']:
        st.success(f"{len(st.session_state['selected_resources'])}개 리소스가 선택되었습니다.")
        
        zip_data = create_zip(st.session_state['selected_resources'])
        st.download_button(
            label="📦 선택한 리소스 일괄 다운로드 (ZIP)",
            data=zip_data,
            file_name="selected_ai_resources.zip",
            mime="application/zip",
            use_container_width=True
        )

# --- 관리자 페이지 ---
def admin_page():
    st.title("🛠️ 리소스 업로드 (관리자)")
    
    # 간단한 보안
    pwd = st.text_input("비밀번호", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("비밀번호를 입력하세요.")
        return

    st.success("인증되었습니다.")
    
    # OpenAI API 키 입력 (세션에 저장)
    api_key = st.text_input("OpenAI API Key (AI 설명 생성용)", type="password")
    if api_key:
        st.session_state['openai_api_key'] = api_key

    with st.form("upload_form", clear_on_submit=True):
        st.subheader("새 리소스 등록")
        title = st.text_input("리소스 제목 (예: 이메일 자동 분류 봇)")
        category = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Other"])
        uploaded_files = st.file_uploader("관련 파일 모두 업로드", accept_multiple_files=True)
        user_hint = st.text_area("AI에게 줄 설명 힌트 (선택사항)", placeholder="이건 n8n으로 만든 봇이고 슬랙이랑 연동됨...")
        
        # AI 설명 생성 버튼
        generate_btn = st.form_submit_button("업로드 및 등록")
        
        if generate_btn and title and uploaded_files:
            # 1. 폴더 생성 (폴더명은 제목을 안전하게 변환)
            folder_name = "".join([c if c.isalnum() else "_" for c in title])
            target_dir = os.path.join(UPLOAD_DIR, folder_name)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            file_names = []
            for up_file in uploaded_files:
                file_path = os.path.join(target_dir, up_file.name)
                with open(file_path, "wb") as f:
                    f.write(up_file.getbuffer())
                file_names.append(up_file.name)
            
            # 2. AI 설명 생성
            description = "설명 없음"
            if st.session_state.get('openai_api_key'):
                with st.spinner("AI가 설명을 작성 중입니다..."):
                    try:
                        description = generate_description(file_names, user_hint)
                    except Exception as e:
                        st.error(f"AI 생성 실패: {e}")
            else:
                description = user_hint if user_hint else "설명이 입력되지 않았습니다."

            # 3. 메타데이터 저장
            meta_data = {
                "title": title,
                "category": category,
                "description": description,
                "files": file_names
            }
            
            with open(os.path.join(target_dir, "info.json"), "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=4)
                
            st.success(f"'{title}' 등록 완료! 파일 {len(file_names)}개 저장됨.")

# --- 앱 실행 라우터 ---
page = st.sidebar.radio("메뉴", ["리소스 탐색", "관리자 업로드"])

if page == "리소스 탐색":
    main_page()
else:
    admin_page()