import contextlib
from logging import getLogger
from os import listdir, remove
from os import path as ospath

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import SetInterval, async_to_sync
from bot.helper.ext_utils.files_utils import get_mime_type
from bot.helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class GoogleDriveUpload(GoogleDriveHelper):
    def __init__(self, listener, path):
        self.listener = listener
        self._updater = None
        self._path = path
        self._is_errored = False
        super().__init__()
        self.is_uploading = True

    def user_setting(self):
        if self.listener.up_dest.startswith("mtp:"):
            self.token_path = f"tokens/{self.listener.user_id}.pickle"
            self.listener.up_dest = self.listener.up_dest.replace("mtp:", "", 1)
            self.use_sa = False
        elif self.listener.up_dest.startswith("tp:"):
            self.listener.up_dest = self.listener.up_dest.replace("tp:", "", 1)
            self.use_sa = False
        elif self.listener.up_dest.startswith("sa:"):
            self.listener.up_dest = self.listener.up_dest.replace("sa:", "", 1)
            self.use_sa = True

    def upload(self, unwanted_files, ft_delete):
        self.user_setting()
        self.service = self.authorize()
        LOGGER.info(f"Uploading: {self._path}")
        self._updater = SetInterval(self.update_interval, self.progress)
        try:
            if ospath.isfile(self._path):
                if self._path.lower().endswith(
                    tuple(self.listener.extension_filter),
                ):
                    raise Exception(
                        "This file extension is excluded by extension filter!",
                    )
                mime_type = get_mime_type(self._path)
                link = self._upload_file(
                    self._path,
                    self.listener.name,
                    mime_type,
                    self.listener.up_dest,
                    ft_delete,
                    in_dir=False,
                )
                if self.listener.is_cancelled:
                    return
                if link is None:
                    raise Exception("Upload has been manually cancelled")
                LOGGER.info(f"Uploaded To G-Drive: {self._path}")
            else:
                mime_type = "Folder"
                dir_id = self.create_directory(
                    ospath.basename(ospath.abspath(self.listener.name)),
                    self.listener.up_dest,
                )
                result = self._upload_dir(
                    self._path,
                    dir_id,
                    unwanted_files,
                    ft_delete,
                )
                if result is None:
                    raise Exception("Upload has been manually cancelled!")
                link = self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)
                if self.listener.is_cancelled:
                    return
                LOGGER.info(f"Uploaded To G-Drive: {self.listener.name}")
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace(">", "").replace("<", "")
            async_to_sync(self.listener.on_upload_error, err)
            self._is_errored = True
        finally:
            self._updater.cancel()
            if self.listener.is_cancelled and not self._is_errored:
                if mime_type == "Folder":
                    LOGGER.info("Deleting uploaded data from Drive...")
                    self.service.files().delete(
                        fileId=dir_id,
                        supportsAllDrives=True,
                    ).execute()
                return
            if self._is_errored:
                return
            async_to_sync(
                self.listener.on_upload_complete,
                link,
                self.total_files,
                self.total_folders,
                mime_type,
                dir_id=self.get_id_from_url(link),
            )

    def _upload_dir(self, input_directory, dest_id, unwanted_files, ft_delete):
        list_dirs = listdir(input_directory)
        if len(list_dirs) == 0:
            return dest_id
        new_id = None
        for item in list_dirs:
            current_file_name = ospath.join(input_directory, item)
            if ospath.isdir(current_file_name):
                current_dir_id = self.create_directory(item, dest_id)
                new_id = self._upload_dir(
                    current_file_name,
                    current_dir_id,
                    unwanted_files,
                    ft_delete,
                )
                self.total_folders += 1
            elif (
                current_file_name not in unwanted_files
                and not item.lower().endswith(
                    tuple(self.listener.extension_filter),
                )
            ):
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                self._upload_file(
                    current_file_name,
                    file_name,
                    mime_type,
                    dest_id,
                    ft_delete,
                )
                self.total_files += 1
                new_id = dest_id
            else:
                if not self.listener.seed or self.listener.new_dir:
                    remove(current_file_name)
                new_id = "filter"
            if self.listener.is_cancelled:
                break
        return new_id

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=(retry_if_exception_type(Exception)),
    )
    def _upload_file(
        self,
        file_path,
        file_name,
        mime_type,
        dest_id,
        ft_delete,
        in_dir=True,
    ):
        # File body description
        file_metadata = {
            "name": file_name,
            "description": "Uploaded by Mirror-leech-telegram-bot",
            "mimeType": mime_type,
        }
        if dest_id is not None:
            file_metadata["parents"] = [dest_id]

        if ospath.getsize(file_path) == 0:
            media_body = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=False,
            )
            response = (
                self.service.files()
                .create(
                    body=file_metadata,
                    media_body=media_body,
                    supportsAllDrives=True,
                )
                .execute()
            )
            if not Config.IS_TEAM_DRIVE:
                self.set_permission(response["id"])

            drive_file = (
                self.service.files()
                .get(fileId=response["id"], supportsAllDrives=True)
                .execute()
            )
            return self.G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get("id"))
        media_body = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True,
            chunksize=100 * 1024 * 1024,
        )

        # Insert a file
        drive_file = self.service.files().create(
            body=file_metadata,
            media_body=media_body,
            supportsAllDrives=True,
        )
        response = None
        retries = 0
        while response is None and not self.listener.is_cancelled:
            try:
                self.status, response = drive_file.next_chunk()
            except HttpError as err:
                if err.resp.status in [500, 502, 503, 504, 429] and retries < 10:
                    retries += 1
                    continue
                if err.resp.get("content-type", "").startswith("application/json"):
                    reason = (
                        eval(err.content).get("error").get("errors")[0].get("reason")
                    )
                    if reason not in [
                        "userRateLimitExceeded",
                        "dailyLimitExceeded",
                    ]:
                        raise err
                    if self.use_sa:
                        if self.sa_count >= self.sa_number:
                            LOGGER.info(
                                f"Reached maximum number of service accounts switching, which is {self.sa_count}",
                            )
                            raise err
                        if self.listener.is_cancelled:
                            return None
                        self.switch_service_account()
                        LOGGER.info(f"Got: {reason}, Trying Again.")
                        return self._upload_file(
                            file_path,
                            file_name,
                            mime_type,
                            dest_id,
                            ft_delete,
                            in_dir,
                        )
                    LOGGER.error(f"Got: {reason}")
                    raise err
        if self.listener.is_cancelled:
            return None
        if not self.listener.seed or self.listener.new_dir or file_path in ft_delete:
            with contextlib.suppress(Exception):
                remove(file_path)
        self.file_processed_bytes = 0
        # Insert new permissions
        if not Config.IS_TEAM_DRIVE:
            self.set_permission(response["id"])
        # Define file instance and get url for download
        if not in_dir:
            drive_file = (
                self.service.files()
                .get(fileId=response["id"], supportsAllDrives=True)
                .execute()
            )
            return self.G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get("id"))
        return None