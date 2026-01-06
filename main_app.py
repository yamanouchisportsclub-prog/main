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

# 1. 環境変数の読み込み
load_dotenv()
FOLDER_ID = os.getenv("FOLDER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

def main():
    try:
        service = get_drive_service()
        query = f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed = false"
        results = service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print("❌ 画像が見つかりませんでした。")
            return

        print(f"✅ 画像を取得: {items[0]['name']}")

        request = service.files().get_media(fileId=items[0]['id'])
        img_data = request.execute()
        base64_image = base64.b64encode(img_data).decode('utf-8')
        
        try:
            with open('past_posts.txt', 'r', encoding='utf-8') as f:
                past_posts = f.read()
        except FileNotFoundError:
            past_posts = "親しみやすいトーンで作成してください。"

        print("🤖 AI分析中（Gemini 3 Flash を使用）...")

        # 【ここが重要！】リストにあった最新モデル名を指定
        # v1beta を使用します
        model_id = "gemini-3-flash-preview"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
        
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"画像の内容を分析し、以下の過去例を参考にInstagram用の文章を作成してください。\n\n【過去例】\n{past_posts}"},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64_image
                        }
                    }
                ]
            }]
        }

        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()

        if response.status_code == 200:
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            print("\n" + "="*40)
            print("✨ ついに完成！ Instagram投稿文 ✨")
            print("="*40)
            print(text)
            print("="*40)
        else:
            print(f"❌ APIエラー: {res_json}")

    except Exception as e:
        print(f"❌ システムエラー: {e}")

if __name__ == "__main__":
    main()