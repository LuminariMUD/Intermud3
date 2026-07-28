#!/usr/bin/env python3

import re
import select
import socket
import sys
import time

from dotenv import dotenv_values


IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240


class MudSession:
    def __init__(self, label, host, account, password):
        self.label = label
        self.host = host
        self.account = account
        self.password = password
        self.sock = socket.create_connection((host, 4100), timeout=8)
        self.sock.setblocking(False)
        self.output = ""
        self.cursor = 0

    def _clean(self, text):
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = "".join(char for char in text if char in "\r\n\t" or ord(char) >= 32)
        return text.replace(self.password, "[REDACTED]").replace(
            self.account, "[GM_ACCOUNT]"
        )

    def pump(self, seconds=0.25):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [self.sock], [], [], min(0.1, max(0, deadline - time.monotonic()))
            )
            if not readable:
                continue
            data = self.sock.recv(65536)
            if not data:
                break

            plain = bytearray()
            index = 0
            while index < len(data):
                if data[index] == IAC and index + 1 < len(data):
                    command = data[index + 1]
                    if command in (WILL, WONT, DO, DONT) and index + 2 < len(data):
                        response = DONT if command in (WILL, WONT) else WONT
                        self.sock.send(bytes((IAC, response, data[index + 2])))
                        index += 3
                        continue
                    if command == SB:
                        end = data.find(bytes((IAC, SE)), index + 2)
                        index = end + 2 if end >= 0 else len(data)
                        continue
                    index += 2
                    continue
                if data[index]:
                    plain.append(data[index])
                index += 1

            self.output += plain.decode("utf-8", "replace")

        return self._clean(self.output)

    def wait_for(self, needle, timeout=10, after=0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if needle.casefold() in self.pump(0.2)[after:].casefold():
                return
        transcript = self._clean(self.output)[after:][-1200:]
        raise RuntimeError(
            f"{self.label}: timed out waiting for {needle!r}; "
            f"recent output follows:\n{transcript}"
        )

    def send_line(self, line):
        self.sock.sendall(line.encode("utf-8") + b"\r\n")

    @staticmethod
    def _has_game_prompt(text):
        return re.search(r"\b\d+/\d+H\s+\d+/\d+V\b", text) is not None

    def login(self):
        self.wait_for("account name", 12)
        checkpoint = len(self._clean(self.output))
        self.send_line(self.account)
        self.wait_for("password", 6, checkpoint)
        checkpoint = len(self._clean(self.output))
        self.send_line(self.password)
        self.wait_for("Your choice", 8, checkpoint)
        checkpoint = len(self._clean(self.output))
        self.send_line("1")

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            transcript = self.pump(0.2)[checkpoint:]
            lowered = transcript.casefold()
            if self._has_game_prompt(transcript):
                break
            if "make your choice" in lowered:
                checkpoint = len(self._clean(self.output))
                self.send_line("1")
                continue
            if "press return" in lowered or "press enter to continue" in lowered:
                checkpoint = len(self._clean(self.output))
                self.send_line("")
                continue
        else:
            transcript = self._clean(self.output)[checkpoint:][-1200:]
            raise RuntimeError(
                f"{self.label}: timed out waiting for the in-game prompt; "
                f"recent output follows:\n{transcript}"
            )

        self.cursor = len(self._clean(self.output))

    def delta(self):
        cleaned = self._clean(self.output)
        delta = cleaned[self.cursor :]
        self.cursor = len(cleaned)
        return delta

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def pump_all(sessions, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for session in sessions.values():
            session.pump(0.05)


def show_deltas(sessions):
    for label, session in sessions.items():
        delta = session.delta().strip()
        if delta:
            print(f"--- {label} ---", flush=True)
            print(delta, flush=True)


def main():
    config = dotenv_values("/home/aiwithapex/projects/Intermud3/.env")
    account = config.get("GAME_MASTER_ACCOUNT")
    password = config.get("GAME_MASTER_ACCOUNT_PASSWORD")
    if not account or not password:
        raise SystemExit("Game Master credentials are not configured")

    sessions = {
        "local": MudSession("local", "127.0.0.1", account, password),
        "prod": MudSession("prod", "74.208.126.44", account, password),
    }
    try:
        for session in sessions.values():
            session.login()
        print("READY local prod", flush=True)

        for raw_line in sys.stdin:
            line = raw_line.rstrip("\n")
            if line == "quit":
                break
            if line.startswith("pump\t"):
                pump_all(sessions, float(line.split("\t", 1)[1]))
                show_deltas(sessions)
                print("DONE", flush=True)
                continue

            fields = line.split("\t", 2)
            if len(fields) < 2 or fields[0] not in sessions:
                print("ERROR expected: <local|prod>\\t<command>\\t[wait]", flush=True)
                continue
            label, command = fields[:2]
            wait = float(fields[2]) if len(fields) == 3 else 1.0
            sessions[label].send_line(command)
            pump_all(sessions, wait)
            print(f"COMMAND {label}: {command}", flush=True)
            show_deltas(sessions)
            print("DONE", flush=True)
    finally:
        for session in sessions.values():
            try:
                session.send_line("quit")
                session.pump(0.5)
            except OSError:
                pass
            session.close()


if __name__ == "__main__":
    main()
