

# app.py
import os
import datetime
import pytz

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler

from rotation_data import ROTATION

# .env 읽기
load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]

# Slack 앱 초기화
app = App(token=SLACK_BOT_TOKEN)

# 타임존 설정 (한국)
KST = pytz.timezone("Asia/Seoul")

scheduler = BackgroundScheduler(timezone=KST)


def get_current_week_index(start_date: datetime.date) -> int:
    """
    기준 start_date(예: 첫번째 로테이션 시작 월요일)로부터
    '현재 주차'를 계산해서 ROTATION 인덱스로 변환
    """
    today = datetime.date.today()
    delta_weeks = (today - start_date).days // 7
    return delta_weeks % len(ROTATION)


def post_weekly_qm_message():
    """
    이번 주 iOS/Android 큐마를 계산해서 슬랙 채널에 메시지 보내기
    """
    # 예: 2025년 1월 6일(월)부터 로테이션 시작했다고 가정
    rotation_start = datetime.date(2025, 1, 6)

    week_idx = get_current_week_index(rotation_start)
    ios_qm_id, android_qm_id = ROTATION[week_idx]

    ios_mention = f"<@{ios_qm_id}>"
    android_mention = f"<@{android_qm_id}>"

    text = (
        f"이번 주 큐마안내드립니다.\n"
        f"- iOS 큐마: {ios_mention}\n"
        f"- Android 큐마: {android_mention} 입니다."
    )

    app.client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text=text,
    )


def setup_scheduler():
    # 매주 월요일 10:00 (KST 기준)마다 실행
    scheduler.add_job(
        post_weekly_qm_message,
        trigger="cron",
        day_of_week="fri",
        hour=12,
        minute=13,
    )
    scheduler.start()


@app.event("app_mention")
def handle_mention_events(body, say):
    """
    테스트용: 봇 멘션하면, '지금 기준 이번 주 큐마' 메시지 한 번 보내기
    """
    post_weekly_qm_message()
    say("이번 주 큐마 안내 메시지를 채널에 전송했습니다!")


if __name__ == "__main__":
    # 스케줄 설정
    setup_scheduler()

    # Socket Mode 시작
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()