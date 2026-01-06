import streamlit as st
import os
import io
import base64
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# --- 1. 初期設定 ---
load_dotenv()

# レイアウト設定を最初に行う
st.set_page_config(page_title="SNS投稿作成プロ", page_icon="📝", layout="wide")

def get_secret(key_name):
    # secrets.tomlがあれば優先、なければ.env
    try:
        if key_name in st.secrets:
            return st.secrets[key_name]
    except:
        pass
    return os.getenv(key_name)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
FOLDER_ID = get_secret("FOLDER_ID")
APP_PASSWORD = get_secret("APP_PASSWORD")

# --- 2. パスワード認証機能 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("🔒 認証が必要です")
    user_pass = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if user_pass == APP_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません")
    st.stop()

# --- 3. メインコンテンツ（認証成功後） ---
st.title("📝 マルチ教室対応 SNS投稿作成プロ")

# --- サイドバー：設定 ---
st.sidebar.header("⚙️ 設定・カスタマイズ")

default_hashtags = "#ボクシング教室 #ボクササイズ #大人の習い事 #運動不足解消 #ストレス発散"
fixed_hashtags = st.sidebar.text_area("必ず入れるハッシュタグ", default_hashtags, height=100)

try:
    with open('past_posts.txt', 'r', encoding='utf-8') as f:
        current_past_posts = f.read()
except FileNotFoundError:
    current_past_posts = "親しみやすいトーンで作成してください。"

new_past_posts = st.sidebar.text_area("AIへの指示・過去の投稿例", current_past_posts, height=300)

if st.sidebar.button("設定を保存する"):
    with open('past_posts.txt', 'w', encoding='utf-8') as f:
        f.write(new_past_posts)
    st.sidebar.success("設定を保存しました！")

# --- Googleドライブ接続関数 ---
def get_drive_service():
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

# --- メインレイアウト ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. 画像の取得")
    if st.button('📸 ドライブから最新画像を取得'):
        try:
            with st.spinner('画像を読み込み中...'):
                service = get_drive_service()
                query = f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed = false"
                results = service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
                items = results.get('files', [])

                if not items:
                    st.error("❌ 画像が見つかりませんでした。")
                else:
                    st.session_state['img_name'] = items[0]['name']
                    request = service.files().get_media(fileId=items[0]['id'])
                    st.session_state['img_data'] = request.execute()
                    st.success(f"取得済み: {st.session_state['img_name']}")
        except Exception as e:
            st.error(f"エラー: {e}")

    if 'img_data' in st.session_state:
        st.image(st.session_state['img_data'], caption="投稿予定の画像", use_container_width=True)

with col2:
    st.header("2. AI文章作成")
    if st.button('🤖 文章を1つ作成する'):
        if 'img_data' not in st.session_state:
            st.warning("先に画像を取得してください。")
        else:
            try:
                with st.spinner('AIが思考中...'):
                    base64_image = base64.b64encode(st.session_state['img_data']).decode('utf-8')
                    # あなたの環境で動作確認済みの Gemini 3 を使用
                    model_id = "gemini-3-flash-preview"
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                    
                    # 💡 指示を厳格化：1案のみ、余計な挨拶や見出しを禁止
                    prompt = f"""
                    画像の内容を分析し、Instagram用の投稿文章を【1つだけ】作成してください。
                    「パターン1」などの見出し、導入文、解説、挨拶などは一切不要です。
                    そのままコピーして投稿できる本文のみを出力してください。
                    
                    【AIへの指示/過去の投稿例】
                    {new_past_posts}
                    
                    【必須ハッシュタグ】
                    {fixed_hashtags}
                    
                    ※文章の最後に必ず上記のハッシュタグを含めてください。
                    """

                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "image/png", "data": base64_image}}
                            ]
                        }]
                    }

                    response = requests.post(url, json=payload)
                    res_json = response.json()
                    st.session_state['generated_text'] = res_json['candidates'][0]['content']['parts'][0]['text']

            except Exception as e:
                st.error(f"AIエラー: {e}")

    if 'generated_text' in st.session_state:
        st.success("✨ 完成しました！")
        
        # 📋 投稿文（テキストエリアの右上にあるアイコンでコピー可能）
        st.subheader("📋 投稿文（コピー用）")
        st.text_area("そのままインスタに貼り付けられます", st.session_state['generated_text'], height=300)
        
        # 🖨️ PDF印刷用セクション
        st.subheader("🖨️ PDF出力・印刷")
        with st.expander("📄 印刷用プレビューを表示"):
            st.write("--- 投稿確認シート ---")
            st.image(st.session_state['img_data'], width=300)
            st.info(st.session_state['generated_text'])
            st.warning("このプレビューを開いた状態で、キーボードの [Ctrl + P] を押し、保存先を「PDFに保存」にしてください。")
            
        st.markdown(f"### [👉 Instagramを開く](https://www.instagram.com/)")