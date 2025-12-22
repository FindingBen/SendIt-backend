import time
import random
import logging
from celery import shared_task
from openai import RateLimitError, APIError, APITimeoutError
from base.auth import OpenAiAuthInit


logger = logging.getLogger(__name__)

class RetrySafeOpenAI:
    """
    Thin wrapper around OpenAI client with exponential backoff.
    """

    def __init__(self):
        self.client = OpenAiAuthInit().clientAuth()

    def chat_completion(self, *, model, messages, max_retries=5):
        attempt = 0

        while True:
            try:
                return self.client.chat.completions.create(
                    model=model,
                    messages=messages
                )

            except (RateLimitError, APITimeoutError, APIError) as e:
                logger.warning(f"OpenAI API error: {e}. Retrying...")
                attempt += 1
                if attempt > max_retries:
                    raise

                # exponential backoff with jitter
                sleep_time = min(2 ** attempt, 30) + random.uniform(0, 1)
                time.sleep(sleep_time)
