from aiofiles import open as aiopen
from aiofiles.os import makedirs
from aiofiles.os import path as aiopath
from dotenv import dotenv_values

# from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from bot import (
    BOT_ID,
    LOGGER,
    aria2_options,
    config_dict,
    qbit_options,
    user_data,
)


class DbManager:
    def __init__(self):
        self._return = False
        self._db = None
        self._conn = None

    async def connect(self):
        try:
            if config_dict["DATABASE_URL"]:
                if self._conn is not None:
                    await self._conn.close()
                self._conn = AsyncMongoClient(
                    config_dict["DATABASE_URL"],
                    server_api=ServerApi("1"),
                )
                self._db = self._conn.luna
                self._return = False
            else:
                self._return = True
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self._return = True

    async def disconnect(self):
        if self._conn is not None:
            await self._conn.close()
        self._conn = None
        self._return = True

    async def db_load(self):
        if self._db is None:
            await self.connect()
        if self._return:
            return
        # Save bot settings
        try:
            await self._db.settings.config.replace_one(
                {"_id": BOT_ID},
                config_dict,
                upsert=True,
            )
        except Exception as e:
            LOGGER.error(f"DataBase Collection Error: {e}")
            return
        # Save Aria2c options
        if await self._db.settings.aria2c.find_one({"_id": BOT_ID}) is None:
            await self._db.settings.aria2c.update_one(
                {"_id": BOT_ID},
                {"$set": aria2_options},
                upsert=True,
            )
        # Save qbittorrent options
        if await self._db.settings.qbittorrent.find_one({"_id": BOT_ID}) is None:
            await self.save_qbit_settings()
        # User Data
        if await self._db.users.find_one():
            rows = self._db.users.find({})
            # return a dict ==> {_id, is_sudo, is_auth, as_doc, thumb, yt_opt, split_size, rclone, rclone_path, token_pickle, gdrive_id, leech_dest, lperfix, lprefix, excluded_extensions, user_transmission, index_url, default_upload}
            async for row in rows:
                uid = row["_id"]
                del row["_id"]
                thumb_path = f"Thumbnails/{uid}.jpg"
                rclone_config_path = f"rclone/{uid}.conf"
                token_path = f"tokens/{uid}.pickle"
                if row.get("thumb"):
                    if not await aiopath.exists("Thumbnails"):
                        await makedirs("Thumbnails")
                    async with aiopen(thumb_path, "wb+") as f:
                        await f.write(row["thumb"])
                    row["thumb"] = thumb_path
                if row.get("rclone_config"):
                    if not await aiopath.exists("rclone"):
                        await makedirs("rclone")
                    async with aiopen(rclone_config_path, "wb+") as f:
                        await f.write(row["rclone_config"])
                    row["rclone_config"] = rclone_config_path
                if row.get("token_pickle"):
                    if not await aiopath.exists("tokens"):
                        await makedirs("tokens")
                    async with aiopen(token_path, "wb+") as f:
                        await f.write(row["token_pickle"])
                    row["token_pickle"] = token_path
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")

    async def update_deploy_config(self):
        if self._return:
            return
        current_config = dict(dotenv_values("config.env"))
        await self._db.settings.deployConfig.replace_one(
            {"_id": BOT_ID},
            current_config,
            upsert=True,
        )

    async def update_config(self, dict_):
        if self._return:
            return
        await self._db.settings.config.update_one(
            {"_id": BOT_ID},
            {"$set": dict_},
            upsert=True,
        )

    async def update_aria2(self, key, value):
        if self._return:
            return
        await self._db.settings.aria2c.update_one(
            {"_id": BOT_ID},
            {"$set": {key: value}},
            upsert=True,
        )

    async def update_qbittorrent(self, key, value):
        if self._return:
            return
        await self._db.settings.qbittorrent.update_one(
            {"_id": BOT_ID},
            {"$set": {key: value}},
            upsert=True,
        )

    async def save_qbit_settings(self):
        if self._return:
            return
        await self._db.settings.qbittorrent.replace_one(
            {"_id": BOT_ID},
            qbit_options,
            upsert=True,
        )

    async def update_private_file(self, path):
        if self._return:
            return
        if await aiopath.exists(path):
            async with aiopen(path, "rb+") as pf:
                pf_bin = await pf.read()
        else:
            pf_bin = ""
        path = path.replace(".", "__")
        await self._db.settings.files.update_one(
            {"_id": BOT_ID},
            {"$set": {path: pf_bin}},
            upsert=True,
        )
        if path == "config.env":
            await self.update_deploy_config()

    async def update_user_data(self, user_id):
        if self._return:
            return
        data = user_data.get(user_id, {})
        if data.get("thumb"):
            del data["thumb"]
        if data.get("rclone_config"):
            del data["rclone_config"]
        if data.get("token_pickle"):
            del data["token_pickle"]
        if data.get("token"):
            del data["token"]
        if data.get("time"):
            del data["time"]
        await self._db.users.replace_one({"_id": user_id}, data, upsert=True)

    async def update_user_doc(self, user_id, key, path=""):
        if self._return:
            return
        if path:
            async with aiopen(path, "rb+") as doc:
                doc_bin = await doc.read()
        else:
            doc_bin = ""
        await self._db.users.update_one(
            {"_id": user_id},
            {"$set": {key: doc_bin}},
            upsert=True,
        )

    async def trunc_table(self, name):
        if self._return:
            return
        await self._db[name][BOT_ID].drop()

    async def get_pm_uids(self):
        if self._return:
            return None
        return [doc["_id"] async for doc in self._db.pm_users[BOT_ID].find({})]

    async def update_pm_users(self, user_id):
        if self._return:
            return
        if not bool(await self._db.pm_users[BOT_ID].find_one({"_id": user_id})):
            await self._db.pm_users[BOT_ID].insert_one({"_id": user_id})
            LOGGER.info(f"New PM User Added : {user_id}")

    async def rm_pm_user(self, user_id):
        if self._return:
            return
        await self._db.pm_users[BOT_ID].delete_one({"_id": user_id})

    async def update_user_tdata(self, user_id, token, time):
        if self._return:
            return
        await self._db.access_token.update_one(
            {"_id": user_id},
            {"$set": {"token": token, "time": time}},
            upsert=True,
        )

    async def update_user_token(self, user_id, token):
        if self._return:
            return
        await self._db.access_token.update_one(
            {"_id": user_id},
            {"$set": {"token": token}},
            upsert=True,
        )

    async def get_token_expiry(self, user_id):
        if self._return:
            return None
        user_data = await self._db.access_token.find_one({"_id": user_id})
        if user_data:
            return user_data.get("time")
        return None

    async def delete_user_token(self, user_id):
        if self._return:
            return
        await self._db.access_token.delete_one({"_id": user_id})

    async def get_user_token(self, user_id):
        if self._return:
            return None
        user_data = await self._db.access_token.find_one({"_id": user_id})
        if user_data:
            return user_data.get("token")
        return None

    async def delete_all_access_tokens(self):
        if self._return:
            return
        await self._db.access_token.delete_many({})


Database = DbManager()
