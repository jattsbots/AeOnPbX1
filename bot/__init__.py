import os
import subprocess
from asyncio import Lock, new_event_loop, set_event_loop
from logging import (
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    StreamHandler,
    basicConfig,
    getLogger,
)
from socket import setdefaulttimeout
from time import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aria2p import API as ariaAPI  # noqa: N811
from aria2p import Client as ariaClient
from qbittorrentapi import Client as QbClient
from tzlocal import get_localzone
from uvloop import install

# from faulthandler import enable as faulthandler_enable
# faulthandler_enable()

install()
setdefaulttimeout(600)

getLogger("qbittorrentapi").setLevel(WARNING)
getLogger("requests").setLevel(WARNING)
getLogger("urllib3").setLevel(WARNING)
getLogger("pyrogram").setLevel(ERROR)
getLogger("httpx").setLevel(WARNING)
getLogger("pymongo").setLevel(WARNING)

bot_start_time = time()

bot_loop = new_event_loop()
set_event_loop(bot_loop)

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)

intervals = {"status": {}, "qb": "", "stopAll": False}
qb_torrents = {}
user_data = {}
aria2_options = {}
qbit_options = {}
queued_dl = {}
queued_up = {}
status_dict = {}
task_dict = {}
rss_dict = {}
non_queued_dl = set()
non_queued_up = set()
multi_tags = set()
task_dict_lock = Lock()
queue_dict_lock = Lock()
qb_listener_lock = Lock()
cpu_eater_lock = Lock()
same_directory_lock = Lock()
extension_filter = ["aria2", "!qB"]
drives_names = []
drives_ids = []
index_urls = []
shorteners_list = []

aria2 = ariaAPI(ariaClient(host="http://localhost", port=6800, secret=""))

subprocess.run(["xnox", "-d", f"--profile={os.getcwd()}"], check=False)


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

trackers = (
    subprocess.check_output(
        "curl -Ns https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/all.txt https://ngosang.github.io/trackerslist/trackers_all_http.txt https://newtrackon.com/api/all https://raw.githubusercontent.com/hezhijie0327/Trackerslist/main/trackerslist_tracker.txt | awk '$0' | tr '\n\n' ','",
        shell=True,
    )
    .decode("utf-8")
    .rstrip(",")
)

with open("a2c.conf", "a+") as a:
    a.write("bt-stop-timeout=600\n")
    a.write(f"bt-tracker=[{trackers}]")
subprocess.run(["xria", "--conf-path=/usr/src/app/a2c.conf"], check=False)


if os.path.exists("shorteners.txt"):
    with open("shorteners.txt", "r+") as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            if len(temp) == 2:
                shorteners_list.append({"domain": temp[0], "api_key": temp[1]})


scheduler = AsyncIOScheduler(timezone=str(get_localzone()), event_loop=bot_loop)
