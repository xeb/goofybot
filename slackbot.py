#!/usr/bin/env python

import os
import re
import fire
import toml
import openai
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
OPENAI_API_TOKEN = os.environ["OPENAI_APP_TOKEN"]

openai.api_key = OPENAI_API_TOKEN
app = App(token=SLACK_BOT_TOKEN)

def generate(prompt):
    config = toml.load("config.toml")["config"]

    additional_temp = prompt.count(":fire:") * 0.05
    temperature=config["temperature"] + additional_temp
    prompt = prompt.replace(":fire:", "")

    if temperature > 1:
        temperature = 0.99

    engine = config["default_engine"]

    # If there's a config of emoji_engine then use that engine
    for key in config.keys():
        if "_engine" in key:
            emoji = key[:-len("_engine")]
            if f":{emoji}:" in prompt:
                engine = config[key]
                prompt = prompt.replace(f":{emoji}:", "").strip()

    print(f"Using {prompt=}")
    response = openai.Completion.create(
        engine=engine,
        prompt=prompt,
        temperature=temperature,
        max_tokens=config["max_tokens"]
    )

    print(f"Received {len(response.choices)=}")
    txt = response.choices[0].text
    return txt

@app.event("app_mention")
def mention_handler_app_mention(body, say, logger):
    event = body["event"]
    thread_ts = event.get("thread_ts", None) or event["ts"]
    channel = event.get("channel", None) or event["channel"]
    print(f"Handling {thread_ts}")
    prompt = (
        event["text"].replace(event["text"].split(" ")[0].strip(), "").strip()
    )  # i feel dirty but its late
    
    if prompt.lower() == "help":
        emoji_engines = ""
        config = toml.load("config.toml")["config"]
        for key in config.keys():
            if "_engine" in key and key != "default_engine":
                emoji = key[:-len("_engine")]
                emoji_engines = emoji_engines + f":{emoji}: == '{config[key]}', \n"

        emoji_engines = emoji_engines + f"\n and the default is {config['default_engine']}"

        say(f"To use me, just mention me with @Goofybot and type your question. You can put :fire: to increase my craziness (up to 4 times). To change the engine, you can use the following emoji's:\n\n {emoji_engines}", thread_ts=thread_ts)
        return

    app.client.reactions_add(channel=channel, timestamp=thread_ts, name="thumbsup")
    print(f"Generating {prompt=}")
    try:
        response = generate(prompt)
        say(response, thread_ts=thread_ts)
    except Exception as e:
        say(f"Uhoh. Error {e=}", thread_ts=thread_ts)


@app.event("message")
def mention_handler_message(body, say):
    event = body["event"]
    thread_ts = event.get("thread_ts", None) or event["ts"]
    messag_ts = event.get("ts", None)
    if "text" not in event:
        return

    channel = event.get("channel", None) or event["channel"]
    message = event["text"].strip()
    user = event.get("user", None)

    print(f"{user=}\n{message=}\n{channel=}\n{thread_ts=}")
    return # note I've disabled this until I can get the username parsing right & avoid a "double message"
    # I need to get the current user

    replies = app.client.conversations_replies(channel=channel, ts=thread_ts)
    history = ""

    for msg in replies["messages"]:
        print(f"{msg=}")
        history = history + f"<@{msg['user']}> " + msg["text"] + "\n"

    history = history + f"<@{user}> " + message # we expect a new line at the end
    print(f"{history=}")

    response = generate(history)
    say(text=response, thread_ts=thread_ts)

    if "GPT-3" in message:
        say(text="Did someone say GPT-3? That's me! Nice to meet you", thread_ts=thread_ts)


def main():
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    fire.Fire(main)

