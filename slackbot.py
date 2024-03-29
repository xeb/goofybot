#!/usr/bin/env python

import os
import re
import fire
import toml
import openai
from termcolor import colored
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
OPENAI_API_TOKEN = os.environ["OPENAI_APP_TOKEN"]

openai.api_key = OPENAI_API_TOKEN
app = App(token=SLACK_BOT_TOKEN)

def generate(prompt, chat_history):
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

    #print(colored(f"Using {prompt=} {chat_history=}", "cyan"))
    #response = openai.Completion.create(
    #    engine=engine,
    #    prompt=prompt,
    #    temperature=temperature,
    #    max_tokens=config["max_tokens"]
    #)

    system_msg = {"role":"system", "content":"You are Goofybot, a virtual assistant meant to entertain a group of immature 40 somethings with jokes and sarcasm. But you still need to tell the truth and be very helpful"}

    messages = chat_history
    messages.insert(0, system_msg)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = messages,
    )

    print(colored(f"Received {len(response.choices)=}", "cyan"))
    print(colored(f"Received {response.choices[0]=}", "cyan"))
    if engine != "gpt-3.5-turbo":
        txt = response.choices[0].text
    else:
        txt = response.choices[0]['message']['content']

    return txt

@app.event("app_mention")
def mention_handler_app_mention(body, say, logger):
    event = body["event"]
    thread_ts = event.get("thread_ts", None) or event["ts"]
    channel = event.get("channel", None) or event["channel"]
    print(colored(f"--------- starting new thread -----\n{thread_ts=}", "green"))
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

    chat_history = []
    chat_history.append({"role":"user", "content": f"<@{event['user']}> " + prompt + "\n" })
    app.client.reactions_add(channel=channel, timestamp=thread_ts, name="heavy_check_mark")
    print(colored(f"Generating {prompt=}", "green"))
    try:
        response = generate(prompt, chat_history)
        say(response, thread_ts=thread_ts)
    except Exception as e:
        say(f"Uhoh. Error {e=}", thread_ts=thread_ts)
        print(colored(f"Error {e=}", "red"))

    print(colored(f"--------- ending new thread -----", "green"))

@app.event("message")
def mention_handler_message(body, say):
    print(colored(f"--------- starting message within a thread -----", "yellow"))
    event = body["event"]
    thread_ts = event.get("thread_ts", None) or event["ts"]
    messag_ts = event.get("ts", None)
    if "text" not in event:
        return

    channel = event.get("channel", None) or event["channel"]
    message = event["text"].strip()
    user = event.get("user", None)

    #print(f"{dir(app.client)=}")
    #current_user = app.client.users_info()
    #current_user = app.client.users_identity()
    current_user = ""

    if "U03MM3WLXHT" in user: #TODO get app.client.users_identity() to work dynamically, stupid OAuth
        print(colored(f"The message was from Goofybot, stopping", "yellow"))
        return

    if "U03SEPH39_" in user:
        print(colored(f"The message was from Goofyboy I think {user=}, stopping", "yellow"))
        return

    print(colored(f"{user=}\n{channel=}\n{thread_ts=}\n{current_user=}", "yellow"))
    #return # note I've disabled this until I can get the username parsing right & avoid a "double message"
    # I need to get the current user

    replies = app.client.conversations_replies(channel=channel, ts=thread_ts)

    chat_history = []
    history = ""

    for msg in replies["messages"]:
        history = history + f"<@{msg['user']}> " + msg["text"] + "\n"
        chat_history.append({"role":"user", "content": f"<@{msg['user']}> " + msg["text"] + "\n" })

    history = history + f"<@{user}> " + message # we expect a new line at the end
    chat_history.append({"role":"user", "content": f"<@{msg['user']}> " + msg["text"] + "\n" })

    # HACK: prevent responding to yourself
    history_parts = history.split("\n")
    if len(history_parts) == 2 and history_parts[0] == history_parts[1]:
        print(colored("Duplicate! exiting", "yellow"))
        return

    if "U03MM3WLXHT" not in history:
        print(colored(f"NOT RESPONDING!!! to {history=}, none of my business", "yellow"))
        return

    if history.count("U03MM3WLXHT") >= 300:
        print(colored(f"NOT RESPONDING!!! I've been too chatty", "yellow"))
        return

    print(colored(f"{history=}", "yellow"))

    response = generate(history, chat_history)

    if len(response) == 0 or response.strip() == "":
        app.client.reactions_add(channel=channel, timestamp=messag_ts, name="shrug")
    else:
        say(text=response, thread_ts=thread_ts)

    if "GPT-3" in message:
        say(text="Did someone say GPT-3? That's me! Nice to meet you", thread_ts=thread_ts)

    print(colored(f"--------- ending message within a thread -----", "yellow"))

def main():
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    fire.Fire(main)

