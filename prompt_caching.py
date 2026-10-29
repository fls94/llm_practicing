"""Prove that OpenAI prompt caching works.

How OpenAI prompt caching works (automatic, no opt-in needed):
  * Only prompts of >= 1024 tokens are eligible.
  * The cache key is the exact PREFIX of the prompt. A hit covers the longest
    previously-seen prefix, in steps of 128 tokens (1024, 1152, 1280, ...).
  * Cached input tokens are billed at a discount (50-90% depending on model);
    everything after the cached prefix is billed at the full input price.
  * The API reports the hit in usage.prompt_tokens_details.cached_tokens.

The experiment:
  1. COLD  - a ~3k-token static prefix (system prompt) + question A. Nothing cached yet.
  2. WARM  - the SAME prefix + a different question B. The prefix is now cached.
  3. BROKEN - change ONE character at the very start of the prefix + question B.
              The prefix no longer matches, so the cache misses again.

Setup: put a .env file next to this script containing
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4.1-mini        # optional
Run:  python learning/prompt_caching.py
"""

import os
import sys
import time
import uuid
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# USD per 1M tokens: (input, cached input, output).
# Check https://openai.com/api/pricing - prices change over time.
PRICES = {
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4.1-nano": (0.10, 0.025, 0.40),
    "gpt-4o": (2.50, 1.25, 10.00),
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "gpt-5": (1.25, 0.125, 10.00),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5-nano": (0.05, 0.005, 0.40),
}

# Chat Completions wraps each message in a few special tokens
# (<|im_start|>system<|im_sep|> ...). Used only to place the cache boundary
# inside our own text for display, so it is an approximation.
FRAMING_TOKENS = 3

COLORS = ["Red", "Blue", "Green", "Black", "Orange", "Grey", "Yellow", "Purple"]
ITEMS = ["tent", "backpack", "sleeping bag", "headlamp", "stove", "trekking pole",
         "rain jacket", "water filter", "camp chair", "cooler"]


def build_static_prefix(run_id: str) -> str:
    """A long, deterministic system prompt: the part we want cached.

    run_id goes FIRST so every run of this script starts with a cold cache
    (OpenAI keeps cached prefixes for minutes, sometimes up to an hour).
    """
    lines = [
        f"Run id: {run_id}",
        "You are the support assistant for Acme Outdoor Gear.",
        "Answer in ONE short sentence, using only the catalog below.",
        "",
        "CATALOG:",
    ]
    for i in range(1, 141):
        lines.append(
            f"SKU-{i:04d} | {COLORS[i % len(COLORS)]} {ITEMS[i % len(ITEMS)]} "
            f"| price ${(i * 37) % 400 + 20}.99 | weight {(i * 53) % 2000 + 150} g "
            f"| warranty {i % 5 + 1} years | stock {(i * 29) % 90}"
        )
    return "\n".join(lines)


def ask(client: OpenAI, system: str, question: str, cache_key: str):
    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},  # static prefix -> cacheable
            {"role": "user", "content": question},  # dynamic suffix -> never cached
        ],
        max_completion_tokens=60,
        # Routing hint: requests sharing a key land on the same cache machine.
        prompt_cache_key=cache_key,
    )
    return resp, time.perf_counter() - start


def usage_numbers(resp):
    u = resp.usage
    details = u.prompt_tokens_details
    cached = (details.cached_tokens or 0) if details else 0
    return u.prompt_tokens, cached, u.completion_tokens


def cost_usd(prompt: int, cached: int, output: int, use_cache: bool = True) -> float:
    p_in, p_cached, p_out = PRICES.get(MODEL, PRICES["gpt-4.1-mini"])
    if not use_cache:
        cached = 0
    return ((prompt - cached) * p_in + cached * p_cached + output * p_out) / 1_000_000


def show_call(label: str, resp, seconds: float, system: str, question: str, enc):
    prompt, cached, output = usage_numbers(resp)
    full = prompt - cached
    print(f"\n=== {label} ===")
    print(f"answer        : {resp.choices[0].message.content!r}")
    print(f"latency       : {seconds:.2f}s")
    print(f"prompt tokens : {prompt:>6}")
    print(f"  cached      : {cached:>6}   <- billed at the discounted cached price")
    print(f"  full price  : {full:>6}   <- billed at the normal input price")
    print(f"output tokens : {output:>6}")
    print(f"cost          : ${cost_usd(prompt, cached, output):.6f}"
          f"   (without cache it would be ${cost_usd(prompt, cached, output, False):.6f})")

    # Draw which part of the prompt was served from cache.
    width = 60
    filled = round(width * cached / prompt) if prompt else 0
    print(f"prompt map    : [{'#' * filled}{'.' * (width - filled)}]  # = cached, . = full price")

    sys_tokens = enc.encode(system)
    q_tokens = enc.encode(question)
    print(f"layout (local tiktoken count): system prompt ~{len(sys_tokens)} tok"
          f" + user question ~{len(q_tokens)} tok")
    if cached == 0:
        print("cache boundary: none - the whole prompt was processed and billed at full price")
        return
    cut = cached - FRAMING_TOKENS  # position of the boundary inside the system text
    if 0 < cut <= len(sys_tokens):
        before = enc.decode(sys_tokens[max(0, cut - 12):cut])
        after = enc.decode(sys_tokens[cut:cut + 12])
        print("cache boundary (approx.) inside the system prompt:")
        print(f"   cached ...{before!r}")
        print(f"   NOT cached {after!r}... + the rest of the system prompt + the user question")
    else:
        print("cache boundary: covers the whole system prompt; only the question tail is full price")


def main():
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit(f"OPENAI_API_KEY missing - create {Path(__file__).parent / '.env'} with OPENAI_API_KEY=sk-...")
    if MODEL not in PRICES:
        print(f"note: no price entry for {MODEL!r}, using gpt-4.1-mini prices for the $ figures")

    client = OpenAI()
    try:
        enc = tiktoken.encoding_for_model(MODEL)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")

    run_id = uuid.uuid4().hex
    cache_key = f"caching-demo-{run_id}"
    prefix = build_static_prefix(run_id)
    q_a = "How much does SKU-0042 cost?"
    q_b = "What is the warranty on SKU-0107?"
    print(f"model: {MODEL}   static prefix: ~{len(enc.encode(prefix))} tokens (needs >= 1024)")

    # 1. Cold: first time this prefix is ever seen -> cache write, full price.
    resp1, t1 = ask(client, prefix, q_a, cache_key)
    show_call("CALL 1  cold: new prefix + question A", resp1, t1, prefix, q_a, enc)

    # 2. Warm: identical prefix, different question. The cache write from call 1
    #    can take a moment to become visible, so retry a few times on a miss.
    for attempt in range(1, 5):
        resp2, t2 = ask(client, prefix, q_b, cache_key)
        if usage_numbers(resp2)[1] > 0:
            break
        print(f"\n(call 2 attempt {attempt}: cache not warm yet, retrying in 2s)")
        time.sleep(2)
    show_call("CALL 2  warm: SAME prefix + question B", resp2, t2, prefix, q_b, enc)

    # 3. Broken: change one character at the START of the prefix. Same length,
    #    same question as call 2, but the prefix no longer matches -> miss.
    broken = "X" + prefix[1:]
    resp3, t3 = ask(client, broken, q_b, cache_key)
    show_call("CALL 3  first char of prefix changed + question B", resp3, t3, broken, q_b, enc)

    print("\n=== SUMMARY ===")
    print(f"{'call':<34}{'prompt':>8}{'cached':>8}{'full':>8}{'cost $':>12}")
    rows = [("1 cold (new prefix)", resp1), ("2 warm (same prefix)", resp2),
            ("3 prefix changed by 1 char", resp3)]
    for name, resp in rows:
        p, c, o = usage_numbers(resp)
        print(f"{name:<34}{p:>8}{c:>8}{p - c:>8}{cost_usd(p, c, o):>12.6f}")

    c1 = cost_usd(*usage_numbers(resp1))
    c2 = cost_usd(*usage_numbers(resp2))
    if usage_numbers(resp2)[1] > 0:
        print(f"\nCall 2 cost {c2 / c1:.0%} of call 1 -> prompt caching saved {1 - c2 / c1:.0%}.")
        print("Call 3 shows the cache is keyed on the exact prefix: one changed character "
              "at the front invalidates everything after it.")
    else:
        print("\nCall 2 never hit the cache (rare: request routed to another machine). Run again.")


if __name__ == "__main__":
    main()
