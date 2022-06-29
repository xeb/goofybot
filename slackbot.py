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

    response = openai.Completion.create(
        engine=config["engine"],
        prompt=prompt,
        temperature=config["temperature"],
        max_tokens=config["max_tokens"]
    )

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
    
    app.client.reactions_add(channel=channel, timestamp=thread_ts, name="thumbsup")
    print(f"Generating {prompt=}")
    response = generate(prompt)
    say(response, thread_ts=thread_ts)


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

    print("{user=}\n{message=}\n{channel=}\n{thread_ts=}")
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

