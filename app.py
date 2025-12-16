import streamlit as st
import os
import json
import io
import zipfile
from github import Github
from openai import OpenAI

# --- 1. 설정 및 비밀키 로드 ---
try:
    # Streamlit Secrets에서 설정값을 가져옵니다.
    GITHUB_TOKEN = st.secrets["general"]["github_token"]
    REPO_NAME = st.secrets["general"]["repo_name"]
    OPENAI_API_KEY = st.secrets["general"].get("openai_api_key", None)
except Exception:
    st.error("🚨 설정 오류: Streamlit Secrets에 github_token과 repo_name이 설정되지 않았습니다.")
    st.stop()

# 관리자 비밀번호 (원하는대로 변경 가능)
ADMIN_PASSWORD = "1234"
UPLOAD_DIR = "resources" # GitHub 내에 저장될 폴더 이름

# 페이지 기본 설정
st.set_page_config(page_title="Red Drive", layout="wide", page_icon="🔴")

# --- 2. 디자인(CSS) 대폭 개선 (가독성 해결) ---
st.markdown("""
<style>
    /* 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: Pretendard, sans-serif; }
    
    /* 🔴 메인 타이틀 */
    .main-title { color: #E63946; font-weight: 800; font-size: 2.5rem; margin-bottom: 0.5rem; }
    .sub-title { color: #555; font-size: 1.1rem; margin-bottom: 2rem; }

    /* 🔍 입력창(Input) 스타일 강제 수정 (검은 배경에서 글씨 안 보이는 문제 해결) */
    .stTextInput input, .stTextArea textarea {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #ddd;
    }
    /* 검색창 라벨 색상 */
    .stTextInput label { color: #333 !important; font-weight: bold; }

    /* 📑 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #ffffff; border-radius: 8px;
        color: #495057; font-weight: 600; border: 1px solid #e9ecef;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stTabs [aria-selected="true"] {
        background-color: #E63946 !important; color: white !important; border: none;
    }

    /* 📦 리소스 카드 스타일 */
    .resource-card {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        border-radius: 15px; padding: 25px; margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); transition: transform 0.2s;
    }
    .resource-card:hover { transform: translateY(-3px); box-shadow: 0 8px 16px rgba(0,0,0,0.1); }
    .resource-card h3 { color: #E63946 !important; margin-top: 0; font-weight: 700; }
    .resource-card p { color: #444 !important; line-height: 1.6; }
    
    /* 📂 파일 목록 박스 */
    .file-box { background-color: #f8f9fa; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 0.9em; }

    /* 사이드바 스타일 */
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    section[data-testid="stSidebar"] * { color: #333 !important; }

    /* 버튼 스타일 */
    div.stButton > button { border-radius: 8px; font-weight: bold; }
    /* 빨간색 버튼 강조 */
    .primary-btn button { background-color: #E63946 !important; color: white !important; border: none; }
    .primary-btn button:hover { background-color: #d62828 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. GitHub 연동 및 기능 함수들 ---

def get_repo():
    """GitHub 저장소 연결"""
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def load_resources_from_github():
    """GitHub에서 리소스 목록 불러오기"""
    resources = []
    repo = get_repo()
    try:
        # resources 폴더의 내용물을 가져옵니다.
        contents = repo.get_contents(UPLOAD_DIR)
        for content in contents:
            if content.type == "dir":
                # info.json 파일 찾기
                try:
                    info_file = repo.get_contents(f"{content.path}/info.json")
                    # 한글 깨짐 방지를 위해 decode
                    info_data = json.loads(info_file.decoded_content.decode("utf-8"))
                    info_data['id'] = content.name
                    info_data['path'] = content.path
                    resources.append(info_data)
                except:
                    continue 
    except:
        return [] # 폴더가 없으면 빈 리스트
    # 최신순 정렬 (이름 기준 역순 등)
    return sorted(resources, key=lambda x: x.get('title', ''), reverse=True)

def upload_to_github(folder_name, files, meta_data):
    """파일과 메타데이터를 GitHub에 업로드"""
    repo = get_repo()
    base_path = f"{UPLOAD_DIR}/{folder_name}"
    
    # 1. 파일 업로드
    for file in files:
        file_content = file.getvalue()
        file_path = f"{base_path}/{file.name}"
        try:
            repo.create_file(file_path, f"Add {file.name}", file_content)
        except:
            # 파일이 이미 존재하면 업데이트(덮어쓰기)
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, f"Update {file.name}", file_content, contents.sha)
            
    # 2. info.json (설명 파일) 생성
    json_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
    json_path = f"{base_path}/info.json"
    try:
        repo.create_file(json_path, "Add info.json", json_content)
    except:
        contents = repo.get_contents(json_path)
        repo.update_file(contents.path, "Update info.json", json_content, contents.sha)

def delete_from_github(folder_path):
    """폴더 전체 삭제"""
    repo = get_repo()
    contents = repo.get_contents(folder_path)
    # 폴더 안의 파일들을 하나씩 삭제해야 폴더가 사라짐
    for content in contents:
        repo.delete_file(content.path, "Delete resource", content.sha)

def download_files_as_zip(selected_resources):
    """선택한 리소스들을 하나의 ZIP으로 압축 (info.json 제외)"""
    repo = get_repo()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in selected_resources:
            folder_path = res['path']
            contents = repo.get_contents(folder_path)
            for content in contents:
                # info.json은 다운로드 제외
                if content.name == "info.json": continue
                
                file_data = content.decoded_content
                # ZIP 안에 폴더 구조 없이 파일만 깔끔하게 넣기
                zf.writestr(content.name, file_data)
    return zip_buffer.getvalue()

def generate_pro_description(file_names, user_hint):
    """OpenAI를 이용한 고퀄리티 설명 생성"""
    if not OPENAI_API_KEY:
        return "💡 (API 키가 없어 자동 설명이 생성되지 않았습니다.)"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
    당신은 IT 전문 테크니컬 라이터입니다. 'Red Drive'에 업로드된 AI 자동화 리소스를 설명해야 합니다.
    
    - 파일 목록: {', '.join(file_names)}
    - 사용자 힌트: {user_hint}
    
    다음 마크다운 형식으로 상세하고 가독성 좋게 작성해주세요:
    
    ### 📝 개요
    (이 리소스가 무엇인지, 어떤 문제를 해결하는지 2문장 요약)
    
    ### ⚙️ 동작 원리 및 구성
    1. **파일명**: 역할 설명
    2. **파일명**: 역할 설명
    
    ### ✨ 기대 효과
    - (효과 1)
    - (효과 2)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 설명 생성 실패: {str(e)}"

# --- 4. 메인 화면 로직 ---

def main():
    st.sidebar.title("🔴 Red Drive")
    menu = st.sidebar.radio("메뉴", ["리소스 탐색", "관리자 모드"], label_visibility="collapsed")

    # [탭 1] 리소스 탐색 (메인 화면)
    if menu == "리소스 탐색":
        st.markdown('<div class="main-title">🔴 Red Drive <span style="font-size:0.5em; color:#bbb;">| AI Resource Hub</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">레드사업실의 AI 도구와 데이터를 영구적으로 아카이빙하고 공유합니다.</div>', unsafe_allow_html=True)
        st.divider()

        # 데이터 로드 (캐시 사용으로 속도 최적화)
        if 'resources_cache' not in st.session_state:
            with st.spinner("🔄 GitHub에서 최신 자료를 불러오는 중..."):
                st.session_state['resources_cache'] = load_resources_from_github()
        
        resources = st.session_state['resources_cache']
        
        # 검색 및 필터
        col_search, col_refresh = st.columns([8, 1])
        with col_search:
            search_query = st.text_input("🔍 리소스 검색 (제목, 내용)", placeholder="예: 회의록 요약, 프롬프트...")
        with col_refresh:
            st.write("") # 줄맞춤
            st.write("") 
            if st.button("🔄"):
                del st.session_state['resources_cache']
                st.rerun()

        if search_query:
            resources = [r for r in resources if search_query.lower() in str(r).lower()]

        if not resources:
            st.info("👋 등록된 리소스가 없습니다. 관리자 모드에서 첫 자료를 올려보세요!")
            return

        # 전체 선택 기능
        if 'selected_ids' not in st.session_state: st.session_state['selected_ids'] = []
        
        c_btn1, c_btn2, _ = st.columns([1.2, 1.2, 7])
        if c_btn1.button("✅ 전체 선택"):
            st.session_state['selected_ids'] = [r['id'] for r in resources]
            st.rerun()
        if c_btn2.button("❌ 선택 해제"):
            st.session_state['selected_ids'] = []
            st.rerun()

        # 리소스 카드 출력
        for res in resources:
            with st.container():
                st.markdown(f"""
                <div class="resource-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                        <span style="background-color:#ffe3e3; color:#E63946; padding:4px 12px; border-radius:20px; font-weight:bold; font-size:0.9em;">
                            {res.get('category', 'General')}
                        </span>
                        <span style="color:#999; font-size:0.9em;">파일 {len(res.get('files', []))}개</span>
                    </div>
                    <h3>{res.get('title')}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                # 내용 펼치기
                with st.expander("📖 상세 설명 및 파일 보기", expanded=False):
                    st.markdown(res.get('description', '설명 없음'))
                    st.markdown('<div class="file-box"><b>📂 포함된 파일:</b><br>' + '<br>'.join([f"- {f}" for f in res.get('files', [])]) + '</div>', unsafe_allow_html=True)
                
                # 선택 체크박스
                is_checked = res['id'] in st.session_state['selected_ids']
                if st.checkbox(f"📥 '{res['title']}' 다운로드 담기", value=is_checked, key=res['id']):
                    if res['id'] not in st.session_state['selected_ids']:
                        st.session_state['selected_ids'].append(res['id'])
                        st.rerun()
                else:
                    if res['id'] in st.session_state['selected_ids']:
                        st.session_state['selected_ids'].remove(res['id'])
                        st.rerun()

        # 하단 플로팅 다운로드 버튼
        if st.session_state['selected_ids']:
            st.markdown("---")
            st.success(f"총 {len(st.session_state['selected_ids'])}개의 리소스가 선택되었습니다.")
            
            selected_objs = [r for r in resources if r['id'] in st.session_state['selected_ids']]
            if st.button("📦 선택한 리소스 일괄 다운로드 (ZIP)", type="primary", use_container_width=True):
                with st.spinner("📦 GitHub에서 파일을 받아 압축하고 있습니다..."):
                    zip_data = download_files_as_zip(selected_objs)
                    st.download_button(
                        label="⬇️ ZIP 파일 내 컴퓨터에 저장하기",
                        data=zip_data,
                        file_name="RedDrive_Resources.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

    # [탭 2] 관리자 모드
    else:
        st.title("🛠️ 관리자 모드")
        
        # 간단 로그인
        if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False
        if not st.session_state['is_admin']:
            pwd = st.text_input("관리자 비밀번호", type="password")
            if st.button("로그인"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state['is_admin'] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 틀렸습니다.")
            return

        st.info(f"✅ GitHub 저장소({REPO_NAME})와 연동되어 있습니다.")

        tab1, tab2 = st.tabs(["📤 신규 업로드", "🗑️ 자료 삭제"])

        # 신규 업로드 탭
        with tab1:
            with st.form("upload_form", clear_on_submit=True):
                st.subheader("새로운 리소스 등록")
                title = st.text_input("제목 (한글 가능)")
                category = st.selectbox("카테고리", ["Workflow", "Prompt", "Data", "Report", "Tool"])
                files = st.file_uploader("관련 파일 업로드 (여러 개 가능)", accept_multiple_files=True)
                hint = st.text_area("AI에게 줄 힌트 (동작 원리 등을 간략히 적어주세요)", height=100)
                
                if st.form_submit_button("🚀 GitHub에 업로드 및 등록"):
                    if title and files:
                        # 1. AI 설명 생성
                        with st.spinner("🤖 AI가 고퀄리티 설명을 작성 중입니다..."):
                            f_names = [f.name for f in files]
                            desc = generate_pro_description(f_names, hint)
                        
                        # 2. GitHub 업로드
                        with st.spinner("☁️ GitHub 서버로 파일을 전송 중입니다..."):
                            folder_name = "".join([c if c.isalnum() else "_" for c in title]) + "_" + os.urandom(4).hex()
                            meta = {"title": title, "category": category, "description": desc, "files": f_names}
                            upload_to_github(folder_name, files, meta)
                            
                        st.balloons()
                        st.success("완료! 안전하게 저장되었습니다.")
                        if 'resources_cache' in st.session_state: del st.session_state['resources_cache'] # 캐시 초기화
                    else:
                        st.warning("제목과 파일을 모두 입력해주세요.")

        # 삭제 탭
        with tab2:
            st.warning("⚠️ 여기서 삭제하면 복구할 수 없습니다.")
            
            # 리소스 새로고침 버튼
            if st.button("목록 새로고침"):
                st.session_state['resources_cache'] = load_resources_from_github()
                
            resources = st.session_state.get('resources_cache', [])
            
            if resources:
                target_title = st.selectbox("삭제할 리소스 선택", [r['title'] for r in resources])
                if st.button("🔥 영구 삭제하기", type="primary"):
                    target_obj = next((r for r in resources if r['title'] == target_title), None)
                    if target_obj:
                        with st.spinner("GitHub에서 삭제 중..."):
                            delete_from_github(target_obj['path'])
                        st.success("삭제되었습니다.")
                        del st.session_state['resources_cache']
                        st.rerun()

if __name__ == "__main__":
    main()
