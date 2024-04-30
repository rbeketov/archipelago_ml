from collections import defaultdict
from threading import Lock
from typing import Dict, Optional, TypedDict

import schedule
from app.logger import Logger
from .bot import Bot, BotWebHooks, SummaryRepo  # TODO: SummaryRepo maybe cyclic
from ..speach_kit import YaSpeechToText
from .recall_ws_hooks import RecallWsHooks  # TODO: maybe cyclic

logger = Logger().get_logger(__name__)


class BotConfig(TypedDict):
    RECALL_API_TOKEN: str
    NAME: str
    MIN_PROMPT_LEN: int
    WEBHOOKS: BotWebHooks
    YA_SPEECH_KIT_API_KEY: str
    FFMPEG_PATH: str
    SUMM_SAVER_ENDP: str
    SUMM_GETTER_ENDP: str
    SUMM_FINISHER_ENDP: str


# bot can be accessed by user id (string)
class BotNet:
    def __init__(self, config: BotConfig):
        self.botnet: Dict[str, Bot] = {} # bot_id: Bot
        # self.user_id_by_bot_id = {}

        # self.jobs_by_bot: Dict[str, List[schedule.Job]] = {}
        self.jobs_by_bot = defaultdict(list)

        logger.info("Botnet config %s", config)

        self.mutex = Lock()

        self.config = config

        self._ws_hooks = RecallWsHooks(self)

        self.summary_repo = SummaryRepo(
            save_endp=self.config["SUMM_SAVER_ENDP"],
            get_endp=self.config["SUMM_GETTER_ENDP"],
            finish_endp=self.config["SUMM_FINISHER_ENDP"],
        )

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

    def get_by_bot_id(self, bot_id: str) -> Optional[Bot]:
        bot = None
        with self.mutex:
            bot = self.botnet.get(bot_id, None)
        return bot

    def _setup_bot(
        self,
        bot: Bot,
        summary_transf: callable,
        summary_interval_sec,
        summary_cleaner: Optional[callable],
    ):
        with self.mutex:
            self.botnet[bot.bot_id] = bot
        self._schedule_jobs_for_bot(
            bot=bot,
            summary_transf=summary_transf,
            summary_interval_sec=summary_interval_sec,
            summary_cleaner=summary_cleaner,
        )

    def _get_leave_callback(
        self,
    ):
        def leave_callback(bot: Bot):
                logger.info("leaving")
                bot.summary_repo.finish(bot_id=bot.bot_id)

                # TODO: remove _stop_jobs.from mutex
                with self.mutex:
                    self.botnet.pop(bot.bot_id, None)
                    BotNet._stop_jobs(self.jobs_by_bot.get(bot.bot_id, None))
                    self.jobs_by_bot.pop(bot.bot_id, None)

        return leave_callback

    def _schedule_jobs_for_bot(
        self,
        bot: Bot,
        summary_transf: callable,
        summary_interval_sec,
        summary_cleaner: Optional[callable],
    ):
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
                logger.info("stopping summary_scheduler")
                self._get_leave_callback()(bot)

        job1 = schedule.every(summary_interval_sec).seconds.do(
            summary_scheduler
        )
        # job2 = schedule.every(20).seconds.do(transcript_scheduler)
        job3 = schedule.every(30).seconds.do(check_stop_schedurer)

        # self.jobs_by_bot[bot.bot_id].extend([job1, job2, job3])
        self.jobs_by_bot[bot.bot_id].extend([job1, job3])

    @staticmethod
    def _stop_jobs(jobs):
        if jobs is None:
            return

        for job in jobs:
            schedule.cancel_job(job)

    # raises: Exception from recall api call
    # TODO: maybe add try catch
    def join_meeting(
        self,
        meetring_url: str,
        summary_transf: callable,
        summary_interval_sec,
        summary_cleaner: Optional[callable],
    ):
        bot = Bot.from_join_meeting(
            bot_name=self.config["NAME"],
            recall_api_token=self.config["RECALL_API_TOKEN"],
            meeting_url=meetring_url,
            summary_repo=self.summary_repo,
            webhooks=self.config["WEBHOOKS"],
            speech_kit=self.speech_kit,
            leave_callback=self._get_leave_callback(), # TODO
        )
        self.summary_repo.save(summary="", bot_id=bot.bot_id)

        self._setup_bot(
            bot=bot,
            summary_transf=summary_transf,
            summary_interval_sec=summary_interval_sec,
            summary_cleaner=summary_cleaner,
        )

    def try_restore_bot(
        self,
        bot_id,
        summary_transf: callable,
        summary_interval_sec,
        summary_cleaner: Optional[callable],
    ) -> Optional[Bot]:
        summ = self.summary_repo.get_summ(bot_id=bot_id)
        if summ is None:
            return None

        from .recall_api import RecallApi
        bot = Bot(
            bot_id=bot_id,
            recall_api=RecallApi(self.config["RECALL_API_TOKEN"]),
            summary_repo=self.summary_repo,
            speech_kit=self.speech_kit,
            leave_callback=self._get_leave_callback(),
        )
        bot.transcription.drop_to_summ(summary=summ)
        self._setup_bot(
            bot=bot,
            summary_transf=summary_transf,
            summary_interval_sec=summary_interval_sec,
            summary_cleaner=summary_cleaner,
        )
        return bot


