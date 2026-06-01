from dotenv import load_dotenv
import os


load_dotenv()

bot_token = os.environ.get("BOT_TOKEN")

suggestion_admin = 1003449012
admins = [1003449012]
best_channel = "@pozdnyak_ai_best"
banned_users_db_path = "banned.json"

min_latency = 10  # in seconds since last user request
max_failed_requests = 1 # for ddos protection
max_logs_size = 1e4
