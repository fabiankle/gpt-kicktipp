import openai

from gpt_kicktipp.settings import GlobalSettings


class OpenAiClient:

    def __init__(self, settings: GlobalSettings):
        self._openai = openai
        if settings.openai_base_url:
            self._openai.base_url = settings.openai_base_url
        if settings.openai_api_key:
            self._openai.api_key = settings.openai_api_key

    def request(self, prompt: str):
        res = self._openai.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            messages=[{
                "role": "system",
                "content": "Du bist ein deutscher Fußballexperte zur Europameisterschaft 2024"
            },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=False,
            max_tokens=2000
        )

        return res.choices[0].message.content
