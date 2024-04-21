from collections import defaultdict
from threading import Lock
from typing import Dict, Optional, TypedDict

import schedule
from app.logger import Logger
from app.meeting_bots.bot import Bot, BotWebHooks
from app.meeting_bots.recall_ws_hooks import RecallWsHooks, get_all_recall_ws_hooks
from app.speach_kit import YaSpeechToText

logger = Logger().get_logger(__name__)


class BotConfig(TypedDict):
    RECALL_API_TOKEN: str
    NAME: str
    MIN_PROMPT_LEN: int
    WEBHOOKS: BotWebHooks
    YA_SPEECH_KIT_API_KEY: str
    FFMPEG_PATH: str


# bot can be accessed by user id (string)
class BotNet:
    def __init__(self, config: BotConfig):
        self.botnet: Dict[str, Bot] = {}
        self.user_id_by_bot_id = {}

        # self.jobs_by_bot: Dict[str, List[schedule.Job]] = {}
        self.jobs_by_bot = defaultdict(list)

        logger.info("Botnet config %s", config)

        self.mutex = Lock()

        self.config = config

        self._ws_hooks = RecallWsHooks(self)

        self.speech_kit = YaSpeechToText(
            api_key=config["YA_SPEECH_KIT_API_KEY"],
            ffmpeg_path=config["FFMPEG_PATH"],
        )

    @property
    def ws_hooks(self) -> RecallWsHooks:
        return self._ws_hooks

    """
    @property
    def ws_hooks_all(self) -> list[callable]:
        return get_all_recall_ws_hooks()
    """

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

                def summary_scheduler():
                    logger.info("summary_scheduler called")

                    bot.make_summary(
                        summary_transf, self.config["MIN_PROMPT_LEN"], summary_cleaner
                    )

                def transcript_scheduler():
                    logger.info("transcript_scheduler called")

                    rt_audio = bot.real_time_audio
                    if rt_audio is None:
                        logger.error("bot.real_time_audio is None")
                    else:
                        transcripts = rt_audio.flush_to_transcripts()
                        for tr in transcripts:
                            bot.add_transcription(tr)

                def check_stop_schedurer():
                    logger.info("check_stop_schedurer called")
                    state = bot.recording_state()
                    logger.info(f"State: {state}")
                    if isinstance(state, str):
                        with self.mutex:
                            logger.info("stopping summary_scheduler")
                            stop_jobs(self.jobs_by_bot[bot.bot_id])
                            self.jobs_by_bot.pop(bot.bot_id, None)

                        leave_callback(bot)

                job1 = schedule.every(summary_interval_sec).seconds.do(
                    summary_scheduler
                )
                job2 = schedule.every(20).seconds.do(transcript_scheduler)
                job3 = schedule.every(30).seconds.do(check_stop_schedurer)

                self.jobs_by_bot[bot.bot_id].extend([job1, job2, job3])

        return Bot(
            user_id=user_id,
            recall_api_token=self.config["RECALL_API_TOKEN"],
            bot_name=self.config["NAME"],
            webhooks=self.config["WEBHOOKS"],
            speech_kit=self.speech_kit,
            join_callback=join_callback,
            leave_callback=leave_callback,
        )


def stop_jobs(jobs):
    if jobs is None:
        return

    for job in jobs:
        schedule.cancel_job(job)
