# ruff: noqa: F401
import contextlib
from asyncio import create_subprocess_exec, gather
from html import escape
from os import execl as osexecl
from signal import SIGINT, signal
from sys import executable
from time import time
from uuid import uuid4

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from aiofiles.os import remove
from psutil import (
    boot_time,
    cpu_count,
    cpu_percent,
    disk_usage,
    net_io_counters,
    swap_memory,
    virtual_memory,
)
from pyrogram.filters import command, regex
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from bot import (
    LOGGER,
    bot,
    bot_name,
    bot_start_time,
    config_dict,
    intervals,
    scheduler,
    user_data,
)

from .helper.ext_utils.bot_utils import (
    cmd_exec,
    create_help_buttons,
    new_task,
    sync_to_async,
)
from .helper.ext_utils.db_handler import Database
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    five_minute_del,
    send_file,
    send_message,
)
from .modules import (
    authorize,
    bot_settings,
    broadcast,
    cancel_task,
    clone,
    exec,
    file_selector,
    force_start,
    gd_count,
    gd_delete,
    gd_search,
    help,
    mediainfo,
    mirror_leech,
    shell,
    speedtest,
    status,
    users_settings,
    ytdlp,
)


@new_task
async def stats(_, message):
    if await aiopath.exists(".git"):
        last_commit = await cmd_exec(
            "git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'",
            True,
        )
        last_commit = last_commit[0]
    else:
        last_commit = "No UPSTREAM_REPO"
    total, used, free, disk = disk_usage("/")
    swap = swap_memory()
    memory = virtual_memory()
    stats = (
        f"<b>Commit Date:</b> {last_commit}\n\n"
        f"<b>Bot Uptime:</b> {get_readable_time(time() - bot_start_time)}\n"
        f"<b>OS Uptime:</b> {get_readable_time(time() - boot_time())}\n\n"
        f"<b>Total Disk Space:</b> {get_readable_file_size(total)}\n"
        f"<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}\n\n"
        f"<b>Upload:</b> {get_readable_file_size(net_io_counters().bytes_sent)}\n"
        f"<b>Download:</b> {get_readable_file_size(net_io_counters().bytes_recv)}\n\n"
        f"<b>CPU:</b> {cpu_percent(interval=0.5)}%\n"
        f"<b>RAM:</b> {memory.percent}%\n"
        f"<b>DISK:</b> {disk}%\n\n"
        f"<b>Physical Cores:</b> {cpu_count(logical=False)}\n"
        f"<b>Total Cores:</b> {cpu_count(logical=True)}\n\n"
        f"<b>SWAP:</b> {get_readable_file_size(swap.total)} | <b>Used:</b> {swap.percent}%\n"
        f"<b>Memory Total:</b> {get_readable_file_size(memory.total)}\n"
        f"<b>Memory Free:</b> {get_readable_file_size(memory.available)}\n"
        f"<b>Memory Used:</b> {get_readable_file_size(memory.used)}\n"
    )
    await send_message(message, stats)


@new_task
async def start(client, message):
    if len(message.command) > 1 and message.command[1] == "private":
        await delete_message(message)
    elif len(message.command) > 1 and len(message.command[1]) == 36:
        userid = message.from_user.id
        input_token = message.command[1]
        stored_token = await Database.get_user_token(userid)
        if stored_token is None:
            return await send_message(
                message,
                "<b>This token is not for you!</b>\n\nPlease generate your own.",
            )
        if input_token != stored_token:
            return await send_message(
                message,
                "Invalid token.\n\nPlease generate a new one.",
            )
        if userid not in user_data:
            return await send_message(
                message,
                "This token is not yours!\n\nKindly generate your own.",
            )
        data = user_data[userid]
        if "token" not in data or data["token"] != input_token:
            return await send_message(
                message,
                "<b>This token has already been used!</b>\n\nPlease get a new one.",
            )
        token = str(uuid4())
        token_time = time()
        data["token"] = token
        data["time"] = token_time
        user_data[userid].update(data)
        await Database.update_user_tdata(userid, token, token_time)
        msg = "Your token has been successfully generated!\n\n"
        msg += f'It will be valid for {get_readable_time(int(config_dict["TOKEN_TIMEOUT"]), True)}'
        return await send_message(message, msg)
    elif await CustomFilters.authorized(client, message):
        help_command = f"/{BotCommands.HelpCommand}"
        start_string = f"This bot can mirror all your links|files|torrents to Google Drive or any rclone cloud or to telegram.\n<b>Type {help_command} to get a list of available commands</b>"
        await send_message(message, start_string)
    else:
        await send_message(message, "You are not a authorized user!")
    await Database.update_pm_users(message.from_user.id)
    return None


@new_task
async def restart(_, message):
    intervals["stopAll"] = True
    restart_message = await send_message(message, "Restarting...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if qb := intervals["qb"]:
        qb.cancel()
    if st := intervals["status"]:
        for intvl in list(st.values()):
            intvl.cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec(
        "pkill",
        "-9",
        "-f",
        "gunicorn|xria|xnox|xtra|xone",
    )
    proc2 = await create_subprocess_exec("python3", "update.py")
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "Starting Ping")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"{end_time - start_time} ms")


@new_task
async def log(_, message):
    buttons = ButtonMaker()
    buttons.data_button("Log display", f"aeon {message.from_user.id} logdisplay")
    reply_message = await send_file(
        message,
        "log.txt",
        buttons=buttons.build_menu(1),
    )
    await delete_message(message)
    await five_minute_del(reply_message)


help_string = f"""
NOTE: Try each command without any argument to see more detalis.
/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Start mirroring to cloud.
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Start leeching to Telegram.
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leech yt-dlp supported link.
/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive.
/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).
/{BotCommands.UserSetCommand[0]} or /{BotCommands.UserSetCommand[1]} [query]: Users settings.
/{BotCommands.BotSetCommand[0]} or /{BotCommands.BotSetCommand[1]} [query]: Bot settings.
/{BotCommands.SelectCommand}: Select files from torrents by gid or reply.
/{BotCommands.ForceStartCommand[0]} or /{BotCommands.ForceStartCommand[1]} [gid]: Force start task by gid or reply.
/{BotCommands.CancelAllCommand} [query]: Cancel all [status] tasks.
/{BotCommands.ListCommand} [query]: Search in Google Drive(s).
/{BotCommands.StatusCommand}: Shows a status of all the downloads.
/{BotCommands.StatsCommand}: Show stats of the machine where the bot is hosted in.
/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot (Only Owner & Sudo).
/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UsersCommand}: show users settings (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).
/{BotCommands.RestartCommand}: Restart and update the bot (Only Owner & Sudo).
/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/{BotCommands.ShellCommand}: Run shell commands (Only Owner).
/{BotCommands.AExecCommand}: Exec async functions (Only Owner).
/{BotCommands.ExecCommand}: Exec sync functions (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clear {BotCommands.AExecCommand} or {BotCommands.ExecCommand} locals (Only Owner).
"""


@new_task
async def bot_help(_, message):
    await send_message(message, help_string)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        cmd = r"""remote_url=$(git config --get remote.origin.url) &&
            if echo "$remote_url" | grep -qE "github\.com[:/](.*)/(.*?)(\.git)?$"; then
                last_commit=$(git log -1 --pretty=format:'%h') &&
                commit_link="https://github.com/AeonOrg/Aeon-MLTB/commit/$last_commit" &&
                echo $commit_link;
            else
                echo "Failed to extract repository name and owner name from the remote URL.";
            fi"""

        result = await cmd_exec(cmd, True)

        commit_link = result[0]

        async with aiopen(".restartmsg") as f:
            content = await f.read()
            chat_id, msg_id = map(int, content.splitlines())

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f'<a href="{commit_link}">Restarted Successfully!</a>',
            )
        except Exception as e:
            print(f"Failed to edit message: {e}")
        await remove(".restartmsg")


@new_task
async def aeon_callback(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="This message not your's!", show_alert=True)
    if data[2] == "logdisplay":
        await query.answer()
        async with aiopen("log.txt") as f:
            logFileLines = (await f.read()).splitlines()

        def parseline(line):
            try:
                return line.split("] ", 1)[1]
            except IndexError:
                return line

        ind, Loglines = 1, ""
        try:
            while len(Loglines) <= 3500:
                Loglines = parseline(logFileLines[-ind]) + "\n" + Loglines
                if ind == len(logFileLines):
                    break
                ind += 1
            startLine = "<pre language='python'>"
            endLine = "</pre>"
            btn = ButtonMaker()
            btn.data_button("Close", f"aeon {user_id} close")
            reply_message = await send_message(
                message,
                startLine + escape(Loglines) + endLine,
                btn.build_menu(1),
            )
            await query.edit_message_reply_markup(None)
            await delete_message(message)
            await five_minute_del(reply_message)
        except Exception as err:
            LOGGER.error(f"TG Log Display : {err!s}")
    elif data[2] == "private":
        await query.answer(url=f"https://t.me/{bot_name}?start=private")
        return None
    else:
        await query.answer()
        await delete_message(message)
        return None


async def main():
    if config_dict["DATABASE_URL"]:
        await Database.db_load()
    await gather(
        sync_to_async(clean_all),
        restart_notification(),
        telegraph.create_account(),
        sync_to_async(start_aria2_listener, wait=False),
    )
    create_help_buttons()

    bot.add_handler(
        MessageHandler(
            start,
            filters=command(
                BotCommands.StartCommand,
            ),
        ),
    )
    bot.add_handler(
        MessageHandler(
            log,
            filters=command(
                BotCommands.LogCommand,
            )
            & CustomFilters.sudo,
        ),
    )
    bot.add_handler(
        MessageHandler(
            restart,
            filters=command(
                BotCommands.RestartCommand,
            )
            & CustomFilters.sudo,
        ),
    )
    bot.add_handler(
        MessageHandler(
            ping,
            filters=command(
                BotCommands.PingCommand,
            )
            & CustomFilters.authorized,
        ),
    )
    bot.add_handler(
        MessageHandler(
            bot_help,
            filters=command(
                BotCommands.HelpCommand,
            )
            & CustomFilters.authorized,
        ),
    )
    bot.add_handler(
        MessageHandler(
            stats,
            filters=command(
                BotCommands.StatsCommand,
            )
            & CustomFilters.authorized,
        ),
    )
    bot.add_handler(CallbackQueryHandler(aeon_callback, filters=regex(r"^aeon")))
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)


bot.loop.run_until_complete(main())
bot.loop.run_forever()
