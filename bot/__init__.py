import subprocess
from asyncio import Lock, new_event_loop, set_event_loop
from datetime import datetime
from logging import (
    ERROR,
    INFO,
    FileHandler,
    Formatter,
    LogRecord,
    StreamHandler,
    basicConfig,
    error,
    getLogger,
    info,
    warning,
)
from os import environ, getcwd, remove
from os import path as ospath
from shutil import rmtree
from socket import setdefaulttimeout
from sys import exit
from time import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aria2p import API
from aria2p import Client as ariaClient
from dotenv import dotenv_values, load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pyrogram import Client as TgClient
from pyrogram import enums
from pytz import timezone
from qbittorrentapi import Client as QbClient
from tzlocal import get_localzone
from uvloop import install

# from faulthandler import enable as faulthandler_enable
# faulthandler_enable()

install()
setdefaulttimeout(600)

getLogger("qbittorrentapi").setLevel(INFO)
getLogger("requests").setLevel(INFO)
getLogger("urllib3").setLevel(INFO)
getLogger("pyrogram").setLevel(ERROR)
getLogger("httpx").setLevel(ERROR)
getLogger("pymongo").setLevel(ERROR)

bot_start_time = time()

bot_loop = new_event_loop()
set_event_loop(bot_loop)


class CustomFormatter(Formatter):
    def formatTime(  # noqa: N802
        self,
        record: LogRecord,
        datefmt: str | None,
    ) -> str:
        dt: datetime = datetime.fromtimestamp(
            record.created,
            tz=timezone("Asia/Dhaka"),
        )
        return dt.strftime(datefmt)

    def format(self, record: LogRecord) -> str:
        return super().format(record).replace(record.levelname, record.levelname[:1])


formatter = CustomFormatter(
    "[%(asctime)s] %(levelname)s - %(message)s [%(module)s:%(lineno)d]",
    datefmt="%d-%b %I:%M:%S %p",
)

file_handler = FileHandler("log.txt")
file_handler.setFormatter(formatter)

stream_handler = StreamHandler()
stream_handler.setFormatter(formatter)

basicConfig(handlers=[file_handler, stream_handler], level=INFO)

LOGGER = getLogger(__name__)

load_dotenv("config.env", override=True)

intervals = {"status": {}, "qb": "", "stopAll": False}
qb_torrents = {}
drives_names = []
drives_ids = []
index_urls = []
global_extension_filter = ["aria2", "!qB"]
user_data = {}
aria2_options = {}
qbit_options = {}
queued_dl = {}
queued_up = {}
non_queued_dl = set()
non_queued_up = set()
multi_tags = set()
shorteners_list = []

try:
    if bool(environ.get("_____REMOVE_THIS_LINE_____")):
        error("The README.md file there to be read! Exiting now!")
        bot_loop.stop()
        exit(1)
except Exception:
    pass

task_dict_lock = Lock()
queue_dict_lock = Lock()
qb_listener_lock = Lock()
cpu_eater_lock = Lock()
subprocess_lock = Lock()
same_directory_lock = Lock()
status_dict = {}
task_dict = {}

BOT_TOKEN = environ.get("BOT_TOKEN", "")
if len(BOT_TOKEN) == 0:
    error("BOT_TOKEN variable is missing! Exiting now")
    bot_loop.stop()
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]

DATABASE_URL = environ.get("DATABASE_URL", "")
if len(DATABASE_URL) == 0:
    DATABASE_URL = ""

if DATABASE_URL:
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn.luna
        current_config = dict(dotenv_values("config.env"))
        old_config = db.settings.deployConfig.find_one({"_id": BOT_ID})
        if old_config is None:
            db.settings.deployConfig.replace_one(
                {"_id": BOT_ID},
                current_config,
                upsert=True,
            )
        else:
            del old_config["_id"]
        if old_config and old_config != current_config:
            db.settings.deployConfig.replace_one(
                {"_id": BOT_ID},
                current_config,
                upsert=True,
            )
        elif config_dict := db.settings.config.find_one({"_id": BOT_ID}):
            del config_dict["_id"]
            for key, value in config_dict.items():
                environ[key] = str(value)
        if pf_dict := db.settings.files.find_one({"_id": BOT_ID}):
            del pf_dict["_id"]
            for key, value in pf_dict.items():
                if value:
                    file_ = key.replace("__", ".")
                    with open(file_, "wb+") as f:
                        f.write(value)
        if a2c_options := db.settings.aria2c.find_one({"_id": BOT_ID}):
            del a2c_options["_id"]
            aria2_options = a2c_options
        if qbit_opt := db.settings.qbittorrent.find_one({"_id": BOT_ID}):
            del qbit_opt["_id"]
            qbit_options = qbit_opt
        conn.close()
        BOT_TOKEN = environ.get("BOT_TOKEN", "")
        BOT_ID = BOT_TOKEN.split(":", 1)[0]
        DATABASE_URL = environ.get("DATABASE_URL", "")
    except Exception as e:
        LOGGER.error(f"Database ERROR: {e}")
else:
    config_dict = {}


OWNER_ID = environ.get("OWNER_ID", "")
if len(OWNER_ID) == 0:
    error("OWNER_ID variable is missing! Exiting now")
    bot_loop.stop()
    exit(1)
else:
    OWNER_ID = int(OWNER_ID)

TELEGRAM_API = environ.get("TELEGRAM_API", "")
if len(TELEGRAM_API) == 0:
    error("TELEGRAM_API variable is missing! Exiting now")
    bot_loop.stop()
    exit(1)
else:
    TELEGRAM_API = int(TELEGRAM_API)

TELEGRAM_HASH = environ.get("TELEGRAM_HASH", "")
if len(TELEGRAM_HASH) == 0:
    error("TELEGRAM_HASH variable is missing! Exiting now")
    bot_loop.stop()
    exit(1)

USER_SESSION_STRING = environ.get("USER_SESSION_STRING", "")
if len(USER_SESSION_STRING) != 0:
    info("Creating client from USER_SESSION_STRING")
    try:
        user = TgClient(
            "user",
            TELEGRAM_API,
            TELEGRAM_HASH,
            session_string=USER_SESSION_STRING,
            parse_mode=enums.ParseMode.HTML,
            max_concurrent_transmissions=10,
        ).start()
        IS_PREMIUM_USER = user.me.is_premium
    except Exception:
        error("Failed to start client from USER_SESSION_STRING")
        IS_PREMIUM_USER = False
        user = ""
else:
    IS_PREMIUM_USER = False
    user = ""

GDRIVE_ID = environ.get("GDRIVE_ID", "")
if len(GDRIVE_ID) == 0:
    GDRIVE_ID = ""

FSUB_IDS = environ.get("FSUB_IDS", "")
if len(FSUB_IDS) == 0:
    FSUB_IDS = ""

PAID_CHAT_ID = environ.get("PAID_CHAT_ID", "")
PAID_CHAT_ID = "" if len(PAID_CHAT_ID) == 0 else int(PAID_CHAT_ID)

PAID_CHAT_LINK = environ.get("PAID_CHAT_LINK", "")
if len(PAID_CHAT_LINK) == 0:
    PAID_CHAT_LINK = ""

TOKEN_TIMEOUT = environ.get("TOKEN_TIMEOUT", "")
TOKEN_TIMEOUT = "" if len(TOKEN_TIMEOUT) == 0 else int(TOKEN_TIMEOUT)

RCLONE_PATH = environ.get("RCLONE_PATH", "")
if len(RCLONE_PATH) == 0:
    RCLONE_PATH = ""

RCLONE_FLAGS = environ.get("RCLONE_FLAGS", "")
if len(RCLONE_FLAGS) == 0:
    RCLONE_FLAGS = ""

DEFAULT_UPLOAD = environ.get("DEFAULT_UPLOAD", "")
if DEFAULT_UPLOAD != "gd":
    DEFAULT_UPLOAD = "rc"

DOWNLOAD_DIR = "/usr/src/app/downloads/"

AUTHORIZED_CHATS = environ.get("AUTHORIZED_CHATS", "")
if len(AUTHORIZED_CHATS) != 0:
    aid = AUTHORIZED_CHATS.split()
    for id_ in aid:
        chat_id, *thread_ids = id_.split("|")
        chat_id = int(chat_id.strip())
        if thread_ids:
            thread_ids = [int(x.strip()) for x in thread_ids]
            user_data[chat_id] = {"is_auth": True, "thread_ids": thread_ids}
        else:
            user_data[chat_id] = {"is_auth": True}

SUDO_USERS = environ.get("SUDO_USERS", "")
if len(SUDO_USERS) != 0:
    aid = SUDO_USERS.split()
    for id_ in aid:
        user_data[int(id_.strip())] = {"is_sudo": True}

EXTENSION_FILTER = environ.get("EXTENSION_FILTER", "")
if len(EXTENSION_FILTER) > 0:
    fx = EXTENSION_FILTER.split()
    for x in fx:
        x = x.lstrip(".")
        global_extension_filter.append(x.strip().lower())

FILELION_API = environ.get("FILELION_API", "")
if len(FILELION_API) == 0:
    FILELION_API = ""

STREAMWISH_API = environ.get("STREAMWISH_API", "")
if len(STREAMWISH_API) == 0:
    STREAMWISH_API = ""

INDEX_URL = environ.get("INDEX_URL", "").rstrip("/")
if len(INDEX_URL) == 0:
    INDEX_URL = ""

LEECH_FILENAME_PREFIX = environ.get("LEECH_FILENAME_PREFIX", "")
if len(LEECH_FILENAME_PREFIX) == 0:
    LEECH_FILENAME_PREFIX = ""

MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

LEECH_SPLIT_SIZE = environ.get("LEECH_SPLIT_SIZE", "")
if (
    len(LEECH_SPLIT_SIZE) == 0
    or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE
    or LEECH_SPLIT_SIZE == "2097152000"
):
    LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
else:
    LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

YT_DLP_OPTIONS = environ.get("YT_DLP_OPTIONS", "")
if len(YT_DLP_OPTIONS) == 0:
    YT_DLP_OPTIONS = ""

LEECH_DUMP_CHAT = environ.get("LEECH_DUMP_CHAT", "")
LEECH_DUMP_CHAT = "" if len(LEECH_DUMP_CHAT) == 0 else LEECH_DUMP_CHAT

MEGA_EMAIL = environ.get("MEGA_EMAIL", "")
MEGA_PASSWORD = environ.get("MEGA_PASSWORD", "")
if len(MEGA_EMAIL) == 0 or len(MEGA_PASSWORD) == 0:
    MEGA_EMAIL = ""
    MEGA_PASSWORD = ""

CMD_SUFFIX = environ.get("CMD_SUFFIX", "")

TORRENT_TIMEOUT = environ.get("TORRENT_TIMEOUT", "")
TORRENT_TIMEOUT = "" if len(TORRENT_TIMEOUT) == 0 else int(TORRENT_TIMEOUT)

QUEUE_ALL = environ.get("QUEUE_ALL", "")
QUEUE_ALL = "" if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

QUEUE_DOWNLOAD = environ.get("QUEUE_DOWNLOAD", "")
QUEUE_DOWNLOAD = "" if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

QUEUE_UPLOAD = environ.get("QUEUE_UPLOAD", "")
QUEUE_UPLOAD = "" if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

STOP_DUPLICATE = environ.get("STOP_DUPLICATE", "")
STOP_DUPLICATE = STOP_DUPLICATE.lower() == "true"

IS_TEAM_DRIVE = environ.get("IS_TEAM_DRIVE", "")
IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == "true"

USE_SERVICE_ACCOUNTS = environ.get("USE_SERVICE_ACCOUNTS", "")
USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == "true"

AS_DOCUMENT = environ.get("AS_DOCUMENT", "")
AS_DOCUMENT = AS_DOCUMENT.lower() == "true"

USER_TRANSMISSION = environ.get("USER_TRANSMISSION", "")
USER_TRANSMISSION = USER_TRANSMISSION.lower() == "true" and IS_PREMIUM_USER

BASE_URL = environ.get("BASE_URL", "").rstrip("/")
if len(BASE_URL) == 0:
    warning("BASE_URL not provided!")
    BASE_URL = ""

UPSTREAM_REPO = environ.get("UPSTREAM_REPO", "")
if len(UPSTREAM_REPO) == 0:
    UPSTREAM_REPO = ""

UPSTREAM_BRANCH = environ.get("UPSTREAM_BRANCH", "")
if len(UPSTREAM_BRANCH) == 0:
    UPSTREAM_BRANCH = "master"

NAME_SUBSTITUTE = environ.get("NAME_SUBSTITUTE", "")
NAME_SUBSTITUTE = "" if len(NAME_SUBSTITUTE) == 0 else NAME_SUBSTITUTE

MIXED_LEECH = environ.get("MIXED_LEECH", "")
MIXED_LEECH = MIXED_LEECH.lower() == "true" and IS_PREMIUM_USER

THUMBNAIL_LAYOUT = environ.get("THUMBNAIL_LAYOUT", "")
THUMBNAIL_LAYOUT = "" if len(THUMBNAIL_LAYOUT) == 0 else THUMBNAIL_LAYOUT

FFMPEG_CMDS = environ.get("FFMPEG_CMDS", "")
try:
    FFMPEG_CMDS = [] if len(FFMPEG_CMDS) == 0 else eval(FFMPEG_CMDS)
except Exception:
    error(f"Wrong FFMPEG_CMDS format: {FFMPEG_CMDS}")
    FFMPEG_CMDS = []

config_dict = {
    "AS_DOCUMENT": AS_DOCUMENT,
    "AUTHORIZED_CHATS": AUTHORIZED_CHATS,
    "BASE_URL": BASE_URL,
    "BOT_TOKEN": BOT_TOKEN,
    "CMD_SUFFIX": CMD_SUFFIX,
    "DATABASE_URL": DATABASE_URL,
    "DEFAULT_UPLOAD": DEFAULT_UPLOAD,
    "EXTENSION_FILTER": EXTENSION_FILTER,
    "FFMPEG_CMDS": FFMPEG_CMDS,
    "FILELION_API": FILELION_API,
    "FSUB_IDS": FSUB_IDS,
    "GDRIVE_ID": GDRIVE_ID,
    "INDEX_URL": INDEX_URL,
    "IS_TEAM_DRIVE": IS_TEAM_DRIVE,
    "LEECH_DUMP_CHAT": LEECH_DUMP_CHAT,
    "LEECH_FILENAME_PREFIX": LEECH_FILENAME_PREFIX,
    "LEECH_SPLIT_SIZE": LEECH_SPLIT_SIZE,
    "MEGA_EMAIL": MEGA_EMAIL,
    "MEGA_PASSWORD": MEGA_PASSWORD,
    "MIXED_LEECH": MIXED_LEECH,
    "NAME_SUBSTITUTE": NAME_SUBSTITUTE,
    "OWNER_ID": OWNER_ID,
    "PAID_CHAT_ID": PAID_CHAT_ID,
    "PAID_CHAT_LINK": PAID_CHAT_LINK,
    "QUEUE_ALL": QUEUE_ALL,
    "QUEUE_DOWNLOAD": QUEUE_DOWNLOAD,
    "QUEUE_UPLOAD": QUEUE_UPLOAD,
    "RCLONE_FLAGS": RCLONE_FLAGS,
    "RCLONE_PATH": RCLONE_PATH,
    "STOP_DUPLICATE": STOP_DUPLICATE,
    "STREAMWISH_API": STREAMWISH_API,
    "SUDO_USERS": SUDO_USERS,
    "TELEGRAM_API": TELEGRAM_API,
    "TELEGRAM_HASH": TELEGRAM_HASH,
    "THUMBNAIL_LAYOUT": THUMBNAIL_LAYOUT,
    "TORRENT_TIMEOUT": TORRENT_TIMEOUT,
    "TOKEN_TIMEOUT": TOKEN_TIMEOUT,
    "USER_TRANSMISSION": USER_TRANSMISSION,
    "UPSTREAM_REPO": UPSTREAM_REPO,
    "UPSTREAM_BRANCH": UPSTREAM_BRANCH,
    "USER_SESSION_STRING": USER_SESSION_STRING,
    "USE_SERVICE_ACCOUNTS": USE_SERVICE_ACCOUNTS,
    "YT_DLP_OPTIONS": YT_DLP_OPTIONS,
}

if GDRIVE_ID:
    drives_names.append("Main")
    drives_ids.append(GDRIVE_ID)
    index_urls.append(INDEX_URL)

if ospath.exists("list_drives.txt"):
    with open("list_drives.txt", "r+") as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            drives_ids.append(temp[1])
            drives_names.append(temp[0].replace("_", " "))
            if len(temp) > 2:
                index_urls.append(temp[2])
            else:
                index_urls.append("")

PORT = environ.get("BASE_URL_PORT") or environ.get("PORT")
subprocess.Popen(
    f"gunicorn web.wserver:app --bind 0.0.0.0:{PORT} --worker-class gevent",
    shell=True,
)

subprocess.run(["xnox", "-d", f"--profile={getcwd()}"], check=False)

if not ospath.exists(".netrc"):
    with open(".netrc", "w"):
        pass
subprocess.run(["chmod", "600", ".netrc"], check=False)
subprocess.run(["cp", ".netrc", "/root/.netrc"], check=False)

trackers = (
    subprocess.check_output(
        "curl -Ns https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/all.txt https://ngosang.github.io/trackerslist/trackers_all_http.txt https://newtrackon.com/api/all https://raw.githubusercontent.com/hezhijie0327/Trackerslist/main/trackerslist_tracker.txt | awk '$0' | tr '\n\n' ','",
        shell=True,
    )
    .decode("utf-8")
    .rstrip(",")
)

with open("a2c.conf", "a+") as a:
    if TORRENT_TIMEOUT is not None:
        a.write(f"bt-stop-timeout={TORRENT_TIMEOUT}\n")
    a.write(f"bt-tracker=[{trackers}]")
subprocess.run(["xria", "--conf-path=/usr/src/app/a2c.conf"], check=False)


if ospath.exists("shorteners.txt"):
    with open("shorteners.txt", "r+") as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            if len(temp) == 2:
                shorteners_list.append({"domain": temp[0], "api_key": temp[1]})


if ospath.exists("accounts.zip"):
    if ospath.exists("accounts"):
        rmtree("accounts")
    subprocess.run(
        ["7z", "x", "-o.", "-aoa", "accounts.zip", "accounts/*.json"],
        check=False,
    )
    subprocess.run(["chmod", "-R", "777", "accounts"], check=False)
    remove("accounts.zip")
if not ospath.exists("accounts"):
    config_dict["USE_SERVICE_ACCOUNTS"] = False


alive = subprocess.Popen(["python3", "alive.py"])


xnox_client = QbClient(
    host="localhost",
    port=8090,
    VERIFY_WEBUI_CERTIFICATE=False,
    REQUESTS_ARGS={"timeout": (30, 60)},
    HTTPADAPTER_ARGS={
        "pool_maxsize": 500,
        "max_retries": 10,
        "pool_block": True,
    },
)


aria2c_global = [
    "bt-max-open-files",
    "download-result",
    "keep-unfinished-download-result",
    "log",
    "log-level",
    "max-concurrent-downloads",
    "max-download-result",
    "max-overall-download-limit",
    "save-session",
    "max-overall-upload-limit",
    "optimize-concurrent-downloads",
    "save-cookies",
    "server-stat-of",
]

aria2 = API(ariaClient(host="http://localhost", port=6800, secret=""))

if not aria2_options:
    aria2_options = aria2.client.get_global_option()
else:
    a2c_glo = {op: aria2_options[op] for op in aria2c_global if op in aria2_options}
    aria2.set_global_options(a2c_glo)


def get_qb_options():
    global qbit_options
    if not qbit_options:
        qbit_options = dict(xnox_client.app_preferences())
        del qbit_options["listen_port"]
        for k in list(qbit_options.keys()):
            if k.startswith("rss"):
                del qbit_options[k]
        xnox_client.app_set_preferences({"web_ui_password": "mltbmltb"})
    else:
        qbit_options["web_ui_password"] = "mltbmltb"
        qb_opt = {**qbit_options}
        xnox_client.app_set_preferences(qb_opt)


get_qb_options()

info("Creating client from BOT_TOKEN")
bot = TgClient(
    "bot",
    TELEGRAM_API,
    TELEGRAM_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML,
    max_concurrent_transmissions=10,
).start()
bot_name = bot.me.username

scheduler = AsyncIOScheduler(timezone=str(get_localzone()), event_loop=bot_loop)
