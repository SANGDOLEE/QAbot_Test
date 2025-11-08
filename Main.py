# --------------------------
#  🔧 환경 설정 및 초기화
# --------------------------
import os  # .env 환경 변수 로드용
import requests  # Notion API 호출
import datetime  # 오늘 날짜 계산
import pytz  # 한국 시간대(KST) 설정

from dotenv import load_dotenv
from slack_bolt import App  # Slack 봇 앱
from slack_bolt.adapter.socket_mode import SocketModeHandler  # Socket Mode 연결
from apscheduler.schedulers.background import BackgroundScheduler  # 자동 스케줄러

from rotation_data import NAME_TO_SLACK_ID  # 이름 → Slack ID 매핑 테이블

# --------------------------
#  🧩 .env 환경 변수 로드
# --------------------------
load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

# --------------------------
#  🤖 Slack 앱 초기화
# --------------------------
app = App(token=SLACK_BOT_TOKEN)

# 타임존 설정 (한국)
KST = pytz.timezone("Asia/Seoul")

# 스케줄러 객체 생성
scheduler = BackgroundScheduler(timezone=KST)

# --------------------------
#  📅 매주 QA Master 공지 메시지 전송
# --------------------------
def post_weekly_qm_message():
    """
    노션에서 이번 주 담당자를 조회해
    Slack 채널에 QA Master 안내 메시지를 전송한다.
    """
    ios_qm_id, android_qm_id = fetch_qm_from_notion_for_today()

    ios_mention = f"<@{ios_qm_id}>" if ios_qm_id else ""
    android_mention = f"<@{android_qm_id}>" if android_qm_id else ""

    app.client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text="금주 QA Master 안내드립니다.",  # 푸시 알림 / 접근성용 fallback 텍스트
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "📋 금주 QA Master 안내드립니다.\n"
                        "Android 큐마는 릴리즈 플래닝을 작성해주세요.\n\n"
                        f"• *iOS 큐마:* {ios_mention}\n"
                        f"• *Android 큐마:* {android_mention}\n"
                    )
                }
            }
        ],
    )

# --------------------------
#  ⏰ 스케줄러 설정
# --------------------------
def setup_scheduler():
    """
    매주 특정 요일/시간에 post_weekly_qm_message() 자동 실행.
    현재 설정: 매주 금요일 17:15 (KST)
    """
    scheduler.add_job(
        post_weekly_qm_message,
        trigger="cron",
        day_of_week="mon",
        hour=10,
        minute=00,
    )
    scheduler.start()

# --------------------------
#  🧾 노션 데이터 조회 함수
# --------------------------
def fetch_qm_from_notion_for_today():
    """
    노션 데이터베이스에서 오늘 날짜가
    '시작일'~'종료일' 사이에 포함된 Row를 찾아
    iOS / Android 담당자 이름을 가져오고,
    Slack ID로 매핑한다.
    매칭 실패 시 None 반환.
    """
    today = datetime.date.today().isoformat()

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    payload = {
        "filter": {
            "and": [
                {"property": "시작일", "date": {"on_or_before": today}},
                {"property": "종료일", "date": {"on_or_after": today}},
            ]
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Notion status:", response.status_code)
    print("Notion body:", response.text)
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])
    if not results:
        raise ValueError(f"오늘 날짜({today})에 해당하는 로테이션 데이터가 없습니다.")

    page = results[0]
    props = page["properties"]

    # Android / iOS 담당자 이름 추출
    android_value = props["Android"]["rich_text"][0]["plain_text"]
    ios_value = props["iOS"]["rich_text"][0]["plain_text"]

    # 이름 → Slack ID 변환 (없으면 None)
    android_qm_id = NAME_TO_SLACK_ID.get(android_value)
    ios_qm_id = NAME_TO_SLACK_ID.get(ios_value)

    return ios_qm_id, android_qm_id

# --------------------------
#  💬 슬랙 멘션 이벤트 핸들러
# --------------------------
@app.event("app_mention")
def handle_mention_events(body, say):
    """
    슬랙에서 봇을 멘션하면,
    수동으로 이번 주 QA Master 메시지를 즉시 전송.
    """
    post_weekly_qm_message()
    say("이번 주 QA Master 메시지를 채널에 전송했습니다!")

# --------------------------
#  🚀 실행 진입점
# --------------------------
if __name__ == "__main__":
    # 1) 실행 시 바로 한 번 쏴보기
    post_weekly_qm_message()

    # 2) 스케줄 설정
    setup_scheduler()

    # 3) Socket Mode 시작
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

# if __name__ == "__main__":
#     # 스케줄 설정
#     setup_scheduler()
#
#     # Socket Mode 시작
#     handler = SocketModeHandler(app, SLACK_APP_TOKEN)
#     handler.start()