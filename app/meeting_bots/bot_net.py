from collections import defaultdict
from threading import Lock
from typing import Dict, Optional, TypedDict, Callable

import schedule
from ..gpt_utils import gpt_req_sender
from ..logger import Logger
from .bot import (
    Bot,
    BotWebHooks,
    SummaryRepo,
)  # TODO: SummaryRepo maybe cyclic
from ..speach_kit import YaSpeechToText
from .recall_ws_hooks import RecallWsHooks  # TODO: maybe cyclic


logger = Logger().get_logger(__name__)

TRANSCRIPT_TIMESTAMP_STEP = 5
THRESHOLD_TIMESTAMP_STEP = 25


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
    GPT_MODEL_URL: str
    GPT_API_KEY: str
    SUMM_TRANSFER_TEMP: int
    SUMM_CLEANER_TEMP: int
    SUMM_TRANSFER_PROMPT: str | Callable  # callable is for prompts with detaliziation
    SUMM_CLEANER_PROMPT: str
    SUMM_INTERVAL_SEC: int


# bot can be accessed by user id (string)
class BotNet:
    def __init__(self, config: BotConfig, clean_non_active=True):
        self.botnet: Dict[str, Bot] = {}  # bot_id: Bot
        # self.user_id_by_bot_id = {}

        # self.jobs_by_bot: Dict[str, List[schedule.Job]] = {}
        self.jobs_by_bot = defaultdict(list)

        logger.info("Botnet config %s", config)

        self.mutex = Lock()

        self.config = config

        self._ws_hooks = RecallWsHooks(self)

        self.summary_baker = SummaryBaker(
            gpt_model_uri=config["GPT_MODEL_URL"], gpt_api_key=config["GPT_API_KEY"]
        )

        self.summary_repo = SummaryRepo(
            save_endp=self.config["SUMM_SAVER_ENDP"],
            get_endp=self.config["SUMM_GETTER_ENDP"],
            finish_endp=self.config["SUMM_FINISHER_ENDP"],
        )

        self.speech_kit = YaSpeechToText(
            api_key=config["YA_SPEECH_KIT_API_KEY"],
            ffmpeg_path=config["FFMPEG_PATH"],
        )

        if clean_non_active:
            clean_res = SummaryActiveCleaner(
                summary_repo=self.summary_repo, recall_api=self.recall_api
            ).clean()

    @property
    def ws_hooks(self) -> RecallWsHooks:
        return self._ws_hooks

    """
    @property
    def ws_hooks_all(self) -> list[Callable]:
        return get_all_recall_ws_hooks()
    """

    def _setup_bot(
        self,
        bot: Bot,
        transf_with_detalization: bool = True,
        with_cleaner: bool = True,
    ):
        with self.mutex:
            self.botnet[bot.bot_id] = bot

        summary_transf_prompt = (
            self.config["SUMM_TRANSFER_PROMPT"](bot.detalization)
            if transf_with_detalization
            else self.config["SUMM_TRANSFER_PROMPT"]
        )

        summary_transf = self.summary_baker.get_callback(
            prompt=summary_transf_prompt,
            temperature=self.config["SUMM_TRANSFER_TEMP"],
        )

        summary_cleaner = (
            self.summary_baker.get_callback(
                prompt=self.config["SUMM_CLEANER_PROMPT"],
                temperature=self.config["SUMM_CLEANER_TEMP"],
            )
            if with_cleaner
            else None
        )

        self._schedule_jobs_for_bot(
            bot=bot,
            summary_transf=summary_transf,
            summary_interval_sec=self.config["SUMM_INTERVAL_SEC"],
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
        summary_transf: Callable,
        summary_interval_sec,
        summary_cleaner: Optional[Callable],
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
                if rt_audio.events_queue:
                    rt_audio.timestamp_counter += TRANSCRIPT_TIMESTAMP_STEP
                with rt_audio.mutex:
                    if rt_audio.timestamp_counter >= THRESHOLD_TIMESTAMP_STEP:
                        tr = rt_audio.get_transcription()
                        if tr:
                            bot.add_transcription(tr)
                    else:
                        logger.info(f"Spent {rt_audio.timestamp_counter}")
                
                #transcripts = rt_audio.flush_to_transcripts()
                #for tr in transcripts:
                #    

        def check_stop_schedurer():
            logger.info("check_stop_schedurer called")
            state = bot.recording_state()
            logger.info(f"State: {state}")
            if isinstance(state, str):
                logger.info("stopping summary_scheduler")
                self._get_leave_callback()(bot)

        job1 = schedule.every(summary_interval_sec).seconds.do(summary_scheduler)
        
        job2 = schedule.every(TRANSCRIPT_TIMESTAMP_STEP).seconds.do(transcript_scheduler)
        
        job3 = schedule.every(30).seconds.do(check_stop_schedurer)

        self.jobs_by_bot[bot.bot_id].extend([job1, job2, job3])
        #self.jobs_by_bot[bot.bot_id].extend([job1, job3])

    @staticmethod
    def _stop_jobs(jobs):
        if jobs is None:
            return

        for job in jobs:
            schedule.cancel_job(job)

    def get_by_bot_id(self, bot_id: str) -> Optional[Bot]:
        bot = None
        with self.mutex:
            bot = self.botnet.get(bot_id, None)
        return bot

    # raises: Exception from recall api call
    # TODO: maybe add try catch
    def join_meeting(
        self,
        meetring_url: str,
        detalization: str,
    ):
        bot = Bot.from_join_meeting(
            bot_name=self.config["NAME"],
            detalization=detalization,
            recall_api_token=self.config["RECALL_API_TOKEN"],
            meeting_url=meetring_url,
            summary_repo=self.summary_repo,
            webhooks=self.config["WEBHOOKS"],
            speech_kit=self.speech_kit,
            leave_callback=self._get_leave_callback(),
        )

        self.summary_repo.init_summary(
            bot_id=bot.bot_id,
            platform=str(bot.platform),
            detalization=detalization,
        )

        self._setup_bot(
            bot=bot,
        )

        return bot

    def try_restore_bot(
        self,
        bot_id,
    ) -> Optional[Bot]:
        summary_model = self.summary_repo.get_summary(bot_id)
        if summary_model is None or not summary_model["active"]:
            return None

        summ = summary_model["text"]
        detalization = summary_model["detalization"]
        platform = summary_model["platform"]

        from .recall_api import RecallApi
        from .platform_parser import Platform

        bot = Bot(
            bot_id=bot_id,
            detalization=detalization,
            platform=Platform.from_str(platform),
            recall_api=RecallApi(self.config["RECALL_API_TOKEN"]),
            summary_repo=self.summary_repo,
            speech_kit=self.speech_kit,
            leave_callback=self._get_leave_callback(),
        )
        bot.transcription.drop_to_summ(summary=summ)
        self._setup_bot(
            bot=bot,
        )
        return bot

    def get_by_id_or_try_restore(
        self,
        bot_id,
    ):
        bot = self.get_by_bot_id(bot_id=bot_id)
        if bot is not None:
            return bot

        logger.info("trying to restore bot")
        bot = self.try_restore_bot(
            bot_id=bot_id,
        )

        if bot is not None:
            logger.info("bot restored")

        return bot

    @property
    def recall_api(self):
        from .recall_api import RecallApi

        return RecallApi(recall_api_token=self.config["RECALL_API_TOKEN"])


class SummaryBaker:
    def __init__(self, gpt_model_uri, gpt_api_key):
        self.gpt_model_uri = gpt_model_uri
        self.gpt_api_key = gpt_api_key

    def get_callback(self, prompt, temperature):
        return gpt_req_sender(
            self.gpt_model_uri,
            prompt,
            self.gpt_api_key,
            temperature,
        )


class SummaryActiveCleaner:
    from .recall_api import RecallApi

    def __init__(self, summary_repo: SummaryRepo, recall_api: RecallApi):
        self.summary_repo = summary_repo
        self.recall_api = recall_api

    def clean(self) -> bool:
        from .bot import SummaryModel

        active_summaries: list[SummaryModel] | None = (
            self.summary_repo.get_active_summaries()
        )
        if active_summaries is None:
            return False

        for summary in active_summaries:
            bot_id = summary["id"]
            if self.recall_api.recording_state_crit(bot_id=bot_id) is not True:
                finish_res = self.summary_repo.finish(bot_id=bot_id)

                if finish_res:
                    logger.info("cleaned summary with id: %s", bot_id)

        return True
