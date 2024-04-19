from collections import defaultdict
from threading import Lock
from typing import Dict, Optional, TypedDict

import schedule
from app.logger import Logger
from app.meeting_bots import Bot, BotWebHooks
from app.meeting_bots.recall_ws_hooks import RecallWsHooks, get_all_recall_ws_hooks

logger = Logger().get_logger(__name__)


class BotConfig(TypedDict):
    RECALL_API_TOKEN: str
    NAME: str
    MIN_PROMPT_LEN: int
    WEBHOOKS: BotWebHooks


# bot can be accessed by user id (string)
class BotNet:
    def __init__(self, config: BotConfig):
        self.botnet: Dict[str, Bot] = {}
        self.user_id_by_bot_id = {}

        # self.jobs_by_bot: Dict[str, List[schedule.Job]] = {}
        self.jobs_by_bot = defaultdict(list)

        logger.info(f"Botnet config: {config}")

        self.mutex = Lock()

        self.config = config

        self.ws_hooks = RecallWsHooks()

    @property
    def ws_hooks(self) -> RecallWsHooks:
        return self.ws_hooks

    @property
    def ws_hooks_all(self) -> list[callable]:
        return get_all_recall_ws_hooks()

    def get_by_user_id(self, user_id: str):
        with self.mutex:
            bot = self.botnet.get(user_id, None)

        return bot

    def get_by_bot_id(self, bot_id: str):
        with self.mutex:
            bot = None

            user_id = self.user_id_by_bot_id.get(bot_id, None)
            if user_id is not None:
                bot = self.botnet.get(user_id, None)

        return bot

    def new_bot(
        self,
        user_id,
        summary_transf: callable,
        summary_interval_sec,
        summary_cleaner: Optional[callable],
    ):
        if self.get_by_user_id(user_id) is not None:
            return None

        def leave_callback(bot: Bot):
            with self.mutex:
                logger.info("leaving")
                self.botnet.pop(bot.user_id, None)
                self.user_id_by_bot_id.pop(bot.bot_id, None)

                stop_jobs(self.jobs_by_bot.get(bot.bot_id, None))
                self.jobs_by_bot.pop(bot.bot_id, None)

        def join_callback(bot: Bot):
            with self.mutex:
                self.botnet[bot.user_id] = bot
                self.user_id_by_bot_id[bot.bot_id] = bot.user_id

                def schedule_wrapper():
                    logger.info("schedule_wrapper called")
                    state = bot.recording_state()
                    logger.info(f"State: {state}")
                    if isinstance(state, str):
                        with self.mutex:
                            logger.info("stopping schedule_wrapper")
                            stop_jobs(self.jobs_by_bot[bot.bot_id])
                            self.jobs_by_bot.pop(bot.bot_id, None)

                        leave_callback(bot)

                    bot.make_summary(
                        summary_transf, self.config["MIN_PROMPT_LEN"], summary_cleaner
                    )

                job = schedule.every(summary_interval_sec).seconds.do(schedule_wrapper)
                self.jobs_by_bot[bot.bot_id].append(job)

        return Bot(
            user_id=user_id,
            recall_api_token=self.config["RECALL_API_TOKEN"],
            bot_name=self.config["NAME"],
            webhooks=self.config["WEBHOOKS"],
            join_callback=join_callback,
            leave_callback=leave_callback,
        )


def stop_jobs(jobs):
    if jobs is None:
        return

    for job in jobs:
        schedule.cancel_job(job)
