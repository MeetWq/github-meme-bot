FROM meetwq/meme-generator:main

RUN pip install --no-cache-dir --upgrade nonebot2 nonebot-adapter-github

COPY bot.py .env /app/
COPY src /app/src/

CMD ["python", "/app/bot.py"]
